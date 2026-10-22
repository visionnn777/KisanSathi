"""Crop recommendation and harvest-cost recording tests using a temporary database."""
from datetime import date, timedelta
from app.models import CropProduction, FarmSeasonRecord, MandiPrice, MandiPriceHistory


def _add_crop_history(db):
    rows = []
    for year in range(2021, 2026):
        suffix = str(year + 1)[-2:]
        rows.extend([
            CropProduction(state="Punjab", district="Ludhiana", crop="Wheat", year_label=f"{year}-{suffix}", year_start=year, season="Rabi", area_ha=100, production_tonnes=430 + (year-2021)*5, source="test"),
            CropProduction(state="Punjab", district="Ludhiana", crop="Maize", year_label=f"{year}-{suffix}", year_start=year, season="Kharif", area_ha=60, production_tonnes=210 + (year-2021)*3, source="test"),
            CropProduction(state="Punjab", district="Ludhiana", crop="Soybean", year_label=f"{year}-{suffix}", year_start=year, season="Kharif", area_ha=40, production_tonnes=80 + (year-2021)*2, source="test"),
            CropProduction(state="Punjab", district="Ludhiana", crop="Rice", year_label=f"{year}-{suffix}", year_start=year, season="Kharif", area_ha=75, production_tonnes=300, source="test"),
        ])
    db.add_all(rows)
    db.commit()


def _add_prices(db):
    today = date.today()
    for crop, price in (("Wheat", 2400), ("Maize", 2200), ("Soybean", 4200), ("Rice", 2900)):
        db.add(MandiPrice(state="Punjab", district="Ludhiana", market="Khanna", commodity=crop, variety="FAQ", grade="FAQ",
                          arrival_date=today, min_price=price-100, max_price=price+100, modal_price=price, source="mandi-api"))
        if crop in ("Maize", "Soybean"):
            db.add_all([
                MandiPriceHistory(state="Punjab", commodity=crop, observation_date=today - timedelta(days=390 - idx * 10),
                    average_modal_price=price + ((idx % 5) - 2) * 45, min_modal_price=price-100,
                    max_modal_price=price+100, markets_count=4, source="mandi-api-history")
                for idx in range(40)
            ])
    db.commit()


