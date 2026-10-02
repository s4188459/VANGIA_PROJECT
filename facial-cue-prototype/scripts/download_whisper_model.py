from __future__ import annotations

import argparse
from pathlib import Path
import sys

MODELS = ("tiny.en", "base.en", "small.en", "medium.en")


def model_output_path(model_name: str, root: Path = Path("models")) -> Path:
    if model_name not in MODELS:
        raise ValueError(f"Unsupported Whisper model: {model_name}")
    return root / f"faster-whisper-{model_name.replace('.', '-')}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Download a faster-whisper model for offline use")
    parser.add_argument("--model", default="small.en", choices=MODELS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or model_output_path(args.model)
    try:
        from huggingface_hub import snapshot_download
        repo = f"Systran/faster-whisper-{args.model}"
        path = snapshot_download(repo_id=repo, local_dir=str(output.resolve()))
    except Exception as exc:
        print(f"Error: could not download Whisper model: {exc}", file=sys.stderr); return 1
    print(f"Whisper model ready: {path}"); return 0


if __name__ == "__main__": raise SystemExit(main())
