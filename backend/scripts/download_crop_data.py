"""Download the public CC0 Indian crop-history CSV without a government API key.

Run from backend/: python -m scripts.download_crop_data
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

import requests

from app import config
from app.services.crop_history import RAW_URL, validate_csv


def download(url: str, destination: Path, timeout: int = 60) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": "KisanSaathi-Hackathon/1.0"}) as response:
            response.raise_for_status()
            fd, temp_name = tempfile.mkstemp(prefix="crop_history_", suffix=".csv", dir=str(destination.parent))
            os.close(fd)
            temp_path = Path(temp_name)
            total = 0
            with temp_path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 128):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > 100 * 1024 * 1024:
                        raise ValueError("The downloaded CSV exceeded the 100 MB safety limit.")
                    output.write(chunk)
        if total < 100:
            raise ValueError("The downloaded response is unexpectedly small; refusing to replace the existing dataset.")
        validate_csv(temp_path)
        temp_path.replace(destination)
        return destination
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Download public Indian crop production history (CC0-1.0 mirror)")
    parser.add_argument("--url", default=config.CROP_HISTORY_URL or RAW_URL,
                        help="CSV URL (default is the documented CC0 repository raw file)")
    parser.add_argument("--output", type=Path, default=config.CROP_HISTORY_CSV,
                        help="Path to save the CSV")
    args = parser.parse_args(argv)
    print(f"Downloading crop history from {args.url}")
    try:
        path = download(args.url, args.output)
        print(f"Saved and validated: {path} ({path.stat().st_size:,} bytes)")
        print("Source is historical crop statistics, not a live feed; see README for attribution and limitations.")
        return 0
    except (requests.RequestException, OSError, ValueError) as exc:
        print(f"ERROR: crop dataset download failed: {exc}", file=sys.stderr)
        print("Check your internet connection or download the CSV manually from the source link in README.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
