import csv
from pathlib import Path

from app.models import CropProduction
from app.services.crop_history import import_crop_csv


def make_csv(tmp_path: Path) -> Path:
    path = tmp_path / "crop_production.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "state", "district", "crop", "year", "season", "area", "production", "yield"
        ])
        writer.writeheader()
        writer.writerow({"state": "Punjab", "district": "Ludhiana", "crop": "Wheat",
                         "year": "2018-19", "season": "Rabi", "area": "100",
                         "production": "450", "yield": "4.5"})
        writer.writerow({"state": "Punjab", "district": "Ludhiana", "crop": "Wheat",
                         "year": "2019-20", "season": "Rabi", "area": "110",
                         "production": "495", "yield": "4.5"})
        # Duplicate observation is ignored by the import step.
        writer.writerow({"state": "Punjab", "district": "Ludhiana", "crop": "Wheat",
                         "year": "2019-20", "season": "Rabi", "area": "110",
                         "production": "495", "yield": "4.5"})
        writer.writerow({"state": "Punjab", "district": "Ludhiana", "crop": "Rice",
                         "year": "2019-20", "season": "Kharif", "area": "80",
                         "production": "320", "yield": "4.0"})
        # Invalid area is skipped.
        writer.writerow({"state": "Punjab", "district": "Ludhiana", "crop": "Rice",
                         "year": "2020-21", "season": "Kharif", "area": "0",
                         "production": "100", "yield": ""})
    return path


def test_crop_import_and_history_api(client, db, tmp_path):
    path = make_csv(tmp_path)
    result = import_crop_csv(db, path)
    assert result["imported"] == 3
    assert result["duplicates_skipped"] == 1
    assert db.query(CropProduction).count() == 3

    status = client.get("/api/crops/status").json()
    assert status["available"] is True
    assert status["rows"] == 3
    assert status["first_year"] == 2018
    assert status["latest_year"] == 2019
    assert status["license"] == "CC0-1.0"

    states = client.get("/api/crops/states").json()
    assert states == ["Punjab"]
    districts = client.get("/api/crops/districts", params={"state": "Punjab"}).json()
    assert districts == ["Ludhiana"]
    seasons = client.get("/api/crops/seasons", params={
        "state": "Punjab", "district": "Ludhiana"
    }).json()
    assert seasons == ["Kharif", "Rabi"]

    result = client.get("/api/crops/history", params={
        "state": "Punjab", "district": "Ludhiana", "season": "Rabi"
    }).json()
    assert result["count"] == 1
    wheat = result["crops"][0]
    assert wheat["crop"] == "Wheat"
    assert wheat["latest_year"] == "2019-20"
    assert wheat["latest_yield_tonnes_per_ha"] == 4.5
    assert result["historical_only"] is True


def test_crop_import_replaces_old_dataset_and_skips_duplicate(db, tmp_path):
    path = make_csv(tmp_path)
    first = import_crop_csv(db, path)
    assert first["imported"] == 3

    # Re-import should replace rows, not multiply them.
    second = import_crop_csv(db, path)
    assert second["imported"] == 3
    assert db.query(CropProduction).count() == 3


def test_bad_crop_csv_does_not_wipe_existing_data(db, tmp_path):
    from app.models import CropProduction
    db.add(CropProduction(
        state="Punjab", district="Ludhiana", crop="Wheat", year_label="2019-20",
        year_start=2019, season="Rabi", area_ha=100, production_tonnes=400,
        source="test"
    ))
    db.commit()
    bad = tmp_path / "bad.csv"
    bad.write_text("state,district\nPunjab,Ludhiana\n", encoding="utf-8")
    try:
        import_crop_csv(db, bad)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected invalid schema to raise ValueError")
    assert db.query(CropProduction).count() == 1


def test_empty_crop_history_endpoints(client):
    response = client.get("/api/crops/status")
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert client.get("/api/crops/states").json() == []


def test_crop_insights_frontend_is_served(client):
    response = client.get("/crops.html")
    assert response.status_code == 200
    assert "Crop Insights" in response.text


def test_all_seasons_uses_annual_total_instead_of_double_counting(db, client):
    """Use the source's annual aggregate when available; otherwise sum the seasons."""
    db.add_all([
        CropProduction(state="Punjab", district="Ludhiana", crop="Rice", year_label="2019-20",
                       year_start=2019, season="Kharif", area_ha=80, production_tonnes=320, source="test"),
        CropProduction(state="Punjab", district="Ludhiana", crop="Rice", year_label="2019-20",
                       year_start=2019, season="Rabi", area_ha=20, production_tonnes=70, source="test"),
        CropProduction(state="Punjab", district="Ludhiana", crop="Rice", year_label="2019-20",
                       year_start=2019, season="All seasons", area_ha=90, production_tonnes=360, source="test"),
    ])
    db.commit()
    response = client.get("/api/crops/history", params={"state": "Punjab", "district": "Ludhiana"})
    assert response.status_code == 200
    rice = response.json()["crops"][0]
    assert rice["crop"] == "Rice"
    assert rice["latest_area_ha"] == 90.0
    assert rice["latest_production_tonnes"] == 360.0
    assert rice["latest_yield_tonnes_per_ha"] == 4.0
    assert rice["observations"] == 1


def test_all_seasons_sums_distinct_season_rows_when_no_annual_total(db, client):
    db.add_all([
        CropProduction(state="Punjab", district="Ludhiana", crop="Rice", year_label="2019-20",
                       year_start=2019, season="Kharif", area_ha=80, production_tonnes=320, source="test"),
        CropProduction(state="Punjab", district="Ludhiana", crop="Rice", year_label="2019-20",
                       year_start=2019, season="Rabi", area_ha=20, production_tonnes=70, source="test"),
    ])
    db.commit()
    response = client.get("/api/crops/history", params={"state": "Punjab", "district": "Ludhiana"})
    rice = response.json()["crops"][0]
    assert rice["latest_area_ha"] == 100.0
    assert rice["latest_production_tonnes"] == 390.0
    assert rice["latest_yield_tonnes_per_ha"] == 3.9
    assert rice["latest_season"] == "All seasons (combined)"
