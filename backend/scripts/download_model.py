"""Download, repair (only the known upstream defect), validate, and install the model.

Run from backend/: python -m scripts.download_model
Optional image smoke test: python -m scripts.download_model --test path/to/leaf.jpg

The model is staged in a temporary directory and validated before replacing the current
local copy, so a failed download does not destroy a working installed model.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.services.model_artifacts import (
    load_preprocessor_config,
    repair_known_preprocessor_config,
    sha256_file,
)
from app.services.remedies import match_label

MODEL_FILES = ["config.json", "preprocessor_config.json", "model.safetensors", "pytorch_model.bin"]


def _get_labels(model) -> tuple[list[str], list[str]]:
    labels_by_id = model.config.id2label or {}
    try:
        ordered = [labels_by_id[key] for key in sorted(labels_by_id, key=lambda value: int(value))]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("The model config has an invalid id2label mapping.") from exc
    if not ordered:
        raise ValueError("The model config has no id2label entries.")
    unmatched = [label for label in ordered if match_label(label) is None]
    return ordered, unmatched


def _weight_file(directory: Path) -> Path:
    for name in ("model.safetensors", "pytorch_model.bin"):
        candidate = directory / name
        if candidate.is_file() and candidate.stat().st_size > 1024:
            return candidate
    raise FileNotFoundError("Downloaded model weights are missing or unexpectedly small.")


def _promote_staged_directory(staging: Path, target: Path) -> None:
    """Replace target only after the staged model passed validation; restore on failure."""
    target.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if target.exists():
        if not target.is_dir():
            raise NotADirectoryError(f"Expected model directory, got a file: {target}")
        backup = target.with_name(f".{target.name}.backup-{os.getpid()}")
        if backup.exists():
            shutil.rmtree(backup)
        os.replace(target, backup)
    try:
        os.replace(staging, target)
    except Exception:
        if backup is not None and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    else:
        if backup is not None and backup.exists():
            shutil.rmtree(backup)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Download and check the disease model")
    parser.add_argument("--test", type=Path, help="Leaf photo to classify after the staged model is loaded")
    args = parser.parse_args(argv)

    try:
        from huggingface_hub import snapshot_download
        from transformers import AutoImageProcessor, AutoModelForImageClassification, pipeline
    except ImportError as exc:
        print(
            "ERROR: required Hugging Face packages are missing. Activate .venv and run "
            "'pip install -r requirements.txt'. Install the CPU/GPU torch build first.",
            file=sys.stderr,
        )
        return 1

    target = Path(config.MODEL_DIR).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {config.MODEL_ID} at pinned revision {config.MODEL_REVISION} ...")
    print(f"The existing installed model will be preserved unless the new copy passes validation.")

    with tempfile.TemporaryDirectory(prefix=f".{target.name}.staging-", dir=str(target.parent)) as temp_root:
        staging = Path(temp_root) / "model"
        staging.mkdir(parents=True, exist_ok=True)
        try:
            snapshot_download(
                repo_id=config.MODEL_ID,
                revision=config.MODEL_REVISION,
                local_dir=str(staging),
                allow_patterns=MODEL_FILES,
            )
            # The Hub's local_dir metadata is not needed after the selected model files are downloaded.
            hub_metadata = staging / ".cache"
            if hub_metadata.exists():
                shutil.rmtree(hub_metadata)

            processor_config_path = staging / "preprocessor_config.json"
            repaired = repair_known_preprocessor_config(
                processor_config_path,
                model_id=config.MODEL_ID,
                revision=config.MODEL_REVISION,
            )
            if repaired:
                print(
                    "WARNING: repaired the known missing outer brace in the pinned upstream "
                    "preprocessor_config.json. The repair was applied only to the local staged copy."
                )

            # Validate both files before letting Transformers parse them.
            load_preprocessor_config(processor_config_path)
            with (staging / "config.json").open("r", encoding="utf-8") as file:
                model_config = json.load(file)
            if not isinstance(model_config.get("id2label"), dict):
                raise ValueError("Downloaded config.json does not contain an id2label mapping.")

            processor = AutoImageProcessor.from_pretrained(str(staging), local_files_only=True)
            model = AutoModelForImageClassification.from_pretrained(str(staging), local_files_only=True)
            labels, unmatched = _get_labels(model)
            print("Labels in the pinned model revision:")
            for index, label in enumerate(labels):
                matched = match_label(label)
                print(f"  {index:>2}  {label:<40} -> {matched or 'NO MATCH'}")
            if unmatched:
                print("ERROR: add advice/label rules before considering these classes supported:", file=sys.stderr)
                for label in unmatched:
                    print(f"  - {label}", file=sys.stderr)
                return 2

            # Serialise the processor and weights from validated in-memory objects, ensuring
            # the installed local config is valid even though the upstream config was malformed.
            processor.save_pretrained(str(staging))
            model.save_pretrained(str(staging), safe_serialization=True)
            del processor, model

            processor_config = load_preprocessor_config(staging / "preprocessor_config.json")
            with (staging / "config.json").open("r", encoding="utf-8") as file:
                saved_config = json.load(file)
            saved_labels_map = saved_config.get("id2label") or {}
            saved_labels = [saved_labels_map[key] for key in sorted(saved_labels_map, key=lambda value: int(value))]
            if saved_labels != labels:
                raise ValueError("The saved model label order differs from the downloaded model label order.")

            weight_path = _weight_file(staging)
            # Run the same pipeline-loading route used by the web app, but against staging.
            classifier = pipeline("image-classification", model=str(staging))
            if args.test:
                from app.services.disease_model import load_image
                image = load_image(args.test.read_bytes())
                predictions = classifier(image, top_k=3)
                print("Smoke-test predictions:")
                for result in predictions:
                    print(f"  {result['label']:<40} {result['score'] * 100:5.1f}%")
            del classifier

            manifest = {
                "format_version": 2,
                "model_id": config.MODEL_ID,
                "revision": config.MODEL_REVISION,
                "repository_license_metadata": "MIT",
                "license_note": "Verify before public/commercial use: the model card text may conflict with repository metadata.",
                "label_mappings_complete": True,
                "labels": labels,
                "weight_filename": weight_path.name,
                "weight_sha256": sha256_file(weight_path),
                "config_sha256": sha256_file(staging / "config.json"),
                "preprocessor_config_sha256": sha256_file(staging / "preprocessor_config.json"),
                "preprocessor_config_validated": True,
                "upstream_preprocessor_repaired": repaired,
                "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            (staging / "model_manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            _promote_staged_directory(staging, target)
        except Exception as exc:
            print(f"ERROR: model download/validation failed: {exc}", file=sys.stderr)
            print(
                "The previous installed model (if any) was preserved. Check internet access, "
                "available disk space, and the error above; do not manually edit the Hub cache.",
                file=sys.stderr,
            )
            return 1

    print(f"Installed validated model to: {target}")
    print("Wrote model_manifest.json with the pinned revision, ordered labels and integrity hashes.")
    print("SUCCESS: processor config, model weights, labels and inference pipeline passed validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
