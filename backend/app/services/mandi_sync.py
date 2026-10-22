"""Shared Mandi Price API sync workflow used by CLI and automatic scheduler.

Never deletes existing real records on a provider failure or empty response.  The
provider's `arrival_date` is the market report date; `fetched_at` is not a market date.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from .. import config
from ..database import Base, SessionLocal, engine
from ..models import MandiSyncStatus
from .community_mandi_api import (
    SUPPORTED_STATES,
    CommunityMandiAPIError,
    fetch_prices as fetch_community_prices,
)
from .price_store import delete_older_than, delete_source, merge_into_csv, normalize_record, save_rows

log = logging.getLogger("kisansaathi.mandi_sync")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _write_status(*, status: str, attempted_at: datetime, succeeded_at: datetime | None,
                  received: int, saved: int, succeeded_states: list[str],
                  failed_states: list[str], message: str) -> None:
    """Upsert one provider status row, without hiding the original sync exception."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        row = db.query(MandiSyncStatus).filter_by(provider="mandi-api").one_or_none()
        if row is None:
            row = MandiSyncStatus(provider="mandi-api")
            db.add(row)
        row.status = status
        row.last_attempt_at = attempted_at
        if succeeded_at is not None:
            row.last_success_at = succeeded_at
        row.rows_received = received
        row.rows_saved = saved
        row.states_succeeded = json.dumps(succeeded_states, ensure_ascii=False)
        row.states_failed = json.dumps(failed_states, ensure_ascii=False)
        row.message = message[:2000]
        db.commit()


def sync_mandi_prices(*, state: str | None = None, commodity: str | None = None) -> dict[str, Any]:
    """Fetch one or all supported states, validate, upsert records, and persist run status.

    Partial provider outages are allowed if at least one selected state returns usable
    records. If no usable records arrive, existing database rows and sample rows remain
    untouched and the result clearly reports failure/no data.
    """
    attempted_at = _now()
    Base.metadata.create_all(bind=engine)

    if state:
        canonical = next((s for s in SUPPORTED_STATES if s.casefold() == state.strip().casefold()), None)
        if canonical is None:
            raise ValueError(f"Unsupported state {state!r}. Choose from: {', '.join(SUPPORTED_STATES)}")
        states = [canonical]
    else:
        states = list(SUPPORTED_STATES)

    raw_records: list[dict] = []
    succeeded_states: list[str] = []
    failed_states: list[str] = []
    empty_states: list[str] = []
    error_messages: list[str] = []

    for current_state in states:
        try:
            batch = fetch_community_prices(state=current_state, commodity=commodity)
            if batch:
                raw_records.extend(batch)
                succeeded_states.append(current_state)
            else:
                empty_states.append(current_state)
                log.warning("Mandi Price API returned no records for %s%s", current_state,
                            f" / {commodity}" if commodity else "")
        except CommunityMandiAPIError as exc:
            failed_states.append(current_state)
            error_messages.append(f"{current_state}: {exc}")
            log.warning("Mandi Price API failed for %s: %s", current_state, exc)

    rows = []
    for record in raw_records:
        normalized = normalize_record(record)
        if normalized and (not commodity or normalized["commodity"].casefold() == commodity.casefold()):
            rows.append(normalized)
    skipped = len(raw_records) - len(rows)

    if not rows:
        if failed_states:
            status = "error"
            message = "No usable records were fetched. Existing stored prices were preserved. " + "; ".join(error_messages)
        else:
            status = "no_data"
            message = "The provider returned no usable price records. Existing stored prices were preserved."
        _write_status(status=status, attempted_at=attempted_at, succeeded_at=None,
                      received=len(raw_records), saved=0, succeeded_states=succeeded_states,
                      failed_states=failed_states or empty_states, message=message)
        return {
            "ok": False, "status": status, "provider": "mandi-api",
            "states_succeeded": succeeded_states, "states_failed": failed_states,
            "states_empty": empty_states, "records_received": len(raw_records),
            "rows_saved": 0, "rows_skipped": skipped, "message": message,
        }

    with SessionLocal() as db:
        saved = save_rows(db, rows, source="mandi-api")
        # Delete synthetic rows only after valid live data has been stored successfully.
        removed_samples = delete_source(db, "sample")
        removed_old = delete_older_than(db, config.PRICE_RETENTION_DAYS)

    total_csv = merge_into_csv(rows, config.SNAPSHOT_CSV, keep_days=config.PRICE_RETENTION_DAYS)
    completed_at = _now()
    if failed_states or empty_states:
        status = "partial"
        message = f"Saved {saved} price rows from {len(succeeded_states)} state(s); some states returned no data or failed."
        if error_messages:
            message += " " + "; ".join(error_messages)
    else:
        status = "success"
        message = f"Saved/updated {saved} price rows from all {len(succeeded_states)} selected state(s)."
    _write_status(status=status, attempted_at=attempted_at, succeeded_at=completed_at,
                  received=len(raw_records), saved=saved, succeeded_states=succeeded_states,
                  failed_states=failed_states + empty_states, message=message)

    dates = sorted({row["arrival_date"] for row in rows})
    return {
        "ok": True, "status": status, "provider": "mandi-api",
        "states_succeeded": succeeded_states, "states_failed": failed_states,
        "states_empty": empty_states, "records_received": len(raw_records),
        "rows_saved": saved, "rows_skipped": skipped,
        "sample_rows_removed": removed_samples, "old_rows_removed": removed_old, "snapshot_rows": total_csv,
        "oldest_arrival_date": dates[0].isoformat(),
        "newest_arrival_date": dates[-1].isoformat(),
        "message": message,
    }
