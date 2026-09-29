from __future__ import annotations

import csv
from pathlib import Path
import re
from typing import Callable, TextIO

from .feature_data import FeatureFrame


BLENDSHAPE_NAMES = (
    "_neutral", "browDownLeft", "browDownRight", "browInnerUp",
    "browOuterUpLeft", "browOuterUpRight", "cheekPuff", "cheekSquintLeft",
    "cheekSquintRight", "eyeBlinkLeft", "eyeBlinkRight", "eyeLookDownLeft",
    "eyeLookDownRight", "eyeLookInLeft", "eyeLookInRight", "eyeLookOutLeft",
    "eyeLookOutRight", "eyeLookUpLeft", "eyeLookUpRight", "eyeSquintLeft",
    "eyeSquintRight", "eyeWideLeft", "eyeWideRight", "jawForward", "jawLeft",
    "jawOpen", "jawRight", "mouthClose", "mouthDimpleLeft", "mouthDimpleRight",
    "mouthFrownLeft", "mouthFrownRight", "mouthFunnel", "mouthLeft",
    "mouthLowerDownLeft", "mouthLowerDownRight", "mouthPressLeft",
    "mouthPressRight", "mouthPucker", "mouthRight", "mouthRollLower",
    "mouthRollUpper", "mouthShrugLower", "mouthShrugUpper", "mouthSmileLeft",
    "mouthSmileRight", "mouthStretchLeft", "mouthStretchRight",
    "mouthUpperUpLeft", "mouthUpperUpRight", "noseSneerLeft", "noseSneerRight",
)


def _snake(value: str) -> str:
    value = value.lstrip("_")
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


BLENDSHAPE_FIELDS = {f"blendshape_{_snake(name)}": name for name in BLENDSHAPE_NAMES}


CSV_FIELDS = (
    "timestamp_s",
    "frame_index",
    "face_visible",
    "confidence",
    "head_center_x",
    "head_center_y",
    "head_depth",
    "head_yaw_deg",
    "head_pitch_deg",
    "head_roll_deg",
    "gaze_left",
    "gaze_right",
    "gaze_up",
    "gaze_down",
    "blink_left",
    "blink_right",
    "blink",
    "brow_inner_up",
    "brow_outer_up_left",
    "brow_outer_up_right",
    "brow_down_left",
    "brow_down_right",
    "brow_raise",
    "jaw_open",
    "mouth_smile_left",
    "mouth_smile_right",
    "mouth_pucker",
    "mouth_funnel",
    "mouth_activity",
    "processing_ms",
    "frame_gap_ms",
    "capture_drop_count",
    "video_frame_index",
    "action_mode",
    "action_calibration_progress",
    "active_action_ids",
    "active_action_strengths",
) + tuple(f"blendshape_{_snake(name)}" for name in BLENDSHAPE_NAMES)
SESSION_PATTERN = re.compile(r"^session_(\d+)(?:_events)?\.csv$")


class RecordingError(RuntimeError):
    pass


def _validate_directory(directory: Path) -> Path:
    folder = Path(directory)
    if not folder.is_dir():
        raise RecordingError(f"Recording directory does not exist: {folder}")
    return folder


def next_session_name(directory: Path) -> str:
    folder = _validate_directory(directory)
    highest = 0
    try:
        for path in folder.iterdir():
            match = SESSION_PATTERN.fullmatch(path.name)
            if match:
                highest = max(highest, int(match.group(1)))
    except OSError as exc:
        raise RecordingError(f"Could not read recording directory: {exc}") from exc
    return f"session_{highest + 1:03d}.csv"


def _format_value(name: str, value) -> str:
    if value is None:
        return ""
    if name == "face_visible":
        return "true" if value else "false"
    if name == "timestamp_s":
        return f"{value:.3f}"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


class CsvSessionRecorder:
    def __init__(self, path: Path, handle: TextIO) -> None:
        self.path = path
        self._handle = handle
        self._writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        self._writer.writeheader()
        self.row_count = 0
        self.closed = False

    @classmethod
    def create(
        cls,
        directory: Path,
        *,
        open_func: Callable[..., TextIO] = open,
    ) -> "CsvSessionRecorder":
        folder = _validate_directory(directory)
        while True:
            path = folder / next_session_name(folder)
            try:
                handle = open_func(
                    path,
                    "x",
                    encoding="utf-8",
                    newline="",
                    buffering=1,
                )
            except FileExistsError:
                continue
            except OSError as exc:
                raise RecordingError(f"Could not create recording file: {exc}") from exc
            try:
                return cls(path, handle)
            except Exception as exc:
                handle.close()
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise RecordingError(f"Could not initialize CSV recording: {exc}") from exc

    def write(self, frame: FeatureFrame) -> None:
        if self.closed:
            raise RecordingError("Cannot write to a closed recording")
        values = vars(frame)
        blendshapes = dict(frame.blendshapes)
        row = {}
        for name in CSV_FIELDS:
            if name.startswith("blendshape_"):
                value = blendshapes.get(BLENDSHAPE_FIELDS[name])
            else:
                value = values[name]
            row[name] = _format_value(name, value)
        try:
            self._writer.writerow(row)
        except (OSError, csv.Error) as exc:
            raise RecordingError(f"Could not write recording row: {exc}") from exc
        self.row_count += 1

    def close(self, *, remove_if_empty: bool = False) -> None:
        if self.closed:
            return
        self.closed = True
        close_error = None
        try:
            try:
                self._handle.flush()
            finally:
                self._handle.close()
        except OSError as exc:
            close_error = RecordingError(f"Could not close recording file: {exc}")

        if remove_if_empty and self.row_count == 0:
            try:
                self.path.unlink(missing_ok=True)
            except OSError as exc:
                if close_error is None:
                    close_error = RecordingError(
                        f"Could not remove empty recording file: {exc}"
                    )
        if close_error is not None:
            raise close_error
