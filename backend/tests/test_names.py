import csv
from pathlib import Path

from app import config
from app.services.place_names import district_entry, load, state_entry
from scripts import build_name_tables

FIXTURE = Path(__file__).parent / "fixtures" / "agridata_sample.csv"


def test_names_js_is_up_to_date():
    current = (config.FRONTEND_DIR / "js" / "names.js").read_text(encoding="utf-8")
    assert current == build_name_tables.build(), "Run: python -m scripts.build_name_tables"


def test_every_state_and_district_has_hindi():
    table = load()
    for key, entry in table["states"].items():
        assert entry["hi"] and entry["en"], key
    for state, districts in table["districts"].items():
        for alias, entry in districts.items():
            assert entry["hi"] and any("ऀ" <= ch <= "ॿ" for ch in entry["hi"]), (state, alias)


def test_old_and_current_spellings_resolve_to_one_name():
    assert district_entry("PUNJAB", "BHATINDA") is district_entry("Punjab", "Bathinda")
    assert district_entry("PUNJAB", "BHATINDA")["hi"] == "बठिंडा"
    assert state_entry("ORISSA")[1]["hi"] == "ओडिशा"
    assert district_entry("Maharashtra", "Aurangabad")["en"].startswith("Chhatrapati Sambhajinagar")
    assert district_entry("Bihar", "AURANGABAD")["en"] == "Aurangabad"   # same name, different state
    with FIXTURE.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            assert district_entry(row["state"], row["district"]), row
