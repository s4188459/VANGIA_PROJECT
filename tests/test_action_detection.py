import unittest

from src.action_detection import ActionDetector, rank_actions
from src.action_types import ActionDetectionConfig, ActionDisplay, ActionMode
from src.feature_data import FeatureFrame


def feature(timestamp, *, visible=True, **changes):
    values = dict(
        confidence=0.95,
        head_yaw_deg=9.0,
        head_pitch_deg=6.0,
        head_roll_deg=-1.0,
        gaze_left=0.10,
        gaze_right=0.10,
        gaze_up=0.10,
        gaze_down=0.219,
        blink_left=0.10,
        blink_right=0.10,
        blink=0.10,
        brow_inner_up=0.30,
        brow_outer_up_left=0.30,
        brow_outer_up_right=0.30,
        brow_down_left=0.10,
        brow_down_right=0.10,
        brow_raise=0.377,
        jaw_open=0.10,
        mouth_smile_left=0.10,
        mouth_smile_right=0.10,
        mouth_pucker=0.75,
        mouth_funnel=0.10,
        mouth_activity=0.75,
    )
    values.update(changes)
    return FeatureFrame(timestamp, round(timestamp * 100), visible, **values)


def fast_config(**changes):
    values = dict(
        baseline_duration_s=0.20,
        baseline_min_samples=3,
        smoothing_window_s=0.04,
        minimum_action_duration_s=0.10,
        release_duration_s=0.05,
    )
    values.update(changes)
    return ActionDetectionConfig(**values)


def calibrated_detector(config=None):
    detector = ActionDetector(config or fast_config())
    snapshots = [detector.update(feature(t))[0] for t in (0.0, 0.1, 0.2)]
    assert snapshots[-1].mode is ActionMode.TRACKING
    return detector


def ids(snapshot):
    return {action.action_id for action in snapshot.actions}


class CalibrationAndFaceTests(unittest.TestCase):
    def test_calibration_requires_time_and_samples_and_keeps_partial_features(self):
        detector = ActionDetector(fast_config())
        first, events = detector.update(feature(0.0, brow_raise=None))
        second, _ = detector.update(feature(0.1, brow_raise=None))
        third, _ = detector.update(feature(0.2, brow_raise=None))
        self.assertEqual(first.mode, ActionMode.CALIBRATING)
        self.assertLess(second.calibration_progress, 1.0)
        self.assertEqual(third.mode, ActionMode.TRACKING)
        self.assertEqual(events, ())
        self.assertIsNotNone(detector.baseline.median("head_yaw_deg"))
        self.assertIsNone(detector.baseline.median("brow_raise"))

    def test_missing_face_time_never_counts_toward_calibration(self):
        detector = ActionDetector(fast_config(
            baseline_duration_s=0.20,
            baseline_min_samples=3,
            max_contiguous_gap_s=0.25,
        ))
        detector.update(feature(0.00))
        detector.update(feature(0.10, visible=False))
        detector.update(feature(0.20))
        snapshot, _ = detector.update(feature(0.30))
        self.assertEqual(snapshot.mode, ActionMode.CALIBRATING)
        self.assertAlmostEqual(detector.baseline.valid_duration_s, 0.10)

    def test_face_loss_confirmation_reacquisition_and_baseline_retention(self):
        detector = calibrated_detector(fast_config(missing_face_hold_s=0.20))
        missing, events = detector.update(feature(0.3, visible=False))
        self.assertEqual(missing.mode, ActionMode.FACE_MISSING)
        self.assertEqual(events, ())
        _, events = detector.update(feature(0.51, visible=False))
        self.assertEqual(events[0].action, "face_not_detected")
        returned, events = detector.update(feature(0.6))
        self.assertTrue(returned.face_reacquired)
        self.assertEqual(events[0].action, "face_detected_again")
        self.assertEqual(detector.baseline.median("head_yaw_deg"), 9.0)


