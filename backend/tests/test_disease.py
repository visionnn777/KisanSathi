"""Owner: Member B. Uses a fake model, so it runs without downloading anything."""
import io

import pytest
from PIL import Image

from app.services import disease_model


def leaf_jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (40, 140, 40)).save(buf, format="JPEG")
    return buf.getvalue()


def fake_classifier(results):
    def classify(image, top_k=3):
        assert image.mode == "RGB"
        return results[:top_k]
    return classify


@pytest.fixture
def use_fake_model(monkeypatch):
    def install(results):
        monkeypatch.setattr(disease_model, "get_classifier", lambda: fake_classifier(results))
    return install


def upload(client, data=None, name="leaf.jpg", ctype="image/jpeg"):
    return client.post("/api/disease/predict", files={"file": (name, data or leaf_jpeg(), ctype)})


def test_confident_disease(client, use_fake_model):
    use_fake_model([{"label": "Wheat___Yellow_Rust", "score": 0.93},
                    {"label": "Wheat___Brown_Rust", "score": 0.05},
                    {"label": "Wheat___Healthy", "score": 0.02}])
    body = upload(client).json()
    assert body["confident"] is True
    assert body["confidence"] == 93.0
    assert body["result"]["id"] == "wheat_yellow_rust"
    assert body["result"]["name"]["hi"] == "पीला रतुआ"
    assert body["result"]["advice"]["hi"]
    # Alternatives below 10% are noise and are hidden.
    assert body["alternatives"] == []
    assert body["uncertain_reason"] is None
    assert "1800-180-1551" in body["expert"]["en"]


def test_visible_alternative_and_close_call(client, use_fake_model):
    use_fake_model([{"label": "Wheat___Yellow_Rust", "score": 0.62},
                    {"label": "Wheat___Brown_Rust", "score": 0.30},
                    {"label": "Wheat___Healthy", "score": 0.08}])
    body = upload(client).json()
    assert body["confident"] is True
    assert [a["name"]["en"] for a in body["alternatives"]] == ["Brown rust"]
    use_fake_model([{"label": "Wheat___Yellow_Rust", "score": 0.61},
                    {"label": "Wheat___Brown_Rust", "score": 0.52}])
    body = upload(client).json()
    assert body["confident"] is False and body["uncertain_reason"] == "close_call"
    assert body["result"]["id"] == "unsure"


def test_photo_without_plant_colours_is_not_trusted(client, use_fake_model):
    use_fake_model([{"label": "Wheat___Healthy", "score": 0.97}, {"label": "Wheat___Brown_Rust", "score": 0.02}])
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (30, 60, 200)).save(buf, format="JPEG")   # a blue photo: sky, shirt, wall
    body = upload(client, data=buf.getvalue()).json()
    assert body["confident"] is False
    assert body["uncertain_reason"] == "not_leaf_like"
    assert body["plant_pixel_share"] < 0.1


def test_brown_diseased_leaf_still_counts_as_plant():
    brown = Image.new("RGB", (64, 64), (140, 90, 40))
    assert disease_model.plant_pixel_share(brown) > 0.9


def test_low_confidence_says_not_sure(client, use_fake_model):
    use_fake_model([{"label": "Rice___Brown_Spot", "score": 0.41}, {"label": "Rice___Leaf_Blast", "score": 0.39}])
    body = upload(client).json()
    assert body["confident"] is False
    assert body["result"]["id"] == "unsure"


def test_invalid_class_says_not_sure_even_if_high(client, use_fake_model):
    use_fake_model([{"label": "Invalid", "score": 0.98}])
    body = upload(client).json()
    assert body["confident"] is False and body["result"]["id"] == "unsure"


def test_not_an_image(client, use_fake_model):
    use_fake_model([{"label": "Invalid", "score": 1.0}])
    assert upload(client, data=b"hello", ctype="image/jpeg").status_code == 400
    assert upload(client, data=b"%PDF-1.4", name="a.pdf", ctype="application/pdf").status_code == 400


def test_too_large(client, use_fake_model, monkeypatch):
    use_fake_model([{"label": "Invalid", "score": 1.0}])
    from app import config
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0.0001)  # about 100 bytes
    assert upload(client).status_code == 413


def test_model_not_installed_gives_503(client, monkeypatch):
    def broken():
        raise disease_model.ModelNotReady("Install torch and transformers")
    monkeypatch.setattr(disease_model, "get_classifier", broken)
    r = upload(client)
    assert r.status_code == 503 and "torch" in r.json()["detail"]


def test_local_model_requires_matching_manifest(tmp_path, monkeypatch):
    import hashlib
    import json
    from app import config

    monkeypatch.setattr(config, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(config, "MODEL_ID", "example/model")
    monkeypatch.setattr(config, "MODEL_REVISION", "immutable-rev")
    (tmp_path / "config.json").write_text(json.dumps({"id2label": {"0": "Wheat___Healthy"}}), encoding="utf-8")
    (tmp_path / "preprocessor_config.json").write_text(json.dumps({
        "do_normalize": True, "do_rescale": True, "do_resize": True,
        "image_mean": [0.5, 0.5, 0.5], "image_std": [0.5, 0.5, 0.5],
        "image_processor_type": "ViTImageProcessor", "resample": 2,
        "rescale_factor": 1 / 255, "size": {"height": 224, "width": 224},
    }), encoding="utf-8")
    weight_bytes = b"test-weight-placeholder"
    (tmp_path / "model.safetensors").write_bytes(weight_bytes)
    weight_hash = hashlib.sha256(weight_bytes).hexdigest()

    # Existing weights without an integrity manifest must not be trusted.
    assert disease_model.model_source() == "example/model"
    (tmp_path / "model_manifest.json").write_text(json.dumps({
        "model_id": "example/model", "revision": "different-rev", "label_mappings_complete": True,
    }), encoding="utf-8")
    assert disease_model.model_source() == "example/model"

    (tmp_path / "model_manifest.json").write_text(json.dumps({
        "model_id": "example/model", "revision": "immutable-rev", "label_mappings_complete": True,
        "labels": ["Wheat___Healthy"], "weight_filename": "model.safetensors", "weight_sha256": weight_hash,
        "config_sha256": hashlib.sha256((tmp_path / "config.json").read_bytes()).hexdigest(),
        "preprocessor_config_sha256": hashlib.sha256((tmp_path / "preprocessor_config.json").read_bytes()).hexdigest(),
    }), encoding="utf-8")
    assert disease_model.model_source() == str(tmp_path)

    # A post-install change to preprocessing config invalidates the pinned manifest.
    (tmp_path / "preprocessor_config.json").write_text("{}", encoding="utf-8")
    assert disease_model.model_source() == "example/model"
