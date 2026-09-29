from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "face_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/latest/face_landmarker.task"
)
MINIMUM_MODEL_BYTES = 1_000_000


def download_model(target: Path = MODEL_PATH, *, force: bool = False) -> Path:
    if target.is_file() and target.stat().st_size >= MINIMUM_MODEL_BYTES and not force:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    request = Request(MODEL_URL, headers={"User-Agent": "facial-cue-prototype/1.0"})
    try:
        with urlopen(request, timeout=60) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output)
        if partial.stat().st_size < MINIMUM_MODEL_BYTES:
            raise RuntimeError("Downloaded model is unexpectedly small")
        partial.replace(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the MediaPipe Face Landmarker model")
    parser.add_argument("--force", action="store_true", help="replace an existing model")
    args = parser.parse_args()
    try:
        path = download_model(force=args.force)
    except Exception as exc:
        print(f"Error: could not download Face Landmarker model: {exc}", file=sys.stderr)
        return 1
    print(f"Face Landmarker model ready: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
