"""Local-yield analysis, crop-switch comparisons and farmer-entered harvest records.

Ownership of harvest records: the server issues a long random "farm record key"
(POST /api/planning/farm-ref). Only its SHA-256 hash is stored next to the records, the key
is always sent in a POST body (never in a URL), and the browser keeps it and shows it as a
backup code. Anyone without the key cannot read the records. This is a bearer-key scheme,
not a full user account: whoever has the key has access.
"""
import hashlib
import secrets
from datetime import datetime, timezone
from math import isfinite
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import FarmReference, FarmSeasonRecord
from ..services import rate_limit
from ..services.crop_advisor import ISSUE_TIPS, recommend_crops
from ..timeutil import today_ist

FARM_REF_MIN = 22


def ref_hash(farm_ref: str) -> str:
    return hashlib.sha256(farm_ref.strip().encode("utf-8")).hexdigest()


def _owned(query, farm_ref: str):
    """Records saved under this key (hashed), plus records saved by older versions under the raw key."""
    return query.filter(or_(FarmSeasonRecord.farm_ref == ref_hash(farm_ref), FarmSeasonRecord.farm_ref == farm_ref))


def _same_text(column, value: str):
    return func.lower(column) == value.strip().lower()

router = APIRouter(prefix="/api/planning", tags=["crop productivity and next-season planning"])

Issue = Literal["low_price", "low_yield", "high_cost", "water_stress", "disease_pest", "weather", "multiple", "unknown"]


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False, extra="forbid")
    farm_ref: str = Field(min_length=FARM_REF_MIN, max_length=80)
    state: str = Field(min_length=2, max_length=100)
    district: str = Field(min_length=2, max_length=120)
    current_crop: str = Field(min_length=2, max_length=120)
    current_season: str = Field(default="", max_length=60)
    target_season: str = Field(min_length=2, max_length=60)
    area_ha: float = Field(gt=0, le=10_000)
    actual_yield_t_per_ha: float | None = Field(default=None, ge=0, le=200)
    actual_sale_price_rs_per_qtl: float | None = Field(default=None, ge=0, le=1_000_000)
    current_cost_rs_per_ha: float | None = Field(default=None, ge=0, le=10_000_000)
    candidate_costs_rs_per_ha: dict[str, float] = Field(default_factory=dict)
    primary_issue: Issue = "unknown"
    water_availability: Literal["rainfed", "limited", "assured", "unknown"] = "unknown"
    soil_type: Literal["sandy", "loamy", "clayey", "alluvial", "black", "red", "unknown"] = "unknown"
    soil_ph: float | None = Field(default=None, ge=3.0, le=10.0)
    notes: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_candidate_costs(self):
        if len(self.candidate_costs_rs_per_ha) > 30:
            raise ValueError("Provide costs for at most 30 candidate crops per request.")
        for crop, amount in self.candidate_costs_rs_per_ha.items():
            if not crop.strip() or not isfinite(float(amount)) or not 0 <= amount <= 10_000_000:
                raise ValueError("Candidate crop costs must be finite values between 0 and 10,000,000 ₹/ha.")
        return self


class SeasonRecordCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False, extra="forbid")
    farm_ref: str = Field(min_length=FARM_REF_MIN, max_length=80)
    state: str = Field(min_length=2, max_length=100)
    district: str = Field(min_length=2, max_length=120)
    crop: str = Field(min_length=2, max_length=120)
    season: str = Field(min_length=2, max_length=60)
    year_start: int = Field(ge=1990, le=2100)
    area_ha: float = Field(gt=0, le=10_000)
    harvested_tonnes: float | None = Field(default=None, ge=0, le=1_000_000)
    yield_t_per_ha: float | None = Field(default=None, ge=0, le=200)
    sale_price_rs_per_qtl: float | None = Field(default=None, ge=0, le=1_000_000)
    cultivation_cost_rs_per_ha: float | None = Field(default=None, ge=0, le=10_000_000)
    seed_cost_rs_per_ha: float | None = Field(default=None, ge=0, le=10_000_000)
    fertiliser_cost_rs_per_ha: float | None = Field(default=None, ge=0, le=10_000_000)
    crop_protection_cost_rs_per_ha: float | None = Field(default=None, ge=0, le=10_000_000)
    labour_cost_rs_per_ha: float | None = Field(default=None, ge=0, le=10_000_000)
    irrigation_cost_rs_per_ha: float | None = Field(default=None, ge=0, le=10_000_000)
    machinery_cost_rs_per_ha: float | None = Field(default=None, ge=0, le=10_000_000)
    harvest_cost_rs_per_ha: float | None = Field(default=None, ge=0, le=10_000_000)
    transport_cost_rs_per_ha: float | None = Field(default=None, ge=0, le=10_000_000)
    other_cost_rs_per_ha: float | None = Field(default=None, ge=0, le=10_000_000)
    primary_issue: Issue = "unknown"
    notes: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_yield(self):
        if self.year_start > today_ist().year + 1:
            raise ValueError("The season year cannot be more than one year in the future.")
        if self.yield_t_per_ha is None and self.harvested_tonnes is None:
            raise ValueError("Provide either yield per hectare or harvested tonnes.")
        if self.yield_t_per_ha is not None and self.harvested_tonnes is not None:
            expected = self.yield_t_per_ha * self.area_ha
            if abs(expected - self.harvested_tonnes) > max(0.05, expected * 0.05):
                raise ValueError("Yield × area does not match the harvested tonnes (more than 5% apart); check the numbers.")
        if self.yield_t_per_ha is None and self.harvested_tonnes is not None:
            object.__setattr__(self, "yield_t_per_ha", round(self.harvested_tonnes / self.area_ha, 4))
        if self.harvested_tonnes is None and self.yield_t_per_ha is not None:
            object.__setattr__(self, "harvested_tonnes", round(self.yield_t_per_ha * self.area_ha, 4))
        cost_fields = (self.seed_cost_rs_per_ha, self.fertiliser_cost_rs_per_ha,
                       self.crop_protection_cost_rs_per_ha, self.labour_cost_rs_per_ha,
                       self.irrigation_cost_rs_per_ha, self.machinery_cost_rs_per_ha,
                       self.harvest_cost_rs_per_ha, self.transport_cost_rs_per_ha, self.other_cost_rs_per_ha)
        supplied = [value for value in cost_fields if value is not None]
        if self.cultivation_cost_rs_per_ha is None and supplied:
            object.__setattr__(self, "cultivation_cost_rs_per_ha", round(sum(supplied), 2))
        elif self.cultivation_cost_rs_per_ha is not None and supplied:
            total_parts = sum(supplied)
            if abs(float(self.cultivation_cost_rs_per_ha) - total_parts) > max(5.0, float(self.cultivation_cost_rs_per_ha) * 0.02):
                raise ValueError("Total cultivation cost differs from the sum of entered cost categories by more than 2%; check the amounts.")
        return self


def _as_record(row: FarmSeasonRecord) -> dict:
    return {
        "id": row.id, "state": row.state, "district": row.district, "crop": row.crop,
        "season": row.season, "year_start": row.year_start, "area_ha": float(row.area_ha),
        "harvested_tonnes": float(row.harvested_tonnes) if row.harvested_tonnes is not None else None,
        "yield_t_per_ha": float(row.yield_t_per_ha) if row.yield_t_per_ha is not None else None,
        "sale_price_rs_per_qtl": float(row.sale_price_rs_per_qtl) if row.sale_price_rs_per_qtl is not None else None,
        "cultivation_cost_rs_per_ha": float(row.cultivation_cost_rs_per_ha) if row.cultivation_cost_rs_per_ha is not None else None,
        "seed_cost_rs_per_ha": float(row.seed_cost_rs_per_ha) if row.seed_cost_rs_per_ha is not None else None,
        "fertiliser_cost_rs_per_ha": float(row.fertiliser_cost_rs_per_ha) if row.fertiliser_cost_rs_per_ha is not None else None,
        "crop_protection_cost_rs_per_ha": float(row.crop_protection_cost_rs_per_ha) if row.crop_protection_cost_rs_per_ha is not None else None,
        "labour_cost_rs_per_ha": float(row.labour_cost_rs_per_ha) if row.labour_cost_rs_per_ha is not None else None,
        "irrigation_cost_rs_per_ha": float(row.irrigation_cost_rs_per_ha) if row.irrigation_cost_rs_per_ha is not None else None,
        "machinery_cost_rs_per_ha": float(row.machinery_cost_rs_per_ha) if row.machinery_cost_rs_per_ha is not None else None,
        "harvest_cost_rs_per_ha": float(row.harvest_cost_rs_per_ha) if row.harvest_cost_rs_per_ha is not None else None,
        "transport_cost_rs_per_ha": float(row.transport_cost_rs_per_ha) if row.transport_cost_rs_per_ha is not None else None,
        "other_cost_rs_per_ha": float(row.other_cost_rs_per_ha) if row.other_cost_rs_per_ha is not None else None,
        "primary_issue": row.primary_issue, "notes": row.notes, "created_at": row.created_at,
    }


class FarmRefBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    farm_ref: str = Field(min_length=FARM_REF_MIN, max_length=80)
    state: str = Field(min_length=2, max_length=100)
    district: str = Field(min_length=2, max_length=120)
    crop: str = Field(min_length=2, max_length=120)


