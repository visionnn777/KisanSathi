from app.services.crop_catalog import canonical_crop, plausible_yield, to_tonnes


def test_exact_matching_keeps_different_crops_apart():
    assert canonical_crop("Sweet potato") == "sweet potato"
    assert canonical_crop("Potato") == "potato"
    assert canonical_crop("Black Gram (Urd Beans)(Whole)") == "black gram"
    assert canonical_crop("Green Gram (Moong)(Whole)") == "green gram"
    assert canonical_crop("Bengal Gram(Gram)(Whole)") == "chickpea"
    assert canonical_crop("Gram") == "chickpea"
    assert canonical_crop("Arhar (Tur/Red Gram)(Whole)") == "pigeon pea"
    assert canonical_crop("Rapeseed &Mustard") == "mustard"
    assert canonical_crop("Paddy(Dhan)(Common)") == "rice"
    assert canonical_crop("Cotton(lint)") == "cotton"
    assert canonical_crop("Bengal Gram Dal (Chana Dal)") != "chickpea"   # processed dal, different price
    assert canonical_crop("Wheat Atta") != "wheat"


def test_units_bales_and_nuts():
    assert to_tonnes("Cotton(lint)", 1000) == 170.0
    assert to_tonnes("Jute", 1000) == 180.0
    assert to_tonnes("Coconut", 5_000_000) is None
    assert to_tonnes("Wheat", 1000) == 1000.0
    assert to_tonnes("Cotton(lint)", 1000, "Tonnes") == 1000.0
    assert to_tonnes("Cotton(lint)", 1000, "Bales") == 170.0
    assert to_tonnes("Coconut", 1000, "Nuts") is None


def test_impossible_yields_are_rejected():
    assert plausible_yield("Wheat", 4.8) is True
    assert plausible_yield("Wheat", 25) is False
    assert plausible_yield("Sugarcane", 80) is True
