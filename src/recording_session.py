from __future__ import annotations

from pathlib import Path
from typing import Callable, TextIO

from .action_event_recorder import ActionEventRecorder
from .action_types import ActionEvent
from .feature_data import FeatureFrame
from .session_recorder import (
    CsvSessionRecorder,
    RecordingError,
    _validate_directory,
    next_session_name,
)


class RecordingSession:
    def __init__(
        self,
        raw_recorder: CsvSessionRecorder,
        event_recorder: ActionEventRecorder,
    ) -> None:
        self._raw = raw_recorder
        self._events = event_recorder
        self.closed = False

    @classmethod
    def create(
        cls,
        directory: Path,
        *,
        open_func: Callable[..., TextIO] = open,
    ) -> "RecordingSession":
        folder = _validate_directory(directory)
        while True:
            raw_path = folder / next_session_name(folder)
            number = raw_path.stem.removeprefix("session_")
            event_path = folder / f"session_{number}_events.csv"
            raw_handle = None
            raw_recorder = None
            event_handle = None
            try:
                raw_handle = open_func(raw_path, "x", encoding="utf-8", newline="", buffering=1)
                raw_recorder = CsvSessionRecorder(raw_path, raw_handle)
                raw_handle = None
                event_handle = open_func(event_path, "x", encoding="utf-8", newline="", buffering=1)
                event_recorder = ActionEventRecorder(event_path, event_handle)
                event_handle = None
                return cls(raw_recorder, event_recorder)
            except FileExistsError:
                cls._cleanup_attempt(raw_recorder, raw_handle, raw_path)
                continue
            except Exception as exc:
                cls._cleanup_attempt(raw_recorder, raw_handle, raw_path)
                if event_handle is not None:
                    event_handle.close()
                    try:
                        event_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                if isinstance(exc, RecordingError):
                    raise
                raise RecordingError(f"Could not initialize paired recording: {exc}") from exc

    @staticmethod
    def _cleanup_attempt(recorder, handle, path: Path) -> None:
        try:
            if recorder is not None:
                recorder.close(remove_if_empty=True)
            elif handle is not None:
                handle.close()
                path.unlink(missing_ok=True)
        except OSError:
            pass

    @property
    def raw_path(self) -> Path:
        return self._raw.path

    @property
    def event_path(self) -> Path:
        return self._events.path

    @property
    def path(self) -> Path:
        return self.raw_path

    @property
    def raw_row_count(self) -> int:
        return self._raw.row_count

    @property
    def event_row_count(self) -> int:
        return self._events.row_count

    @property
    def row_count(self) -> int:
        return self.raw_row_count

    def write_feature(self, frame: FeatureFrame) -> None:
        self._raw.write(frame)

    def write_event(self, event: ActionEvent) -> None:
        self._events.write(event)

    def close(self, *, remove_if_empty: bool = False) -> None:
        if self.closed:
            return
        self.closed = True
        remove_pair = remove_if_empty and self.raw_row_count == 0 and self.event_row_count == 0
        errors = []
        for recorder in (self._raw, self._events):
            try:
                recorder.close(remove_if_empty=remove_pair)
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RecordingError("; ".join(errors))
