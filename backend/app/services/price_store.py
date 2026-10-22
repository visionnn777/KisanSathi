"""Normalize and persist mandi-price quotes/history in the configured SQLAlchemy database.

Owner: Member C
"""
import csv
import math
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import MandiPrice, MandiPriceHistory

KEY_FIELDS = ["state", "district", "market", "commodity", "variety", "grade", "arrival_date"]
PRICE_FIELDS = ["min_price", "max_price", "modal_price"]
CSV_FIELDS = KEY_FIELDS + PRICE_FIELDS
DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d")


def parse_date(text: str):
    text = (text or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _price(text) -> float | None:
    try:
        value = float(str(text).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def normalize_record(record: dict) -> dict | None:
    """Turn one API record into a clean row, or None if it is unusable.

    Works with lower-case keys (state, arrival_date, modal_price) and with the
    older styles (State, Arrival_Date, Modal_x0020_Price).
    """
    k = {
        str(key).strip().lower().replace("_x0020_", "_").replace(" ", "_"): value
        for key, value in record.items()
    }

    def text(name):
        return str(k.get(name) or "").strip()

    row = {name: text(name) for name in ["state", "district", "market", "commodity", "variety", "grade"]}
    row["arrival_date"] = parse_date(text("arrival_date"))
    for name in PRICE_FIELDS:
        row[name] = _price(k.get(name))

    if not (row["state"] and row["market"] and row["commodity"] and row["arrival_date"]):
        return None
    if row["modal_price"] is None:
        return None
    # Fill a missing min/max with the modal price so every row is complete.
    row["min_price"] = row["min_price"] or row["modal_price"]
    row["max_price"] = row["max_price"] or row["modal_price"]
    # Reject internally inconsistent prices rather than quietly normalizing official data.
    if row["min_price"] > row["max_price"]:
        return None
    if not (row["min_price"] <= row["modal_price"] <= row["max_price"]):
        return None
    return row


def _row_key(row: dict) -> tuple:
    return tuple(row[f] for f in KEY_FIELDS)


def dedupe(rows: list[dict]) -> list[dict]:
    """Keep one row per mandi + commodity + variety + grade + day (the last one wins)."""
    return list({_row_key(r): r for r in rows}.values())


def save_rows(db: Session, rows: list[dict], source: str = "data.gov.in", chunk: int = 500) -> int:
    """Insert new rows and update prices of rows that already exist. Returns rows written."""
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:  # SQLite, used by the automatic tests
        from sqlalchemy.dialects.sqlite import insert

    rows = dedupe(rows)
    written = 0
    for start in range(0, len(rows), chunk):
        batch = [dict(r, source=source) for r in rows[start:start + chunk]]
        stmt = insert(MandiPrice).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=KEY_FIELDS,
            set_={name: stmt.excluded[name] for name in PRICE_FIELDS + ["source"]},
        )
        db.execute(stmt)
        written += len(batch)  # every row is either inserted or updated
    db.commit()
    return written


def delete_older_than(db: Session, days: int) -> int:
    """Remove stored market quotes whose report date is more than `days` old (0 keeps all)."""
    if not days:
        return 0
    from datetime import timedelta
    from ..timeutil import today_ist
    cutoff = today_ist() - timedelta(days=days)
    count = db.query(MandiPrice).filter(MandiPrice.arrival_date < cutoff).delete(synchronize_session=False)
    db.commit()
    return count


def delete_source(db: Session, source: str) -> int:
    count = db.query(MandiPrice).filter(MandiPrice.source == source).delete(synchronize_session=False)
    db.commit()
    return count


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(dedupe(rows), key=lambda r: (r["arrival_date"], r["state"], r["commodity"], r["market"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in rows:
            out = {name: r[name] for name in CSV_FIELDS}
            out["arrival_date"] = r["arrival_date"].isoformat()
            writer.writerow(out)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = [normalize_record(r) for r in csv.DictReader(f)]
    return [r for r in rows if r]


def merge_into_csv(new_rows: list[dict], path: Path, keep_days: int = 0) -> int:
    """Add new rows to the backup CSV, keeping older days (up to keep_days). Returns total rows."""
    all_rows = dedupe(read_csv(path) + new_rows)
    if keep_days:
        from datetime import timedelta
        from ..timeutil import today_ist
        cutoff = today_ist() - timedelta(days=keep_days)
        all_rows = [r for r in all_rows if r["arrival_date"] >= cutoff]
    write_csv(all_rows, path)
    return len(all_rows)


def normalize_history_record(record: dict, *, state: str, commodity: str) -> dict | None:
    """Normalize one provider aggregate-history row without fabricating a market quote."""
    # Normalize snake_case, spaced labels, and camelCase from different JSON exporters.
    k = {}
    for key, value in record.items():
        label = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key).strip())
        label = label.lower().replace("-", "_").replace(" ", "_")
        k[label] = value

    date_value = next((k.get(name) for name in ("date", "arrival_date", "market_date", "observation_date", "report_date", "timestamp") if k.get(name)), None)
    if isinstance(date_value, str):
        # Some JSON serializers expose ISO timestamps (e.g. 2026-10-18T00:00:00Z)
        # where the API documentation shows a date. Preserve the observation day.
        cleaned_date = date_value.strip()
        parsed_date = parse_date(cleaned_date)
        if parsed_date is None and len(cleaned_date) >= 10:
            parsed_date = parse_date(cleaned_date[:10])
    else:
        parsed_date = None
    if parsed_date is None:
        return None

    value = next((k.get(name) for name in (
        "avg_modal_price", "average_modal_price", "avg_price", "average_price",
        "mean_modal_price", "avg_modal", "modal_price", "price", "value",
    ) if k.get(name) is not None), None)
    price = _price(value)
    if price is None:
        return None

    min_value = next((k.get(name) for name in ("min_modal_price", "min_price", "low_price") if k.get(name) is not None), None)
    max_value = next((k.get(name) for name in ("max_modal_price", "max_price", "high_price") if k.get(name) is not None), None)
    low = _price(min_value) if min_value is not None else None
    high = _price(max_value) if max_value is not None else None
    if low is not None and high is not None and low > high:
        return None
    if low is not None and price < low:
        return None
    if high is not None and price > high:
        return None

    count_value = next((k.get(name) for name in ("markets_count", "market_count", "number_of_markets", "markets", "count") if k.get(name) is not None), None)
    if isinstance(count_value, list):
        count = len(count_value)
    else:
        try:
            count = int(count_value) if count_value is not None else None
            if count is not None and count < 0:
                count = None
        except (TypeError, ValueError):
            count = None
    return {
        "state": state, "commodity": commodity, "observation_date": parsed_date,
        "average_modal_price": price, "min_modal_price": low, "max_modal_price": high,
        "markets_count": count, "source": "mandi-api-history",
    }


def save_history_rows(db: Session, rows: list[dict], chunk: int = 500) -> int:
    """Upsert normalized state/commodity aggregate history observations."""
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    unique = {}
    for row in rows:
        key = (row["state"], row["commodity"], row["observation_date"], row["source"])
        unique[key] = row
    rows = list(unique.values())
    written = 0
    for start in range(0, len(rows), chunk):
        batch = [dict(r) for r in rows[start:start + chunk]]
        stmt = insert(MandiPriceHistory).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=["state", "commodity", "observation_date", "source"],
            set_={name: stmt.excluded[name] for name in [
                "average_modal_price", "min_modal_price", "max_modal_price", "markets_count", "fetched_at"
            ]},
        )
        db.execute(stmt)
        written += len(batch)
    db.commit()
    return written
