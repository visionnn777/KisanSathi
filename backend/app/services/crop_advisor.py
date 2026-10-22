"""Transparent, evidence-based local crop comparison using imported history and mandi observations.

This is a decision-support MVP, not a trained profit predictor. Unknown costs or stale prices
are surfaced as data gaps; values are never silently substituted with invented market data.

Every data gap is returned twice: as English text (``data_gaps``) for API users, and as a
code with parameters (``data_gap_codes``) so the app can show it in Hindi or English.
"""
from __future__ import annotations

from datetime import date
from statistics import median, pstdev
from typing import Any

from sqlalchemy.orm import Session

from .. import config
from ..models import CropProduction, MandiPrice, MandiPriceHistory
from ..timeutil import days_old, today_ist
from .crop_catalog import canonical_crop, clean_name, plausible_yield, row_tonnes, unit_for
from .place_names import same_district, same_state

ALL_SEASONS = {"", "all", "all seasons", "all season", "whole year", "annual", "all year"}
# Names farmers use -> the season name used by Indian crop statistics
SEASON_ALIASES = {"zaid": "summer", "zayad": "summer", "zaid summer": "summer", "garma": "summer",
                  "summer": "summer", "kharif": "kharif", "rabi": "rabi", "winter": "winter",
                  "autumn": "autumn", "whole year": "whole year"}
# Months in which the crop of each season is mostly harvested and sold (used for seasonal prices).
HARVEST_MONTHS = {"kharif": {10, 11, 12, 1}, "rabi": {3, 4, 5, 6}, "summer": {5, 6, 7},
                  "winter": {12, 1, 2, 3}, "autumn": {8, 9, 10, 11}}

