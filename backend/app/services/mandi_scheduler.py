"""Small dependency-free daily scheduler for the in-process mandi refresh.

Safe with several workers: before each run a worker must take a database lease
(table scheduler_leases). Only the lease holder refreshes; the others skip that round.
On hosts that sleep when idle (free cloud tiers), the in-process timer cannot run while
the server sleeps: use an external daily job instead (see deploy/README.md) and set
MANDI_AUTO_REFRESH_ENABLED=0.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import uuid
from datetime import timedelta

from .. import config
from ..database import Base, SessionLocal, engine
from ..models import SchedulerLease
from ..timeutil import now_utc
from .mandi_sync import sync_mandi_prices

log = logging.getLogger("kisansaathi.mandi_scheduler")
LEASE_NAME = "mandi-refresh"
OWNER_ID = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
_state = {"enabled": False, "last_run_by_this_process": None, "skipped_because_other_worker": 0}


def scheduler_state() -> dict:
    return {
        "enabled": config.MANDI_AUTO_REFRESH_ENABLED,
        "interval_hours": config.MANDI_REFRESH_INTERVAL_HOURS,
        "mode": "in-process with database lease" if config.MANDI_AUTO_REFRESH_ENABLED else "disabled",
        "last_run_by_this_process": _state["last_run_by_this_process"],
    }


def acquire_lease(owner: str = OWNER_ID, hours: float | None = None) -> bool:
    """Take or renew the refresh lease. Returns False while another worker holds it."""
    hours = hours if hours is not None else max(1.0, config.MANDI_REFRESH_INTERVAL_HOURS * 0.9)
    now = now_utc()
    Base.metadata.create_all(bind=engine, tables=[SchedulerLease.__table__])
    with SessionLocal() as db:
        row = db.get(SchedulerLease, LEASE_NAME)
        if row is not None:
            until = row.lease_until if row.lease_until.tzinfo else row.lease_until.replace(tzinfo=now.tzinfo)
            if row.owner != owner and until > now:
                return False
            row.owner = owner
            row.lease_until = now + timedelta(hours=hours)
        else:
            db.add(SchedulerLease(name=LEASE_NAME, owner=owner, lease_until=now + timedelta(hours=hours)))
        try:
            db.commit()
        except Exception:  # another worker inserted the row at the same moment
            db.rollback()
            return False
    return True


async def daily_mandi_refresh_loop(stop_event: asyncio.Event) -> None:
    """Refresh on startup (if configured), then every N hours, holding the lease while running."""
    _state["enabled"] = True
    if not config.MANDI_REFRESH_ON_STARTUP:
        log.info("Automatic mandi refresh is enabled; first run will occur after %s hour(s).",
                 config.MANDI_REFRESH_INTERVAL_HOURS)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=config.MANDI_REFRESH_INTERVAL_HOURS * 3600)
        except asyncio.TimeoutError:
            pass

    while not stop_event.is_set():
        try:
            if await asyncio.to_thread(acquire_lease):
                result = await asyncio.to_thread(sync_mandi_prices)
                _state["last_run_by_this_process"] = now_utc().isoformat()
                if result.get("ok"):
                    log.info("Automatic mandi refresh completed: status=%s saved=%s newest_market_date=%s",
                             result.get("status"), result.get("rows_saved"), result.get("newest_arrival_date"))
                else:
                    log.warning("Automatic mandi refresh returned no usable data: %s", result.get("message"))
            else:
                _state["skipped_because_other_worker"] += 1
                log.info("Another worker holds the mandi refresh lease; skipping this round.")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Unexpected error during automatic mandi refresh; saved prices were not deliberately cleared.")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=config.MANDI_REFRESH_INTERVAL_HOURS * 3600)
        except asyncio.TimeoutError:
            continue
        else:
            break
