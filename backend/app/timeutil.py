"""One place for "today" and "now".

Indian mandi reports and forecasts are dated in Indian Standard Time. A cloud server usually
runs on UTC, where "today" changes at 5:30 am IST, so ages were off by a day in the early
morning. Use these helpers instead of date.today().
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_ist() -> date:
    return datetime.now(IST).date()


def days_old(day: date | None) -> int | None:
    """Whole days between a report date and today in India; None for missing or future dates."""
    if day is None:
        return None
    age = (today_ist() - day).days
    return age if age >= 0 else None
