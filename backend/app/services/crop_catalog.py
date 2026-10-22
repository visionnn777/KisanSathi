"""One shared list of crop names, units and sanity limits.

Why this exists
- Different sources spell crops differently: "Rapeseed &Mustard", "Mustard", "Bengal Gram(Gram)(Whole)".
  Names are matched exactly against known aliases (never by loose substring), so
  "Sweet potato" is not "potato" and "Black Gram (Urd)" is not chickpea.
- Indian crop statistics do not use tonnes for every crop: cotton is counted in bales of
  170 kg of lint, jute/mesta/sunn hemp in bales of 180 kg, and coconut in nuts. Dividing
  bales by hectares and calling it tonnes gives impossible yields, so production is
  converted here and coconut is excluded from tonne-based yields.
- Any yield above a generous per-crop upper limit is treated as a data error and left out
  of medians instead of silently distorting them.
"""
from __future__ import annotations

import re

COTTON_BALE_KG = 170
FIBRE_BALE_KG = 180

# canonical name -> aliases (all lower-case, punctuation removed)
ALIASES: dict[str, set[str]] = {
    "rice": {"rice", "paddy", "dhan", "paddy dhan", "rice paddy", "paddy dhan common", "paddy dhan basmati", "basmati rice"},
    "wheat": {"wheat", "gehun", "gehu"},
    "maize": {"maize", "corn", "makka", "maize grain"},
    "barley": {"barley", "jau", "barley jau"},
    "pearl millet": {"pearl millet", "bajra", "bajra pearl millet cumbu", "cumbu"},
    "sorghum": {"sorghum", "jowar", "jowar sorghum"},
    "finger millet": {"finger millet", "ragi", "ragi finger millet"},
    "small millets": {"small millets"},
    "chickpea": {"chickpea", "chick pea", "gram", "bengal gram", "chana", "kabuli chana", "bengal gram gram whole"},
    "pigeon pea": {"pigeon pea", "arhar", "tur", "red gram", "arhar tur", "tur red gram"},
    "green gram": {"green gram", "moong", "mung", "moong green gram"},
    "black gram": {"black gram", "urad", "urd", "urd beans"},
    "lentil": {"lentil", "masoor", "masur"},
    "horse gram": {"horse gram", "horsegram", "kulthi", "kulthi horse gram"},
    "moth bean": {"moth", "moth bean", "math"},
    "khesari": {"khesari", "kesari", "lathyrus"},
    "peas and beans": {"peas beans pulses", "peas and beans", "peas beans"},
    "other kharif pulses": {"other kharif pulses"},
    "other rabi pulses": {"other rabi pulses"},
    "mustard": {"mustard", "rapeseed", "rapeseed mustard", "sarson", "rapeseed and mustard"},
    "soybean": {"soybean", "soyabean", "soya bean"},
    "groundnut": {"groundnut", "peanut", "mungfali", "groundnut pods", "groundnut pods raw"},
    "sesame": {"sesame", "sesamum", "til", "gingelly", "sesamum sesame gingelly til"},
    "linseed": {"linseed", "alsi"},
    "castor": {"castor", "castor seed", "castorseed"},
    "sunflower": {"sunflower", "sunflower seed"},
    "safflower": {"safflower"},
    "niger": {"niger", "niger seed", "nigerseed"},
    "cotton": {"cotton", "kapas", "cotton lint"},
    "jute": {"jute"},
    "mesta": {"mesta"},
    "sunn hemp": {"sunn hemp", "sannhamp", "sanhamp"},
    "sugarcane": {"sugarcane", "sugar cane", "ganna"},
    "potato": {"potato", "aloo"},
    "sweet potato": {"sweet potato", "shakarkand"},
    "tapioca": {"tapioca", "cassava"},
    "onion": {"onion", "pyaz"},
    "garlic": {"garlic", "lahsun"},
    "ginger": {"ginger", "dry ginger", "ginger dry", "ginger green"},
    "turmeric": {"turmeric", "haldi"},
    "coriander": {"coriander", "coriander seed", "dhaniya"},
    "dry chillies": {"dry chillies", "dry chilli", "red chilli", "chilli dry"},
    "green chilli": {"green chilli", "green chili", "chilli green"},
    "black pepper": {"black pepper", "pepper"},
    "cardamom": {"cardamom", "cardamoms", "elaichi"},
    "arecanut": {"arecanut", "areca nut", "betelnut", "supari"},
    "cashewnut": {"cashewnut", "cashew", "cashewnuts", "cashew nut"},
    "coconut": {"coconut"},
    "banana": {"banana", "kela", "banana green"},
    "tobacco": {"tobacco"},
    "guar": {"guar", "guar seed", "guar seed cluster beans seed"},
    "tomato": {"tomato", "tamatar"},
    "brinjal": {"brinjal", "eggplant", "baingan"},
    "cauliflower": {"cauliflower", "phool gobhi"},
    "cabbage": {"cabbage", "patta gobhi"},
}

