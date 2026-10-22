"""Inspect a downloaded crop-disease CSV before attempting to train or integrate a model.

Run from backend/: python -m scripts.inspect_disease_csv ../data/crop_disease.csv
This deliberately does not assume a CSV contains images merely because it lists diseases.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

IMAGE_HINTS = ("image", "img", "photo", "picture", "filepath", "file_path", "file_name", "filename", "image_url", "image_path")
LABEL_HINTS = ("disease", "infection", "diagnosis", "class", "label", "condition", "symptom")


def inspect(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"CSV file does not exist: {path}")
    if path.stat().st_size == 0:
        raise ValueError("CSV file is empty.")

    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        if not headers:
            raise ValueError("No CSV header row was found.")
        image_columns = [h for h in headers if any(h.lower().replace(" ", "_").find(hint) >= 0 for hint in IMAGE_HINTS)]
        label_columns = [h for h in headers if any(hint in h.lower().replace(" ", "_") for hint in LABEL_HINTS)]
        rows = 0
        label_counts: dict[str, Counter] = {h: Counter() for h in label_columns}
        nonempty_image_refs = Counter()
        image_examples: dict[str, list[str]] = {h: [] for h in image_columns}
        for row in reader:
            rows += 1
            for column in label_columns:
                value = (row.get(column) or "").strip()
                if value:
                    label_counts[column][value] += 1
            for column in image_columns:
                value = (row.get(column) or "").strip()
                if value:
                    nonempty_image_refs[column] += 1
                    if len(image_examples[column]) < 3:
                        image_examples[column].append(value[:180])

    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "columns": headers,
        "rows": rows,
        "image_columns": image_columns,
        "label_columns": label_columns,
        "label_counts": label_counts,
        "nonempty_image_refs": nonempty_image_refs,
        "image_examples": image_examples,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inspect crop-disease CSV columns and label coverage")
    parser.add_argument("csv", type=Path, help="Path to the downloaded disease CSV")
    args = parser.parse_args(argv)
    try:
        result = inspect(args.csv)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"File: {result['path']}")
    print(f"Size: {result['bytes']:,} bytes | data rows: {result['rows']:,}")
    print("Columns: " + ", ".join(result["columns"]))
    print("Possible image/path columns: " + (", ".join(result["image_columns"]) or "NONE FOUND"))
    print("Possible disease/label columns: " + (", ".join(result["label_columns"]) or "NONE FOUND"))
    for column, counts in result["label_counts"].items():
        print(f"\nTop values in {column}:")
        for label, count in counts.most_common(20):
            print(f"  {count:>7,}  {label}")
    for column in result["image_columns"]:
        print(f"\nNon-empty references in {column}: {result['nonempty_image_refs'][column]:,}")
        for value in result["image_examples"][column]:
            print(f"  example: {value}")

    references = sum(result["nonempty_image_refs"].values())
    if not result["image_columns"] or not references:
        print("\nASSESSMENT: this CSV does not appear to contain usable image references. It may be descriptive metadata, not image-training data.")
        print("A CSV with disease names alone cannot train the current leaf-image classifier; image files and verified labels are required.")
    else:
        print("\nASSESSMENT: candidate image references found. Check that each referenced image is accessible, licensed for reuse, and correctly labelled before training.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
