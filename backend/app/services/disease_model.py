"""Loads the pretrained plant disease model once and runs predictions.

Owner: Member B

Model: wambugu71/crop_leaf_diseases_vit (Hugging Face) - maize, potato, rice, wheat,
plus an "Invalid" class for photos that are not crop leaves.
`python -m scripts.download_model` saves a copy in ml/model/ so the demo works offline.
"""
import hashlib
import io
import json
import logging
import threading
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from .. import config
from .model_artifacts import load_preprocessor_config, sha256_file

log = logging.getLogger("kisansaathi.model")

_classifier = None
_load_error = None
_lock = threading.Lock()


class ModelNotReady(Exception):
    """The model could not be loaded (packages missing, no internet on first run, ...)."""


def _has_local_model_artifacts() -> bool:
    """Return True if a local model download was started or exists but is not trusted."""
    directory = config.MODEL_DIR
    return directory.is_dir() and any(
        (directory / name).is_file()
        for name in ("config.json", "preprocessor_config.json", "model.safetensors",
                     "pytorch_model.bin", "model_manifest.json")
    )


def model_source() -> str:
    """Use a local model only when its manifest, JSON configs, labels and hashes match.

    A legacy folder without a manifest is deliberately ignored: it could contain weights
    whose label ordering does not match our advice mapping. Processor JSON is parsed and
    schema-checked here so a present-but-malformed file is never treated as installed.
    """
    manifest_path = config.MODEL_DIR / "model_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        model_config_path = config.MODEL_DIR / "config.json"
        processor_path = config.MODEL_DIR / "preprocessor_config.json"
        weight_name = manifest.get("weight_filename")
        weight_path = config.MODEL_DIR / weight_name if weight_name in {"model.safetensors", "pytorch_model.bin"} else None
        model_config = json.loads(model_config_path.read_text(encoding="utf-8")) if model_config_path.is_file() else {}
        raw_labels = model_config.get("id2label") or {}
        local_labels = [raw_labels[key] for key in sorted(raw_labels, key=lambda key: int(key))]
        # This validates both JSON syntax and the required image preprocessing schema.
        load_preprocessor_config(processor_path)
        checksum_matches = False
        if weight_path and weight_path.is_file() and manifest.get("weight_sha256"):
            checksum_matches = sha256_file(weight_path) == manifest.get("weight_sha256")
        config_hash_matches = not manifest.get("config_sha256") or (
            model_config_path.is_file() and sha256_file(model_config_path) == manifest.get("config_sha256")
        )
        processor_hash_matches = not manifest.get("preprocessor_config_sha256") or (
            processor_path.is_file() and sha256_file(processor_path) == manifest.get("preprocessor_config_sha256")
        )
        matches = (
            manifest.get("model_id") == config.MODEL_ID
            and manifest.get("revision") == config.MODEL_REVISION
            and manifest.get("label_mappings_complete") is True
            and bool(manifest.get("labels"))
            and local_labels == manifest.get("labels")
            and model_config_path.is_file()
            and processor_path.is_file()
            and checksum_matches
            and config_hash_matches
            and processor_hash_matches
        )
        if matches:
            return str(config.MODEL_DIR)
        log.warning("Ignoring local disease model: manifest, label order, revision or artifact checksums did not match.")
    except (OSError, ValueError, TypeError) as exc:
        if (config.MODEL_DIR / "config.json").exists() or manifest_path.exists():
            log.warning("Ignoring local disease model with invalid or incomplete artifacts: %s", exc)
    return config.MODEL_ID


def get_classifier():
    global _classifier, _load_error
    if _classifier is not None:
        return _classifier
    with _lock:
        if _classifier is None:
            try:
                from transformers import pipeline
            except ImportError as exc:
                _load_error = "Install torch and transformers (see README, step 'Install packages')."
                raise ModelNotReady(_load_error) from exc
            try:
                source = model_source()
                # If a project-local download exists but fails its manifest/config checks,
                # do not silently ignore it and trigger a confusing network/cache failure.
                if source == config.MODEL_ID and _has_local_model_artifacts():
                    _load_error = (
                        "The local disease model is incomplete, malformed, or failed its integrity checks. "
                        "Stop the server and run 'python -m scripts.download_model' from the backend folder."
                    )
                    raise ModelNotReady(_load_error)
                kwargs = {"model": source}
                if source == config.MODEL_ID:
                    kwargs["revision"] = config.MODEL_REVISION
                _classifier = pipeline("image-classification", **kwargs)
                _load_error = None
                log.info("Disease model loaded from %s", source)
            except ModelNotReady:
                raise
            except Exception as exc:  # network down, corrupt Hub cache, missing files, ...
                _load_error = (
                    f"Could not load the model from {model_source()}: {exc}. "
                    "If this is a fresh setup, run 'python -m scripts.download_model' from backend."
                )
                raise ModelNotReady(_load_error) from exc
    return _classifier


def warm_up():
    """Load the model in the background when the server starts, so the first photo is fast."""
    try:
        get_classifier()
    except ModelNotReady as exc:
        log.warning("Disease model not ready yet: %s", exc)


def status() -> str:
    if _classifier is not None:
        return "ready"
    return "error" if _load_error else "not loaded"


def load_image(image_bytes: bytes) -> Image.Image:
    """Open the photo, fix phone rotation, convert to RGB. Raises ValueError if not an image."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(image_bytes))
            if image.width < 32 or image.height < 32:
                raise ValueError("The photo is too small. Please take a clear close-up of one leaf.")
            if image.width * image.height > 40_000_000:
                raise ValueError("The photo is too large in pixel dimensions. Please resize it and try again.")
            image.load()  # Force decoding while the decompression-bomb guard is active.
            image = ImageOps.exif_transpose(image)
            return image.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("The photo is"):
            raise
        raise ValueError("This file is not a safe, readable photo. Please send a JPG or PNG leaf image.") from exc


# A leaf photo, healthy or diseased, is mostly green, yellow or brown plant tissue. Selfies, sky,
# documents and most indoor scenes are not. This is a simple colour check (not a second model):
# it only blocks photos with almost no plant-coloured pixels, which the model's "Invalid" class
# alone does not reliably catch.
PLANT_HUE_MIN, PLANT_HUE_MAX = 14, 120          # PIL hue scale 0-255, roughly 20 to 170 degrees
PLANT_MIN_SATURATION, PLANT_MIN_BRIGHTNESS = 38, 31
MIN_PLANT_SHARE = 0.10


def plant_pixel_share(image: Image.Image) -> float:
    """Share of pixels (0-1) whose colour could be plant tissue."""
    small = image.convert("RGB").resize((64, 64)).convert("HSV")
    pixels = list(small.getdata())
    plant = sum(1 for h, s, v in pixels
                if PLANT_HUE_MIN <= h <= PLANT_HUE_MAX and s >= PLANT_MIN_SATURATION and v >= PLANT_MIN_BRIGHTNESS)
    return plant / len(pixels) if pixels else 0.0


def analyse(image_bytes: bytes, top_k: int = 3) -> tuple[list[dict], float]:
    """Model results (best first) plus the share of plant-coloured pixels in the photo."""
    image = load_image(image_bytes)
    classifier = get_classifier()
    return classifier(image, top_k=top_k), plant_pixel_share(image)


def predict(image_bytes: bytes, top_k: int = 3):
    """Returns a list like [{"label": "...", "score": 0.0-1.0}, ...], best first."""
    return analyse(image_bytes, top_k)[0]