_INDEX = {alias: canonical for canonical, aliases in ALIASES.items() for alias in aliases | {canonical}}

# Production unit used by Indian crop statistics when it is not tonnes.
PRODUCTION_UNIT = {"cotton": "bales170", "jute": "bales180", "mesta": "bales180", "sunn hemp": "bales180", "coconut": "nuts"}

# Generous upper limits for district yields in tonnes per hectare (after unit conversion).
# Values above these are data-entry errors in practice and are excluded from medians.
MAX_YIELD_T_HA = {
    "rice": 10, "wheat": 8, "maize": 12, "barley": 6, "pearl millet": 5, "sorghum": 6,
    "finger millet": 6, "small millets": 4, "chickpea": 4, "pigeon pea": 4, "green gram": 3,
    "black gram": 3, "lentil": 3, "horse gram": 3, "moth bean": 3, "khesari": 3,
    "peas and beans": 6, "other kharif pulses": 4, "other rabi pulses": 4, "mustard": 4,
    "soybean": 5, "groundnut": 6, "sesame": 2.5, "linseed": 3, "castor": 5, "sunflower": 4,
    "safflower": 3, "niger": 2, "cotton": 3, "jute": 5, "mesta": 5, "sunn hemp": 5,
    "sugarcane": 200, "potato": 50, "sweet potato": 40, "tapioca": 70, "onion": 60, "garlic": 25,
    "ginger": 40, "turmeric": 40, "coriander": 4, "dry chillies": 8, "black pepper": 4,
    "cardamom": 2, "arecanut": 8, "cashewnut": 4, "banana": 100, "tobacco": 6, "guar": 4,
}
DEFAULT_MAX_YIELD_T_HA = 100.0


def clean_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def canonical_crop(value: str) -> str:
    """Map any spelling to one canonical crop name, using exact alias matches only."""
    text = str(value or "")
    full = clean_name(text)
    if full in _INDEX:
        return _INDEX[full]
    base = clean_name(text.split("(")[0])
    if base in _INDEX:
        return _INDEX[base]
    for inside in re.findall(r"\(([^)]*)\)", text):
        for part in re.split(r"[/,]", inside):
            key = clean_name(part)
            if key in _INDEX and key not in {"whole", "raw", "common"}:
                return _INDEX[key]
    return full


def unit_for(crop: str) -> str:
    return PRODUCTION_UNIT.get(canonical_crop(crop), "tonnes")


def to_tonnes(crop: str, value: float | None, unit: str | None = None) -> float | None:
    """Convert a production figure to tonnes. Returns None when no tonne value exists (coconut nuts).

    unit=None means the source did not say; the usual unit for that crop in Indian statistics is used.
    """
    if value is None:
        return None
    declared = (unit or "").strip().lower()
    if declared in {"tonnes", "tonne", "tons", "ton", "t", "metric tonnes"}:
        return float(value)
    kind = unit_for(crop) if not declared else (
        "bales170" if "bale" in declared and canonical_crop(crop) == "cotton" else
        "bales180" if "bale" in declared else
        "nuts" if "nut" in declared else
        "unknown")
    if kind == "bales170":
        return float(value) * COTTON_BALE_KG / 1000
    if kind == "bales180":
        return float(value) * FIBRE_BALE_KG / 1000
    if kind in {"nuts", "unknown"}:
        return None
    return float(value)


def row_tonnes(row) -> float | None:
    """Production in tonnes for a stored CropProduction row.

    Rows imported by this version carry production_unit ("tonnes" or "nuts").
    Rows from an older import (unit missing) get the usual unit for their crop.
    """
    unit = getattr(row, "production_unit", None)
    value = float(row.production_tonnes) if row.production_tonnes is not None else None
    if unit == "tonnes":
        return value
    if unit == "nuts":
        return None
    return to_tonnes(row.crop, value)


def plausible_yield(crop: str, tonnes_per_ha: float | None) -> bool:
    if tonnes_per_ha is None or tonnes_per_ha < 0:
        return False
    return tonnes_per_ha <= MAX_YIELD_T_HA.get(canonical_crop(crop), DEFAULT_MAX_YIELD_T_HA)