WATER_NEED = {
    "rice": "high", "sugarcane": "high", "banana": "high", "jute": "medium-high", "turmeric": "medium-high",
    "ginger": "medium-high", "tomato": "medium-high", "potato": "medium", "onion": "medium",
    "maize": "medium", "wheat": "medium", "soybean": "medium", "cotton": "medium", "groundnut": "medium",
    "brinjal": "medium", "green chilli": "medium", "dry chillies": "medium", "cauliflower": "medium",
    "cabbage": "medium", "garlic": "medium", "sweet potato": "medium", "tapioca": "medium",
    "sunflower": "medium", "mesta": "medium", "tobacco": "medium", "mustard": "low-medium",
    "chickpea": "low-medium", "pigeon pea": "low-medium", "lentil": "low-medium", "green gram": "low-medium",
    "black gram": "low-medium", "barley": "low-medium", "linseed": "low-medium", "castor": "low-medium",
    "coriander": "low-medium", "peas and beans": "low-medium", "pearl millet": "low", "sorghum": "low",
    "finger millet": "low", "small millets": "low", "sesame": "low", "safflower": "low", "niger": "low",
    "horse gram": "low", "moth bean": "low", "guar": "low", "khesari": "low",
}
SOIL_PREFERENCES = {
    "rice": {"clayey", "alluvial", "black"}, "wheat": {"loamy", "alluvial", "clayey", "black"},
    "maize": {"loamy", "alluvial", "black"}, "mustard": {"sandy", "loamy", "alluvial"},
    "chickpea": {"loamy", "black", "alluvial"}, "pigeon pea": {"loamy", "red", "black"},
    "pearl millet": {"sandy", "loamy", "red"}, "sorghum": {"black", "loamy", "red"},
    "groundnut": {"sandy", "loamy", "red"}, "cotton": {"black", "loamy"},
    "soybean": {"black", "loamy"}, "potato": {"sandy", "loamy"},
    "onion": {"sandy", "loamy", "alluvial"}, "tomato": {"loamy", "alluvial"},
}
# Broad indicative ranges only, not a soil-test interpretation or agronomic exclusion rule.
PH_PREFERENCES = {
    "rice": (5.0, 7.5), "wheat": (6.0, 7.8), "maize": (5.5, 7.5),
    "mustard": (5.5, 8.0), "chickpea": (6.0, 8.0), "pigeon pea": (5.5, 7.5),
    "pearl millet": (5.5, 8.0), "sorghum": (5.5, 8.0), "groundnut": (5.5, 7.0),
    "cotton": (5.5, 8.0), "soybean": (5.5, 7.5), "potato": (5.0, 6.8),
    "onion": (6.0, 7.5), "tomato": (5.5, 7.5), "sugarcane": (6.0, 8.0),
    "banana": (5.5, 7.5), "brinjal": (5.5, 7.5), "green chilli": (5.5, 7.5),
    "cauliflower": (5.5, 7.5), "cabbage": (5.5, 7.5), "garlic": (5.5, 7.5),
}
ROTATION_GROUP = {
    "maize": "cereal", "wheat": "cereal", "rice": "cereal", "barley": "cereal", "pearl millet": "cereal",
    "sorghum": "cereal", "finger millet": "cereal", "small millets": "cereal",
    "chickpea": "legume", "pigeon pea": "legume", "lentil": "legume", "green gram": "legume",
    "black gram": "legume", "horse gram": "legume", "moth bean": "legume", "khesari": "legume",
    "peas and beans": "legume", "other kharif pulses": "legume", "other rabi pulses": "legume",
    "soybean": "legume", "groundnut": "legume", "guar": "legume",
    "mustard": "oilseed", "sesame": "oilseed", "linseed": "oilseed", "castor": "oilseed",
    "sunflower": "oilseed", "safflower": "oilseed", "niger": "oilseed",
    "cotton": "fibre", "jute": "fibre", "mesta": "fibre", "sunn hemp": "fibre",
    "potato": "solanaceae", "tomato": "solanaceae", "brinjal": "solanaceae", "green chilli": "solanaceae",
    "dry chillies": "solanaceae", "sweet potato": "root", "tapioca": "root",
}
ISSUE_TIPS = {
    "low_price": {
        "en": ["Compare net realisation across nearby markets, including transport, loading, commission and quality deductions.", "Check price dates and crop variety/grade before selling; a high headline price may apply to a different grade.", "For the next season, compare multi-year seasonal prices and a buyer/market plan before changing crops."],
        "hi": ["बेचने से पहले नज़दीकी मंडियों की शुद्ध प्राप्ति तुलना करें; परिवहन, लदाई, कमीशन और गुणवत्ता कटौती जोड़ें।", "कीमत की तारीख, किस्म और ग्रेड देखें; अधिक कीमत किसी अलग ग्रेड की हो सकती है।", "अगली फसल बदलने से पहले कई वर्षों की मौसमी कीमत और खरीदार/बाजार योजना देखें।"]},
    "low_yield": {
        "en": ["Compare actual yield with this district's same-crop, same-season history; district averages are benchmarks, not a farm forecast.", "Review sowing date, seed quality, plant stand, weeds, pest/disease signs, soil test and irrigation timing with a local extension worker.", "Record input use and harvest weight next season so the cause can be distinguished from normal weather variation."],
        "hi": ["वास्तविक उपज की तुलना जिले की उसी फसल और मौसम की ऐतिहासिक उपज से करें; यह केवल क्षेत्रीय आधार है, खेत का पूर्वानुमान नहीं।", "बुवाई का समय, बीज, पौध संख्या, खरपतवार, कीट/रोग, मिट्टी जाँच और सिंचाई समय स्थानीय कृषि विशेषज्ञ के साथ देखें।", "अगले मौसम में लागत और तौली गई उपज लिखें ताकि कारण समझा जा सके।"]},
    "high_cost": {
        "en": ["Break costs into seed, fertiliser, crop protection, labour, irrigation, machinery, harvest and transport.", "Use soil-test-based nutrient plans and compare total cost per hectare, not the sticker price of a single input.", "Compare break-even price = total cost per hectare ÷ expected quintals per hectare."],
        "hi": ["बीज, खाद, फसल सुरक्षा, मजदूरी, सिंचाई, मशीन, कटाई और परिवहन की लागत अलग-अलग लिखें।", "मिट्टी जाँच के अनुसार पोषण योजना अपनाएँ और एक इनपुट की कीमत नहीं, प्रति हेक्टेयर कुल लागत तुलना करें।", "लाभ-हानि बराबर कीमत = प्रति हेक्टेयर कुल लागत ÷ अपेक्षित क्विंटल प्रति हेक्टेयर।"]},
    "water_stress": {
        "en": ["Check root-zone moisture before irrigating; weather-model estimates are not soil sensors.", "Use field-appropriate irrigation timing, repair leaks, and avoid irrigating just before substantial forecast rain.", "Consider lower-water candidates only if district records, soil and sowing window support them."],
        "hi": ["सिंचाई से पहले जड़ क्षेत्र की नमी जाँचें; मौसम का अनुमान मिट्टी सेंसर नहीं है।", "स्थानीय जरूरत के अनुसार सिंचाई करें, रिसाव ठीक करें और भारी बारिश से ठीक पहले अनावश्यक सिंचाई न करें।", "कम पानी वाली फसल तभी चुनें जब जिले के रिकॉर्ड, मिट्टी और बुवाई का समय अनुकूल हों।"]},
    "disease_pest": {
        "en": ["Inspect several plants across the field; a single leaf photo cannot establish field-wide incidence.", "Remove/contain severely affected material only when the crop-specific guidance supports it, and avoid moving infected debris.", "Ask KVK or the Kisan Call Centre before selecting any pesticide; follow the label and pre-harvest interval."],
        "hi": ["पूरे खेत में कई पौधों की जाँच करें; एक पत्ती की फोटो से पूरे खेत में रोग का स्तर पता नहीं चलता।", "गंभीर प्रभावित सामग्री हटाएँ/अलग करें, जहाँ फसल-विशेष सलाह ऐसा कहे; संक्रमित अवशेष न फैलाएँ।", "कीटनाशक चुनने से पहले KVK या किसान कॉल सेंटर से पूछें; लेबल और कटाई-पूर्व अंतराल मानें।"]},
    "weather": {
        "en": ["Compare the event with the local IMD advisory and note crop stage and damage extent.", "Improve drainage after heavy rain; during dry spells check soil moisture and critical flowering/grain-fill stages.", "Use district contingency plans for locally suitable alternatives after weather damage."],
        "hi": ["मौसम की घटना को स्थानीय IMD सलाह से मिलाएँ और फसल की अवस्था व नुकसान दर्ज करें।", "भारी बारिश के बाद जल निकासी सुधारें; सूखे में मिट्टी की नमी तथा फूल/दाना भरने की अवस्था देखें।", "मौसम से नुकसान के बाद स्थानीय उपयुक्त विकल्पों के लिए जिला आकस्मिक योजना देखें।"]},
    "multiple": {
        "en": ["Separate the problem into yield, sale-price and cost components before deciding to switch crops.", "Keep receipts and field records; then compare alternatives with local yield, current dated prices and farmer-entered costs.", "Get local KVK advice before making a major crop-switch or input decision."],
        "hi": ["फसल बदलने से पहले समस्या को उपज, बिक्री कीमत और लागत में अलग करें।", "रसीदें और खेत रिकॉर्ड रखें; फिर स्थानीय उपज, तारीख वाली कीमत और किसान द्वारा दी लागत से विकल्प तुलना करें।", "बड़ा फसल बदलाव या इनपुट निर्णय लेने से पहले स्थानीय KVK सलाह लें।"]},
    "unknown": {
        "en": ["Record harvested quantity, sale price and input costs before concluding why the season was poor.", "Choose one or two field observations to check with a local extension worker.", "The planner will flag unavailable data instead of assuming the cause."],
        "hi": ["मौसम खराब रहा ऐसा निष्कर्ष निकालने से पहले उपज, बिक्री कीमत और लागत लिखें।", "स्थानीय कृषि विशेषज्ञ के साथ जाँचने के लिए एक-दो खेत संकेत दर्ज करें।", "आवश्यक डेटा न मिलने पर यह प्लानर कारण मानकर नहीं चलेगा, बल्कि कमी बताएगा।"]},
}




