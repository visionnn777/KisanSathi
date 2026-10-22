"""Validation helpers for local Hugging Face model artifacts.

The pinned wambugu71 revision has a known upstream defect: its
``preprocessor_config.json`` is missing the final brace for the outer JSON object.
The repair below is deliberately limited to that exact repository/revision and only
accepts a one-character, schema-valid repair. It must never become a generic JSON fixer.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

KNOWN_BROKEN_MODEL_ID = "wambugu71/crop_leaf_diseases_vit"
KNOWN_BROKEN_REVISION = "2b77473a26a2974a9bfb7f0c7880ed84f9b302df"
_ALLOWED_PROCESSOR_TYPES = {"ViTFeatureExtractor", "ViTImageProcessor"}


def validate_preprocessor_config(value: Any) -> dict[str, Any]:
    """Validate the essential shape of this model's image processor configuration."""
    if not isinstance(value, dict):
        raise ValueError("preprocessor_config.json must contain a JSON object")
    if value.get("image_processor_type") not in _ALLOWED_PROCESSOR_TYPES:
        raise ValueError("preprocessor_config.json has an unexpected image_processor_type")
    size = value.get("size")
    if not isinstance(size, dict) or size.get("height") != 224 or size.get("width") != 224:
        raise ValueError("preprocessor_config.json must specify a 224 x 224 image size")
    for flag in ("do_normalize", "do_rescale", "do_resize"):
        if not isinstance(value.get(flag), bool):
            raise ValueError(f"preprocessor_config.json is missing boolean {flag!r}")
    for key in ("image_mean", "image_std"):
        values = value.get(key)
        if (not isinstance(values, list) or len(values) != 3
                or any(not isinstance(x, (int, float)) or not math.isfinite(float(x)) for x in values)):
            raise ValueError(f"preprocessor_config.json must contain three numeric {key} values")
    rescale = value.get("rescale_factor")
    if not isinstance(rescale, (int, float)) or not math.isfinite(float(rescale)) or float(rescale) <= 0:
        raise ValueError("preprocessor_config.json has an invalid rescale_factor")
    return value


def load_preprocessor_config(path: str | Path) -> dict[str, Any]:
    """Read and schema-check a processor JSON file without modifying it."""
    p = Path(path)
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read valid JSON from {p}: {exc}") from exc
    return validate_preprocessor_config(value)


def repair_known_preprocessor_config(
    path: str | Path, *, model_id: str, revision: str
) -> bool:
    """Repair only the known missing outer brace. Return True if repaired.

    A valid config is only validated and is not rewritten. For malformed configs, the
    exact pinned model/revision is required; adding one brace must produce valid JSON
    and pass the strict schema checks above. Writes are atomic within the directory.
    """
    p = Path(path)
    try:
        original = p.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"Could not read downloaded processor config {p}: {exc}") from exc

    try:
        current = json.loads(original)
    except json.JSONDecodeError as original_error:
        if (model_id != KNOWN_BROKEN_MODEL_ID or revision != KNOWN_BROKEN_REVISION):
            raise ValueError(
                f"The processor config is malformed, and no safe repair is defined for "
                f"{model_id}@{revision}. Original parse error: {original_error}"
            ) from original_error
        repaired_text = original.rstrip() + "\n}\n"
        try:
            repaired = json.loads(repaired_text)
            validate_preprocessor_config(repaired)
        except (json.JSONDecodeError, ValueError) as repair_error:
            raise ValueError(
                "The pinned model's processor config is malformed in a way that does not "
                "match the known missing-outer-brace defect; refusing to guess a repair."
            ) from repair_error
        temporary = p.with_name(p.name + ".repair-tmp")
        try:
            temporary.write_text(json.dumps(repaired, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(temporary, p)
        finally:
            if temporary.exists():
                temporary.unlink()
        return True

    validate_preprocessor_config(current)
    return False


def sha256_file(path: str | Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