@router.post("/farm-ref")
def new_farm_reference(request: Request, db: Session = Depends(get_db)):
    """Issue a new private farm-record key. Keep it safe: it is the only way to read the records."""
    rate_limit.limit_client(request, "farm_ref", 20, 3600)
    key = secrets.token_urlsafe(24)
    db.add(FarmReference(ref_hash=ref_hash(key)))
    db.commit()
    return {"farm_ref": key, "note": "Save this key. Records saved with it can only be opened with it."}


@router.post("/recommendations")
def next_season_recommendations(data: RecommendationRequest, request: Request, db: Session = Depends(get_db)):
    rate_limit.limit_client(request, "planner", 60, 600)
    payload = data.model_dump()
    # Reuse the latest saved outcome for this farm key if current yield is not typed again.
    if payload["actual_yield_t_per_ha"] is None:
        latest = (_owned(db.query(FarmSeasonRecord), payload["farm_ref"]).filter(
            _same_text(FarmSeasonRecord.state, payload["state"]),
            _same_text(FarmSeasonRecord.district, payload["district"]),
            _same_text(FarmSeasonRecord.crop, payload["current_crop"]),
        ).order_by(FarmSeasonRecord.year_start.desc(), FarmSeasonRecord.id.desc()).first())
        if latest is not None:
            payload["actual_yield_t_per_ha"] = float(latest.yield_t_per_ha) if latest.yield_t_per_ha is not None else None
            if payload["actual_sale_price_rs_per_qtl"] is None and latest.sale_price_rs_per_qtl is not None:
                payload["actual_sale_price_rs_per_qtl"] = float(latest.sale_price_rs_per_qtl)
            if payload["current_cost_rs_per_ha"] is None and latest.cultivation_cost_rs_per_ha is not None:
                payload["current_cost_rs_per_ha"] = float(latest.cultivation_cost_rs_per_ha)
    try:
        return recommend_crops(db, payload)
    except Exception as exc:
        # Avoid returning SQL/query internals to the browser; keep detail in server logs.
        import logging
        logging.getLogger("kisansaathi.planning").exception("Crop recommendation failed")
        raise HTTPException(status_code=500, detail="Crop comparison could not be completed. Check server logs and imported data.") from exc


@router.post("/records")
def save_season_record(data: SeasonRecordCreate, request: Request, db: Session = Depends(get_db)):
    rate_limit.limit_client(request, "planner_records", 30, 3600)
    row = FarmSeasonRecord(
        farm_ref=ref_hash(data.farm_ref), state=data.state, district=data.district, crop=data.crop,
        season=data.season, year_start=data.year_start, area_ha=data.area_ha,
        harvested_tonnes=data.harvested_tonnes, yield_t_per_ha=data.yield_t_per_ha,
        sale_price_rs_per_qtl=data.sale_price_rs_per_qtl,
        cultivation_cost_rs_per_ha=data.cultivation_cost_rs_per_ha,
        seed_cost_rs_per_ha=data.seed_cost_rs_per_ha, fertiliser_cost_rs_per_ha=data.fertiliser_cost_rs_per_ha,
        crop_protection_cost_rs_per_ha=data.crop_protection_cost_rs_per_ha, labour_cost_rs_per_ha=data.labour_cost_rs_per_ha,
        irrigation_cost_rs_per_ha=data.irrigation_cost_rs_per_ha, machinery_cost_rs_per_ha=data.machinery_cost_rs_per_ha,
        harvest_cost_rs_per_ha=data.harvest_cost_rs_per_ha, transport_cost_rs_per_ha=data.transport_cost_rs_per_ha,
        other_cost_rs_per_ha=data.other_cost_rs_per_ha, primary_issue=data.primary_issue,
        notes=data.notes, created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"saved": True, "record": _as_record(row),
            "privacy_note": "Saved under your private farm record key (only its hash is stored). Keep the key: it is the only way to open these records."}


# POST, so the private key never appears in a URL, browser history or server access log.
@router.post("/records/latest")
def latest_season_record(data: FarmRefBody, request: Request, db: Session = Depends(get_db)):
    rate_limit.limit_client(request, "planner", 60, 600)
    row = (_owned(db.query(FarmSeasonRecord), data.farm_ref).filter(
        _same_text(FarmSeasonRecord.state, data.state), _same_text(FarmSeasonRecord.district, data.district),
        _same_text(FarmSeasonRecord.crop, data.crop),
    ).order_by(FarmSeasonRecord.year_start.desc(), FarmSeasonRecord.id.desc()).first())
    return {"available": row is not None, "record": _as_record(row) if row else None}
