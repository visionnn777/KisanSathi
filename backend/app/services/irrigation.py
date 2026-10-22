"""Live-weather irrigation planning with a daily root-zone water balance (FAO-56, chapter 8).

How the number is made, day by day for the next 7 days:
1. Crop water use ETc = ET0 (forecast, Open-Meteo) x Kc (representative FAO-56 crop coefficient).
2. Rain counts in proportion to its forecast chance (40% chance of 10 mm counts as 4 mm), and only the
   share that soaks in for the chosen soil (a stated heuristic) is kept.
3. The root zone holds TAW = 1000 x (field capacity - wilting point) x root depth  [FAO-56 eq. 82].
   The crop can use RAW = p x TAW before it is stressed [eq. 83]; p follows FAO-56 Table 22,
   adjusted for the day's ETc (p + 0.04 x (5 - ETc)).
4. The farmer's report sets how empty the root zone starts: wet = full, normal = half of RAW used,
   dry = RAW used up (water now), unknown = half of RAW (an assumption we say out loud).
5. Each day: depletion = depletion - effective rain + ETc [eq. 85, without runoff, capillary rise or
   deep percolation]. When depletion reaches RAW, one irrigation refills the root zone.
6. Gross water = net water / system efficiency; 1 mm on 1 hectare = 10,000 litres.

Not modelled: measured soil moisture, groundwater, salinity, and paddy ponding/puddling (no volume
is given for rice).
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite

import requests  # noqa: F401  (kept so tests can patch irrigation.requests.get)

from . import weather
from .weather import IrrigationDataError, _find_location, _get_json, current_conditions, weather_alerts  # noqa: F401

GEOCODING_URL = weather.GEOCODING_URL
FORECAST_URL = weather.FORECAST_URL

# Representative FAO-56 single Kc values by stage; local cultivar, climate and practice vary.
KC = {
    "maize": {"initial": 0.40, "development": 0.80, "mid_season": 1.15, "late_season": 0.70},
    "wheat": {"initial": 0.35, "development": 0.75, "mid_season": 1.15, "late_season": 0.45},
    "rice": {"initial": 1.05, "development": 1.10, "mid_season": 1.20, "late_season": 0.90},
    "tomato": {"initial": 0.45, "development": 0.75, "mid_season": 1.15, "late_season": 0.80},
    "potato": {"initial": 0.45, "development": 0.75, "mid_season": 1.15, "late_season": 0.85},
    "soybean": {"initial": 0.35, "development": 0.75, "mid_season": 1.10, "late_season": 0.60},
    "onion": {"initial": 0.50, "development": 0.75, "mid_season": 1.05, "late_season": 0.85},
    "mustard": {"initial": 0.35, "development": 0.70, "mid_season": 1.10, "late_season": 0.35},
    "chickpea": {"initial": 0.40, "development": 0.70, "mid_season": 1.00, "late_season": 0.35},
    "groundnut": {"initial": 0.40, "development": 0.75, "mid_season": 1.10, "late_season": 0.60},
    "cotton": {"initial": 0.35, "development": 0.70, "mid_season": 1.15, "late_season": 0.70},
    "sugarcane": {"initial": 0.40, "development": 0.85, "mid_season": 1.20, "late_season": 1.05},
    "pearl millet": {"initial": 0.30, "development": 0.70, "mid_season": 1.00, "late_season": 0.30},
    "sorghum": {"initial": 0.30, "development": 0.70, "mid_season": 1.00, "late_season": 0.55},
}
# FAO-56 Table 22: maximum effective rooting depth (lower value, as suggested for irrigation
# scheduling) and depletion fraction p at ETc of about 5 mm/day.
ROOT_DEPTH_M = {"maize": 1.0, "wheat": 1.0, "rice": 0.5, "tomato": 0.7, "potato": 0.4, "soybean": 0.6,
                "onion": 0.3, "mustard": 1.0, "chickpea": 0.6, "groundnut": 0.5, "cotton": 1.0,
                "sugarcane": 1.2, "pearl millet": 1.0, "sorghum": 1.0}
DEPLETION_P = {"maize": 0.55, "wheat": 0.55, "rice": 0.20, "tomato": 0.40, "potato": 0.35, "soybean": 0.50,
               "onion": 0.30, "mustard": 0.60, "chickpea": 0.50, "groundnut": 0.50, "cotton": 0.65,
               "sugarcane": 0.65, "pearl millet": 0.55, "sorghum": 0.55}
# Roots are shallower early in the season (a stated simplification of FAO-56's root growth).
STAGE_ROOT_FRACTION = {"initial": 0.30, "development": 0.65, "mid_season": 1.0, "late_season": 1.0}
MIN_ROOT_DEPTH_M = 0.15
# Water held between field capacity and wilting point, mm per metre of soil:
# middle of the FAO-56 Table 19 range (sand 0.05-0.11, sandy loam 0.11-0.15, loam 0.13-0.18,
# silt loam 0.13-0.19, clay 0.12-0.20 m3/m3). Red soils are often sandy loams; black soils are clays.
SOIL_WATER_MM_PER_M = {"sandy": 80, "loamy": 155, "alluvial": 160, "clayey": 160, "black": 160, "red": 130, "unknown": 140}
# Share of rain that soaks in rather than running off (explicit heuristic, not a calibrated value).
SOIL_EFFECTIVE_RAIN = {"sandy": 0.65, "loamy": 0.80, "alluvial": 0.80, "clayey": 0.70, "black": 0.75, "red": 0.72, "unknown": 0.80}
SOIL_LABELS = {"sandy": "Sandy", "loamy": "Loamy", "alluvial": "Alluvial", "clayey": "Clayey", "black": "Black soil", "red": "Red soil", "unknown": "Unknown"}
STAGE_NAMES = {
    "initial": "Initial / establishment",
    "development": "Vegetative development",
    "mid_season": "Mid-season / flowering or peak growth",
    "late_season": "Late season / ripening",
}
START_DEPLETION_OF_RAW = {"wet": 0.0, "normal": 0.5, "unknown": 0.5, "dry": 1.0}


def _finite_float(value):
    try:
        n = float(value)
        return n if isfinite(n) else None
    except (TypeError, ValueError):
        return None


def get_live_forecast(location: str, state: str | None = None, forecast_days: int = 7) -> dict:
    """Kept for older imports; the single implementation lives in services/weather.py."""
    return weather.get_live_forecast(location, state, forecast_days)


def root_zone_schedule(days: list[dict], crop: str, stage: str, soil: str, moisture: str,
                       efficiency: float) -> dict:
    """Daily FAO-56 style water balance. `days` need date, et0_mm, rain_mm, rain_probability_pct."""
    depth = max(MIN_ROOT_DEPTH_M, ROOT_DEPTH_M[crop] * STAGE_ROOT_FRACTION[stage])
    taw = SOIL_WATER_MM_PER_M[soil] * depth
    kc = KC[crop][stage]
    runoff_share = SOIL_EFFECTIVE_RAIN[soil]
    etc_values = [d["et0_mm"] * kc for d in days]
    average_etc = sum(etc_values) / len(etc_values) if etc_values else 5.0
    p = min(0.8, max(0.1, DEPLETION_P[crop] + 0.04 * (5 - average_etc)))
    raw = p * taw
    depletion = START_DEPLETION_OF_RAW[moisture] * raw
    start = depletion
    events = []
    expected_rain_total = effective_rain_total = 0.0
    timeline = []
    for day, etc in zip(days, etc_values):
        chance = day.get("rain_probability_pct")
        share = (chance / 100) if chance is not None else 1.0
        expected_rain = day["rain_mm"] * share
        effective_rain = expected_rain * runoff_share
        expected_rain_total += expected_rain
        effective_rain_total += effective_rain
        depletion = max(0.0, depletion - effective_rain) + etc
        depletion = min(depletion, taw)
        irrigate = depletion >= raw - 1e-9
        net = depletion if irrigate else 0.0
        if irrigate:
            events.append({"date": day["date"], "net_mm": round(net, 1), "gross_mm": round(net / efficiency, 1)})
            depletion = 0.0
        timeline.append({"date": day["date"], "depletion_mm": round(depletion, 1), "irrigate": irrigate})
    net_total = sum(e["net_mm"] for e in events)
    return {
        "root_depth_m": round(depth, 2), "total_available_water_mm": round(taw, 1),
        "depletion_fraction_p": round(p, 2), "readily_available_water_mm": round(raw, 1),
        "starting_depletion_mm": round(start, 1), "starting_assumption": moisture,
        "ending_depletion_mm": round(depletion, 1),
        "expected_rain_mm": round(expected_rain_total, 2), "effective_rain_mm": round(effective_rain_total, 2),
        "irrigation_events": events, "net_irrigation_mm": round(net_total, 1),
        "gross_irrigation_mm": round(net_total / efficiency, 1), "timeline": timeline,
    }


def calculate_irrigation(location: str, state: str | None, crop: str, stage: str,
                         area_ha: float, efficiency: float = 0.70, soil_texture: str = "unknown",
                         field_moisture: str = "unknown") -> dict:
    crop_key = crop.strip().lower()
    if crop_key not in KC:
        raise ValueError(f"Unsupported crop. Choose one of: {', '.join(KC)}")
    if stage not in STAGE_NAMES:
        raise ValueError("Unsupported crop growth stage.")
    if not isfinite(area_ha) or area_ha <= 0 or area_ha > 10_000:
        raise ValueError("Area must be a positive number up to 10,000 hectares.")
    if not isfinite(efficiency) or not 0.30 <= efficiency <= 1.0:
        raise ValueError("Irrigation efficiency must be between 0.30 and 1.00.")
    soil_key = soil_texture.strip().lower()
    if soil_key not in SOIL_EFFECTIVE_RAIN:
        raise ValueError("Unsupported soil texture.")
    moisture_key = field_moisture.strip().lower()
    if moisture_key not in START_DEPLETION_OF_RAW:
        raise ValueError("field_moisture must be unknown, dry, normal, or wet.")

    place = _find_location(location, state)
    payload = weather.fetch_forecast(place, 7)
    rows = weather.daily_rows(payload, 7)
    records = []
    for row in rows:
        et0_mm, rain_mm = row["et0_mm"], row["rain_mm"]
        if et0_mm is None or rain_mm is None or et0_mm < 0 or rain_mm < 0:
            continue
        chance = row["rain_probability_pct"]
        records.append({
            "date": row["date"], "et0_mm": round(et0_mm, 2), "rain_mm": round(rain_mm, 2),
            "rain_probability_pct": round(max(0, min(100, chance)), 0) if chance is not None else None,
            "temperature_max_c": row["temperature_max_c"], "temperature_min_c": row["temperature_min_c"],
            "wind_max_kmh": row["wind_max_kmh"], "weather_code": row["weather_code"],
            "crop_et_mm": round(et0_mm * KC[crop_key][stage], 2),
        })
    if not records:
        raise IrrigationDataError("The weather provider returned no 7-day ET₀/rain forecast.")

    schedule = root_zone_schedule(records, crop_key, stage, soil_key, moisture_key, efficiency)
    et0_total = sum(d["et0_mm"] for d in records)
    rain_total = sum(d["rain_mm"] for d in records)
    crop_et_total = sum(d["crop_et_mm"] for d in records)
    simple_deficit = max(0.0, crop_et_total - schedule["effective_rain_mm"])
    rice = crop_key == "rice"

    advice_en = ["This is a weather-based planning estimate, not a field measurement. Check the root zone before irrigating."]
    advice_hi = ["यह मौसम पर आधारित योजना का अनुमान है, खेत की नमी का माप नहीं। सिंचाई से पहले जड़ क्षेत्र की नमी जाँचें।"]
    codes = ["planning_only"]
    if moisture_key == "unknown":
        advice_en.append("Soil moisture was not reported, so the plan assumes the root zone is half-way to needing water. Choose wet, normal or dry for a better estimate.")
        advice_hi.append("मिट्टी की नमी नहीं बताई गई, इसलिए माना गया है कि जड़ क्षेत्र आधा सूख चुका है। बेहतर अनुमान के लिए गीली, सामान्य या सूखी चुनें।")
        codes.append("moisture_assumed")
    elif moisture_key == "wet":
        advice_en.append("You reported wet soil, so the plan starts with a full root zone. Recheck the field after 2–3 days.")
        advice_hi.append("आपने मिट्टी गीली बताई है, इसलिए योजना भरे जड़ क्षेत्र से शुरू होती है। 2–3 दिन बाद खेत फिर देखें।")
        codes.append("moisture_wet")
    elif moisture_key == "dry":
        advice_en.append("You reported dry soil, so the first watering is planned for today. Split it by local practice if the soil cannot take it at once.")
        advice_hi.append("आपने मिट्टी सूखी बताई है, इसलिए पहली सिंचाई आज की योजना में है। मिट्टी एक साथ न सोख पाए तो स्थानीय तरीके से बाँटकर दें।")
        codes.append("moisture_dry")
    if not schedule["irrigation_events"] and not rice:
        advice_en.append("No watering is needed in the next 7 days if your soil report is right; rain and stored soil water should cover the crop.")
        advice_hi.append("अगर मिट्टी की नमी सही बताई है तो अगले 7 दिन सिंचाई की ज़रूरत नहीं; बारिश और मिट्टी में रखा पानी फसल के लिए काफ़ी होना चाहिए।")
        codes.append("no_irrigation_needed")
    if rain_total >= 15:
        advice_en.append("Rain is forecast within the planning window; reassess after rainfall and avoid waterlogging.")
        advice_hi.append("योजना अवधि में बारिश का अनुमान है; बारिश के बाद फिर आकलन करें और जलभराव से बचें।")
        codes.append("rain_in_window")
    if rice:
        advice_en.append("Paddy-specific water depth, land preparation, seepage/percolation and drainage are excluded. No gross irrigation volume is shown for rice.")
        advice_hi.append("धान के खेत की पानी की गहराई, खेत की तैयारी, रिसाव/गहराई में पानी जाना और जल निकासी शामिल नहीं हैं। धान के लिए कुल सिंचाई मात्रा नहीं दिखाई जाती।")
        codes.append("rice_excluded")

    gross_mm = schedule["gross_irrigation_mm"]
    events = [{**event, "litres": round(event["gross_mm"] * 10_000 * area_ha)} for event in schedule["irrigation_events"]]
    return {
        "location": {**place, "latitude": round(place["latitude"], 4), "longitude": round(place["longitude"], 4)},
        "crop": crop_key, "stage": stage, "stage_name": STAGE_NAMES[stage], "kc": KC[crop_key][stage],
        "area_ha": round(area_ha, 4), "irrigation_efficiency": round(efficiency, 2),
        "soil_texture": soil_key, "soil_texture_label": SOIL_LABELS[soil_key], "field_moisture_reported": moisture_key,
        "current_weather": current_conditions(payload), "forecast_days": records, "alerts": weather_alerts(records),
        "root_zone": {k: v for k, v in schedule.items() if k not in {"irrigation_events", "timeline"}},
        "root_zone_timeline": schedule["timeline"],
        "irrigation_events": [] if rice else events,
        "totals": {
            "forecast_days": len(records), "reference_et0_mm": round(et0_total, 2),
            "estimated_crop_water_use_mm": round(crop_et_total, 2), "forecast_rain_mm": round(rain_total, 2),
            "expected_rain_mm": schedule["expected_rain_mm"],
            "estimated_effective_rain_mm": schedule["effective_rain_mm"],
            "effective_rain_fraction_assumption": SOIL_EFFECTIVE_RAIN[soil_key],
            "simple_deficit_mm": round(simple_deficit, 2),
            "estimated_net_deficit_mm": schedule["net_irrigation_mm"],
            "estimated_gross_irrigation_mm": None if rice else gross_mm,
            "estimated_gross_water_litres": None if rice else round(gross_mm * 10_000 * area_ha),
        },
        "advice": {"en": advice_en, "hi": advice_hi}, "advice_codes": codes,
        "source": "Open-Meteo Forecast API (live request), FAO-56 crop coefficients, root depths and soil water ranges",
        "source_urls": ["https://open-meteo.com/en/docs", "https://www.fao.org/4/X0490E/x0490e0b.htm",
                        "https://www.fao.org/4/X0490E/x0490e0e.htm"],
        "weather_retrieved_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "7-day planning estimate only: a simplified FAO-56 root-zone water balance from forecast weather and your soil report. No soil sensor is connected. For rice, no paddy irrigation volume is calculated. Verify field moisture and consult KVK/IMD guidance.",
    }