class _Gaps:
    """Collect data gaps as English text plus a translatable code."""

    def __init__(self):
        self.text: list[str] = []
        self.codes: list[dict] = []

    def add(self, code: str, english: str, **params) -> None:
        self.text.append(english)
        self.codes.append({"code": code, "params": params})


def normalise_season(value: str) -> str:
    key = clean_name(value)
    return SEASON_ALIASES.get(key, key)


def _season_matches(row_season: str, wanted: str) -> bool:
    return normalise_season(row_season) == normalise_season(wanted)


def _matching_rows(db: Session, state: str, district: str) -> list[CropProduction]:
    """Rows for a district, accepting current or old spellings ("Bathinda" = "BHATINDA")."""
    states = [s for (s,) in db.query(CropProduction.state).distinct().all() if same_state(s, state)]
    if not states:
        return []
    pairs = (db.query(CropProduction.state, CropProduction.district)
             .filter(CropProduction.state.in_(states)).distinct().all())
    wanted = [(s, d) for s, d in pairs if same_district(s, d, district)]
    if not wanted:
        return []
    rows: list[CropProduction] = []
    for s, d in wanted:
        rows.extend(db.query(CropProduction).filter(CropProduction.state == s, CropProduction.district == d)
                    .order_by(CropProduction.year_start.asc()).all())
    return rows


def _aggregate_by_year(rows: list[CropProduction], all_seasons: bool) -> list[dict]:
    """One value per year, with production in tonnes and impossible yields removed."""
    by_year: dict[tuple[int, str], list[CropProduction]] = {}
    for row in rows:
        by_year.setdefault((row.year_start, row.year_label), []).append(row)
    result = []
    aggregate_names = {"all season", "all seasons", "whole year", "annual", "all year"}
    for (year, label), entries in sorted(by_year.items()):
        annual = [r for r in entries if clean_name(r.season) in aggregate_names]
        if all_seasons:
            selected = annual[:1] if annual else entries
        else:
            selected = entries[:1]
        tonnes = [row_tonnes(r) for r in selected]
        if not selected or any(t is None for t in tonnes):
            continue
        area = sum(float(r.area_ha) for r in selected)
        production = sum(tonnes)
        if area <= 0 or production < 0:
            continue
        crop_yield = production / area
        if not plausible_yield(selected[0].crop, crop_yield):
            continue
        result.append({"year_start": year, "year_label": label, "area_ha": area,
                       "production_tonnes": production, "yield_t_ha": crop_yield})
    return result


