"""Regression tests for the pinned model's malformed upstream processor JSON."""
import json

import pytest

from app.services.model_artifacts import (
    KNOWN_BROKEN_MODEL_ID,
    KNOWN_BROKEN_REVISION,
    load_preprocessor_config,
    repair_known_preprocessor_config,
)

# Mirrors the 324-byte file shown at the exact pinned Hugging Face revision: the
# size object closes, but the outer JSON object does not.
KNOWN_MALFORMED_CONFIG = '''{
"do_normalize": true,
"do_rescale": true,
"do_resize": true,
"image_mean": [
0.5,
0.5,
0.5
],
"image_processor_type": "ViTFeatureExtractor",
"image_std": [
0.5,
0.5,
0.5
],
"resample": 2,
"rescale_factor": 0.00392156862745098,
"size": {
"height": 224,
"width": 224
}'''


def test_repairs_only_the_known_missing_outer_brace(tmp_path):
    path = tmp_path / "preprocessor_config.json"
    path.write_text(KNOWN_MALFORMED_CONFIG, encoding="utf-8")

    repaired = repair_known_preprocessor_config(
        path, model_id=KNOWN_BROKEN_MODEL_ID, revision=KNOWN_BROKEN_REVISION
    )

    assert repaired is True
    loaded = load_preprocessor_config(path)
    assert loaded["image_processor_type"] == "ViTFeatureExtractor"
    assert loaded["size"] == {"height": 224, "width": 224}
    assert path.read_text(encoding="utf-8").rstrip().endswith("}")
    # A second run is idempotent and does not rewrite valid JSON.
    before = path.read_bytes()
    assert repair_known_preprocessor_config(
        path, model_id=KNOWN_BROKEN_MODEL_ID, revision=KNOWN_BROKEN_REVISION
    ) is False
    assert path.read_bytes() == before


def test_does_not_repair_an_unrelated_model_or_revision(tmp_path):
    path = tmp_path / "preprocessor_config.json"
    path.write_text(KNOWN_MALFORMED_CONFIG, encoding="utf-8")

    with pytest.raises(ValueError, match="no safe repair"):
        repair_known_preprocessor_config(
            path, model_id="other/model", revision=KNOWN_BROKEN_REVISION
        )

    with pytest.raises(ValueError, match="no safe repair"):
        repair_known_preprocessor_config(
            path, model_id=KNOWN_BROKEN_MODEL_ID, revision="main"
        )
    assert path.read_text(encoding="utf-8") == KNOWN_MALFORMED_CONFIG


def test_refuses_malformed_config_that_is_not_fixed_by_one_brace(tmp_path):
    path = tmp_path / "preprocessor_config.json"
    path.write_text('{"size": {"height": 224,, "width": 224}', encoding="utf-8")

    with pytest.raises(ValueError, match="does not match the known missing-outer-brace defect"):
        repair_known_preprocessor_config(
            path, model_id=KNOWN_BROKEN_MODEL_ID, revision=KNOWN_BROKEN_REVISION
        )


def test_valid_but_wrong_schema_is_rejected(tmp_path):
    path = tmp_path / "preprocessor_config.json"
    path.write_text(json.dumps({"image_processor_type": "Unknown", "size": {"height": 224, "width": 224}}), encoding="utf-8")

    with pytest.raises(ValueError, match="unexpected image_processor_type"):
        repair_known_preprocessor_config(
            path, model_id=KNOWN_BROKEN_MODEL_ID, revision=KNOWN_BROKEN_REVISION
        )


def test_download_script_repairs_and_installs_staged_model(tmp_path, monkeypatch):
    """Exercise the real downloader flow without network access or ML dependencies."""
    import sys
    import types
    from pathlib import Path

    from app import config
    from scripts import download_model

    target = tmp_path / "installed-model"
    target.mkdir()
    (target / "keep-until-success.txt").write_text("old install", encoding="utf-8")
    monkeypatch.setattr(config, "MODEL_DIR", target)
    monkeypatch.setattr(config, "MODEL_ID", KNOWN_BROKEN_MODEL_ID)
    monkeypatch.setattr(config, "MODEL_REVISION", KNOWN_BROKEN_REVISION)

    model_config = {"id2label": {"0": "Wheat___Healthy"}}
    valid_processor = {
        "do_normalize": True, "do_rescale": True, "do_resize": True,
        "image_mean": [0.5, 0.5, 0.5], "image_std": [0.5, 0.5, 0.5],
        "image_processor_type": "ViTImageProcessor", "resample": 2,
        "rescale_factor": 1 / 255, "size": {"height": 224, "width": 224},
    }

    def fake_snapshot_download(*, repo_id, revision, local_dir, allow_patterns):
        assert repo_id == KNOWN_BROKEN_MODEL_ID
        assert revision == KNOWN_BROKEN_REVISION
        folder = Path(local_dir)
        (folder / "config.json").write_text(json.dumps(model_config), encoding="utf-8")
        (folder / "preprocessor_config.json").write_text(KNOWN_MALFORMED_CONFIG, encoding="utf-8")
        (folder / "model.safetensors").write_bytes(b"x" * 2048)
        return str(folder)

    class FakeProcessor:
        def save_pretrained(self, directory):
            (Path(directory) / "preprocessor_config.json").write_text(json.dumps(valid_processor), encoding="utf-8")

    class FakeModel:
        config = types.SimpleNamespace(id2label={"0": "Wheat___Healthy"})

        def save_pretrained(self, directory, safe_serialization=True):
            (Path(directory) / "config.json").write_text(json.dumps(model_config), encoding="utf-8")
            (Path(directory) / "model.safetensors").write_bytes(b"valid-weight" * 200)

    class FakeAutoImageProcessor:
        @staticmethod
        def from_pretrained(directory, local_files_only=False):
            # Ensure the known upstream config was repaired before Transformers loads it.
            load_preprocessor_config(Path(directory) / "preprocessor_config.json")
            return FakeProcessor()

    class FakeAutoModel:
        @staticmethod
        def from_pretrained(directory, local_files_only=False):
            return FakeModel()

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.snapshot_download = fake_snapshot_download
    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoImageProcessor = FakeAutoImageProcessor
    fake_transformers.AutoModelForImageClassification = FakeAutoModel
    fake_transformers.pipeline = lambda *args, **kwargs: (lambda image, top_k=3: [])
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    assert download_model.main([]) == 0
    manifest = json.loads((target / "model_manifest.json").read_text(encoding="utf-8"))
    assert manifest["upstream_preprocessor_repaired"] is True
    assert manifest["preprocessor_config_validated"] is True
    assert manifest["weight_sha256"]
    assert load_preprocessor_config(target / "preprocessor_config.json")["size"]["width"] == 224
    assert not (target / "keep-until-success.txt").exists()


def test_download_failure_preserves_existing_install(tmp_path, monkeypatch):
    import sys
    import types

    from app import config
    from scripts import download_model

    target = tmp_path / "installed-model"
    target.mkdir()
    marker = target / "known-good-marker.txt"
    marker.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(config, "MODEL_DIR", target)

    fake_hub = types.ModuleType("huggingface_hub")
    def fail_download(**kwargs):
        raise RuntimeError("simulated offline network")
    fake_hub.snapshot_download = fail_download
    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoImageProcessor = object()
    fake_transformers.AutoModelForImageClassification = object()
    fake_transformers.pipeline = object()
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    assert download_model.main([]) == 1
    assert marker.read_text(encoding="utf-8") == "keep"
