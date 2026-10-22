"""Backfill state-level historical prices from the keyless Mandi Price API.

Run from backend/:
  python -m scripts.fetch_mandi_history --state Punjab --commodity Wheat
  python -m scripts.fetch_mandi_history --state Punjab --commodity Wheat --years 5

The provider history endpoint is a state-level trend aggregate, not an individual mandi quote.
Run it selectively for the current crop and likely alternatives to respect rate limits.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from app.database import Base, SessionLocal, engine
from app.services.community_mandi_api import CommunityMandiAPIError, SUPPORTED_STATES, fetch_price_history
from app.services.price_store import normalize_history_record, save_history_rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Backfill historical state-level mandi price observations")
    parser.add_argument("--state", required=True, choices=SUPPORTED_STATES)
    parser.add_argument("--commodity", required=True, help="Use the provider's commodity spelling, e.g. Wheat")
    parser.add_argument("--years", type=int, default=5, choices=range(1, 7), help="History length, 1–6 years (default 5)")
    parser.add_argument("--from-date", help="Optional ISO start date YYYY-MM-DD")
    parser.add_argument("--to-date", help="Optional ISO end date YYYY-MM-DD (defaults to today)")
    args = parser.parse_args(argv)
    end = date.fromisoformat(args.to_date) if args.to_date else date.today()
    start = date.fromisoformat(args.from_date) if args.from_date else end - timedelta(days=365 * args.years)
    if start > end:
        parser.error("--from-date must be on or before --to-date")
    try:
        print(f"Fetching state-level history for {args.commodity} in {args.state}: {start} to {end}...")
        raw = fetch_price_history(state=args.state, commodity=args.commodity, from_date=start.isoformat(), to_date=end.isoformat())
        rows = [normalized for item in raw if (normalized := normalize_history_record(item, state=args.state, commodity=args.commodity))]
        if not rows:
            print(f"No usable historical price observations were returned (raw rows: {len(raw)}). No history records changed.", file=sys.stderr)
            return 1
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            written = save_history_rows(db, rows)
            from app.models import MandiPriceHistory
            stored_count = db.query(MandiPriceHistory).filter_by(state=args.state, commodity=args.commodity).count()
        dates = sorted(row["observation_date"] for row in rows)
        print(f"Fetched {len(raw)} row(s); valid {len(rows)}; inserted/updated {written}.")
        print(f"Observation dates: {dates[0]} to {dates[-1]}.")
        print(f"Stored history rows for this state/crop: {stored_count}.")
        print("Note: values are state-level historical aggregates, not a specific mandi quote or guaranteed seasonal forecast.")
        return 0
    except (CommunityMandiAPIError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
