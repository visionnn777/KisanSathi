"""Owner: Member C"""
from datetime import date

from app import config
from app.services import mandi_api
from app.services.price_store import normalize_record, read_csv, save_rows


def test_normalize_handles_both_key_styles():
    new_style = {"state": "Punjab", "district": "Ludhiana", "market": "Khanna", "commodity": "Wheat",
                 "variety": "Dara", "grade": "FAQ", "arrival_date": "16/10/2026",
                 "min_price": "2400", "max_price": "2,550", "modal_price": "2480"}
    old_style = {"State": "Punjab", "District": "Ludhiana", "Market": "Khanna", "Commodity": "Wheat",
                 "Variety": "Dara", "Grade": "FAQ", "Arrival_Date": "16/10/2026",
                 "Min_x0020_Price": "2400", "Max_x0020_Price": "2550", "Modal_x0020_Price": "2480"}
    a, b = normalize_record(new_style), normalize_record(old_style)
    assert a == b
    assert a["arrival_date"] == date(2026, 10, 16)
    assert a["max_price"] == 2550.0


def test_normalize_skips_bad_rows():
    assert normalize_record({"state": "Punjab", "market": "Khanna", "commodity": "Wheat",
                             "arrival_date": "16/10/2026", "modal_price": "NR"}) is None
    assert normalize_record({"state": "Punjab", "market": "Khanna", "commodity": "Wheat",
                             "arrival_date": "not a date", "modal_price": "2000"}) is None


def test_sample_csv_loads_and_best_market_is_highest(client, db):
    rows = read_csv(config.SAMPLE_CSV)
    assert len(rows) > 100
    save_rows(db, rows, source="sample")
    save_rows(db, rows, source="sample")  # running twice must not duplicate

    status = client.get("/api/prices/status").json()
    assert status["rows"] == len(rows) and status["sources"] == ["sample"]

    states = client.get("/api/prices/states").json()
    assert "Punjab" in states
    crops = client.get("/api/prices/commodities", params={"state": "Punjab"}).json()
    assert "Wheat" in crops

    best = client.get("/api/prices/best", params={"state": "Punjab", "commodity": "Wheat"}).json()
    prices = [m["modal_price"] for m in best["markets"]]
    assert prices == sorted(prices, reverse=True) and len(prices) == 5
    assert best["date"] == "2026-10-16" and best["source"] == "sample"
    assert best["markets"][0]["modal_per_kg"] == round(prices[0] / 100, 2)

    history = client.get("/api/prices/history", params={"state": "Punjab", "commodity": "Wheat"}).json()
    assert [h["date"] for h in history] == ["2026-10-14", "2026-10-15", "2026-10-16"]


def test_best_with_no_data(client):
    r = client.get("/api/prices/best", params={"state": "Nowhere", "commodity": "Wheat"})
    assert r.json() == {"date": None, "source": None, "markets": []}


class FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


class FakeSession:
    """Pretends to be data.gov.in: 2500 records, at most 1000 per page."""
    def __init__(self, total=2500):
        self.total, self.calls = total, []

    def get(self, url, params, timeout):
        self.calls.append(dict(params))
        offset, limit = int(params["offset"]), int(params["limit"])
        n = max(0, min(limit, self.total - offset))
        records = [{"state": "Punjab", "market": f"M{offset + i}", "commodity": "Wheat",
                    "arrival_date": "16/10/2026", "modal_price": "2400"} for i in range(n)]
        return FakeResponse({"total": self.total, "count": n, "records": records})


def test_fetch_all_pages_through_everything():
    session = FakeSession(total=2500)
    records = mandi_api.fetch_all(session=session)
    assert len(records) == 2500
    assert [c["offset"] for c in session.calls] == [0, 1000, 2000]


def test_fetch_all_with_state_filter():
    session = FakeSession(total=10)
    records = mandi_api.fetch_all(state="Punjab", session=session)
    assert len(records) == 10
    assert session.calls[0]["filters[state.keyword]"] == "Punjab"
    assert len(session.calls) == 1  # the first page is reused, not downloaded twice


def test_missing_key_gives_clear_error(monkeypatch):
    monkeypatch.setattr(config, "DATA_GOV_API_KEY", config.PLACEHOLDER_API_KEY)
    try:
        mandi_api.api_key()
        assert False, "should have raised"
    except mandi_api.MandiAPIError as exc:
        assert "DATA_GOV_API_KEY" in str(exc)
