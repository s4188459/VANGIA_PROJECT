from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionMode(str, Enum):
    CALIBRATING = "calibrating"
    TRACKING = "tracking"
    FACE_MISSING = "face_missing"
    PAUSED = "paused"


@dataclass(frozen=True)
class ActionDetectionConfig:
    baseline_duration_s: float = 2.0
    baseline_min_samples: int = 30
    smoothing_window_s: float = 0.25
    max_contiguous_gap_s: float = 0.25
    missing_face_hold_s: float = 0.20
    face_reacquired_display_s: float = 1.0
    minimum_action_duration_s: float = 0.25
    release_duration_s: float = 0.15
    default_cooldown_s: float = 0.30
    blink_minimum_duration_s: float = 0.05
    blink_display_duration_s: float = 0.35
    long_eye_closure_duration_s: float = 0.80
    temporal_history_s: float = 2.0
    stillness_duration_s: float = 1.50
    frequent_blink_window_s: float = 8.0
    frequent_blink_count: int = 4
    maximum_overlay_actions: int = 4
    sensitivity: float = 1.0
    adaptive_mad_multiplier: float = 6.0
    gaze_delta_floor: float = 0.30
    gaze_dominance_margin: float = 0.08
    generic_head_speed_deg_s: float = 20.0
    generic_mouth_delta_floor: float = 0.12

    def __post_init__(self) -> None:
        if not 0.5 <= self.sensitivity <= 2.0:
            raise ValueError("sensitivity must be between 0.5 and 2.0")
        positive_timings = (
            self.baseline_duration_s,
            self.smoothing_window_s,
            self.max_contiguous_gap_s,
        )
        nonnegative_timings = (
            self.missing_face_hold_s,
            self.face_reacquired_display_s,
            self.minimum_action_duration_s,
            self.release_duration_s,
            self.default_cooldown_s,
            self.blink_minimum_duration_s,
            self.blink_display_duration_s,
            self.long_eye_closure_duration_s,
            self.temporal_history_s,
            self.stillness_duration_s,
            self.frequent_blink_window_s,
        )
        if any(value <= 0 for value in positive_timings) or any(
            value < 0 for value in nonnegative_timings
        ):
            raise ValueError("Action detection timing values are invalid")
        if (
            self.baseline_min_samples <= 0
            or self.frequent_blink_count <= 0
            or self.maximum_overlay_actions <= 0
        ):
            raise ValueError("Action detection counts must be positive")


@dataclass(frozen=True)
class ActionDisplay:
    action_id: str
    label: str
    duration_s: float
    strength: float
    generic: bool = False


@dataclass(frozen=True)
class ActionEvent:
    start_time_s: float
    end_time_s: float
    action: str
    duration_s: float
    peak_strength: float
    status: str


@dataclass(frozen=True)
class ActionSnapshot:
    mode: ActionMode
    calibration_progress: float = 1.0
    actions: tuple[ActionDisplay, ...] = ()
    face_reacquired: bool = False
