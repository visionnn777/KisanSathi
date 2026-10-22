"""Measure the disease model on YOUR OWN labelled leaf photos (honest accuracy for judges).

Put photos in one folder per true label, for example:
    field_photos/wheat_yellow_rust/IMG_001.jpg
    field_photos/wheat_healthy/IMG_007.jpg
    field_photos/rice_leaf_blast/...
Folder names may be the app's ids (wheat_yellow_rust) or the model's labels (Wheat___Yellow_Rust).
Then, from backend/:
    python -m scripts.evaluate_model field_photos --report ../model_evaluation.md

The report gives overall accuracy, accuracy when the app was confident, how often it said
"not sure", and precision/recall per class, with the number of photos behind every figure.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

from app import config
from app.routers.disease import MIN_MARGIN
from app.services import disease_model
from app.services.remedies import match_label

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp"}


def evaluate(folder: Path, classify=None) -> dict:
    """classify(image_bytes) -> (results, plant_share); defaults to the real model."""
    classify = classify or (lambda data: disease_model.analyse(data, top_k=3))
    rows = []
    for class_dir in sorted(p for p in folder.iterdir() if p.is_dir()):
        truth = match_label(class_dir.name) or class_dir.name.lower()
        for image_path in sorted(class_dir.iterdir()):
            if image_path.suffix.lower() not in IMAGE_TYPES:
                continue
            try:
                results, share = classify(image_path.read_bytes())
            except ValueError as exc:
                rows.append({"file": str(image_path), "truth": truth, "predicted": "unreadable", "confident": False, "error": str(exc)})
                continue
            top = results[0]
            predicted = match_label(top["label"]) or top["label"]
            second = float(results[1]["score"]) if len(results) > 1 else 0.0
            confident = (share >= disease_model.MIN_PLANT_SHARE and predicted not in (None, "invalid")
                         and float(top["score"]) >= config.CONFIDENCE_MIN and float(top["score"]) - second >= MIN_MARGIN)
            rows.append({"file": str(image_path), "truth": truth, "predicted": predicted,
                         "score": float(top["score"]), "confident": confident})
    total = len(rows)
    correct = sum(r["truth"] == r["predicted"] for r in rows)
    confident_rows = [r for r in rows if r["confident"]]
    confident_correct = sum(r["truth"] == r["predicted"] for r in confident_rows)
    labels = sorted({r["truth"] for r in rows} | {r["predicted"] for r in rows})
    per_class = {}
    for label in labels:
        tp = sum(r["truth"] == label and r["predicted"] == label for r in rows)
        fp = sum(r["truth"] != label and r["predicted"] == label for r in rows)
        fn = sum(r["truth"] == label and r["predicted"] != label for r in rows)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
        per_class[label] = {"photos": tp + fn, "precision": precision, "recall": recall, "f1": f1}
    confusion: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        confusion[r["truth"]][r["predicted"]] += 1
    return {
        "photos": total, "accuracy": correct / total if total else None,
        "confident_share": len(confident_rows) / total if total else None,
        "accuracy_when_confident": confident_correct / len(confident_rows) if confident_rows else None,
        "per_class": per_class, "confusion": {k: dict(v) for k, v in confusion.items()}, "rows": rows,
    }


def _pct(value):
    return "—" if value is None else f"{value * 100:.1f}%"


def report_markdown(result: dict) -> str:
    lines = ["# Crop Doctor: accuracy on our own photos", "",
             f"Photos tested: **{result['photos']}**", "",
             f"- Top answer correct: **{_pct(result['accuracy'])}**",
             f"- App was confident on: {_pct(result['confident_share'])} of photos",
             f"- Correct when the app was confident: **{_pct(result['accuracy_when_confident'])}**", "",
             "| Class | Photos | Precision | Recall | F1 |", "| --- | --- | --- | --- | --- |"]
    for label, stats in sorted(result["per_class"].items()):
        lines.append(f"| {label} | {stats['photos']} | {_pct(stats['precision'])} | {_pct(stats['recall'])} | {_pct(stats['f1'])} |")
    lines += ["", "Small numbers of photos give rough figures; say how many photos each number is based on."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the disease model on labelled photo folders")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--report", type=Path, help="Write a Markdown report here")
    args = parser.parse_args(argv)
    if not args.folder.is_dir():
        print(f"ERROR: {args.folder} is not a folder", file=sys.stderr)
        return 1
    try:
        result = evaluate(args.folder)
    except disease_model.ModelNotReady as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    text = report_markdown(result)
    print(text)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
        print(f"Report saved to {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
