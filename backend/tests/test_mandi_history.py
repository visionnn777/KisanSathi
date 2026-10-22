"""Historical price adapter tests: normalize aggregates without confusing them with quotes."""
from datetime import date
import pytest
from app.models import MandiPriceHistory
from app.services import community_mandi_api
from app.services.price_store import normalize_history_record, save_history_rows

class FakeResponse:
    status_code = 200
    def __init__(self, body): self.body = body
    def json(self): return self.body
    def raise_for_status(self): pass

class FakeSession:
    def __init__(self, body): self.body, self.calls = body, []
    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append((url, params))
        return FakeResponse(self.body)


def test_history_fetch_uses_expected_route_and_date_parameters():
    body = {"success": True, "data": [{"date": "2026-10-10", "avg_modal_price": 2400}]}
    session = FakeSession(body)
    result = community_mandi_api.fetch_price_history(
        state="Punjab", commodity="Wheat", from_date="2026-01-01", to_date="2026-10-18", session=session
    )
    assert result == body["data"]
    url, params = session.calls[0]
    assert url.endswith("/prices/history")
    assert params == {"state": "Punjab", "commodity": "Wheat", "from": "2026-01-01", "to": "2026-10-18"}


def test_history_fetch_rejects_bad_dates_and_unsupported_state():
    with pytest.raises(community_mandi_api.CommunityMandiAPIError, match="ISO dates"):
        community_mandi_api.fetch_price_history(state="Punjab", commodity="Wheat", from_date="bad", to_date="2026-10-18")
    with pytest.raises(community_mandi_api.CommunityMandiAPIError, match="Unsupported state"):
        community_mandi_api.fetch_price_history(state="Rajasthan", commodity="Wheat", from_date="2026-01-01", to_date="2026-10-18")


def test_history_normalizer_handles_snake_and_camel_case():
    row = normalize_history_record({"observationDate": "2026-10-10", "averageModalPrice": "2,450",
                                    "minModalPrice": 2300, "maxModalPrice": 2600, "marketsCount": 5},
                                   state="Punjab", commodity="Wheat")
    assert row is not None
    assert row["observation_date"] == date(2026, 10, 10)
    assert row["average_modal_price"] == 2450
    assert row["markets_count"] == 5


def test_history_normalizer_handles_iso_timestamp_date():
    row = normalize_history_record({"timestamp": "2026-10-10T15:30:00Z", "averageModalPrice": 2450},
                                   state="Punjab", commodity="Wheat")
    assert row is not None
    assert row["observation_date"] == date(2026, 10, 10)


def test_history_normalizer_rejects_invalid_or_inconsistent_data():
    assert normalize_history_record({"date": "not-a-date", "price": 2300}, state="Punjab", commodity="Wheat") is None
    assert normalize_history_record({"date": "2026-10-10", "price": 0}, state="Punjab", commodity="Wheat") is None
    assert normalize_history_record({"date": "2026-10-10", "price": 2400, "min_price": 2600, "max_price": 2300}, state="Punjab", commodity="Wheat") is None


def test_history_rows_upsert_without_duplicates(db):
    row = {"state": "Punjab", "commodity": "Wheat", "observation_date": date(2026, 10, 10),
           "average_modal_price": 2400, "min_modal_price": 2200, "max_modal_price": 2550,
           "markets_count": 3, "source": "mandi-api-history"}
    assert save_history_rows(db, [row]) == 1
    updated = dict(row, average_modal_price=2475, markets_count=4)
    assert save_history_rows(db, [updated]) == 1
    rows = db.query(MandiPriceHistory).all()
    assert len(rows) == 1
    assert float(rows[0].average_modal_price) == 2475
    assert rows[0].markets_count == 4
