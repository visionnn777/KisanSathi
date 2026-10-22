"""Import the downloaded crop-history CSV into the configured database.

Run from backend/: python -m scripts.import_crop_history
"""
import argparse
import sys
from pathlib import Path

from app import config
from app.database import Base, SessionLocal, engine
from app.services.crop_history import SOURCE_LABEL, import_crop_csv


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Import crop production history into KisanSaathi")
    parser.add_argument("--file", type=Path, default=config.CROP_HISTORY_CSV,
                        help="CSV produced by scripts.download_crop_data")
    args = parser.parse_args(argv)
    try:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            result = import_crop_csv(db, args.file)
        print(f"Imported {result['imported']:,} observations into crop_production_history.")
        print(f"Duplicate rows skipped: {result['duplicates_skipped']:,}")
        print(f"Attribution: {SOURCE_LABEL}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: crop-history import failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: database import failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