def _window_stats(points: list[tuple[date, float]], months: set[int] | None) -> dict:
    chosen = [(d, v) for d, v in points if months is None or d.month in months]
    values = [v for _, v in chosen]
    return {
        "observations": len(chosen),
        "years": len({d.year for d, _ in chosen}),
        "median": round(median(values), 2) if values else None,
        "low": round(min(values), 2) if values else None,
        "high": round(max(values), 2) if values else None,
        "first_date": chosen[0][0].isoformat() if chosen else None,
        "last_date": chosen[-1][0].isoformat() if chosen else None,
    }


def _price_stats(db: Session, state: str, canonical: str, season: str = "") -> dict[str, Any]:
    """Combine recent market quotations with separately stored state-level history.

    Individual market quotes and provider-aggregated history are deliberately kept
    separate; an aggregate historical value is not passed off as a single mandi price.
    """
    states = [s for (s,) in db.query(MandiPrice.state).distinct().all() if same_state(s, state)]
    rows = (db.query(MandiPrice).filter(MandiPrice.state.in_(states or [state]))
            .order_by(MandiPrice.arrival_date.desc()).limit(20000).all())
    matches = [r for r in rows if canonical_crop(r.commodity) == canonical
               and r.modal_price and float(r.modal_price) > 0]

    history_states = [s for (s,) in db.query(MandiPriceHistory.state).distinct().all() if same_state(s, state)]
    history_rows = (db.query(MandiPriceHistory).filter(MandiPriceHistory.state.in_(history_states or [state]))
                    .order_by(MandiPriceHistory.observation_date.desc()).limit(20000).all())
    history_matches = [r for r in history_rows if canonical_crop(r.commodity) == canonical
                       and r.average_modal_price and float(r.average_modal_price) > 0]
    # Keep one observation per date if provider exports duplicate spellings of a commodity.
    by_history_date: dict[date, list[float]] = {}
    for r in history_matches:
        by_history_date.setdefault(r.observation_date, []).append(float(r.average_modal_price))
    historical = [(day, median(values)) for day, values in sorted(by_history_date.items())]
    historical_prices = [value for _, value in historical]
    historical_span = (historical[-1][0] - historical[0][0]).days if len(historical) >= 2 else 0
    long_trend = None
    if len(historical) >= 6:
        n = max(1, len(historical) // 4)
        early = median(value for _, value in historical[:n])
        late = median(value for _, value in historical[-n:])
        if early > 0:
            long_trend = round((late - early) / early * 100, 1)
    season_key = normalise_season(season)
    months = HARVEST_MONTHS.get(season_key)
    long_history = {
        "observations": len(historical), "span_days": historical_span,
        "first_date": historical[0][0].isoformat() if historical else None,
        "last_date": historical[-1][0].isoformat() if historical else None,
        "median": round(median(historical_prices), 2) if historical_prices else None,
        "low": round(min(historical_prices), 2) if historical_prices else None,
        "high": round(max(historical_prices), 2) if historical_prices else None,
        "trend_pct": long_trend, "source": "mandi-api-history state-level aggregate" if historical else None,
        "harvest_months": sorted(months) if months else None,
        "harvest_window": _window_stats(historical, months) if months else None,
    }

    if not matches:
        return {"price": None, "date": None, "age_days": None, "records": 0,
                "distinct_dates": 0, "history_median": None, "trend_pct": None,
                "is_stale": True, "source": None, "markets": [], "min_price": None,
                "max_price": None, "history_low": None, "history_high": None,
                "long_history": long_history}

    latest_date = max(r.arrival_date for r in matches)
    latest = [r for r in matches if r.arrival_date == latest_date]
    values = [float(r.modal_price) for r in latest]
    age = days_old(latest_date)
    today = today_ist()
    by_date: dict[date, list[float]] = {}
    for r in matches:
        observed_age = (today - r.arrival_date).days
        if 0 <= observed_age <= 365:
            by_date.setdefault(r.arrival_date, []).append(float(r.modal_price))
    daily_medians = [(d, median(v)) for d, v in sorted(by_date.items())]
    recent_dates = daily_medians[-10:]
    trend = None
    if len(recent_dates) >= 2 and recent_dates[0][1] > 0:
        trend = round((recent_dates[-1][1] - recent_dates[0][1]) / recent_dates[0][1] * 100, 1)
    return {
        "price": round(median(values), 2), "date": latest_date.isoformat(), "age_days": age,
        "records": len(matches), "distinct_dates": len(by_date),
        "history_median": round(median(v for _, v in recent_dates), 2) if recent_dates else None,
        "trend_pct": trend, "is_stale": age is None or age > config.PLANNER_PRICE_MAX_AGE_DAYS,
        "source": latest[0].source, "markets": sorted({r.market for r in latest})[:8],
        "min_price": round(min(float(r.min_price) for r in latest), 2),
        "max_price": round(max(float(r.max_price) for r in latest), 2),
        "history_low": round(min(v for _, v in recent_dates), 2) if recent_dates else None,
        "history_high": round(max(v for _, v in recent_dates), 2) if recent_dates else None,
        "long_history": long_history,
    }


def _cost_for(candidate_costs: dict[str, float], crop_name: str, canonical: str) -> float | None:
    for key, value in candidate_costs.items():
        if canonical_crop(key) in {canonical, canonical_crop(crop_name)}:
            try:
                n = float(value)
                return n if 0 <= n <= 10_000_000 else None
            except (TypeError, ValueError):
                return None
    return None


def _water_fit(crop: str, water: str, season: str = "") -> tuple[bool, str]:
    need = WATER_NEED.get(crop, "unknown")
    season_key = normalise_season(season)
    if crop == "rice" and water in {"rainfed", "limited"} and season_key in {"kharif", "autumn", "", "whole year", "all seasons"}:
        # About half of India's rice area is rainfed lowland or upland rice, so do not exclude it.
        return True, "rainfed_rice_caution"
    if water == "rainfed" and need == "high":
        return False, "excluded_water_constraint"
    if water == "limited" and need == "high":
        return False, "high_water_need_caution"
    return True, "fit" if need in {"low", "low-medium"} and water in {"rainfed", "limited"} else "review_water_need"


def _rotation(current: str, candidate: str) -> str:
    a, b = ROTATION_GROUP.get(current), ROTATION_GROUP.get(candidate)
    if not a or not b:
        return "unknown"
    if a == b:
        return "same_group_as_current"
    if b == "legume" and a != "legume":
        return "legume_after_non_legume"
    return "different_group"


def _data_age(year_start: int | None) -> int | None:
    return None if year_start is None else max(0, today_ist().year - (year_start + 1))


def _yield_diagnosis(rows: list[CropProduction], crop: str, season: str,
                     actual_yield: float | None) -> dict:
    crop_rows = [r for r in rows if canonical_crop(r.crop) == canonical_crop(crop)]
    all_seasons = clean_name(season) in ALL_SEASONS
    if not all_seasons:
        crop_rows = [r for r in crop_rows if _season_matches(r.season, season)]
    observations = _aggregate_by_year(crop_rows, all_seasons)
    recent = observations[-5:]
    yields = [o["yield_t_ha"] for o in recent]
    baseline = median(yields) if yields else None
    gap = round((actual_yield / baseline - 1) * 100, 1) if actual_yield is not None and baseline else None
    return {"actual_yield_t_per_ha": actual_yield, "local_median_yield_t_per_ha": round(baseline, 3) if baseline is not None else None,
            "yield_observations": len(observations), "yield_gap_pct_vs_local_median": gap,
            "benchmark_years": [o["year_label"] for o in recent],
            "benchmark_data_age_years": _data_age(recent[-1]["year_start"]) if recent else None,
            "interpretation": ("no_farmer_yield" if actual_yield is None else
                               "below_local_benchmark" if gap is not None and gap < -15 else
                               "near_or_above_local_benchmark" if gap is not None else "insufficient_yield_data"),
            "note": "District-level yield is a comparison benchmark, not a farm-specific yield forecast."}


def recommend_crops(db: Session, data: dict) -> dict[str, Any]:
    state, district = data["state"].strip(), data["district"].strip()
    current_crop = data["current_crop"].strip()
    season = data["target_season"].strip()
    all_seasons = clean_name(season) in ALL_SEASONS
    crop_rows = _matching_rows(db, state, district)
    season_rows = crop_rows if all_seasons else [r for r in crop_rows if _season_matches(r.season, season)]
    if not crop_rows:
        return {"status": "data_missing", "state": state, "district": district, "target_season": season,
                "current_crop": current_crop, "candidates": [], "data_gaps": [
                    "No imported historical crop records match this state/district. Run python -m scripts.setup_crop_data and confirm spelling."],
                "data_gap_codes": [{"code": "district_missing", "params": {}}],
                "setup_command": "python -m scripts.setup_crop_data", "disclaimer": _disclaimer()}
    if not season_rows:
        return {"status": "season_data_missing", "state": state, "district": district, "target_season": season,
                "current_crop": current_crop, "candidates": [], "data_gaps": [
                    "The selected season has no matching history for this district. Try the exact season name shown by Crop Insights."],
                "data_gap_codes": [{"code": "season_missing", "params": {}}],
                "disclaimer": _disclaimer()}

    current_canonical = canonical_crop(current_crop)
    by_canonical: dict[str, list[CropProduction]] = {}
    display_name: dict[str, str] = {}
    for row in season_rows:
        canonical = canonical_crop(row.crop)
        if not canonical or canonical == current_canonical or unit_for(row.crop) == "nuts":
            continue
        by_canonical.setdefault(canonical, []).append(row)
        display_name.setdefault(canonical, row.crop)

    latest_year_all = max(r.year_start for r in crop_rows)
    data_age = _data_age(latest_year_all)
    candidate_costs = data.get("candidate_costs_rs_per_ha") or {}
    output = []
    excluded = []
    for canonical, rows in by_canonical.items():
        water_ok, water_flag = _water_fit(canonical, data.get("water_availability", "unknown"), season)
        name = display_name[canonical]
        if not water_ok:
            excluded.append({"crop": name, "canonical_crop": canonical, "reason_code": water_flag,
                             "reason": "High water requirement relative to selected water availability; verify local suitability before reconsidering."})
            continue
        observations = _aggregate_by_year(rows, all_seasons)
        if not observations:
            continue
        recent = observations[-5:]
        yields = [o["yield_t_ha"] for o in recent]
        y_median = round(median(yields), 3) if yields else None
        y_min, y_max = (round(min(yields), 3), round(max(yields), 3)) if yields else (None, None)
        y_cv = (round(pstdev(yields) / (sum(yields) / len(yields)) * 100, 1)
                if len(yields) >= 2 and sum(yields) > 0 else None)
        p = _price_stats(db, state, canonical, season)
        cost = _cost_for(candidate_costs, name, canonical)
        gaps = _Gaps()
        # A current quote is useful market context, but it is not a sound proxy for
        # next-season price. Use observed historical aggregates only when coverage is broad.
        price_usable = p["price"] is not None and (p["age_days"] is not None and p["age_days"] <= config.PLANNER_PRICE_MAX_AGE_DAYS)
        long_history = p.get("long_history") or {}
        long_count = int(long_history.get("observations") or 0)
        long_span = int(long_history.get("span_days") or 0)
        window = long_history.get("harvest_window") or {}
        if window.get("observations", 0) >= 12 and window.get("years", 0) >= 2 and window.get("median") is not None:
            reference_price, price_low, price_high = float(window["median"]), window["low"], window["high"]
            reference_basis = "historical_state_aggregate_median_harvest_months"
        elif long_count >= 12 and long_span >= 180 and long_history.get("median") is not None:
            reference_price, price_low, price_high = float(long_history["median"]), long_history["low"], long_history["high"]
            reference_basis = "historical_state_aggregate_median_all_dates_not_season_specific"
        else:
            reference_price = price_low = price_high = None
            reference_basis = None
        historical_price_ready = reference_price is not None
        enough_yield = len(yields) >= 2 and y_median is not None
        gross = round(y_median * 10 * reference_price, 2) if enough_yield and historical_price_ready else None
        net = round(gross - cost, 2) if gross is not None and cost is not None else None
        gross_low = round(y_min * 10 * float(price_low), 2) if gross is not None and price_low is not None else None
        gross_high = round(y_max * 10 * float(price_high), 2) if gross is not None and price_high is not None else None
        price_evidence = ("strong" if long_count >= 100 and long_span >= 730 else
                          "moderate" if long_count >= 30 and long_span >= 180 else
                          "limited" if long_count > 0 or (price_usable and p["distinct_dates"] >= 3) else
                          "unavailable_or_stale")
        yield_evidence = "strong" if len(yields) >= 5 else "moderate" if len(yields) >= 3 else "limited"
        soil = data.get("soil_type", "unknown")
        preferred = SOIL_PREFERENCES.get(canonical)
        soil_fit = "unknown" if soil in (None, "unknown") or not preferred else ("likely_match" if soil in preferred else "review_soil_fit")
        ph = data.get("soil_ph")
        ph_range = PH_PREFERENCES.get(canonical)
        if ph is None or ph_range is None:
            soil_ph_fit = "unknown"
        else:
            soil_ph_fit = "within_broad_range" if ph_range[0] <= float(ph) <= ph_range[1] else "outside_broad_range_review"
        rotation = _rotation(current_canonical, canonical)
        latest_obs = observations[-1]
        candidate_age = _data_age(latest_obs["year_start"])
        if candidate_age is not None and candidate_age > config.CROP_DATA_OLD_AFTER_YEARS:
            gaps.add("yield_data_old", f"The newest yield record for this crop is from {latest_obs['year_label']} ({candidate_age} years old).",
                     year=latest_obs["year_label"], age=candidate_age)
        if len(yields) < 3:
            gaps.add("few_yield_years", "Fewer than 3 recent local crop-yield observations.")
        if p["price"] is None:
            gaps.add("no_current_price", "No matching current mandi-price record exists in the database for this crop and state.")
        elif not price_usable:
            gaps.add("current_price_old", f"Latest matched market quote is older than {config.PLANNER_PRICE_MAX_AGE_DAYS} days; shown for context only and excluded from current-market comparison.",
                     days=config.PLANNER_PRICE_MAX_AGE_DAYS)
        elif p["distinct_dates"] < 3:
            gaps.add("few_price_dates", "Fewer than 3 distinct dated mandi prices are stored; short-term price evidence is limited.")
        if cost is None:
            gaps.add("enter_cost", "Enter a realistic candidate cultivation cost per hectare to calculate net returns.")
        if not long_count:
            gaps.add("no_price_history", f"No historical state-level price series is stored for {name}. Backfill it with: python -m scripts.fetch_mandi_history --state \"{state}\" --commodity \"{name}\" --years 5.",
                     crop=name, state=state)
        elif not historical_price_ready:
            gaps.add("short_price_history", "Historical price coverage has fewer than 12 observations or spans less than 180 days; no expected revenue/net return is calculated from the current quote alone.")
        elif reference_basis.endswith("harvest_months"):
            gaps.add("seasonal_price_used", "Expected price is the median of state-level history in this season's usual harvest months; check local buyers and grade before deciding.")
        else:
            gaps.add("all_year_price_used", "Historical prices are an all-date state-level aggregate, not a target-season-specific price model. Check seasonality and local buyer access before deciding.")
        if p["price"] is not None and price_usable and p["distinct_dates"] < 3:
            gaps.add("price_snapshot", "Current price is a snapshot, not a seasonal price forecast.")
        if soil_fit == "review_soil_fit":
            gaps.add("soil_review", "Recorded soil type does not match broad soil preferences in the advisor rules; confirm locally, do not treat as automatic exclusion.")
        if soil_ph_fit == "outside_broad_range_review":
            gaps.add("ph_review", f"Entered soil pH is outside the broad illustrative range {ph_range[0]}–{ph_range[1]}; confirm the soil test and crop suitability with local agricultural staff. This is not an automatic exclusion.",
                     low=ph_range[0], high=ph_range[1])
        if canonical not in WATER_NEED:
            gaps.add("water_need_unknown", "Water requirement profile not configured for this crop; verify with a local agronomist.")
        if water_flag == "rainfed_rice_caution":
            gaps.add("rainfed_rice", "Rice is widely grown rainfed in Kharif, but yields depend heavily on monsoon rain and field bunds; check local varieties and sowing window.")
        if rotation == "same_group_as_current":
            gaps.add("same_rotation_group", "Same crop family as your current crop; rotating to a different family usually breaks pest and disease cycles.")
        if canonical == "rice":
            gaps.add("rice_paddy_units", "Crop statistics record milled rice, while many mandis quote paddy; compare like with like before estimating income.")
        output.append({
            "crop": name, "canonical_crop": canonical, "water_need": WATER_NEED.get(canonical, "unknown"),
            "water_fit": water_flag, "soil_fit": soil_fit, "preferred_soils_general": sorted(preferred) if preferred else [],
            "rotation": rotation,
            "historical_yield_t_per_ha_median": y_median, "historical_yield_t_per_ha_range": [y_min, y_max],
            "yield_observations": len(yields), "yield_cv_pct": y_cv,
            "yield_years": [o["year_label"] for o in recent],
            "yield_data_age_years": candidate_age,
            "latest_area_ha": round(latest_obs["area_ha"], 2), "latest_year": latest_obs["year_label"],
            "yield_evidence": yield_evidence,
            "soil_ph": float(ph) if ph is not None else None,
            "broad_soil_ph_range": list(ph_range) if ph_range else None,
            "soil_ph_fit": soil_ph_fit,
            "latest_mandi_price_rs_per_qtl": p["price"] if price_usable else None,
            "mandi_price_date": p["date"], "mandi_price_age_days": p["age_days"], "mandi_source": p["source"],
            "matched_markets": p["markets"], "price_observations": p["records"], "price_distinct_dates": p["distinct_dates"],
            "price_trend_pct": p["trend_pct"], "price_evidence": price_evidence,
            "historical_price_observations": long_count,
            "historical_price_span_days": long_span,
            "historical_price_first_date": long_history.get("first_date"),
            "historical_price_last_date": long_history.get("last_date"),
            "historical_price_median_rs_per_qtl": long_history.get("median"),
            "historical_price_range_rs_per_qtl": [long_history.get("low"), long_history.get("high")] if long_history.get("low") is not None else None,
            "historical_price_trend_pct": long_history.get("trend_pct"),
            "historical_price_source": long_history.get("source"),
            "harvest_month_price": window or None,
            "historical_price_sufficient_for_estimate": historical_price_ready,
            "reference_price_for_estimate_rs_per_qtl": reference_price,
            "reference_price_basis": reference_basis,
            "estimated_gross_revenue_rs_per_ha": gross,
            "observed_envelope_gross_revenue_rs_per_ha": {"low": gross_low, "high": gross_high} if gross_low is not None and gross_high is not None else None,
            "user_entered_cost_rs_per_ha": cost, "estimated_net_return_rs_per_ha": net,
            "estimated_net_return_for_area_rs": round(net * float(data["area_ha"]), 2) if net is not None else None,
            "calculation_code": "net_from_history" if net is not None else "net_unavailable",
            "calculation_basis": "local median yield × 10 quintals/tonne × historical state-level aggregate price median, minus user-entered cost; not a forecast" if net is not None else "net return unavailable until sufficiently broad historical price, local yield and user-entered candidate cost data are available",
            "data_gaps": gaps.text,
            "data_gap_codes": gaps.codes,
        })

    # Rank by net-return estimates only if at least two candidates have one. Otherwise list
    # crops by how much land they recently covered in this district: a description, not advice.
    comparable_net_count = sum(c["estimated_net_return_rs_per_ha"] is not None for c in output)
    if comparable_net_count >= 2:
        output.sort(key=lambda c: (c["estimated_net_return_rs_per_ha"] is not None,
                                  c["estimated_net_return_rs_per_ha"] if c["estimated_net_return_rs_per_ha"] is not None else -1e18,
                                  c["yield_observations"]), reverse=True)
        rank_basis = "net_return_estimate_using_user_entered_costs_for_at_least_two_candidates"
        ranked = True
    else:
        output.sort(key=lambda c: (c["latest_year"], c["latest_area_ha"]), reverse=True)
        rank_basis = "recent_area_in_district_not_a_recommendation"
        ranked = False

    current_diag = _yield_diagnosis(crop_rows, current_crop, data.get("current_season") or season, data.get("actual_yield_t_per_ha"))
    current_gross = None
    current_net = None
    actual_yield = data.get("actual_yield_t_per_ha")
    current_sale_price = data.get("actual_sale_price_rs_per_qtl")
    current_cost = data.get("current_cost_rs_per_ha")
    if actual_yield is not None and current_sale_price is not None:
        current_gross = round(float(actual_yield) * 10 * float(current_sale_price), 2)
        if current_cost is not None:
            current_net = round(current_gross - float(current_cost), 2)
    break_even = (round(float(current_cost) / (float(actual_yield) * 10), 2)
                  if current_cost is not None and actual_yield is not None and float(actual_yield) > 0 else None)
    current_diag["actual_season_economics"] = {"gross_revenue_rs_per_ha": current_gross, "net_return_rs_per_ha": current_net,
                                               "break_even_price_rs_per_qtl": break_even,
                                               "cost_input_available": current_cost is not None}
    tips = ISSUE_TIPS.get(data.get("primary_issue", "unknown"), ISSUE_TIPS["unknown"])
    gaps = _Gaps()
    if data_age is not None and data_age > config.CROP_DATA_OLD_AFTER_YEARS:
        gaps.add("crop_data_old", f"The district crop records end in {latest_year_all}-{str(latest_year_all + 1)[-2:]}, about {data_age} years ago. Treat yields as a historical pattern.",
                 year=f"{latest_year_all}-{str(latest_year_all + 1)[-2:]}", age=data_age)
    if not output:
        gaps.add("no_alternatives", "No alternative crops remain after the district/season and water-availability filters.")
    if not any(c["latest_mandi_price_rs_per_qtl"] is not None for c in output):
        gaps.add("no_fresh_price", "No fresh matched price is available for the candidate crops. Import/check the mandi feed; no revenue estimate can be made.")
    if not any(c["historical_price_observations"] > 0 for c in output):
        gaps.add("no_history_any", "No historical price series has been backfilled for candidate crops. A current quote cannot establish seasonal profitability; use scripts.fetch_mandi_history for each key candidate.")
    if not any(c["estimated_net_return_rs_per_ha"] is not None for c in output):
        gaps.add("no_net_return", "Net profitability has not been established: fresh prices, yield evidence and farmer-entered candidate costs are required.")
    if current_diag["yield_observations"] < 3:
        gaps.add("current_few_years", "The current crop has fewer than 3 observations for a robust local yield comparison.")
    confidence = "exploratory"
    if output and ranked and all(c["yield_observations"] >= 5 and c["price_evidence"] == "strong" and c["user_entered_cost_rs_per_ha"] is not None for c in output[:3]):
        confidence = "better_data_coverage_but_not_a_guarantee"
    return {
        "status": "ok" if output else "no_candidates", "state": state, "district": district,
        "current_crop": current_crop, "target_season": season, "area_ha": data["area_ha"],
        "crop_data_latest_year": latest_year_all, "crop_data_age_years": data_age,
        "current_crop_assessment": current_diag, "productivity_actions": tips,
        "candidate_count": len(output), "candidates": output[:10], "excluded_candidates": excluded,
        "ranked": ranked, "rank_basis": rank_basis, "recommendation_confidence": confidence,
        "data_gaps": gaps.text, "data_gap_codes": gaps.codes,
        "source": {"production": "Historical crop production CSV; community-cleaned mirror under CC0-1.0", "price": "KisanSaathi stored mandi observations; provider attribution/date is shown per candidate", "historical_price": "Mandi Price API state-level aggregate history; not an individual market quote", "yield_units": "tonnes per hectare", "price_units": "Indian rupees per quintal"},
        "disclaimer": _disclaimer(),
    }


def _disclaimer() -> str:
    return ("Decision-support prototype, not a guaranteed crop or profit forecast. Regional yields are benchmarks; current mandi quotes may not match farm-gate prices; "
            "revenue estimates exclude costs unless you enter them. Historical price observations may not cover a full season. Confirm seed/variety, sowing window, soil, water, pest risk, buyer/procurement access and local recommendations with KVK/agriculture officials before switching crops.")
