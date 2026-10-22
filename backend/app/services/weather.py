"""Live weather lookup using Open-Meteo's public forecast API (no key for non-commercial use).

Rain is read from `precipitation_sum`, which includes showers (Open-Meteo's `rain_sum`
does not: monsoon rain often falls as showers). Alerts use India Meteorological Department
rain categories: heavy rain is 64.5–115.5 mm in 24 hours, very heavy 115.6–204.4 mm,
extremely heavy 204.5 mm or more; 15.6–64.4 mm is moderate rain.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from .place_names import same_state

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SOURCE_URL = "https://open-meteo.com/en/docs"
CURRENT_FIELDS = ("temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,"
                  "showers,weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m")
DAILY_FIELDS = ("weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,"
                "precipitation_probability_max,et0_fao_evapotranspiration,wind_speed_10m_max")

WMO_CONDITIONS = {
    0: ("Clear sky", "साफ़ आसमान"), 1: ("Mainly clear", "मुख्यतः साफ़"),
    2: ("Partly cloudy", "आंशिक बादल"), 3: ("Overcast", "बादल छाए हुए"),
    45: ("Fog", "कोहरा"), 48: ("Depositing rime fog", "कोहरा"),
    51: ("Light drizzle", "हल्की बूंदाबांदी"), 53: ("Drizzle", "बूंदाबांदी"),
    55: ("Dense drizzle", "तेज़ बूंदाबांदी"), 61: ("Slight rain", "हल्की बारिश"),
    63: ("Moderate rain", "मध्यम बारिश"), 65: ("Heavy rain", "भारी बारिश"),
    71: ("Slight snow", "हल्की बर्फ़बारी"), 73: ("Moderate snow", "मध्यम बर्फ़बारी"),
    75: ("Heavy snow", "भारी बर्फ़बारी"), 80: ("Rain showers", "बारिश की बौछारें"),
    81: ("Moderate rain showers", "मध्यम बारिश की बौछारें"),
    82: ("Violent rain showers", "तेज़ बारिश की बौछारें"),
    95: ("Thunderstorm", "आंधी-तूफ़ान"), 96: ("Thunderstorm with hail", "ओलों के साथ तूफ़ान"),
    99: ("Severe thunderstorm with hail", "ओलों के साथ तेज़ तूफ़ान"),
}

# IMD 24-hour rainfall categories (mm)
RAIN_MODERATE, RAIN_HEAVY, RAIN_VERY_HEAVY, RAIN_EXTREME = 15.6, 64.5, 115.6, 204.5
HOT_DAY_C, SEVERE_HEAT_C = 40.0, 45.0   # IMD heat-wave thresholds for plains use 40 °C and 45 °C
SPRAY_WIND_KMH, STRONG_WIND_KMH = 15.0, 40.0


class IrrigationDataError(Exception):
    """The weather or location provider gave no usable answer."""


def _get_json(url: str, params: dict, timeout: int = 12) -> dict:
    try:
        response = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": "KisanSaathi/1.0"})
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise IrrigationDataError("Live weather data is temporarily unavailable. Check internet access and try again.") from exc
    if not isinstance(payload, dict):
        raise IrrigationDataError("Weather provider returned an unexpected response.")
    return payload


def _state_matches(admin1: str, state: str) -> bool:
    return same_state(admin1 or "", state) or state.casefold() in str(admin1 or "").casefold()


def _find_location(location: str, state: str | None) -> dict:
    payload = _get_json(GEOCODING_URL, {
        "name": location, "count": 10, "language": "en", "format": "json", "countryCode": "IN",
    })
    results = payload.get("results") or []
    results = [r for r in results if isinstance(r, dict) and (r.get("country_code") or "").upper() == "IN"]
    if state:
        selected = [r for r in results if _state_matches(str(r.get("admin1", "")), state)]
        if not selected:
            raise IrrigationDataError("The location did not match the supplied state. Check the town/state or try a nearby district headquarters.")
        results = selected
    if not results:
        raise IrrigationDataError("Location not found in India. Try a nearby town/city and state.")
    result = results[0]
    try:
        latitude, longitude = float(result["latitude"]), float(result["longitude"])
    except (KeyError, TypeError, ValueError) as exc:
        raise IrrigationDataError("The location result did not contain usable coordinates.") from exc
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise IrrigationDataError("The location result contained invalid coordinates.")
    return {"name": result.get("name", location), "state": result.get("admin1"), "latitude": latitude, "longitude": longitude}


def _finite(value: Any) -> float | None:
    try:
        n = float(value)
        return n if n == n and abs(n) != float("inf") else None
    except (TypeError, ValueError):
        return None


def condition(code: Any) -> dict[str, Any]:
    try:
        code_n = int(code)
    except (TypeError, ValueError):
        code_n = -1
    label = WMO_CONDITIONS.get(code_n, ("Conditions unavailable", "मौसम की जानकारी उपलब्ध नहीं"))
    return {"code": code_n if code_n >= 0 else None, "label": {"en": label[0], "hi": label[1]}}


def fetch_forecast(place: dict, forecast_days: int) -> dict:
    return _get_json(FORECAST_URL, {
        "latitude": place["latitude"], "longitude": place["longitude"],
        "current": CURRENT_FIELDS, "daily": DAILY_FIELDS,
        "forecast_days": int(forecast_days), "timezone": "Asia/Kolkata",
    })


def current_conditions(payload: dict) -> dict | None:
    raw = payload.get("current") or {}
    if not raw:
        return None
    return {
        "time": raw.get("time"), "temperature_c": _finite(raw.get("temperature_2m")),
        "feels_like_c": _finite(raw.get("apparent_temperature")),
        "relative_humidity_pct": _finite(raw.get("relative_humidity_2m")),
        "is_day": raw.get("is_day"), "precipitation_mm": _finite(raw.get("precipitation")),
        "rain_mm": _finite(raw.get("rain")), "showers_mm": _finite(raw.get("showers")),
        "cloud_cover_pct": _finite(raw.get("cloud_cover")),
        "wind_speed_kmh": _finite(raw.get("wind_speed_10m")),
        "wind_gusts_kmh": _finite(raw.get("wind_gusts_10m")),
        "weather_code": raw.get("weather_code"),
        "condition": condition(raw.get("weather_code")),
    }


def daily_rows(payload: dict, forecast_days: int) -> list[dict]:
    daily = payload.get("daily") or {}

    def series(key):
        value = daily.get(key)
        return value if isinstance(value, list) else []

    times = series("time")
    precipitation = series("precipitation_sum") or series("rain_sum")
    rows = []
    for i in range(min(int(forecast_days), len(times))):
        def at(values):
            return _finite(values[i]) if i < len(values) else None
        rows.append({
            "date": times[i],
            "condition": condition(series("weather_code")[i] if i < len(series("weather_code")) else None),
            "weather_code": series("weather_code")[i] if i < len(series("weather_code")) else None,
            "temperature_max_c": at(series("temperature_2m_max")),
            "temperature_min_c": at(series("temperature_2m_min")),
            "precipitation_mm": at(precipitation),
            "rain_mm": at(precipitation),          # includes showers
            "rain_probability_pct": at(series("precipitation_probability_max")),
            "et0_mm": at(series("et0_fao_evapotranspiration")),
            "wind_max_kmh": at(series("wind_speed_10m_max")),
        })
    return rows


def _alert(day: str, severity: str, code: str, en: str, hi: str) -> dict:
    return {"date": day, "severity": severity, "code": code, "message": {"en": en, "hi": hi}}


def weather_alerts(days: list[dict]) -> list[dict]:
    alerts = []
    for day in days:
        date, rain = day["date"], day.get("rain_mm") or 0
        if rain >= RAIN_EXTREME:
            alerts.append(_alert(date, "warning", "extremely_heavy_rain",
                                 "Extremely heavy rain is forecast (IMD category: 204.5 mm or more). Follow local IMD warnings, protect stored produce and keep drains open.",
                                 "अत्यधिक भारी बारिश का अनुमान है (IMD श्रेणी: 204.5 मिमी या अधिक)। स्थानीय IMD चेतावनी मानें, रखी उपज बचाएँ और नालियाँ खुली रखें।"))
        elif rain >= RAIN_VERY_HEAVY:
            alerts.append(_alert(date, "warning", "very_heavy_rain",
                                 "Very heavy rain is forecast (IMD category: 115.6–204.4 mm). Check drainage and avoid irrigation and spraying.",
                                 "बहुत भारी बारिश का अनुमान है (IMD श्रेणी: 115.6–204.4 मिमी)। जल निकासी देखें; सिंचाई और छिड़काव न करें।"))
        elif rain >= RAIN_HEAVY:
            alerts.append(_alert(date, "caution", "heavy_rain",
                                 "Heavy rain is forecast (IMD category: 64.5–115.5 mm). Check local IMD advisories and drainage; avoid unnecessary irrigation.",
                                 "भारी बारिश का अनुमान है (IMD श्रेणी: 64.5–115.5 मिमी)। स्थानीय IMD सलाह और जल निकासी देखें; अनावश्यक सिंचाई न करें।"))
        elif rain >= RAIN_MODERATE:
            alerts.append(_alert(date, "info", "moderate_rain",
                                 "Moderate rain is forecast (15.6–64.4 mm). You may be able to delay irrigation; recheck the field after rain.",
                                 "मध्यम बारिश का अनुमान है (15.6–64.4 मिमी)। सिंचाई टाल सकते हैं; बारिश के बाद खेत फिर देखें।"))
        top = day.get("temperature_max_c") or 0
        if top >= SEVERE_HEAT_C:
            alerts.append(_alert(date, "warning", "severe_heat",
                                 "Severe heat is forecast (45 °C or more). Irrigate in the cool hours if the crop needs water and check the local IMD heat warning.",
                                 "भीषण गर्मी का अनुमान है (45 °C या अधिक)। फसल को पानी चाहिए तो ठंडे समय सिंचाई करें और स्थानीय IMD लू चेतावनी देखें।"))
        elif top >= HOT_DAY_C:
            alerts.append(_alert(date, "caution", "heat",
                                 "Very hot day forecast (40 °C or more). Check crop stress and local advice; do not irrigate solely from this alert.",
                                 "बहुत गर्म दिन का अनुमान है (40 °C या अधिक)। फसल में तनाव और स्थानीय सलाह देखें; केवल इस सूचना पर सिंचाई न करें।"))
        wind = day.get("wind_max_kmh") or 0
        if wind >= STRONG_WIND_KMH:
            alerts.append(_alert(date, "caution", "wind",
                                 "Strong wind is possible (40 km/h or more). Do not spray; check official local warnings before operating equipment.",
                                 "तेज़ हवा संभव है (40 किमी/घंटा या अधिक)। छिड़काव न करें; उपकरण चलाने से पहले स्थानीय चेतावनी देखें।"))
        elif wind >= SPRAY_WIND_KMH:
            alerts.append(_alert(date, "info", "spray_wind",
                                 "Wind may reach 15 km/h or more. Spray only in calm morning or evening hours to avoid drift.",
                                 "हवा 15 किमी/घंटा या अधिक हो सकती है। दवा उड़कर न फैले, इसलिए सुबह-शाम शांत समय में ही छिड़काव करें।"))
    return alerts


def get_live_forecast(location: str, state: str | None = None, forecast_days: int = 7) -> dict:
    """Resolve an Indian town, retrieve current conditions plus a multi-day forecast.

    Forecasts are model guidance, not a weather warning issued by IMD. Coordinates and
    the provider's current timestamp are returned to make source/freshness transparent.
    """
    if not 1 <= int(forecast_days) <= 7:
        raise ValueError("forecast_days must be between 1 and 7")
    place = _find_location(location, state)
    payload = _get_json(FORECAST_URL, {
        "latitude": place["latitude"], "longitude": place["longitude"],
        "current": CURRENT_FIELDS, "daily": DAILY_FIELDS,
        "forecast_days": int(forecast_days), "timezone": "Asia/Kolkata",
    })
    days = daily_rows(payload, forecast_days)
    if not days:
        raise IrrigationDataError("The weather provider returned no usable daily forecast. Try again later.")
    return {
        "location": {**place, "latitude": round(place["latitude"], 4), "longitude": round(place["longitude"], 4)},
        "current": current_conditions(payload), "daily": days, "alerts": weather_alerts(days),
        "timezone": payload.get("timezone", "Asia/Kolkata"), "timezone_abbreviation": payload.get("timezone_abbreviation"),
        "generation_time_ms": payload.get("generationtime_ms"), "source": "Open-Meteo Forecast API",
        "source_url": SOURCE_URL, "usage_note": "Live forecast response retrieved at request time. Model forecasts can change; this is not an official IMD warning.",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
    }
