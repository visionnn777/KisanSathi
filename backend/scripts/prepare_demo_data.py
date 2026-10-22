"""One command to fill the database for a demo or a judge visit.

Run from backend/ on a laptop with internet:
    python -m scripts.prepare_demo_data --state Punjab --crops Wheat Paddy Maize Mustard
It (1) imports crop history if it is missing, (2) fetches current mandi prices for the state,
(3) backfills state-level price history for each crop (so the Next Season Planner can estimate
revenue), and (4) adds the fake demo listings with the demo PIN. Each step reports what it got;
nothing is invented when a provider returns no data.
"""
from __future__ import annotations

import argparse
import sys

from app.database import Base, SessionLocal, engine
from app.models import CropProduction
from app.services.community_mandi_api import SUPPORTED_STATES
from scripts import fetch_mandi_history, fetch_prices, seed_listings, setup_crop_data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Prepare demo data for KisanSaathi")
    parser.add_argument("--state", default="Punjab", choices=SUPPORTED_STATES)
    parser.add_argument("--crops", nargs="+", default=["Wheat", "Paddy(Dhan)(Common)", "Maize", "Mustard"],
                        help="Provider commodity names to backfill history for")
    parser.add_argument("--years", type=int, default=3, choices=range(1, 7))
    args = parser.parse_args(argv)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        has_crops = db.query(CropProduction.id).first() is not None
    steps = []
    if not has_crops:
        print("== Crop history ==")
        steps.append(("crop history", setup_crop_data.main([])))
    print(f"== Current mandi prices for {args.state} ==")
    steps.append(("current prices", fetch_prices.main(["--state", args.state])))
    for crop in args.crops:
        print(f"== Price history: {crop} ==")
        steps.append((f"history {crop}", fetch_mandi_history.main(["--state", args.state, "--commodity", crop, "--years", str(args.years)])))
    print("== Demo listings ==")
    steps.append(("demo listings", seed_listings.main([])))
    print("\nSummary:")
    for name, code in steps:
        print(f"  {'OK    ' if code == 0 else 'FAILED'} {name}")
    return 0 if all(code == 0 for _, code in steps) else 1


if __name__ == "__main__":
    sys.exit(main())
