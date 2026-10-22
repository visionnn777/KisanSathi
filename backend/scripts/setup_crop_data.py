"""One-command setup: download and import the public crop-history dataset.

Run from backend/: python -m scripts.setup_crop_data
No data.gov.in API key is required. The app must have a working DATABASE_URL.
"""
import argparse
import sys
from pathlib import Path

from app import config
from app.database import Base, SessionLocal, engine
from app.services.crop_history import RAW_URL, import_crop_csv
from scripts.download_crop_data import download


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and install KisanSaathi crop-history data")
    parser.add_argument("--url", default=config.CROP_HISTORY_URL or RAW_URL)
    parser.add_argument("--skip-download", action="store_true", help="Import an existing data/crop_production.csv")
    parser.add_argument("--file", type=Path, default=None,
                        help="Import this CSV instead (for example the newer district APY export from India Data Portal)")
    args = parser.parse_args(argv)
    try:
        source_file = args.file or config.CROP_HISTORY_CSV
        if args.file is None and not args.skip_download:
            print("1/2 Downloading the public crop-history CSV...")
            download(args.url, config.CROP_HISTORY_CSV)
        print("2/2 Importing crop records into the database...")
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            result = import_crop_csv(db, source_file)
        print(f"Done: imported {result['imported']:,} crop/year/season records.")
        print(f"Duplicates skipped: {result['duplicates_skipped']:,}.")
        print(f"Bale figures converted to tonnes: {result.get('converted_bales', 0):,}; "
              f"coconut rows kept in nuts: {result.get('kept_as_nuts', 0):,}; "
              f"rows skipped for an unknown unit: {result.get('skipped_unknown_unit', 0):,}.")
        print("Open the app and choose Crop Insights to explore district-level history.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
