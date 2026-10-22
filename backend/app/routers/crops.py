"""Historical crop-production insights for a selected Indian district and season."""
from collections import defaultdict
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models import CropProduction
from ..services.crop_catalog import canonical_crop, plausible_yield, row_tonnes, unit_for
from ..services.crop_history import LICENSE, RAW_URL, SOURCE_LABEL, SOURCE_URL
from ..timeutil import today_ist


def _data_age(latest_year_start: int | None) -> dict:
    """How old the newest record is. An agricultural year 2012-13 ends in mid-2013."""
    if latest_year_start is None:
        return {"data_age_years": None, "is_old": False}
    age = max(0, today_ist().year - (latest_year_start + 1))
    return {"data_age_years": age, "is_old": age > config.CROP_DATA_OLD_AFTER_YEARS,
            "old_after_years": config.CROP_DATA_OLD_AFTER_YEARS}

router = APIRouter(prefix="/api/crops", tags=["crop history"])

_AGGREGATE_SEASONS = {"all season", "all seasons", "whole year", "whole-year", "annual", "all year"}


def _annual_observations(observations: list[CropProduction]) -> list[dict]:
    """Create one value per crop/year for the All seasons view.

    If the source has a pre-aggregated annual row, prefer it to avoid double counting.
    Otherwise combine the distinct season rows for that crop/year.
    """
    by_year: dict[tuple[int, str], list[CropProduction]] = defaultdict(list)
    for row in observations:
        by_year[(row.year_start, row.year_label)].append(row)

    annual = []
    for (year_start, year_label), year_rows in sorted(by_year.items()):
        aggregate_rows = [
            row for row in year_rows
            if " ".join(str(row.season).strip().lower().replace("-", " ").split()) in _AGGREGATE_SEASONS
        ]
        if aggregate_rows:
            # Stable preference when multiple annual synonyms appear.
            aggregate_rows.sort(key=lambda row: (
                0 if "all season" in row.season.strip().lower() else
                1 if "whole" in row.season.strip().lower() else 2,
                row.season,
            ))
            selected = aggregate_rows[:1]
        else:
            selected = year_rows
        tonnes = [row_tonnes(row) for row in selected]
        if any(value is None for value in tonnes):
            continue  # coconut counted in nuts: no tonne figure to add up
        area = sum(float(row.area_ha) for row in selected)
        production = sum(tonnes)
        annual.append({
            "year_start": year_start,
            "year_label": year_label,
            "season": selected[0].season if len(selected) == 1 else "All seasons (combined)",
            "area_ha": area,
            "production_tonnes": production,
        })
    return annual


@router.get("/status")
def crop_data_status(db: Session = Depends(get_db)):
    count = db.query(func.count(CropProduction.id)).scalar() or 0
    earliest = db.query(func.min(CropProduction.year_start)).scalar()
    latest = db.query(func.max(CropProduction.year_start)).scalar()
    state_count = db.query(func.count(func.distinct(CropProduction.state))).scalar() or 0
    legacy_rows = db.query(func.count(CropProduction.id)).filter(CropProduction.production_unit.is_(None)).scalar() or 0
    return {
        **_data_age(latest),
        "needs_reimport": legacy_rows > 0,
        "available": count > 0,
        "rows": count,
        "states": state_count,
        "first_year": earliest,
        "latest_year": latest,
        "source": SOURCE_LABEL,
        "source_url": SOURCE_URL,
        "download_url": RAW_URL,
        "license": LICENSE,
        "data_type": "historical",
        "disclaimer": "Historical crop statistics describe past cultivation and output; they are not a standalone planting recommendation or a yield forecast.",
        "setup_command": "python -m scripts.setup_crop_data",
    }


@router.get("/states")
def crop_states(db: Session = Depends(get_db)):
    return [value for (value,) in db.query(CropProduction.state).distinct().order_by(CropProduction.state).all()]


@router.get("/districts")
def crop_districts(state: str = Query(min_length=1), db: Session = Depends(get_db)):
    return [value for (value,) in db.query(CropProduction.district)
            .filter(CropProduction.state == state).distinct().order_by(CropProduction.district).all()]


@router.get("/seasons")
def crop_seasons(state: str = Query(min_length=1), district: str = Query(min_length=1),
                 db: Session = Depends(get_db)):
    return [value for (value,) in db.query(CropProduction.season)
            .filter(CropProduction.state == state, CropProduction.district == district)
            .distinct().order_by(CropProduction.season).all()]


