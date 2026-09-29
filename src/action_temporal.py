from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import fields
import math
import statistics

from .action_types import ActionDetectionConfig, ActionDisplay, ActionEvent
from .feature_data import FeatureFrame


_NON_FEATURE_FIELDS = {
    "timestamp_s", "frame_index", "face_visible", "processing_ms",
    "frame_gap_ms", "capture_drop_count", "blendshapes",
    "video_frame_index", "action_mode", "action_calibration_progress",
    "active_action_ids", "active_action_strengths",
}
NUMERIC_FEATURE_FIELDS = tuple(
    field.name for field in fields(FeatureFrame) if field.name not in _NON_FEATURE_FIELDS
)


class BaselineModel:
    def __init__(self, config: ActionDetectionConfig) -> None:
        self.config = config
        self._values: dict[str, list[float]] = defaultdict(list)
        self._valid_frames = 0
        self._valid_duration_s = 0.0
        self._last_visible_timestamp: float | None = None

    def add(self, frame: FeatureFrame, timestamp_s: float | None = None) -> None:
        if not frame.face_visible:
            self.break_contiguous()
            return
        timestamp = frame.timestamp_s if timestamp_s is None else timestamp_s
        timestamp = float(timestamp)
        if self._last_visible_timestamp is not None:
            gap = timestamp - self._last_visible_timestamp
            if 0.0 < gap <= self.config.max_contiguous_gap_s:
                self._valid_duration_s += gap
        self._last_visible_timestamp = timestamp
        self._valid_frames += 1
        for name in NUMERIC_FEATURE_FIELDS:
            value = getattr(frame, name)
            if value is not None and math.isfinite(float(value)):
                self._values[name].append(float(value))

    def break_contiguous(self) -> None:
        self._last_visible_timestamp = None

    @property
    def valid_duration_s(self) -> float:
        return self._valid_duration_s

    @property
    def complete(self) -> bool:
        return (
            self._valid_frames >= self.config.baseline_min_samples
            and self._valid_duration_s >= self.config.baseline_duration_s
        )

    @property
    def progress(self) -> float:
        sample_progress = self._valid_frames / self.config.baseline_min_samples
        time_progress = self._valid_duration_s / self.config.baseline_duration_s
        return max(0.0, min(1.0, sample_progress, time_progress))

    def median(self, name: str) -> float | None:
        values = self._values.get(name, ())
        if len(values) < self.config.baseline_min_samples:
            return None
        return float(statistics.median(values))

    def mad(self, name: str) -> float | None:
        center = self.median(name)
        if center is None:
            return None
        return float(statistics.median(abs(value - center) for value in self._values[name]))


class RollingFeatureWindow:
    def __init__(self, smoothing_window_s: float) -> None:
        if smoothing_window_s <= 0:
            raise ValueError("smoothing_window_s must be positive")
        self.smoothing_window_s = smoothing_window_s
        self._values: dict[str, deque[tuple[float, float]]] = defaultdict(deque)

    def add(self, frame: FeatureFrame) -> None:
        cutoff = frame.timestamp_s - self.smoothing_window_s
        for values in self._values.values():
            while values and values[0][0] < cutoff:
                values.popleft()
        for name in NUMERIC_FEATURE_FIELDS:
            value = getattr(frame, name)
            if value is not None and math.isfinite(float(value)):
                self._values[name].append((frame.timestamp_s, float(value)))

    def median(self, name: str) -> float | None:
        values = self._values.get(name, ())
        if not values:
            return None
        return float(statistics.median(value for _, value in values))

    def clear(self) -> None:
        self._values.clear()


class TimedActionState:
    def __init__(
        self,
        action_id: str,
        label: str,
        minimum_duration_s: float,
        release_duration_s: float,
        cooldown_s: float,
        *,
        generic: bool = False,
    ) -> None:
        self.action_id = action_id
        self.label = label
        self.minimum_duration_s = minimum_duration_s
        self.release_duration_s = release_duration_s
        self.cooldown_s = cooldown_s
        self.generic = generic
        self.reset()

    def reset(self) -> None:
        self._candidate_start: float | None = None
        self._active_start: float | None = None
        self._release_start: float | None = None
        self._peak = 0.0
        self._last_timestamp: float | None = None
        self._cooldown_until = float("-inf")

    @property
    def active(self) -> bool:
        return self._active_start is not None

    def update(
        self,
        timestamp_s: float,
        strength: float | None,
        activation_threshold: float,
        release_threshold: float,
    ) -> tuple[ActionDisplay | None, ActionEvent | None]:
        timestamp = float(timestamp_s)
        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            raise ValueError("Action timestamps must increase")
        self._last_timestamp = timestamp

        if strength is None or not math.isfinite(float(strength)):
            self._candidate_start = None
            return self._release(timestamp, 0.0)
        value = float(strength)

        if self._active_start is None:
            if timestamp < self._cooldown_until:
                return None, None
            if value < activation_threshold:
                self._candidate_start = None
                return None, None
            if self._candidate_start is None:
                self._candidate_start = timestamp
                self._peak = value
                if self.minimum_duration_s > 0:
                    return None, None
            self._peak = max(self._peak, value)
            if timestamp - self._candidate_start < self.minimum_duration_s:
                return None, None
            self._active_start = self._candidate_start
            self._release_start = None
        else:
            self._peak = max(self._peak, value)

        if value < release_threshold:
            return self._release(timestamp, value)
        self._release_start = None
        return self._display(timestamp, value), None

    def _release(
        self, timestamp: float, strength: float
    ) -> tuple[ActionDisplay | None, ActionEvent | None]:
        if self._active_start is None:
            return None, None
        if self._release_start is None:
            self._release_start = timestamp
            return self._display(timestamp, strength), None
        if timestamp - self._release_start < self.release_duration_s:
            return self._display(timestamp, strength), None
        end = self._release_start
        event = self._event(end, "completed")
        self._clear_after_event(timestamp)
        return None, event

    def _display(self, timestamp: float, strength: float) -> ActionDisplay:
        assert self._active_start is not None
        return ActionDisplay(
            self.action_id,
            self.label,
            max(0.0, timestamp - self._active_start),
            max(0.0, strength),
            self.generic,
        )

    def _event(self, end: float, status: str) -> ActionEvent:
        assert self._active_start is not None
        return ActionEvent(
            self._active_start,
            end,
            self.action_id,
            max(0.0, end - self._active_start),
            self._peak,
            status,
        )

    def _clear_after_event(self, timestamp: float) -> None:
        self._candidate_start = None
        self._active_start = None
        self._release_start = None
        self._peak = 0.0
        self._cooldown_until = timestamp + self.cooldown_s

    def interrupt(self, timestamp_s: float) -> ActionEvent | None:
        if self._active_start is None:
            self._candidate_start = None
            self._release_start = None
            return None
        end = max(self._active_start, float(timestamp_s))
        event = self._event(end, "interrupted")
        self._clear_after_event(end)
        return event
