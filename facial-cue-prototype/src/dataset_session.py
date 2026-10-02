from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from copy import deepcopy
import json
import csv
from pathlib import Path
from typing import Any
from threading import RLock
from importlib.metadata import version, PackageNotFoundError
import platform

from .capture_types import CaptureRegion
from .session_clock import SessionClock
from .session_recorder import CsvSessionRecorder, RecordingError, _validate_directory
from .session_types import ComponentStatus, SessionOptions
from .landmark_timing import LandmarkTimingRecorder


class DatasetSession:
    def __init__(self, directory: Path, options: SessionOptions, region: CaptureRegion,
                 clock: SessionClock, raw: CsvSessionRecorder) -> None:
        self.directory = directory
        self.options = options
        self.region = region
        self.clock = clock
        self.landmark_timing = LandmarkTimingRecorder(clock)
        self._raw = raw
        self.session_path = directory / "session.json"
        self.manifest_path = self.session_path
        self._manifest_lock = RLock()
        self.closed = False
        self._video_map = None
        self._event_journal = None
        self._event_count = 0
        self._last_drop = {}
        self._manifest: dict[str, Any] = {
            "schema_version": "3.0",
            "status": "recording",
            "session_id": directory.name,
            "participant_id": options.participant_id or None,
            "started_at_local": clock.started_at_local,
            "ended_at_local": None,
            "duration_s": 0.0,
            "region": region.as_mss_region(),
            "options": {k: getattr(options, k) for k in ("video", "system_audio", "microphone", "transcript")},
            "consent": {"confirmed": options.consent_confirmed, "confirmed_at_local": clock.started_at_local},
            "components": {}, "warnings": [], "errors": [], "drops": {},
            "audio": {"file": None, "channels": {}, "intervals": []},
            "transcription": {"live": {}, "final": {"status": "not_started"}},
            "observable_events": [],
            "media_stats": {}, "drop_details": [],
            "runtime": {"python": platform.python_version(), "packages": {}},
            "interpretation_boundary": "Observable data only; no psychological or confusion inference.",
        }
        for package in ("mediapipe", "opencv-contrib-python", "faster-whisper", "ctranslate2", "mss", "numpy", "scipy"):
            try: self._manifest["runtime"]["packages"][package] = version(package)
            except PackageNotFoundError: pass
        self._write_manifest()

    @classmethod
    def create(cls, parent: Path, options: SessionOptions, region: CaptureRegion,
               clock: SessionClock, metadata: dict[str, Any] | None = None) -> "DatasetSession":
        folder = _validate_directory(Path(parent))
        numbers = [int(p.name[8:]) for p in folder.iterdir()
                   if p.is_dir() and p.name.startswith("session_") and p.name[8:].isdigit()]
        number = max(numbers, default=0) + 1
        while True:
            target = folder / f"session_{number:03d}"
            try:
                target.mkdir()
                break
            except FileExistsError:
                number += 1
        raw = None
        raw_handle = None
        try:
            raw_path = target / "features.csv"
            raw_handle = open(raw_path, "x", encoding="utf-8", newline="", buffering=1)
            raw = CsvSessionRecorder(raw_path, raw_handle)
            session = cls(target, options, region, clock, raw)
            if metadata:
                session._manifest["metadata"] = metadata
                session._write_manifest()
            return session
        except Exception:
            if raw_handle is not None:
                raw_handle.close()
            for child in target.glob("*"):
                child.unlink(missing_ok=True)
            target.rmdir()
            raise

    @property
    def path(self) -> Path: return self._raw.path
    @property
    def raw_path(self) -> Path: return self._raw.path
    @property
    def raw_row_count(self) -> int: return self._raw.row_count
    @property
    def event_row_count(self) -> int: return self._event_count

    def _write_manifest(self) -> None:
        with self._manifest_lock:
            temp = self.session_path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(self._manifest, indent=2, ensure_ascii=True), encoding="utf-8")
            temp.replace(self.session_path)

    def write_feature(self, frame) -> None: self._raw.write(frame)

    def record_video_mapping(self, source_index: int, video_index: int) -> None:
        with self._manifest_lock:
            if self.closed:
                raise RecordingError("Dataset is closed; late video mapping rejected")
            if self._video_map is None:
                self._video_map = (self.directory / "video-map.tmp").open("x", encoding="ascii", newline="")
            csv.writer(self._video_map).writerow((source_index, video_index))

    def _finalize_video_mapping(self) -> None:
        if self._video_map is None: return
        self._video_map.close()
        mapping_path = self.directory / "video-map.tmp"
        temporary = self.raw_path.with_suffix(".csv.tmp")
        try:
            with mapping_path.open(newline="") as mappings, self.raw_path.open(newline="", encoding="utf-8") as raw, temporary.open("w", newline="", encoding="utf-8") as output:
                mapping = iter(csv.reader(mappings))
                current = next(mapping, None)
                rows = csv.DictReader(raw)
                writer = csv.DictWriter(output, fieldnames=rows.fieldnames)
                writer.writeheader()
                for row in rows:
                    index = int(row["frame_index"])
                    while current is not None and int(current[0]) < index:
                        current = next(mapping, None)
                    row["video_frame_index"] = current[1] if current is not None and int(current[0]) == index else ""
                    writer.writerow(row)
            temporary.replace(self.raw_path)
            mapping_path.unlink()
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    def write_event(self, event) -> None:
        with self._manifest_lock:
            if self.closed: raise RecordingError("Cannot write to a closed dataset")
            if self._event_journal is None:
                self._event_journal = (self.directory / "events.tmp.jsonl").open("x", encoding="utf-8", buffering=1)
            self._event_journal.write(json.dumps(asdict(event), ensure_ascii=True) + "\n")
            self._event_count += 1

    def record_audio_interval(self, interval: dict[str, Any]) -> None:
        with self._manifest_lock:
            self._manifest["audio"]["intervals"].append(dict(interval))
            self._write_manifest()

    def set_audio_metadata(self, metadata: dict[str, Any]) -> None:
        with self._manifest_lock:
            intervals = self._manifest["audio"].get("intervals", [])
            self._manifest["audio"] = {**metadata, "intervals": intervals}
            self._write_manifest()

    def set_transcription_metadata(self, metadata: dict[str, Any]) -> None:
        with self._manifest_lock:
            self._manifest["transcription"].update(metadata)
            self._write_manifest()

    def snapshot(self) -> dict[str, Any]:
        with self._manifest_lock:
            return deepcopy(self._manifest)

    def update_component(self, status: ComponentStatus) -> None:
        with self._manifest_lock:
            self._manifest["components"][status.component] = {"state": status.state.value, "message": status.message}
            self._write_manifest()

    def add_warning(self, text: str) -> None:
        with self._manifest_lock:
            self._manifest["warnings"].append(text); self._write_manifest()

    def add_error(self, component: str, text: str) -> None:
        with self._manifest_lock:
            self._manifest["errors"].append({"component": component, "message": text, "timestamp_s": self.clock.elapsed_s()})
            self._write_manifest()

    def mark_drop(self, kind: str, *, start_s=None, end_s=None, reason="") -> None:
        with self._manifest_lock:
            self._manifest["drops"][kind] = self._manifest["drops"].get(kind, 0) + 1
            previous = self._last_drop.get(kind)
            if (previous is not None and previous["reason"] == reason and start_s is not None
                    and previous["end_s"] is not None and 0 <= start_s - previous["end_s"] <= .05):
                previous["end_s"] = end_s
                previous["count"] += 1
            else:
                detail = {"kind": kind, "start_s": start_s, "end_s": end_s, "reason": reason, "count": 1}
                self._manifest["drop_details"].append(detail)
                self._last_drop[kind] = detail

    def record_media_stats(self, component: str, stats) -> None:
        from dataclasses import is_dataclass
        with self._manifest_lock:
            if is_dataclass(stats): stats = asdict(stats)
            self._manifest["media_stats"][component] = stats
            self._write_manifest()

    def close(self, *, status: str = "closed", remove_if_empty: bool = False) -> None:
        if self.closed: return
        self.closed = True
        errors = []
        try:
            self._manifest["landmark_timing"] = self.landmark_timing.close(self.directory)
        except Exception as exc:
            self._manifest["landmark_timing"] = {"finalized": False, "error": str(exc)}
            errors.append(f"Landmark timing: {exc}")
        for recorder in (self._raw,):
            try: recorder.close(remove_if_empty=False)
            except Exception as exc: errors.append(str(exc))
        try: self._finalize_video_mapping()
        except Exception as exc: errors.append(str(exc))
        event_path = self.directory / "events.tmp.jsonl"
        if self._event_journal is not None:
            try:
                self._event_journal.close()
                with event_path.open(encoding="utf-8") as events:
                    self._manifest["observable_events"] = [json.loads(line) for line in events]
            except Exception as exc: errors.append(str(exc))
        self._manifest["status"] = "incomplete" if errors else status
        self._manifest["ended_at_local"] = datetime.now().astimezone().isoformat()
        self._manifest["duration_s"] = self.clock.elapsed_s()
        if errors: self._manifest["errors"].extend({"component": "storage", "message": e} for e in errors)
        self._write_manifest()
        if not errors: event_path.unlink(missing_ok=True)
        if remove_if_empty and self.raw_row_count == 0 and self.event_row_count == 0:
            for child in self.directory.iterdir():
                if child.is_file(): child.unlink(missing_ok=True)
            self.directory.rmdir()
        if errors: raise RecordingError("; ".join(errors))