def test_crop_planner_uses_local_history_current_dated_prices_and_separate_historical_series(client, db):
    _add_crop_history(db)
    _add_prices(db)
    response = client.post("/api/planning/recommendations", json={
        "farm_ref": "test-farm-reference-1234567", "state": "Punjab", "district": "Ludhiana",
        "current_crop": "Wheat", "current_season": "Rabi", "target_season": "Kharif", "area_ha": 1.5,
        "actual_yield_t_per_ha": 3.2, "actual_sale_price_rs_per_qtl": 2200, "current_cost_rs_per_ha": 32000,
        "candidate_costs_rs_per_ha": {"Maize": 26000, "Soybean": 30000},
        "primary_issue": "low_yield", "water_availability": "limited", "soil_type": "loamy", "soil_ph": 6.5,
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["current_crop_assessment"]["yield_gap_pct_vs_local_median"] is not None
    candidates = {item["canonical_crop"]: item for item in payload["candidates"]}
    assert "maize" in candidates and "soybean" in candidates
    maize = candidates["maize"]
    assert maize["latest_mandi_price_rs_per_qtl"] == 2200
    assert maize["historical_price_observations"] == 40
    assert maize["historical_price_median_rs_per_qtl"] is not None
    assert maize["historical_price_sufficient_for_estimate"] is True
    # Kharif target: the price comes from Oct–Jan history when there is enough of it.
    assert maize["reference_price_basis"] in {"historical_state_aggregate_median_harvest_months",
                                              "historical_state_aggregate_median_all_dates_not_season_specific"}
    assert maize["estimated_gross_revenue_rs_per_ha"] == round(maize["historical_yield_t_per_ha_median"] * 10 * maize["reference_price_for_estimate_rs_per_qtl"], 2)
    assert maize["estimated_net_return_rs_per_ha"] == round(maize["estimated_gross_revenue_rs_per_ha"] - 26000, 2)
    # About half of India's rice is rainfed: with limited water, rice gets a caution, not an exclusion.
    rice = candidates["rice"]
    assert rice["water_fit"] == "rainfed_rice_caution"
    assert any(code["code"] == "rainfed_rice" for code in rice["data_gap_codes"])
    assert payload["ranked"] is True
    status = client.get("/api/prices/status").json()
    assert status["historical_price_series"]["rows"] == 80


def test_planner_returns_missing_data_without_inventing_alternatives(client):
    response = client.post("/api/planning/recommendations", json={
        "farm_ref": "test-farm-reference-1234567", "state": "Punjab", "district": "Unknown district",
        "current_crop": "Wheat", "current_season": "Rabi", "target_season": "Kharif", "area_ha": 1,
        "primary_issue": "unknown", "water_availability": "unknown", "soil_type": "unknown",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "data_missing"
    assert response.json()["candidates"] == []


def test_save_harvest_record_sums_cost_categories_and_returns_them(client, db):
    response = client.post("/api/planning/records", json={
        "farm_ref": "test-farm-reference-1234567", "state": "Punjab", "district": "Ludhiana", "crop": "Wheat",
        "season": "Rabi", "year_start": 2025, "area_ha": 2.0, "harvested_tonnes": 7.0,
        "sale_price_rs_per_qtl": 2300, "seed_cost_rs_per_ha": 10000, "fertiliser_cost_rs_per_ha": 12000,
        "crop_protection_cost_rs_per_ha": 2000, "labour_cost_rs_per_ha": 8000,
        "irrigation_cost_rs_per_ha": 3000, "machinery_cost_rs_per_ha": 2000,
        "harvest_cost_rs_per_ha": 4000, "transport_cost_rs_per_ha": 1000,
    })
    assert response.status_code == 200, response.text
    record = response.json()["record"]
    assert record["yield_t_per_ha"] == 3.5
    assert record["cultivation_cost_rs_per_ha"] == 42000
    assert record["seed_cost_rs_per_ha"] == 10000
    assert db.query(FarmSeasonRecord).count() == 1


def test_save_harvest_record_rejects_conflicting_total_and_parts(client):
    response = client.post("/api/planning/records", json={
        "farm_ref": "test-farm-reference-1234567", "state": "Punjab", "district": "Ludhiana", "crop": "Wheat",
        "season": "Rabi", "year_start": 2025, "area_ha": 1, "yield_t_per_ha": 4.0,
        "cultivation_cost_rs_per_ha": 100000, "seed_cost_rs_per_ha": 10000, "labour_cost_rs_per_ha": 8000,
    })
    assert response.status_code == 422


def test_planner_does_not_use_single_current_quote_as_next_season_revenue(client, db):
    _add_crop_history(db)
    today = date.today()
    db.add(MandiPrice(state="Punjab", district="Ludhiana", market="Khanna", commodity="Maize", variety="FAQ", grade="FAQ",
                      arrival_date=today, min_price=2100, max_price=2300, modal_price=2200, source="mandi-api"))
    db.commit()
    response = client.post("/api/planning/recommendations", json={
        "farm_ref": "test-farm-reference-1234567", "state": "Punjab", "district": "Ludhiana",
        "current_crop": "Wheat", "current_season": "Rabi", "target_season": "Kharif", "area_ha": 1.0,
        "candidate_costs_rs_per_ha": {"Maize": 26000}, "primary_issue": "low_price",
        "water_availability": "limited", "soil_type": "loamy"
    })
    assert response.status_code == 200, response.text
    maize = next(item for item in response.json()["candidates"] if item["canonical_crop"] == "maize")
    assert maize["latest_mandi_price_rs_per_qtl"] == 2200
    assert maize["historical_price_sufficient_for_estimate"] is False
    assert maize["estimated_gross_revenue_rs_per_ha"] is None
    assert maize["estimated_net_return_rs_per_ha"] is None
