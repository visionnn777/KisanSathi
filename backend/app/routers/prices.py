"""Mandi Bhav: today's best mandis for a crop, read from our own database.

Owner: Member C

The app serves normalized records from its configured SQLAlchemy database (SQLite by
 default for local demos, PostgreSQL supported for deployment). Manual and scheduled
scripts import provider records; saved data remains available when the upstream API is down.
"""
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MandiPrice, MandiPriceHistory, MandiSyncStatus
from .. import config
from ..timeutil import days_old as _days_old

router = APIRouter(prefix="/api/prices", tags=["prices"])

QUINTAL_KG = 100


@router.get("/status")
def price_status(db: Session = Depends(get_db)):
    """How much price data we have, the newest date, and whether it is sample data."""
    rows = db.query(func.count(MandiPrice.id)).scalar() or 0
    latest = db.query(func.max(MandiPrice.arrival_date)).scalar()
    sources = [s for (s,) in db.query(MandiPrice.source).distinct().order_by(MandiPrice.source)]
    days_old = _days_old(latest)
    history_rows = db.query(func.count(MandiPriceHistory.id)).scalar() or 0
    history_latest = db.query(func.max(MandiPriceHistory.observation_date)).scalar()
    history_oldest = db.query(func.min(MandiPriceHistory.observation_date)).scalar()
    sync = db.query(MandiSyncStatus).filter_by(provider="mandi-api").one_or_none()
    sync_payload = None
    if sync is not None:
        try:
            succeeded_states = json.loads(sync.states_succeeded or "[]")
        except (TypeError, ValueError):
            succeeded_states = []
        try:
            failed_states = json.loads(sync.states_failed or "[]")
        except (TypeError, ValueError):
            failed_states = []
        sync_payload = {
            "provider": sync.provider,
            "status": sync.status,
            "last_attempt_at": sync.last_attempt_at,
            "last_success_at": sync.last_success_at,
            "rows_received": sync.rows_received,
            "rows_saved": sync.rows_saved,
            "states_succeeded": succeeded_states,
            "states_failed": failed_states,
            "message": sync.message,
        }
    return {
        "rows": rows,
        "latest_date": latest,
        "sources": sources,
        "days_old": days_old,
        "is_stale": days_old is not None and days_old > config.PRICE_STALE_DAYS,
        "stale_after_days": config.PRICE_STALE_DAYS,
        "planner_price_max_age_days": config.PLANNER_PRICE_MAX_AGE_DAYS,
        "is_sample": "sample" in sources,
        "has_government_source": "data.gov.in" in sources,
        "has_live_source": any(s in {"data.gov.in", "mandi-api"} for s in sources),
        "providers": sources,
        "historical_price_series": {
            "rows": history_rows,
            "oldest_observation_date": history_oldest,
            "latest_observation_date": history_latest,
            "source": "mandi-api-history state-level aggregate" if history_rows else None,
            "note": "This series is aggregated across reporting mandis and is not an individual mandi quote.",
        },
        "auto_refresh": {
            "enabled": config.MANDI_AUTO_REFRESH_ENABLED,
            "on_startup": config.MANDI_REFRESH_ON_STARTUP,
            "interval_hours": config.MANDI_REFRESH_INTERVAL_HOURS,
            "mode": "in-process single worker" if config.MANDI_AUTO_REFRESH_ENABLED else "disabled",
        },
        "last_sync": sync_payload or {"provider": "mandi-api", "status": "idle",
                                      "message": "No automatic refresh has completed in this database yet."},
    }


@router.get("/states")
def list_states(db: Session = Depends(get_db)):
    return [s for (s,) in db.query(MandiPrice.state).distinct().order_by(MandiPrice.state)]


@router.get("/commodities")
def list_commodities(state: str, db: Session = Depends(get_db)):
    q = (db.query(MandiPrice.commodity).filter(MandiPrice.state == state)
         .distinct().order_by(MandiPrice.commodity))
    return [c for (c,) in q]


@router.get("/best")
def best_markets(state: str, commodity: str, limit: int = Query(5, ge=1, le=20),
                 db: Session = Depends(get_db)):
    """Highest modal (most common) prices on the newest day we have for this crop."""
    base = db.query(MandiPrice).filter(MandiPrice.state == state, MandiPrice.commodity == commodity)
    latest = base.with_entities(func.max(MandiPrice.arrival_date)).scalar()
    if latest is None:
        return {"date": None, "source": None, "markets": []}
    rows = (base.filter(MandiPrice.arrival_date == latest)
            .order_by(MandiPrice.modal_price.desc(), MandiPrice.market).limit(limit).all())
    return {
        "date": latest,
        "source": rows[0].source if rows else None,
        "markets": [{
            "market": r.market,
            "district": r.district,
            "variety": r.variety,
            "min_price": r.min_price,
            "max_price": r.max_price,
            "modal_price": r.modal_price,
            "modal_per_kg": round(r.modal_price / QUINTAL_KG, 2),
        } for r in rows],
    }


@router.get("/history")
def price_history(state: str, commodity: str, days: int = Query(14, ge=1, le=60),
                  db: Session = Depends(get_db)):
    """Average modal price across the state's mandis for each recent day (oldest first)."""
    rows = (
        db.query(MandiPrice.arrival_date, func.avg(MandiPrice.modal_price), func.count(MandiPrice.id))
        .filter(MandiPrice.state == state, MandiPrice.commodity == commodity)
        .group_by(MandiPrice.arrival_date)
        .order_by(MandiPrice.arrival_date.desc())
        .limit(days)
        .all()
    )
    return [
        {"date": d, "avg_modal_price": round(float(avg), 2), "markets": n}
        for d, avg, n in reversed(rows)
    ]
