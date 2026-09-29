from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path


def _row(segment) -> dict:
    value = asdict(segment)
    value["source"] = segment.source.value
    return value


def replace_transcript_with_final(path: Path, segments) -> None:
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            if path.exists():
                with path.open(encoding="utf-8") as existing:
                    for line in existing:
                        if not line.strip(): continue
                        row = json.loads(line)
                        if row.get("phase", "live") != "final":
                            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            for segment in segments:
                handle.write(json.dumps(_row(segment), ensure_ascii=False) + "\n")
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


class TranscriptStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._handle = open(self.path, "x", encoding="utf-8", buffering=1)
        self.closed = False

    def append_live(self, segment) -> None:
        self._handle.write(json.dumps(_row(segment), ensure_ascii=False) + "\n")

    def write(self, segment) -> None:
        self.append_live(segment)

    def read_phase(self, phase: str) -> tuple[dict, ...]:
        if not self.closed: self._handle.flush()
        return tuple(
            row for row in (json.loads(line) for line in self.path.read_text("utf-8").splitlines())
            if row.get("phase", "live") == phase
        )

    def replace_with_final(self, segments) -> None:
        if not self.closed: self._handle.flush()
        if not self.closed:
            self._handle.close(); self.closed = True
        replace_transcript_with_final(self.path, segments)

    def close(self) -> None:
        if self.closed: return
        self.closed = True; self._handle.close()


class TranscriptWriter(TranscriptStore):
    """Compatibility name while orchestrator callers migrate."""
    def __init__(self, jsonl_path: Path, _srt_path: Path | None = None) -> None:
        super().__init__(jsonl_path)
