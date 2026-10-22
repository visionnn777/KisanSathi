"""Import and query-ready normalization for the openly licensed Indian crop-history CSV.

The upstream file is a community-cleaned mirror derived from Government of India crop
statistics, released under CC0-1.0 by its repository. It is historical, not a live feed.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterator

from sqlalchemy.orm import Session

from ..models import CropProduction
from .crop_catalog import canonical_crop, to_tonnes, unit_for

SOURCE_LABEL = "k0rn/India_Agri_Data (CC0-1.0; historical mirror)"
SOURCE_URL = "https://github.com/k0rn/India_Agri_Data"
RAW_URL = "https://raw.githubusercontent.com/k0rn/India_Agri_Data/master/agridata.csv"
LICENSE = "CC0-1.0"

ALIASES = {
    "state": {"state", "state_name", "statename", "states"},
    "district": {"district", "district_name", "districtname"},
    "crop": {"crop", "crop_name", "cropname", "commodity"},
    "year": {"year", "crop_year", "cropyear", "year_of_production", "agri_year"},
    "season": {"season", "crop_season", "cropseason"},
    "area": {"area", "area_ha", "area_in_hectare", "area_hectares", "cultivated_area"},
    "production": {"production", "production_tonnes", "production_tons", "output", "crop_production",
                   "production_tonne", "production_in_tonnes"},
    # Optional unit columns, present in the India Data Portal / DES district APY export.
    "production_unit": {"production_unit", "production_units", "unit_of_production"},
    "area_unit": {"area_unit", "area_units", "unit_of_area"},
}
HECTARE_UNITS = {"hectare", "hectares", "ha", "hect", "hectare ha"}


def key_name(value: str) -> str:
    value = (value or "").replace("\ufeff", "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def _column_map(fieldnames: list[str] | None) -> dict[str, str]:
    if not fieldnames:
        raise ValueError("CSV is empty or has no header row.")
    normalized = {key_name(name): name for name in fieldnames if name}
    found: dict[str, str] = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                found[target] = normalized[alias]
                break
    required = {"state", "district", "crop", "year", "area", "production"}
    missing = required - found.keys()
    if missing:
        raise ValueError(
            "Unsupported crop CSV schema; missing columns for: " + ", ".join(sorted(missing))
            + ". Expected state, district, crop, year, area and production columns."
        )
    return found


def _number(value) -> float | None:
    if value is None:
        return None
    raw = str(value).strip().replace(",", "")
    if not raw or raw.lower() in {"na", "n/a", "null", "none", "nan", "-"}:
        return None
    try:
        result = float(raw)
    except (TypeError, ValueError):
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _year(value) -> tuple[str, int] | None:
    text = str(value or "").strip()
    match = re.search(r"(?<!\d)((?:19|20)\d{2})(?:\s*[-/]\s*(?:\d{2}|(?:19|20)\d{2}))?", text)
    if not match:
        return None
    start = int(match.group(1))
    # Preserve the upstream label; normalize a bare year without making one up.
    label = re.sub(r"\s+", "", text) if text else str(start)
    return label, start


def validate_csv(path: Path) -> dict[str, str]:
    if not path.exists() or path.stat().st_size == 0:
        raise ValueError(f"Crop dataset file does not exist or is empty: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return _column_map(reader.fieldnames)


def iter_crop_rows(path: Path, stats: dict | None = None) -> Iterator[dict]:
    """Yield normalized observations with production converted to tonnes.

    If the file has a production-unit column (DES / India Data Portal APY export), that unit is
    used. Otherwise the usual unit for each crop in Indian statistics is applied: cotton in
    bales of 170 kg, jute/mesta/sunn hemp in bales of 180 kg, coconut in nuts (kept as nuts and
    never turned into a tonne yield).
    """
    stats = stats if stats is not None else {}
    stats.setdefault("converted_bales", 0)
    stats.setdefault("kept_as_nuts", 0)
    stats.setdefault("skipped_unknown_unit", 0)
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = _column_map(reader.fieldnames)
        unit_col = columns.get("production_unit")
        area_unit_col = columns.get("area_unit")
        for raw in reader:
            state = str(raw.get(columns["state"]) or "").strip()
            district = str(raw.get(columns["district"]) or "").strip()
            crop = str(raw.get(columns["crop"]) or "").strip()
            year = _year(raw.get(columns["year"]))
            area = _number(raw.get(columns["area"]))
            production = _number(raw.get(columns["production"]))
            season_col = columns.get("season")
            season = str(raw.get(season_col) or "Unknown").strip() if season_col else "Unknown"
            if not state or not district or not crop or not year:
                continue
            if area is None or production is None or area <= 0 or production < 0:
                continue
            if area_unit_col:
                area_unit = str(raw.get(area_unit_col) or "").strip().lower()
                if area_unit and area_unit not in HECTARE_UNITS:
                    stats["skipped_unknown_unit"] += 1
                    continue
            declared_unit = str(raw.get(unit_col) or "").strip() if unit_col else None
            tonnes = to_tonnes(crop, production, declared_unit or None)
            if tonnes is None:
                looks_like_nuts = ("nut" in (declared_unit or "").lower()) or (
                    not declared_unit and unit_for(crop) == "nuts")
                if not looks_like_nuts:
                    stats["skipped_unknown_unit"] += 1
                    continue
                stats["kept_as_nuts"] += 1
                stored, unit = production, "nuts"
            else:
                if (declared_unit and "bale" in declared_unit.lower()) or (
                        not declared_unit and unit_for(crop).startswith("bales")):
                    stats["converted_bales"] += 1
                stored, unit = tonnes, "tonnes"
            year_label, year_start = year
            yield {
                "state": " ".join(state.split()),
                "district": " ".join(district.split()),
                "crop": crop,
                "year_label": year_label,
                "year_start": year_start,
                "season": " ".join((season or "Unknown").split()),
                "area_ha": area,
                "production_tonnes": stored,
                "production_unit": unit,
                "source": SOURCE_LABEL,
            }


def import_crop_csv(db: Session, path: Path, batch_size: int = 2000) -> dict:
    """Replace imported history transactionally; a failed import preserves prior data."""
    validate_csv(path)
    seen: set[tuple] = set()
    batch: list[dict] = []
    imported = 0
    skipped_duplicates = 0
    stats: dict = {}
    try:
        db.query(CropProduction).delete(synchronize_session=False)
        db.flush()
        for row in iter_crop_rows(path, stats):
            key = (row["state"], row["district"], row["crop"], row["year_label"], row["season"])
            if key in seen:
                skipped_duplicates += 1
                continue
            seen.add(key)
            batch.append(row)
            if len(batch) >= batch_size:
                db.bulk_insert_mappings(CropProduction, batch)
                imported += len(batch)
                batch.clear()
        if batch:
            db.bulk_insert_mappings(CropProduction, batch)
            imported += len(batch)
        if imported == 0:
            raise ValueError("No valid crop-history rows were found in the CSV.")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"imported": imported, "duplicates_skipped": skipped_duplicates, "source": SOURCE_LABEL, **stats}
