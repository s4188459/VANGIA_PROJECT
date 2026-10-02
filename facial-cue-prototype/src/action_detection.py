from __future__ import annotations

from collections import deque

from .action_temporal import BaselineModel, RollingFeatureWindow, TimedActionState
from .action_types import (
    ActionDetectionConfig,
    ActionDisplay,
    ActionEvent,
    ActionMode,
    ActionSnapshot,
)
from .feature_data import FeatureFrame


_LABELS = {
    "head_turned_left": "Head turned left",
    "head_turned_right": "Head turned right",
    "head_raised": "Head raised",
    "head_lowered": "Head lowered",
    "head_tilted_left": "Head tilted left",
    "head_tilted_right": "Head tilted right",
    "eyes_looking_left": "Eyes looking left",
    "eyes_looking_right": "Eyes looking right",
    "eyes_looking_up": "Eyes looking up",
    "eyes_looking_down": "Eyes looking down",
    "inner_brows_raised": "Inner brows raised",
    "brows_raised": "Brows raised",
    "brows_lowered": "Brows lowered",
    "asymmetric_brow_movement": "Asymmetric brow movement",
    "jaw_opened": "Jaw opened",
    "smile_movement_detected": "Smile movement detected",
    "mouth_puckered": "Mouth puckered",
    "mouth_funnel_detected": "Mouth funnel detected",
    "mouth_movement_detected": "Mouth movement detected",
    "asymmetric_eye_closure": "Asymmetric eye closure",
    "nodding": "Nodding",
    "shaking_head": "Shaking head",
    "head_movement_detected": "Head movement detected",
    "head_mostly_still": "Head mostly still",
    "frequent_blinking": "Frequent blinking",
}

_GENERIC_IDS = {"mouth_movement_detected", "head_movement_detected", "head_mostly_still", "brows_raised"}


def rank_actions(
    displays: tuple[ActionDisplay, ...] | list[ActionDisplay], maximum: int
) -> tuple[ActionDisplay, ...]:
    present = {item.action_id for item in displays}
    suppressed = set()
    if "long_eye_closure" in present:
        suppressed.add("blinking")
    if present & {"nodding", "shaking_head"}:
        suppressed.add("head_movement_detected")
    if present & {"nodding", "shaking_head", "head_movement_detected"}:
        suppressed.add("head_mostly_still")
    if present & {"inner_brows_raised", "asymmetric_brow_movement"}:
        suppressed.add("brows_raised")
    if present & {"jaw_opened", "smile_movement_detected", "mouth_puckered", "mouth_funnel_detected"}:
        suppressed.add("mouth_movement_detected")
    remaining = [item for item in displays if item.action_id not in suppressed]
    remaining.sort(
        key=lambda item: (
            item.generic or item.action_id in _GENERIC_IDS,
            -item.duration_s,
            -item.strength,
            item.action_id,
        )
    )
    return tuple(remaining[:maximum])


