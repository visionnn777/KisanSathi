from datetime import date

from app import config
from app.services import mandi_sync
from app.services.community_mandi_api import CommunityMandiAPIError, SUPPORTED_STATES
from app.services.price_store import read_csv, save_rows


def _record(state):
    return {
        "state": state, "district": "Demo district", "market": "Demo mandi",
        "commodity": "Wheat", "variety": "Demo", "grade": "FAQ",
        "arrival_date": date.today().isoformat(), "min_price": 2000,
        "max_price": 2400, "modal_price": 2200,
    }


def test_sync_mandi_prices_all_states_upserts_and_records_status(monkeypatch, db, client, tmp_path):
    monkeypatch.setattr(mandi_sync, "fetch_community_prices",
                        lambda *, state, commodity=None: [_record(state)])
    monkeypatch.setattr(config, "SNAPSHOT_CSV", tmp_path / "mandi_snapshot.csv")
    result = mandi_sync.sync_mandi_prices()
    assert result["ok"] is True
    assert result["status"] == "success"
    assert len(result["states_succeeded"]) == 5
    assert result["rows_saved"] == 5

    # Same five observations on the next run update existing rows instead of duplicating them.
    result2 = mandi_sync.sync_mandi_prices()
    assert result2["rows_saved"] == 5
    from app.models import MandiPrice, MandiSyncStatus
    check = db.query(MandiPrice).filter_by(source="mandi-api").count()
    sync = db.query(MandiSyncStatus).filter_by(provider="mandi-api").one()
    assert check == 5
    assert sync.status == "success"
    assert sync.last_success_at is not None
    api_status = client.get("/api/prices/status").json()
    assert api_status["last_sync"]["status"] == "success"
    assert api_status["auto_refresh"]["enabled"] is False  # disabled for isolated tests


def test_sync_failure_preserves_existing_records_and_reports_error(monkeypatch, db):
    sample_rows = read_csv(config.SAMPLE_CSV)[:2]
    save_rows(db, sample_rows, source="sample")
    initial = db.query(__import__("app.models", fromlist=["MandiPrice"]).MandiPrice).count()

    def fail(*, state, commodity=None):
        raise CommunityMandiAPIError("provider unavailable")

    monkeypatch.setattr(mandi_sync, "fetch_community_prices", fail)
    result = mandi_sync.sync_mandi_prices()
    assert result["ok"] is False
    assert result["status"] == "error"
    assert result["rows_saved"] == 0
    from app.models import MandiPrice, MandiSyncStatus
    assert db.query(MandiPrice).count() == initial
    status = db.query(MandiSyncStatus).filter_by(provider="mandi-api").one()
    assert status.status == "error"
    assert "preserved" in status.message


def test_empty_provider_response_does_not_count_as_a_success(monkeypatch):
    monkeypatch.setattr(mandi_sync, "fetch_community_prices", lambda *, state, commodity=None: [])
    result = mandi_sync.sync_mandi_prices(state=SUPPORTED_STATES[0])
    assert result["ok"] is False
    assert result["status"] == "no_data"
    assert result["states_empty"] == [SUPPORTED_STATES[0]]


def test_scheduler_runs_a_refresh_in_background_then_stops(monkeypatch):
    import asyncio
    from app.services import mandi_scheduler

    async def scenario():
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        calls = []

        def fake_sync():
            calls.append(True)
            loop.call_soon_threadsafe(stop_event.set)
            return {"ok": True, "status": "success", "rows_saved": 1,
                    "newest_arrival_date": date.today().isoformat()}

        monkeypatch.setattr(mandi_scheduler, "sync_mandi_prices", fake_sync)
        monkeypatch.setattr(config, "MANDI_REFRESH_ON_STARTUP", True)
        await asyncio.wait_for(mandi_scheduler.daily_mandi_refresh_loop(stop_event), timeout=2)
        assert calls == [True]

    asyncio.run(scenario())
