"""Add demo listings so the Direct Market page is not empty on stage.

Owner: Member A

Run from the backend folder:
    python -m scripts.seed_listings          # add the demo listings (safe to run twice)
    python -m scripts.seed_listings --reset  # remove them again

All phone numbers start with 900000 and are fake on purpose.
Every demo listing uses the same farmer PIN, DEMO_PIN below, so you can show "My listings"
and "Mark as sold" on stage: phone 9000000001 + PIN kisan-demo-2026.
DATA YOU CAN CHANGE: names, villages and districts below - use places from your own state.
"""
import argparse
import sys

from app.database import Base, SessionLocal, engine
from app.models import BuyerInterest, Listing
from app.security import hash_owner_pin

DEMO_PREFIX = "900000"
DEMO_PIN = "kisan-demo-2026"

DEMO_LISTINGS = [
    # farmer_name, phone, crop, quantity_kg, price_per_kg, village, district, state
    ("Ramesh Kumar", "9000000001", "Tomato", 500, 14, "Bichpuri", "Agra", "Uttar Pradesh"),
    ("Sunita Devi", "9000000002", "Potato", 1200, 11, "Kheragarh", "Agra", "Uttar Pradesh"),
    ("Mohan Singh", "9000000003", "Wheat", 2000, 24.5, "Samrala", "Ludhiana", "Punjab"),
    ("Gurpreet Kaur", "9000000004", "Paddy", 3000, 23, "Khanna", "Ludhiana", "Punjab"),
    ("Anil Patil", "9000000005", "Onion", 800, 18, "Lasalgaon", "Nashik", "Maharashtra"),
    ("Kavita Jadhav", "9000000006", "Tomato", 400, 15, "Narayangaon", "Pune", "Maharashtra"),
    ("Suresh Yadav", "9000000007", "Maize", 1500, 21, "Bahraich", "Bahraich", "Uttar Pradesh"),
    ("Meena Kumari", "9000000008", "Potato", 900, 10.5, "Farrukhabad", "Farrukhabad", "Uttar Pradesh"),
    ("Harjit Singh", "9000000009", "Wheat", 2500, 24, "Jagraon", "Ludhiana", "Punjab"),
    ("Lakshmi Bai", "9000000010", "Onion", 600, 17.5, "Yeola", "Nashik", "Maharashtra"),
    ("Rajesh Verma", "9000000011", "Cauliflower", 300, 20, "Barabanki", "Barabanki", "Uttar Pradesh"),
    ("Pooja Sharma", "9000000012", "Green Chilli", 150, 35, "Sonipat", "Sonipat", "Haryana"),
]

FIELDS = ["farmer_name", "phone", "crop", "quantity_kg", "price_per_kg", "village", "district", "state"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Add or remove demo listings")
    parser.add_argument("--reset", action="store_true", help="Delete the demo listings")
    args = parser.parse_args(argv)

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        demo = db.query(Listing).filter(Listing.phone.like(f"{DEMO_PREFIX}%"))
        if args.reset:
            ids = [l.id for l in demo]
            if ids:
                db.query(BuyerInterest).filter(BuyerInterest.listing_id.in_(ids)).delete(synchronize_session=False)
            count = demo.delete(synchronize_session=False)
            db.commit()
            print(f"Removed {count} demo listings.")
            return 0

        existing = {(l.phone, l.crop): l for l in demo}
        added = upgraded = 0
        for values in DEMO_LISTINGS:
            item = dict(zip(FIELDS, values))
            row = existing.get((item["phone"], item["crop"]))
            if row is not None:
                if not row.owner_pin_hash:  # listings seeded by older versions had no PIN
                    row.owner_pin_hash = hash_owner_pin(DEMO_PIN)
                    upgraded += 1
                continue
            db.add(Listing(**item, owner_pin_hash=hash_owner_pin(DEMO_PIN)))
            added += 1
        db.commit()
    print(f"Added {added} demo listings ({len(DEMO_LISTINGS) - added} were already there; {upgraded} given the demo PIN).")
    print(f"Demo login for 'My listings': phone 9000000001, PIN {DEMO_PIN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
