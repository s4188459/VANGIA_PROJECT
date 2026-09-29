from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import TextIO

from .action_types import ActionEvent
from .session_recorder import RecordingError


EVENT_CSV_FIELDS = (
    "start_time_s",
    "end_time_s",
    "action",
    "duration_s",
    "peak_strength",
    "status",
)


class ActionEventRecorder:
    def __init__(self, path: Path, handle: TextIO) -> None:
        self.path = Path(path)
        self._handle = handle
        self._writer = csv.DictWriter(handle, fieldnames=EVENT_CSV_FIELDS)
        self._writer.writeheader()
        self.row_count = 0
        self.closed = False

    def write(self, event: ActionEvent) -> None:
        if self.closed:
            raise RecordingError("Cannot write to a closed recording")
        if event.status not in {"completed", "interrupted"}:
            raise RecordingError("Action event status must be completed or interrupted")
        values = (
            event.start_time_s,
            event.end_time_s,
            event.duration_s,
            event.peak_strength,
        )
        if not all(math.isfinite(float(value)) for value in values):
            raise RecordingError("Action event values must be finite")
        if event.end_time_s < event.start_time_s or event.duration_s < 0:
            raise RecordingError("Action event times and duration must be non-negative and ordered")
        row = {
            "start_time_s": f"{event.start_time_s:.3f}",
            "end_time_s": f"{event.end_time_s:.3f}",
            "action": event.action,
            "duration_s": f"{event.duration_s:.3f}",
            "peak_strength": f"{event.peak_strength:.4f}",
            "status": event.status,
        }
        try:
            self._writer.writerow(row)
        except (OSError, csv.Error) as exc:
            raise RecordingError(f"Could not write action event: {exc}") from exc
        self.row_count += 1

    def close(self, *, remove_if_empty: bool = False) -> None:
        if self.closed:
            return
        self.closed = True
        error = None
        try:
            try:
                self._handle.flush()
            finally:
                self._handle.close()
        except OSError as exc:
            error = RecordingError(f"Could not close action event file: {exc}")
        if remove_if_empty and self.row_count == 0:
            try:
                self.path.unlink(missing_ok=True)
            except OSError as exc:
                error = error or RecordingError(f"Could not remove empty action event file: {exc}")
        if error is not None:
            raise error
