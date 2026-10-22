"""Tests on a small extract of the real crop dataset (tests/fixtures/agridata_sample.csv).

These catch problems that tidy invented data hides: production in bales and nuts, old district
spellings (BHATINDA, MANSHA) and season names (Summer, not Zaid)."""
from pathlib import Path

from app.models import CropProduction
from app.services.crop_history import import_crop_csv

FIXTURE = Path(__file__).parent / "fixtures" / "agridata_sample.csv"


def _import(db):
    return import_crop_csv(db, FIXTURE)


def test_import_converts_bales_and_keeps_coconut_in_nuts(db):
    result = _import(db)
    assert result["imported"] > 600
    assert result["converted_bales"] > 0          # Punjab cotton and Assam jute
    assert result["kept_as_nuts"] > 0             # Kerala coconut
    cotton = db.query(CropProduction).filter_by(state="PUNJAB", district="LUDHIANA", crop="Cotton(lint)",
                                                year_label="1999-00", season="Kharif").one()
    assert cotton.production_unit == "tonnes"
    assert float(cotton.production_tonnes) == 2000 * 170 / 1000   # 2000 bales of 170 kg
    coconut = db.query(CropProduction).filter_by(crop="Coconut").first()
    assert coconut.production_unit == "nuts"


def test_crop_insights_has_only_plausible_yields_and_reports_data_age(client, db):
    _import(db)
    status = client.get("/api/crops/status").json()
    assert status["latest_year"] == 2012 and status["is_old"] is True and status["data_age_years"] >= 10
    body = client.get("/api/crops/history", params={"state": "PUNJAB", "district": "LUDHIANA"}).json()
    cotton = next(c for c in body["crops"] if c["crop"] == "Cotton(lint)")
    assert cotton["latest_yield_tonnes_per_ha"] < 3            # lint yield, not bales per hectare
    assert cotton["production_unit_note"] == "converted_from_bales"
    kerala = client.get("/api/crops/history", params={"state": "KERALA", "district": "KOZHIKODE"}).json()
    assert "Coconut" in kerala["crops_without_tonnes"]
    assert all(c["crop"] != "Coconut" for c in kerala["crops"])


def test_planner_accepts_current_district_names_and_flags_old_data(client, db):
    _import(db)
    body = {"farm_ref": "test-farm-reference-1234567", "state": "Punjab", "district": "Bathinda",
            "current_crop": "Wheat", "current_season": "Rabi", "target_season": "Kharif", "area_ha": 2}
    result = client.post("/api/planning/recommendations", json=body).json()
    assert result["status"] == "ok"
    assert result["crop_data_latest_year"] == 2012
    assert any(code["code"] == "crop_data_old" for code in result["data_gap_codes"])
    assert result["ranked"] is False and result["rank_basis"] == "recent_area_in_district_not_a_recommendation"
    cotton = next(c for c in result["candidates"] if c["canonical_crop"] == "cotton")
    assert cotton["historical_yield_t_per_ha_median"] < 3
    mansa = client.post("/api/planning/recommendations", json={**body, "district": "Mansa"}).json()
    assert mansa["status"] == "ok"


def test_zaid_matches_the_datasets_summer_season(client, db):
    _import(db)
    body = {"farm_ref": "test-farm-reference-1234567", "state": "Assam", "district": "Nagaon",
            "current_crop": "Jute", "current_season": "", "target_season": "Zaid", "area_ha": 1}
    result = client.post("/api/planning/recommendations", json=body).json()
    assert result["status"] == "ok", result
