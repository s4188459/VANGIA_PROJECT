from __future__ import annotations

from dataclasses import dataclass
import math
from threading import Lock

import numpy as np


@dataclass(frozen=True)
class FeatureFrame:
    timestamp_s: float
    frame_index: int
    face_visible: bool
    confidence: float | None = None
    head_center_x: float | None = None
    head_center_y: float | None = None
    head_depth: float | None = None
    head_yaw_deg: float | None = None
    head_pitch_deg: float | None = None
    head_roll_deg: float | None = None
    gaze_left: float | None = None
    gaze_right: float | None = None
    gaze_up: float | None = None
    gaze_down: float | None = None
    blink_left: float | None = None
    blink_right: float | None = None
    blink: float | None = None
    brow_inner_up: float | None = None
    brow_outer_up_left: float | None = None
    brow_outer_up_right: float | None = None
    brow_down_left: float | None = None
    brow_down_right: float | None = None
    brow_raise: float | None = None
    jaw_open: float | None = None
    mouth_smile_left: float | None = None
    mouth_smile_right: float | None = None
    mouth_pucker: float | None = None
    mouth_funnel: float | None = None
    mouth_activity: float | None = None
    processing_ms: float | None = None
    frame_gap_ms: float | None = None
    capture_drop_count: int = 0
    blendshapes: tuple[tuple[str, float], ...] = ()
    video_frame_index: int | None = None
    action_mode: str = ""
    action_calibration_progress: float | None = None
    active_action_ids: str = ""
    active_action_strengths: str = ""


def _all_or_none(values: tuple[float | None, ...], reducer) -> float | None:
    if any(value is None for value in values):
        return None
    return float(reducer(value for value in values if value is not None))


def _mean(values: tuple[float | None, ...]) -> float | None:
    return _all_or_none(values, lambda present: sum(present) / len(values))


def matrix_to_euler_degrees(matrix) -> tuple[float, float, float] | None:
    try:
        rotation = np.asarray(matrix, dtype=float)
    except (TypeError, ValueError):
        return None
    if rotation.shape not in {(3, 3), (4, 4)} or not np.isfinite(rotation).all():
        return None
    rotation = rotation[:3, :3]
    sine_yaw = float(np.clip(-rotation[2, 0], -1.0, 1.0))
    yaw = math.asin(sine_yaw)

    if abs(abs(sine_yaw) - 1.0) > 1e-6:
        pitch = math.atan2(rotation[2, 1], rotation[2, 2])
        roll = math.atan2(rotation[1, 0], rotation[0, 0])
    else:
        pitch = math.atan2(-rotation[1, 2], rotation[1, 1])
        roll = 0.0

    return tuple(math.degrees(angle) for angle in (yaw, pitch, roll))


def _blendshape_map(result) -> dict[str, float]:
    groups = getattr(result, "face_blendshapes", None) or []
    if not groups:
        return {}
    return {
        str(category.category_name): float(category.score)
        for category in groups[0]
        if getattr(category, "category_name", None)
    }


def extract_feature_frame(result, timestamp_s: float, frame_index: int) -> FeatureFrame:
    faces = getattr(result, "face_landmarks", None) or []
    if not faces:
        return FeatureFrame(timestamp_s, frame_index, False)

    landmarks = faces[0]
    scores = _blendshape_map(result)
    matrices = getattr(result, "facial_transformation_matrixes", None) or []
    orientation = matrix_to_euler_degrees(matrices[0]) if matrices else None
    yaw, pitch, roll = orientation or (None, None, None)

    blink_left = scores.get("eyeBlinkLeft")
    blink_right = scores.get("eyeBlinkRight")
    brow_inner_up = scores.get("browInnerUp")
    brow_outer_up_left = scores.get("browOuterUpLeft")
    brow_outer_up_right = scores.get("browOuterUpRight")
    jaw_open = scores.get("jawOpen")
    mouth_smile_left = scores.get("mouthSmileLeft")
    mouth_smile_right = scores.get("mouthSmileRight")
    mouth_pucker = scores.get("mouthPucker")
    mouth_funnel = scores.get("mouthFunnel")

    return FeatureFrame(
        timestamp_s=float(timestamp_s),
        frame_index=int(frame_index),
        face_visible=True,
        head_center_x=sum(float(point.x) for point in landmarks) / len(landmarks),
        head_center_y=sum(float(point.y) for point in landmarks) / len(landmarks),
        head_depth=sum(float(point.z) for point in landmarks) / len(landmarks),
        head_yaw_deg=yaw,
        head_pitch_deg=pitch,
        head_roll_deg=roll,
        gaze_left=_mean((scores.get("eyeLookOutLeft"), scores.get("eyeLookInRight"))),
        gaze_right=_mean((scores.get("eyeLookInLeft"), scores.get("eyeLookOutRight"))),
        gaze_up=_mean((scores.get("eyeLookUpLeft"), scores.get("eyeLookUpRight"))),
        gaze_down=_mean((scores.get("eyeLookDownLeft"), scores.get("eyeLookDownRight"))),
        blink_left=blink_left,
        blink_right=blink_right,
        blink=_mean((blink_left, blink_right)),
        brow_inner_up=brow_inner_up,
        brow_outer_up_left=brow_outer_up_left,
        brow_outer_up_right=brow_outer_up_right,
        brow_down_left=scores.get("browDownLeft"),
        brow_down_right=scores.get("browDownRight"),
        brow_raise=_all_or_none(
            (brow_inner_up, brow_outer_up_left, brow_outer_up_right),
            max,
        ),
        jaw_open=jaw_open,
        mouth_smile_left=mouth_smile_left,
        mouth_smile_right=mouth_smile_right,
        mouth_pucker=mouth_pucker,
        mouth_funnel=mouth_funnel,
        mouth_activity=_all_or_none(
            (
                jaw_open,
                mouth_smile_left,
                mouth_smile_right,
                mouth_pucker,
                mouth_funnel,
            ),
            max,
        ),
        blendshapes=tuple(sorted(scores.items())),
    )


def gaze_label(frame: FeatureFrame, threshold: float = 0.2) -> str:
    values = {
        "Left": frame.gaze_left,
        "Right": frame.gaze_right,
        "Up": frame.gaze_up,
        "Down": frame.gaze_down,
    }
    present = {name: value for name, value in values.items() if value is not None}
    if not present:
        return "--"
    direction, score = max(present.items(), key=lambda item: item[1])
    return direction if score >= threshold else "Center"


class LatestFeatureFrame:
    def __init__(self) -> None:
        self._lock = Lock()
        self._frame: FeatureFrame | None = None

    def publish(self, frame: FeatureFrame) -> None:
        with self._lock:
            self._frame = frame

    def take(self) -> FeatureFrame | None:
        with self._lock:
            frame = self._frame
            self._frame = None
        return frame

    def clear(self) -> None:
        with self._lock:
            self._frame = None
