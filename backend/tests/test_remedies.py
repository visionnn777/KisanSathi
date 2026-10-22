"""Owner: Member B. Every label style we expect from the model must find its advice."""
import pytest

from app.services.remedies import DISEASES, describe, match_label

CASES = {
    "Corn___Common_Rust": "corn_common_rust",
    "Corn Gray Leaf Spot": "corn_gray_leaf_spot",
    "Corn___Northern_Leaf_Blight": "corn_leaf_blight",
    "Corn___Healthy": "corn_healthy",
    "Potato___Early_Blight": "potato_early_blight",
    "Potato Late Blight": "potato_late_blight",
    "Potato___Healthy": "potato_healthy",
    "Rice___Brown_Spot": "rice_brown_spot",
    "Rice___Leaf_Blast": "rice_leaf_blast",
    "Rice Hispa": "rice_hispa",
    "Rice___Healthy": "rice_healthy",
    "Wheat___Brown_Rust": "wheat_brown_rust",
    "Wheat___Yellow_Rust": "wheat_yellow_rust",
    "Wheat___Healthy": "wheat_healthy",
    "Invalid": "invalid",
}


@pytest.mark.parametrize("label,expected", CASES.items())
def test_match_label(label, expected):
    assert match_label(label) == expected


def test_unknown_label():
    assert match_label("Tomato___Late_blight") is None
    assert describe("Tomato___Late_blight")["id"] == "unsure"


def test_every_entry_has_both_languages():
    for disease_id, info in DISEASES.items():
        assert info["name"]["en"] and info["name"]["hi"], disease_id
        assert len(info["advice"]["en"]) == len(info["advice"]["hi"]) >= 2, disease_id



def test_every_supported_disease_has_bilingual_management_sections():
    required_sections = ("immediate_steps", "prevention", "monitoring", "crop_care", "escalate_if", "chemical_safety")
    for label, expected in CASES.items():
        if expected == "invalid":
            continue
        result = describe(label)
        assert result["id"] == expected
        for section in required_sections:
            assert result["management"][section]["en"], (label, section, "en")
            assert result["management"][section]["hi"], (label, section, "hi")
        assert result["sources"]


def test_uncertain_result_does_not_offer_specific_chemical_or_crop_diagnosis():
    result = describe("a blurry photo of a cup")
    assert result["id"] == "unsure"
    assert "does not prescribe" in " ".join(result["management"]["chemical_safety"]["en"]).lower()
    assert result["management"]["crop_care"]["hi"]
