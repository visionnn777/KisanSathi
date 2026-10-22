"""Live-weather parsing and API contract, with all network calls mocked."""
from app.services import weather


def test_live_forecast_parses_current_conditions_daily_et0_and_alerts(monkeypatch):
    place = {"name": "Ludhiana", "state": "Punjab", "latitude": 30.9, "longitude": 75.85}
    payload = {
        "timezone": "Asia/Kolkata", "timezone_abbreviation": "IST", "generationtime_ms": 2.1,
        "current": {"time": "2026-10-18T09:00", "temperature_2m": 39, "relative_humidity_2m": 35,
                    "apparent_temperature": 41, "is_day": 1, "precipitation": 0, "rain": 0,
                    "showers": 0, "weather_code": 0, "cloud_cover": 5,
                    "wind_speed_10m": 8, "wind_gusts_10m": 13},
        "daily": {"time": ["2026-10-18", "2026-10-19"], "weather_code": [0, 65],
                  "temperature_2m_max": [39, 30], "temperature_2m_min": [25, 22],
                  "precipitation_sum": [0, 31], "rain_sum": [0, 31],
                  "precipitation_probability_max": [0, 90], "et0_fao_evapotranspiration": [5.2, 3.1],
                  "wind_speed_10m_max": [18, 38]},
    }
    monkeypatch.setattr(weather, "_find_location", lambda location, state: place)
    monkeypatch.setattr(weather, "_get_json", lambda url, params: payload)
    out = weather.get_live_forecast("Ludhiana", "Punjab", 2)
    assert out["current"]["temperature_c"] == 39
    assert out["daily"][0]["et0_mm"] == 5.2
    assert out["daily"][1]["rain_mm"] == 31
    # IMD: 31 mm is moderate rain (heavy starts at 64.5 mm); 39 °C is below the 40 °C hot-day mark;
    # 38 km/h is too windy for spraying but not "strong wind" (40 km/h).
    assert {a["code"] for a in out["alerts"]} == {"moderate_rain", "spray_wind"}
    assert out["source"] == "Open-Meteo Forecast API"
    assert out["retrieved_at_utc"]


def test_live_forecast_fails_if_provider_has_no_daily_dates(monkeypatch):
    monkeypatch.setattr(weather, "_find_location", lambda location, state: {"name": location, "state": state, "latitude": 1, "longitude": 1})
    monkeypatch.setattr(weather, "_get_json", lambda url, params: {"daily": {"time": []}})
    try:
        weather.get_live_forecast("Test Town", "Punjab", 7)
    except weather.IrrigationDataError as exc:
        assert "no usable daily forecast" in str(exc)
    else:
        raise AssertionError("Expected missing forecast to raise a provider error")


def test_weather_route_returns_forecast_and_validates_days(client, monkeypatch):
    from app.routers import weather as weather_router
    monkeypatch.setattr(weather_router, "get_live_forecast", lambda location, state, days: {
        "location": {"name": location, "state": state}, "daily": [], "source": "Open-Meteo Forecast API"
    })
    good = client.get("/api/weather/forecast", params={"location": "Ludhiana", "state": "Punjab", "days": 7})
    assert good.status_code == 200
    assert good.json()["source"] == "Open-Meteo Forecast API"
    bad = client.get("/api/weather/forecast", params={"location": "Ludhiana", "state": "Punjab", "days": 8})
    assert bad.status_code == 422


def test_imd_categories_for_heavy_rain_heat_and_wind():
    days = [{"date": "d1", "rain_mm": 70, "temperature_max_c": 41, "wind_max_kmh": 45},
            {"date": "d2", "rain_mm": 120, "temperature_max_c": 46, "wind_max_kmh": 5},
            {"date": "d3", "rain_mm": 210, "temperature_max_c": 30, "wind_max_kmh": 5}]
    codes = [(a["date"], a["code"]) for a in weather.weather_alerts(days)]
    assert ("d1", "heavy_rain") in codes and ("d1", "heat") in codes and ("d1", "wind") in codes
    assert ("d2", "very_heavy_rain") in codes and ("d2", "severe_heat") in codes
    assert ("d3", "extremely_heavy_rain") in codes
