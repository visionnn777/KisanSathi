"""Health check, scheduler lease, price retention, farm record keys and model evaluation."""
from datetime import timedelta
from pathlib import Path

from PIL import Image

from app.models import FarmSeasonRecord, MandiPrice
from app.timeutil import today_ist


def test_health_reports_real_database_state(client, monkeypatch):
    ok = client.get("/health")
    assert ok.status_code == 200 and ok.json()["database"] == "connected"
    from app import main

    class Broken:
        def connect(self):
            raise RuntimeError("database down")
        dialect = main.engine.dialect
    monkeypatch.setattr(main, "engine", Broken())
    down = client.get("/health")
    assert down.status_code == 503 and down.json()["database"] == "unavailable"


def test_only_one_worker_holds_the_refresh_lease():
    from app.services.mandi_scheduler import acquire_lease
    assert acquire_lease("worker-a") is True
    assert acquire_lease("worker-b") is False
    assert acquire_lease("worker-a") is True      # the holder can renew


def test_old_prices_are_removed_by_retention(db):
    from app.services.price_store import delete_older_than
    today = today_ist()
    for days in (10, 800):
        db.add(MandiPrice(state="Punjab", district="Ludhiana", market=f"M{days}", commodity="Wheat", variety="", grade="",
                          arrival_date=today - timedelta(days=days), min_price=2300, max_price=2500, modal_price=2400, source="mandi-api"))
    db.commit()
    assert delete_older_than(db, 730) == 1
    assert db.query(MandiPrice).count() == 1


def test_farm_record_key_is_hashed_and_never_in_a_url(client, db):
    key = client.post("/api/planning/farm-ref").json()["farm_ref"]
    assert len(key) >= 22
    record = {"farm_ref": key, "state": "Punjab", "district": "Ludhiana", "crop": "Wheat", "season": "Rabi",
              "year_start": 2025, "area_ha": 2.0, "harvested_tonnes": 8.0}
    assert client.post("/api/planning/records", json=record).status_code == 200
    stored = db.query(FarmSeasonRecord).one()
    assert stored.farm_ref != key and len(stored.farm_ref) == 64
    found = client.post("/api/planning/records/latest", json={"farm_ref": key, "state": "punjab", "district": "LUDHIANA", "crop": "wheat"}).json()
    assert found["available"] is True and found["record"]["yield_t_per_ha"] == 4.0
    other = client.post("/api/planning/records/latest", json={"farm_ref": "someone-elses-key-0000000", "state": "Punjab", "district": "Ludhiana", "crop": "Wheat"}).json()
    assert other["available"] is False
    # The old GET form (key in the URL) no longer exists.
    assert client.get("/api/planning/records/latest", params={"farm_ref": key}).status_code in (404, 405)


def test_record_rejects_conflicting_harvest_and_future_year(client):
    base = {"farm_ref": "test-farm-reference-1234567", "state": "Punjab", "district": "Ludhiana", "crop": "Wheat",
            "season": "Rabi", "year_start": 2025, "area_ha": 2.0}
    assert client.post("/api/planning/records", json={**base, "yield_t_per_ha": 4.0, "harvested_tonnes": 12.0}).status_code == 422
    assert client.post("/api/planning/records", json={**base, "year_start": today_ist().year + 3, "yield_t_per_ha": 4.0}).status_code == 422


def test_evaluate_model_reports_accuracy_from_folders(tmp_path: Path):
    from scripts.evaluate_model import evaluate, report_markdown
    for folder, colour in (("wheat_yellow_rust", (190, 170, 40)), ("wheat_healthy", (40, 140, 40))):
        (tmp_path / folder).mkdir()
        for i in range(2):
            Image.new("RGB", (40, 40), colour).save(tmp_path / folder / f"{i}.jpg")

    def fake(data):  # always answers yellow rust
        return [{"label": "Wheat___Yellow_Rust", "score": 0.9}, {"label": "Wheat___Healthy", "score": 0.1}], 1.0
    result = evaluate(tmp_path, classify=fake)
    assert result["photos"] == 4 and result["accuracy"] == 0.5
    assert result["per_class"]["wheat_yellow_rust"]["recall"] == 1.0
    assert result["per_class"]["wheat_healthy"]["recall"] == 0.0
    assert "Photos tested: **4**" in report_markdown(result)
