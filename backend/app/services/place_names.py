"""Place-name table: clean English names, Hindi names and every known spelling.

Source: app/data/place_names.txt (curated by hand). Used to
- match a typed or current name ("Bathinda", "Odisha") to the old spelling used in the crop
  dataset ("BHATINDA", "ORISSA"), and
- build frontend/js/names.js for Hindi display (python -m scripts.build_name_tables).
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "place_names.txt"


def place_key(value: str) -> str:
    """'A & N ISLANDS' -> 'ANDNISLANDS', 'N.SHAHAR' -> 'NSHAHAR', 'Ropar (Rupnagar)' -> 'ROPARRUPNAGAR'."""
    text = str(value or "").upper().replace("&", "AND")
    return re.sub(r"[^A-Z0-9]", "", text)


def _split(line: str) -> tuple[str, str, list[str]]:
    parts = [part.strip() for part in line.split("|")]
    while len(parts) < 3:
        parts.append("")
    english, hindi, aliases = parts[0], parts[1], [a.strip() for a in parts[2].split(";") if a.strip()]
    return english, hindi, aliases


@lru_cache(maxsize=1)
def load() -> dict:
    """{"states": {key: entry}, "state_alias": {alias_key: key}, "districts": {state_key: {alias_key: entry}}}"""
    states: dict[str, dict] = {}
    state_alias: dict[str, str] = {}
    districts: dict[str, dict[str, dict]] = {}
    current = None
    for raw in DATA_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            english, hindi, aliases = _split(line[1:])
            current = place_key(english)
            states[current] = {"en": english, "hi": hindi}
            for name in [english, *aliases]:
                state_alias[place_key(name)] = current
            districts.setdefault(current, {})
            continue
        if current is None:
            raise ValueError(f"District line before any state: {line!r}")
        english, hindi, aliases = _split(line)
        entry = {"en": english, "hi": hindi}
        for name in [english, *aliases]:
            districts[current].setdefault(place_key(name), entry)
    return {"states": states, "state_alias": state_alias, "districts": districts}


def state_entry(name: str) -> tuple[str, dict] | tuple[None, None]:
    table = load()
    key = table["state_alias"].get(place_key(name))
    return (key, table["states"][key]) if key else (None, None)


def district_entry(state: str, district: str) -> dict | None:
    key, _ = state_entry(state)
    if key is None:
        return None
    return load()["districts"].get(key, {}).get(place_key(district))


def same_state(a: str, b: str) -> bool:
    ka, _ = state_entry(a)
    kb, _ = state_entry(b)
    return (ka is not None and ka == kb) or place_key(a) == place_key(b)


def same_district(state: str, a: str, b: str) -> bool:
    """True when two spellings name the same district of this state ('Bathinda' vs 'BHATINDA')."""
    if place_key(a) == place_key(b):
        return True
    ea, eb = district_entry(state, a), district_entry(state, b)
    return ea is not None and ea is eb