class StaticActionTests(unittest.TestCase):
    def assert_action(self, changes, expected):
        detector = calibrated_detector()
        for timestamp in (0.30, 0.40, 0.50):
            detector.update(feature(timestamp, **changes))
        snapshot, _ = detector.update(feature(0.62, **changes))
        self.assertIn(expected, ids(snapshot))

    def test_all_head_orientations(self):
        cases = (
            ({"head_yaw_deg": -7.0}, "head_turned_left"),
            ({"head_yaw_deg": 25.0}, "head_turned_right"),
            ({"head_pitch_deg": -7.0}, "head_raised"),
            ({"head_pitch_deg": 19.0}, "head_lowered"),
            ({"head_roll_deg": -14.0}, "head_tilted_left"),
            ({"head_roll_deg": 12.0}, "head_tilted_right"),
        )
        for changes, expected in cases:
            with self.subTest(expected=expected):
                self.assert_action(changes, expected)

    def test_gaze_is_baseline_relative_dominant_and_independent_from_head(self):
        detector = calibrated_detector()
        detector.update(feature(0.30, gaze_down=0.46, brow_raise=0.81))
        snapshot, _ = detector.update(feature(0.42, gaze_down=0.46, brow_raise=0.81))
        self.assertNotIn("eyes_looking_down", ids(snapshot))
        detector.update(feature(0.60, gaze_down=0.63, brow_raise=0.34))
        snapshot, _ = detector.update(feature(0.72, gaze_down=0.63, brow_raise=0.34))
        self.assertIn("eyes_looking_down", ids(snapshot))

        tied = calibrated_detector()
        tied.update(feature(0.30, gaze_left=0.50, gaze_right=0.46))
        snapshot, _ = tied.update(feature(0.42, gaze_left=0.50, gaze_right=0.46))
        self.assertFalse(ids(snapshot) & {"eyes_looking_left", "eyes_looking_right"})

    def test_brow_and_mouth_specific_actions_and_nonzero_pucker_baseline(self):
        cases = (
            ({"brow_inner_up": 0.50}, "inner_brows_raised"),
            ({"brow_raise": 0.65, "brow_outer_up_left": 0.55, "brow_outer_up_right": 0.55}, "brows_raised"),
            ({"brow_down_left": 0.35, "brow_down_right": 0.35}, "brows_lowered"),
            ({"brow_outer_up_left": 0.55, "brow_outer_up_right": 0.25}, "asymmetric_brow_movement"),
            ({"jaw_open": 0.40}, "jaw_opened"),
            ({"mouth_smile_left": 0.40, "mouth_smile_right": 0.40}, "smile_movement_detected"),
            ({"mouth_pucker": 0.95}, "mouth_puckered"),
            ({"mouth_funnel": 0.30}, "mouth_funnel_detected"),
        )
        for changes, expected in cases:
            with self.subTest(expected=expected):
                self.assert_action(changes, expected)
        neutral = calibrated_detector()
        neutral.update(feature(0.30, mouth_pucker=0.75))
        snapshot, _ = neutral.update(feature(0.42, mouth_pucker=0.75))
        self.assertNotIn("mouth_puckered", ids(snapshot))

    def test_large_gap_interrupts_and_nonincreasing_timestamp_fails(self):
        detector = calibrated_detector()
        detector.update(feature(0.30, head_yaw_deg=25.0))
        detector.update(feature(0.42, head_yaw_deg=25.0))
        snapshot, events = detector.update(feature(0.80, head_yaw_deg=25.0))
        self.assertIn("head_turned_right", {event.action for event in events})
        self.assertEqual(events[0].status, "interrupted")
        self.assertNotIn("head_turned_right", ids(snapshot))
        with self.assertRaisesRegex(ValueError, "timestamps must increase"):
            detector.update(feature(0.80))


