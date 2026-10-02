import math
import unittest

from src.action_temporal import BaselineModel, RollingFeatureWindow, TimedActionState
from src.action_types import ActionDetectionConfig
from src.feature_data import FeatureFrame


def frame_at(timestamp, *, visible=True, yaw=10.0, brow=0.4):
    return FeatureFrame(
        timestamp_s=timestamp,
        frame_index=round(timestamp * 100),
        face_visible=visible,
        head_yaw_deg=yaw,
        brow_raise=brow,
    )


class ActionDetectionConfigTests(unittest.TestCase):
    def test_defaults_and_sensitivity_validation(self):
        config = ActionDetectionConfig()
        self.assertEqual(config.baseline_duration_s, 2.0)
        self.assertEqual(config.baseline_min_samples, 30)
        self.assertEqual(config.maximum_overlay_actions, 4)
        with self.assertRaisesRegex(ValueError, "sensitivity"):
            ActionDetectionConfig(sensitivity=0.4)
        with self.assertRaisesRegex(ValueError, "timing"):
            ActionDetectionConfig(release_duration_s=-0.1)
        with self.assertRaisesRegex(ValueError, "counts"):
            ActionDetectionConfig(frequent_blink_count=0)


class BaselineModelTests(unittest.TestCase):
    def test_collects_finite_visible_values_independently(self):
        baseline = BaselineModel(ActionDetectionConfig(
            baseline_duration_s=0.01, baseline_min_samples=2
        ))
        baseline.add(frame_at(0.00, yaw=9.0, brow=0.35))
        baseline.add(frame_at(0.04, yaw=11.0, brow=None))
        baseline.add(frame_at(0.08, visible=False, yaw=100.0, brow=100.0))
        baseline.add(frame_at(0.12, yaw=math.nan, brow=math.inf))

        self.assertAlmostEqual(baseline.median("head_yaw_deg"), 10.0)
        self.assertIsNone(baseline.median("brow_raise"))
        self.assertAlmostEqual(baseline.mad("head_yaw_deg"), 1.0)

    def test_completion_requires_samples_and_contiguous_observation_time(self):
        baseline = BaselineModel(ActionDetectionConfig(
            baseline_duration_s=0.10,
            baseline_min_samples=3,
            max_contiguous_gap_s=0.05,
        ))
        for timestamp in (0.00, 0.04, 0.20, 0.24):
            baseline.add(frame_at(timestamp))
        self.assertFalse(baseline.complete)
        self.assertAlmostEqual(baseline.valid_duration_s, 0.08)
        self.assertLessEqual(baseline.progress, 1.0)
        baseline.add(frame_at(0.28))
        self.assertTrue(baseline.complete)
        self.assertEqual(baseline.progress, 1.0)


class RollingFeatureWindowTests(unittest.TestCase):
    def test_median_rejects_spike_and_expires_old_values(self):
        window = RollingFeatureWindow(0.25)
        window.add(frame_at(0.00, yaw=10.0))
        window.add(frame_at(0.10, yaw=100.0))
        window.add(frame_at(0.20, yaw=10.0))
        self.assertEqual(window.median("head_yaw_deg"), 10.0)
        window.add(frame_at(0.40, yaw=20.0))
        self.assertEqual(window.median("head_yaw_deg"), 15.0)

    def test_missing_values_are_not_zero_and_clear_removes_samples(self):
        window = RollingFeatureWindow(0.25)
        window.add(frame_at(0.0, yaw=None))
        self.assertIsNone(window.median("head_yaw_deg"))
        window.add(frame_at(0.1, yaw=5.0))
        window.clear()
        self.assertIsNone(window.median("head_yaw_deg"))


class TimedActionStateTests(unittest.TestCase):
    def make_state(self):
        return TimedActionState("test_action", "Test action", 0.25, 0.15, 0.30)

    def test_activation_requires_hold_and_release_uses_hysteresis(self):
        state = self.make_state()
        self.assertEqual(state.update(1.00, 0.70, 0.60, 0.35), (None, None))
        display, event = state.update(1.30, 0.72, 0.60, 0.35)
        self.assertAlmostEqual(display.duration_s, 0.30)
        self.assertEqual(display.action_id, "test_action")
        self.assertIsNone(event)
        display, event = state.update(1.40, 0.40, 0.60, 0.35)
        self.assertIsNotNone(display)
        self.assertIsNone(event)
        state.update(1.50, 0.20, 0.60, 0.35)
        display, event = state.update(1.70, 0.20, 0.60, 0.35)
        self.assertIsNone(display)
        self.assertEqual(event.status, "completed")
        self.assertAlmostEqual(event.end_time_s, 1.50)
        self.assertAlmostEqual(event.duration_s, 0.50)
        self.assertAlmostEqual(event.peak_strength, 0.72)

    def test_interruption_is_idempotent_and_pending_does_not_emit(self):
        pending = self.make_state()
        pending.update(1.0, 0.8, 0.6, 0.35)
        self.assertIsNone(pending.interrupt(1.1))

        active = self.make_state()
        active.update(2.0, 0.8, 0.6, 0.35)
        active.update(2.3, 0.9, 0.6, 0.35)
        event = active.interrupt(2.4)
        self.assertEqual(event.status, "interrupted")
        self.assertAlmostEqual(event.duration_s, 0.4)
        self.assertIsNone(active.interrupt(2.5))

    def test_cooldown_and_timestamp_validation(self):
        state = self.make_state()
        state.update(1.0, 0.8, 0.6, 0.35)
        state.update(1.3, 0.8, 0.6, 0.35)
        state.update(1.4, 0.1, 0.6, 0.35)
        state.update(1.6, 0.1, 0.6, 0.35)
        self.assertEqual(state.update(1.7, 0.9, 0.6, 0.35), (None, None))
        with self.assertRaisesRegex(ValueError, "Action timestamps must increase"):
            state.update(1.7, 0.9, 0.6, 0.35)


if __name__ == "__main__":
    unittest.main()
