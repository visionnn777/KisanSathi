"""Import dated mandi prices into KisanSaathi.

Default: keyless community Mandi Price API for Maharashtra, Uttar Pradesh, Punjab,
Madhya Pradesh and Karnataka. The same workflow is used by the automatic daily job.

From backend/: 
  python -m scripts.fetch_prices
  python -m scripts.fetch_prices --state Punjab --commodity Wheat
  python -m scripts.fetch_prices --provider data.gov.in --state Punjab
"""
import argparse
import sys

from app import config
from app.database import Base, SessionLocal, engine
from app.services.mandi_sync import sync_mandi_prices
from app.services.price_store import delete_source, merge_into_csv, normalize_record, save_rows
from app.services.mandi_api import MandiAPIError, fetch_all as fetch_government_prices


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch dated mandi prices into the KisanSaathi database")
    parser.add_argument("--state", help='One supported state, e.g. "Punjab"')
    parser.add_argument("--commodity", help='Optional crop filter, e.g. "Wheat" or "Onion"')
    parser.add_argument("--provider", choices=("mandi-api", "data.gov.in"), default="mandi-api",
                        help="Price provider (default: keyless mandi-api)")
    args = parser.parse_args(argv)

    Base.metadata.create_all(bind=engine)
    if args.provider == "mandi-api":
        try:
            result = sync_mandi_prices(state=args.state, commodity=args.commodity)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 2
        print(f"Provider: {result['provider']}")
        print(f"Status: {result['status']}")
        print(f"States with records: {', '.join(result['states_succeeded']) or '(none)'}")
        if result["states_failed"]:
            print(f"States failed: {', '.join(result['states_failed'])}")
        if result["states_empty"]:
            print(f"States with no matching records: {', '.join(result['states_empty'])}")
        print(f"Received {result['records_received']} record(s); saved/updated {result['rows_saved']}; skipped {result['rows_skipped']} invalid/filtered row(s).")
        if result.get("newest_arrival_date"):
            print(f"Market arrival dates in this download: {result['oldest_arrival_date']} to {result['newest_arrival_date']} (may not be today's date).")
        if result.get("sample_rows_removed"):
            print(f"Removed {result['sample_rows_removed']} synthetic sample rows after live data was stored.")
        print(f"{result['message']}")
        if result.get("snapshot_rows") is not None:
            print(f"Backup CSV updated: {config.SNAPSHOT_CSV} ({result['snapshot_rows']} rows).")
        return 0 if result["ok"] else 1

    # Optional official provider remains available for users with a functioning data.gov.in key.
    if args.commodity:
        print("NOTE: data.gov.in provider does not apply --commodity server-side; filtering after fetch.")
    print("Fetching from data.gov.in" + (f" (state: {args.state})" if args.state else "") + " ...")
    try:
        raw_records = fetch_government_prices(state=args.state)
    except MandiAPIError as exc:
        print(f"ERROR: {exc}")
        return 1
    rows = []
    for record in raw_records:
        row = normalize_record(record)
        if row and (not args.commodity or row["commodity"].casefold() == args.commodity.casefold()):
            rows.append(row)
    if not rows:
        print(f"No usable price records returned ({len(raw_records)} received). No database rows were changed.")
        return 1
    with SessionLocal() as db:
        written = save_rows(db, rows, source="data.gov.in")
        removed = delete_source(db, "sample")
    total_csv = merge_into_csv(rows, config.SNAPSHOT_CSV)
    dates = sorted({r["arrival_date"] for r in rows})
    print(f"Received {len(raw_records)}; saved/updated {written}; market dates {dates[0]} to {dates[-1]}.")
    if removed:
        print(f"Removed {removed} synthetic sample rows after valid government data was stored.")
    print(f"Backup CSV updated: {config.SNAPSHOT_CSV} ({total_csv} rows).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
