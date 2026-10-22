"""Irrigation math and API are tested without relying on live weather APIs."""
from app.services import irrigation


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_irrigation_calculation(monkeypatch):
    replies = [
        {"results": [{"name": "Ludhiana", "admin1": "Punjab", "country_code": "IN",
                      "latitude": 30.9, "longitude": 75.85}]},
        {"daily": {
            "time": ["2026-10-18", "2026-10-19", "2026-10-20"],
            "et0_fao_evapotranspiration": [4.0, 5.0, 6.0],
            "precipitation_sum": [1.0, 0.0, 8.0],
            "precipitation_probability_max": [10, 5, 70],
        }},
    ]
    calls = []

    def fake_get(url, params, timeout, headers):
        calls.append((url, params))
        return FakeResponse(replies.pop(0))

    monkeypatch.setattr(irrigation.requests, "get", fake_get)
    result = irrigation.calculate_irrigation("Ludhiana", "Punjab", "maize", "mid_season", 1.0, 0.75)
    assert result["location"]["name"] == "Ludhiana"
    assert result["kc"] == 1.15
    totals = result["totals"]
    assert totals["estimated_crop_water_use_mm"] == 17.25          # (4+5+6) x 1.15
    assert totals["forecast_rain_mm"] == 9.0
    assert totals["expected_rain_mm"] == 5.7                       # 1x10% + 0x5% + 8x70%
    assert totals["estimated_effective_rain_mm"] == 4.56           # 80% soaks in (unknown soil)
    assert totals["simple_deficit_mm"] == 12.69
    # Root zone: TAW 140 mm (unknown soil, 1 m roots); p = 0.55 + 0.04 x (5 - 5.75) = 0.52 -> RAW 72.8 mm.
    # Start half of RAW used (36.4 mm, stated assumption); after 3 days 49.1 mm < RAW: no watering yet.
    zone = result["root_zone"]
    assert zone["total_available_water_mm"] == 140.0 and zone["readily_available_water_mm"] == 72.8
    assert totals["estimated_net_deficit_mm"] == 0
    assert totals["estimated_gross_water_litres"] == 0
    assert "moisture_assumed" in result["advice_codes"] and "no_irrigation_needed" in result["advice_codes"]
    assert len(calls) == 2


def test_dry_soil_plans_watering_today_and_wet_soil_needs_none(monkeypatch):
    def replies():
        return [
            {"results": [{"name": "Ludhiana", "admin1": "Punjab", "country_code": "IN", "latitude": 30.9, "longitude": 75.85}]},
            {"daily": {"time": ["2026-10-18", "2026-10-19", "2026-10-20"],
                       "et0_fao_evapotranspiration": [4.0, 5.0, 6.0], "precipitation_sum": [1.0, 0.0, 8.0],
                       "precipitation_probability_max": [10, 5, 70]}},
        ]
    queue = replies()
    monkeypatch.setattr(irrigation.requests, "get", lambda url, params, timeout, headers: FakeResponse(queue.pop(0)))
    dry = irrigation.calculate_irrigation("Ludhiana", "Punjab", "maize", "mid_season", 1.0, 0.75, field_moisture="dry")
    # Starts at RAW (72.8 mm used); day 1: 72.8 - 0.08 + 4.6 = 77.3 mm -> refill on day 1.
    assert dry["irrigation_events"][0]["date"] == "2026-10-18"
    assert dry["irrigation_events"][0]["net_mm"] == 77.3
    assert dry["totals"]["estimated_net_deficit_mm"] == 77.3
    assert dry["totals"]["estimated_gross_irrigation_mm"] == 103.1   # 77.3 / 0.75
    assert dry["totals"]["estimated_gross_water_litres"] == 1031000
    queue[:] = replies()
    wet = irrigation.calculate_irrigation("Ludhiana", "Punjab", "maize", "mid_season", 1.0, 0.75, field_moisture="wet")
    assert wet["irrigation_events"] == [] and wet["totals"]["estimated_gross_water_litres"] == 0
    assert "moisture_wet" in wet["advice_codes"]


def test_showers_count_as_rain(monkeypatch):
    queue = [
        {"results": [{"name": "Nagpur", "admin1": "Maharashtra", "country_code": "IN", "latitude": 21.1, "longitude": 79.1}]},
        {"daily": {"time": ["2026-07-01"], "et0_fao_evapotranspiration": [4.0],
                   "rain_sum": [0.0], "precipitation_sum": [36.0], "precipitation_probability_max": [100]}},
    ]
    monkeypatch.setattr(irrigation.requests, "get", lambda url, params, timeout, headers: FakeResponse(queue.pop(0)))
    result = irrigation.calculate_irrigation("Nagpur", "Maharashtra", "cotton", "mid_season", 1.0, 0.7)
    assert result["totals"]["forecast_rain_mm"] == 36.0


def test_irrigation_endpoint_validation(client, monkeypatch):
    from app.routers import irrigation as irrigation_router

    monkeypatch.setattr(irrigation_router, "calculate_irrigation", lambda *args: {"totals": {"estimated_gross_water_litres": 1000}})
    response = client.post("/api/irrigation/estimate", json={
        "location": "Ludhiana", "state": "Punjab", "crop": "maize", "stage": "mid_season",
        "area_ha": 1.0, "efficiency": 0.75,
    })
    assert response.status_code == 200
    invalid = client.post("/api/irrigation/estimate", json={
        "location": "Ludhiana", "crop": "rice", "stage": "mid_season", "area_ha": 1.0,
    })
    assert invalid.status_code == 422


def test_wrong_state_does_not_return_forecast_for_another_place(monkeypatch):
    replies = [{"results": [{"name": "Mumbai", "admin1": "Maharashtra", "country_code": "IN",
                            "latitude": 19.0, "longitude": 72.8}]}]
    def fake_get(url, params, timeout, headers):
        return FakeResponse(replies.pop(0))
    monkeypatch.setattr(irrigation.requests, "get", fake_get)
    try:
        irrigation.calculate_irrigation("Mumbai", "Punjab", "wheat", "initial", 1.0)
    except irrigation.IrrigationDataError as exc:
        assert "supplied state" in str(exc)
    else:
        raise AssertionError("Expected a location/state mismatch error")