@router.get("/history")
def crop_history(
    state: str = Query(min_length=1),
    district: str = Query(min_length=1),
    season: str | None = Query(default=None),
    limit: int = Query(default=15, ge=1, le=40),
    db: Session = Depends(get_db),
):
    query = db.query(CropProduction).filter(
        CropProduction.state == state,
        CropProduction.district == district,
    )
    if season:
        query = query.filter(CropProduction.season == season)
    rows = query.order_by(CropProduction.year_start.asc()).all()
    if not rows:
        return {"state": state, "district": district, "season": season, "count": 0,
                "first_year": None, "latest_year": None, "crops": [],
                "source": SOURCE_LABEL, "historical_only": True}

    by_crop: dict[str, list[CropProduction]] = defaultdict(list)
    for row in rows:
        by_crop[row.crop].append(row)

    summaries = []
    year_bounds = []
    skipped_units: list[str] = []
    for crop, crop_rows in by_crop.items():
        if unit_for(crop) == "nuts":
            skipped_units.append(crop)
            continue
        if season:
            observations = [{
                "year_start": item.year_start, "year_label": item.year_label,
                "season": item.season, "area_ha": float(item.area_ha),
                "production_tonnes": row_tonnes(item),
            } for item in crop_rows if row_tonnes(item) is not None]
            # De-duplicate safely if malformed external data has duplicate records after import.
            annual_map = {(item["year_start"], item["year_label"]): item for item in observations}
            observations = list(annual_map.values())
        else:
            observations = _annual_observations(crop_rows)
        observations.sort(key=lambda item: (item["year_start"], item["year_label"]))
        if not observations:
            continue
        # Years whose yield is physically impossible for this crop are data errors: leave them out.
        clean = [item for item in observations if item["area_ha"] > 0
                 and plausible_yield(crop, item["production_tonnes"] / item["area_ha"])]
        excluded = len(observations) - len(clean)
        observations = clean
        if not observations:
            continue
        latest = observations[-1]
        recent = observations[-5:]
        yields = [item["production_tonnes"] / item["area_ha"] for item in recent]
        oldest = observations[0]
        year_bounds.extend(observations)
        growth_pct = None
        if len(observations) > 1 and oldest["production_tonnes"] > 0:
            growth_pct = round((latest["production_tonnes"] - oldest["production_tonnes"])
                               / oldest["production_tonnes"] * 100, 1)
        summaries.append({
            "crop": crop,
            "latest_year": latest["year_label"],
            "latest_year_start": latest["year_start"],
            "latest_season": latest["season"],
            "latest_area_ha": round(latest["area_ha"], 2),
            "latest_production_tonnes": round(latest["production_tonnes"], 2),
            "latest_yield_tonnes_per_ha": round(latest["production_tonnes"] / latest["area_ha"], 3)
                if latest["area_ha"] > 0 else None,
            "average_recent_yield_tonnes_per_ha": round(mean(yields), 3) if yields else None,
            "observations": len(observations),
            "implausible_years_excluded": excluded,
            "production_unit_note": "converted_from_bales" if unit_for(crop).startswith("bales") else None,
            "canonical_crop": canonical_crop(crop),
            "first_year": oldest["year_label"],
            "production_change_pct_since_first_record": growth_pct,
        })

    if not summaries:
        return {"state": state, "district": district, "season": season, "count": 0,
                "first_year": None, "latest_year": None, "crops": [], "crops_without_tonnes": skipped_units,
                "source": SOURCE_LABEL, "historical_only": True}
    # Sort by latest reported cultivated area, a historical pattern indicator—not suitability.
    summaries.sort(key=lambda item: (item["latest_year_start"], item["latest_area_ha"]), reverse=True)
    first_year = min(year_bounds, key=lambda item: item["year_start"])
    latest_year = max(year_bounds, key=lambda item: item["year_start"])
    return {
        **_data_age(latest_year["year_start"]),
        "crops_without_tonnes": skipped_units,
        "state": state,
        "district": district,
        "season": season,
        "count": len(summaries),
        "first_year": first_year["year_label"],
        "latest_year": latest_year["year_label"],
        "crops": summaries[:limit],
        "source": SOURCE_LABEL,
        "source_url": SOURCE_URL,
        "license": LICENSE,
        "historical_only": True,
        "disclaimer": "Rankings reflect the latest available recorded area in this dataset. They do not account for today's soil condition, water availability, input cost, market demand or weather, and should not be treated as a planting recommendation.",
    }