class RankingTests(unittest.TestCase):
    def test_suppression_sorting_and_limit(self):
        displays = (
            ActionDisplay("mouth_movement_detected", "Mouth movement detected", 2, 2, True),
            ActionDisplay("jaw_opened", "Jaw opened", 1, 1),
            ActionDisplay("head_movement_detected", "Head movement detected", 3, 2, True),
            ActionDisplay("nodding", "Nodding", 1, 2),
            ActionDisplay("z", "Z", 0.5, 1),
            ActionDisplay("a", "A", 0.5, 1),
        )
        ranked = rank_actions(displays, 4)
        self.assertEqual([item.action_id for item in ranked], ["nodding", "jaw_opened", "a", "z"])


class TemporalActionTests(unittest.TestCase):
    def test_normal_blink_long_closure_and_asymmetry(self):
        detector = calibrated_detector(fast_config(smoothing_window_s=0.02))
        detector.update(feature(0.30, blink=0.8, blink_left=0.8, blink_right=0.8))
        detector.update(feature(0.36, blink=0.8, blink_left=0.8, blink_right=0.8))
        snapshot, events = detector.update(feature(0.40))
        self.assertIn("blinking", ids(snapshot))
        self.assertIn("blinking", {event.action for event in events})

        long_detector = calibrated_detector(fast_config(smoothing_window_s=0.02))
        for timestamp in (0.30, 0.50, 0.70, 0.90, 1.10, 1.15):
            snapshot, _ = long_detector.update(feature(
                timestamp, blink=0.85, blink_left=0.85, blink_right=0.85
            ))
        self.assertIn("long_eye_closure", ids(snapshot))
        snapshot, events = long_detector.update(feature(1.20))
        self.assertNotIn("blinking", ids(snapshot))
        self.assertIn("long_eye_closure", {event.action for event in events})

        asymmetric = calibrated_detector(fast_config(smoothing_window_s=0.02))
        for timestamp in (0.30, 0.40, 0.50, 0.62):
            snapshot, _ = asymmetric.update(feature(
                timestamp, blink=0.40, blink_left=0.70, blink_right=0.10
            ))
        self.assertIn("asymmetric_eye_closure", ids(snapshot))

    def test_four_blinks_in_window_show_frequent_blinking(self):
        detector = calibrated_detector(fast_config(smoothing_window_s=0.02))
        timestamp = 0.30
        snapshot = None
        for _ in range(4):
            detector.update(feature(timestamp, blink=0.8, blink_left=0.8, blink_right=0.8))
            detector.update(feature(timestamp + 0.06, blink=0.8, blink_left=0.8, blink_right=0.8))
            snapshot, _ = detector.update(feature(timestamp + 0.10))
            timestamp += 0.25
        self.assertIn("frequent_blinking", ids(snapshot))

    def test_nod_shake_generic_movement_and_stillness(self):
        nod = calibrated_detector(fast_config(smoothing_window_s=0.02))
        for timestamp, pitch in zip((0.30, 0.40, 0.50, 0.60, 0.70), (6, 18, -6, 18, 18)):
            snapshot, _ = nod.update(feature(timestamp, head_pitch_deg=pitch))
        self.assertIn("nodding", ids(snapshot))

        shake = calibrated_detector(fast_config(smoothing_window_s=0.02))
        for timestamp, yaw in zip((0.30, 0.40, 0.50, 0.60, 0.70), (9, 22, -4, 22, 22)):
            snapshot, _ = shake.update(feature(timestamp, head_yaw_deg=yaw))
        self.assertIn("shaking_head", ids(snapshot))

        moving = calibrated_detector(fast_config(smoothing_window_s=0.02))
        for timestamp, roll in zip((0.30, 0.40, 0.50, 0.60, 0.70), (-1, 3, 7, 11, 15)):
            snapshot, _ = moving.update(feature(timestamp, head_roll_deg=roll))
        self.assertIn("head_movement_detected", ids(snapshot))

        still = calibrated_detector(fast_config(smoothing_window_s=0.02))
        for step in range(17):
            snapshot, _ = still.update(feature(0.30 + step * 0.10))
        self.assertIn("head_mostly_still", ids(snapshot))


if __name__ == "__main__":
    unittest.main()