class ActionDetector:
    def __init__(self, config: ActionDetectionConfig = ActionDetectionConfig()) -> None:
        self.config = config
        self.baseline = BaselineModel(config)
        self.window = RollingFeatureWindow(config.smoothing_window_s)
        self._last_timestamp: float | None = None
        self._missing_start: float | None = None
        self._missing_confirmed = False
        self._reacquired_until = float("-inf")
        self._states = self._make_states()
        self._closure_start: float | None = None
        self._closure_frames = 0
        self._closure_peak = 0.0
        self._long_closure_active = False
        self._blink_visible_until = float("-inf")
        self._blink_times: deque[float] = deque()
        self._head_history: deque[tuple[float, float, float, float]] = deque()

    def _make_states(self) -> dict[str, TimedActionState]:
        states = {}
        for action_id, label in _LABELS.items():
            if action_id in {"asymmetric_brow_movement", "asymmetric_eye_closure"}:
                duration = 0.30
            elif action_id in {"nodding", "shaking_head", "head_mostly_still", "frequent_blinking"}:
                duration = 0.0
            else:
                duration = self.config.minimum_action_duration_s
            states[action_id] = TimedActionState(
                action_id,
                label,
                duration,
                self.config.release_duration_s,
                self.config.default_cooldown_s,
                generic=action_id in _GENERIC_IDS,
            )
        return states

    def update(self, frame: FeatureFrame) -> tuple[ActionSnapshot, tuple[ActionEvent, ...]]:
        timestamp = float(frame.timestamp_s)
        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            raise ValueError("Action frame timestamps must increase")
        events: list[ActionEvent] = []
        if (
            self._last_timestamp is not None
            and timestamp - self._last_timestamp > self.config.max_contiguous_gap_s
        ):
            events.extend(self._interrupt_all(self._last_timestamp))
            self._clear_temporal()
        self._last_timestamp = timestamp

        if not frame.face_visible:
            return self._update_missing(timestamp, events)

        reacquired = False
        if self._missing_start is not None:
            if self._missing_confirmed:
                reacquired = True
                self._reacquired_until = timestamp + self.config.face_reacquired_display_s
                events.append(ActionEvent(timestamp, timestamp, "face_detected_again", 0.0, 1.0, "completed"))
            self._missing_start = None
            self._missing_confirmed = False
            self.window.clear()

        if not self.baseline.complete:
            self.baseline.add(frame)
            mode = ActionMode.TRACKING if self.baseline.complete else ActionMode.CALIBRATING
            return ActionSnapshot(mode, self.baseline.progress, (), reacquired), tuple(events)

        self.window.add(frame)
        displays, detected_events = self._update_static(timestamp)
        temporal_displays, temporal_events = self._update_temporal(timestamp)
        displays.extend(temporal_displays)
        events.extend(detected_events)
        events.extend(temporal_events)
        snapshot = ActionSnapshot(
            ActionMode.TRACKING,
            1.0,
            rank_actions(displays, self.config.maximum_overlay_actions),
            reacquired or timestamp < self._reacquired_until,
        )
        return snapshot, tuple(events)

    def _update_missing(
        self, timestamp: float, events: list[ActionEvent]
    ) -> tuple[ActionSnapshot, tuple[ActionEvent, ...]]:
        if not self.baseline.complete:
            self.baseline.break_contiguous()
        if self._missing_start is None:
            self._missing_start = timestamp
        elif (
            not self._missing_confirmed
            and timestamp - self._missing_start >= self.config.missing_face_hold_s
        ):
            self._missing_confirmed = True
            events.extend(self._interrupt_all(self._missing_start))
            events.append(ActionEvent(
                self._missing_start,
                timestamp,
                "face_not_detected",
                timestamp - self._missing_start,
                1.0,
                "completed",
            ))
            self._clear_temporal(reset_states=False)
        return ActionSnapshot(ActionMode.FACE_MISSING, self.baseline.progress), tuple(events)

    def _threshold(self, feature_name: str, floor: float) -> float | None:
        center = self.baseline.median(feature_name)
        mad = self.baseline.mad(feature_name)
        if center is None or mad is None:
            return None
        return max(floor, mad * self.config.adaptive_mad_multiplier) / self.config.sensitivity

    def _relative(self, feature_name: str) -> float | None:
        value = self.window.median(feature_name)
        center = self.baseline.median(feature_name)
        if value is None or center is None:
            return None
        return value - center

    def _strength(self, feature: str, floor: float, direction: float = 1.0) -> float | None:
        relative = self._relative(feature)
        threshold = self._threshold(feature, floor)
        if relative is None or threshold is None or threshold <= 0:
            return None
        return max(0.0, direction * relative) / threshold

    def _derived_strength(self, value: float | None, floor: float) -> float | None:
        if value is None:
            return None
        return max(0.0, value) / (floor / self.config.sensitivity)

    def _update_state(
        self, action_id: str, timestamp: float, strength: float | None
    ) -> tuple[ActionDisplay | None, ActionEvent | None]:
        return self._states[action_id].update(timestamp, strength, 1.0, 0.60)

    def _update_static(self, timestamp: float) -> tuple[list[ActionDisplay], list[ActionEvent]]:
        strengths = {
            "head_turned_left": self._strength("head_yaw_deg", 15.0, -1.0),
            "head_turned_right": self._strength("head_yaw_deg", 15.0),
            "head_raised": self._strength("head_pitch_deg", 12.0, -1.0),
            "head_lowered": self._strength("head_pitch_deg", 12.0),
            "head_tilted_left": self._strength("head_roll_deg", 12.0, -1.0),
            "head_tilted_right": self._strength("head_roll_deg", 12.0),
        }
        strengths.update(self._gaze_strengths())
        strengths.update(self._brow_strengths())
        strengths.update(self._mouth_strengths())

        displays: list[ActionDisplay] = []
        events: list[ActionEvent] = []
        for action_id, state in self._states.items():
            if action_id not in strengths:
                continue
            display, event = state.update(timestamp, strengths[action_id], 1.0, 0.60)
            if display is not None:
                displays.append(display)
            if event is not None:
                events.append(event)
        return displays, events

    def _gaze_strengths(self) -> dict[str, float]:
        values = {}
        for direction in ("left", "right", "up", "down"):
            strength = self._strength(f"gaze_{direction}", self.config.gaze_delta_floor)
            values[direction] = 0.0 if strength is None else strength
        ordered = sorted(values.items(), key=lambda item: item[1], reverse=True)
        winner, strongest = ordered[0]
        raw_threshold = self.config.gaze_delta_floor / self.config.sensitivity
        dominance = (strongest - ordered[1][1]) * raw_threshold
        result = {f"eyes_looking_{name}": 0.0 for name in values}
        if strongest >= 1.0 and dominance >= self.config.gaze_dominance_margin:
            result[f"eyes_looking_{winner}"] = strongest
        return result

    def _brow_strengths(self) -> dict[str, float | None]:
        left = self._relative("brow_outer_up_left")
        right = self._relative("brow_outer_up_right")
        down_left = self._relative("brow_down_left")
        down_right = self._relative("brow_down_right")
        asymmetry = None if left is None or right is None else abs(left - right)
        lowered = None if down_left is None or down_right is None else (down_left + down_right) / 2
        return {
            "inner_brows_raised": self._strength("brow_inner_up", 0.15),
            "brows_raised": self._strength("brow_raise", 0.20),
            "brows_lowered": self._derived_strength(lowered, 0.15),
            "asymmetric_brow_movement": self._derived_strength(asymmetry, 0.18),
        }

    def _mouth_strengths(self) -> dict[str, float | None]:
        smile_left = self._relative("mouth_smile_left")
        smile_right = self._relative("mouth_smile_right")
        smile = None if smile_left is None or smile_right is None else (smile_left + smile_right) / 2
        direct = [
            self._relative(name)
            for name in ("jaw_open", "mouth_smile_left", "mouth_smile_right", "mouth_pucker", "mouth_funnel")
        ]
        generic = max((abs(value) for value in direct if value is not None), default=None)
        return {
            "jaw_opened": self._strength("jaw_open", 0.20),
            "smile_movement_detected": self._derived_strength(smile, 0.20),
            "mouth_puckered": self._strength("mouth_pucker", 0.18),
            "mouth_funnel_detected": self._strength("mouth_funnel", 0.15),
            "mouth_movement_detected": self._derived_strength(generic, self.config.generic_mouth_delta_floor),
        }

    def _update_temporal(self, timestamp: float) -> tuple[list[ActionDisplay], list[ActionEvent]]:
        displays: list[ActionDisplay] = []
        events: list[ActionEvent] = []
        blink_displays, blink_events = self._update_blinks(timestamp)
        displays.extend(blink_displays)
        events.extend(blink_events)

        left = self.window.median("blink_left")
        right = self.window.median("blink_right")
        asymmetry = None if left is None or right is None else abs(left - right)
        asym_strength = self._derived_strength(asymmetry, 0.25)
        display, event = self._update_state("asymmetric_eye_closure", timestamp, asym_strength)
        if display is not None:
            displays.append(display)
        if event is not None:
            events.append(event)

        head_displays, head_events = self._update_head_motion(timestamp)
        displays.extend(head_displays)
        events.extend(head_events)
        return displays, events

    def _blink_threshold(self) -> float | None:
        center = self.baseline.median("blink")
        mad = self.baseline.mad("blink")
        if center is None or mad is None:
            return None
        return max(0.55, center + mad * self.config.adaptive_mad_multiplier) / self.config.sensitivity

    def _update_blinks(self, timestamp: float) -> tuple[list[ActionDisplay], list[ActionEvent]]:
        displays: list[ActionDisplay] = []
        events: list[ActionEvent] = []
        value = self.window.median("blink")
        threshold = self._blink_threshold()
        closed = value is not None and threshold is not None and value >= threshold

        if closed:
            if self._closure_start is None:
                self._closure_start = timestamp
                self._closure_frames = 1
                self._closure_peak = float(value)
            else:
                self._closure_frames += 1
                self._closure_peak = max(self._closure_peak, float(value))
            duration = timestamp - self._closure_start
            if duration >= self.config.long_eye_closure_duration_s:
                self._long_closure_active = True
                displays.append(ActionDisplay(
                    "long_eye_closure", "Long eye closure", duration,
                    self._closure_peak / threshold,
                ))
        elif self._closure_start is not None:
            duration = timestamp - self._closure_start
            if self._long_closure_active:
                events.append(ActionEvent(
                    self._closure_start, timestamp, "long_eye_closure", duration,
                    self._closure_peak / threshold, "completed",
                ))
            elif (
                self._closure_frames >= 2
                and duration >= self.config.blink_minimum_duration_s
            ):
                events.append(ActionEvent(
                    self._closure_start, timestamp, "blinking", duration,
                    self._closure_peak / threshold, "completed",
                ))
                self._blink_visible_until = timestamp + self.config.blink_display_duration_s
                self._blink_times.append(timestamp)
            self._reset_closure()

        if timestamp < self._blink_visible_until and not self._long_closure_active:
            displays.append(ActionDisplay("blinking", "Blinking", 0.0, 1.0))
        cutoff = timestamp - self.config.frequent_blink_window_s
        while self._blink_times and self._blink_times[0] < cutoff:
            self._blink_times.popleft()
        frequent_strength = len(self._blink_times) / self.config.frequent_blink_count
        display, event = self._update_state(
            "frequent_blinking", timestamp, frequent_strength
        )
        if display is not None:
            displays.append(display)
        if event is not None:
            events.append(event)
        return displays, events

    def _reset_closure(self) -> None:
        self._closure_start = None
        self._closure_frames = 0
        self._closure_peak = 0.0
        self._long_closure_active = False

    @staticmethod
    def _has_oscillation(values: list[float], minimum_excursion: float) -> bool:
        if len(values) < 4:
            return False
        turns = [values[0]]
        previous_sign = 0
        for index in range(1, len(values)):
            delta = values[index] - values[index - 1]
            sign = 1 if delta > 0.5 else -1 if delta < -0.5 else 0
            if sign == 0:
                continue
            if previous_sign and sign != previous_sign:
                turns.append(values[index - 1])
            previous_sign = sign
        turns.append(values[-1])
        excursions = [
            abs(second - first)
            for first, second in zip(turns, turns[1:])
            if abs(second - first) >= minimum_excursion
        ]
        return len(excursions) >= 2

    def _update_head_motion(self, timestamp: float) -> tuple[list[ActionDisplay], list[ActionEvent]]:
        displays: list[ActionDisplay] = []
        events: list[ActionEvent] = []
        yaw = self._relative("head_yaw_deg")
        pitch = self._relative("head_pitch_deg")
        roll = self._relative("head_roll_deg")
        if yaw is None or pitch is None or roll is None:
            return displays, events
        self._head_history.append((timestamp, yaw, pitch, roll))
        cutoff = timestamp - self.config.temporal_history_s
        while self._head_history and self._head_history[0][0] < cutoff:
            self._head_history.popleft()

        recent = [item for item in self._head_history if item[0] >= timestamp - 1.5]
        nodding = self._has_oscillation([item[2] for item in recent], 10.0)
        shaking = self._has_oscillation([item[1] for item in recent], 12.0)
        speed_strength = 0.0
        if len(self._head_history) >= 2:
            before, current = self._head_history[-2], self._head_history[-1]
            elapsed = current[0] - before[0]
            if elapsed > 0:
                speed = sum(abs(current[i] - before[i]) for i in (1, 2, 3)) / elapsed
                speed_strength = speed / self.config.generic_head_speed_deg_s
        span = self._head_history[-1][0] - self._head_history[0][0]
        still = False
        if span >= self.config.stillness_duration_s:
            still = all(
                max(item[index] for item in self._head_history)
                - min(item[index] for item in self._head_history) < 3.0
                for index in (1, 2, 3)
            )
        strengths = {
            "nodding": 1.0 if nodding else 0.0,
            "shaking_head": 1.0 if shaking else 0.0,
            "head_movement_detected": speed_strength,
            "head_mostly_still": 1.0 if still else 0.0,
        }
        for action_id, strength in strengths.items():
            display, event = self._update_state(action_id, timestamp, strength)
            if display is not None:
                displays.append(display)
            if event is not None:
                events.append(event)
        return displays, events

    def _interrupt_states(self, timestamp: float) -> list[ActionEvent]:
        return [event for state in self._states.values() if (event := state.interrupt(timestamp)) is not None]

    def _interrupt_all(self, timestamp: float) -> list[ActionEvent]:
        events = self._interrupt_states(timestamp)
        if self._long_closure_active and self._closure_start is not None:
            events.append(ActionEvent(
                self._closure_start,
                timestamp,
                "long_eye_closure",
                max(0.0, timestamp - self._closure_start),
                self._closure_peak,
                "interrupted",
            ))
        return events

    def _clear_temporal(self, *, reset_states: bool = True) -> None:
        self.window.clear()
        self._head_history.clear()
        self._blink_times.clear()
        self._blink_visible_until = float("-inf")
        self._reset_closure()
        if reset_states:
            for state in self._states.values():
                state.reset()

    def interrupt(
        self, timestamp_s: float, mode: ActionMode
    ) -> tuple[ActionSnapshot, tuple[ActionEvent, ...]]:
        events = tuple(self._interrupt_all(timestamp_s))
        self._clear_temporal()
        return ActionSnapshot(mode, self.baseline.progress), events
