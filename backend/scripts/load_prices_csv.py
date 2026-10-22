"""Load mandi prices from a CSV file into the database (works with no internet).

Owner: Member C

Run from the backend folder:
    python -m scripts.load_prices_csv            # loads data/mandi_snapshot.csv (real data you fetched)
    python -m scripts.load_prices_csv --sample   # loads data/sample_mandi_prices.csv (made-up demo values)

Use --sample only while building, before you have an API key. The app shows a
"sample data" warning whenever sample rows are in the database.
"""
import argparse
import sys
from pathlib import Path

from app import config
from app.database import Base, SessionLocal, engine
from app.services.price_store import delete_source, read_csv, save_rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Load mandi prices from CSV")
    parser.add_argument("--sample", action="store_true", help="Load the made-up sample file")
    parser.add_argument("--file", type=Path, help="Any CSV with the same columns")
    parser.add_argument("--source", choices=["data.gov.in", "sample", "custom"],
                        help="Provenance label for --file; never label your own CSV as government data")
    args = parser.parse_args(argv)

    path = args.file or (config.SAMPLE_CSV if args.sample else config.SNAPSHOT_CSV)
    if args.source:
        source = args.source
    elif args.sample:
        source = "sample"
    elif args.file:
        source = "custom"
    else:
        source = "data.gov.in"
    rows = read_csv(path)
    if not rows:
        print(f"No rows found in {path}.")
        if not args.sample:
            print("Run python -m scripts.fetch_prices first, or use --sample while building.")
        return 1

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        written = save_rows(db, rows, source=source)
        removed = delete_source(db, "sample") if source == "data.gov.in" else 0
    print(f"Loaded {written} rows from {path} (source: {source}).")
    if removed:
        print(f"Removed {removed} sample rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
