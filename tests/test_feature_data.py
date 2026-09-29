import math
import unittest
from types import SimpleNamespace

import numpy as np

from src.feature_data import (
    FeatureFrame,
    LatestFeatureFrame,
    extract_feature_frame,
    gaze_label,
    matrix_to_euler_degrees,
)


def category(name, score):
    return SimpleNamespace(category_name=name, score=score)


def visible_result(matrix=None, omit=()):
    values = {
        "eyeLookOutLeft": 0.8,
        "eyeLookInRight": 0.6,
        "eyeLookInLeft": 0.2,
        "eyeLookOutRight": 0.4,
        "eyeLookUpLeft": 0.7,
        "eyeLookUpRight": 0.5,
        "eyeLookDownLeft": 0.1,
        "eyeLookDownRight": 0.3,
        "eyeBlinkLeft": 0.1,
        "eyeBlinkRight": 0.3,
        "browInnerUp": 0.4,
        "browOuterUpLeft": 0.7,
        "browOuterUpRight": 0.5,
        "browDownLeft": 0.2,
        "browDownRight": 0.1,
        "jawOpen": 0.8,
        "mouthSmileLeft": 0.3,
        "mouthSmileRight": 0.4,
        "mouthPucker": 0.2,
        "mouthFunnel": 0.1,
    }
    blendshapes = [
        category(name, value)
        for name, value in reversed(tuple(values.items()))
        if name not in omit
    ]
    landmarks = [
        SimpleNamespace(x=0.2, y=0.4, z=-0.1),
        SimpleNamespace(x=0.6, y=0.8, z=0.3),
    ]
    return SimpleNamespace(
        face_landmarks=[landmarks],
        face_blendshapes=[blendshapes],
        facial_transformation_matrixes=[
            np.eye(4, dtype=float) if matrix is None else matrix
        ],
    )


class FeatureExtractionTests(unittest.TestCase):
    def test_extracts_named_features_and_aggregates(self):
        frame = extract_feature_frame(visible_result(), 12.4, 8)

        self.assertTrue(frame.face_visible)
        self.assertIsNone(frame.confidence)
        self.assertAlmostEqual(frame.head_center_x, 0.4)
        self.assertAlmostEqual(frame.head_center_y, 0.6)
        self.assertAlmostEqual(frame.head_depth, 0.1)
        self.assertAlmostEqual(frame.gaze_left, 0.7)
        self.assertAlmostEqual(frame.gaze_right, 0.3)
        self.assertAlmostEqual(frame.gaze_up, 0.6)
        self.assertAlmostEqual(frame.gaze_down, 0.2)
        self.assertAlmostEqual(frame.blink, 0.2)
        self.assertAlmostEqual(frame.brow_raise, 0.7)
        self.assertAlmostEqual(frame.mouth_activity, 0.8)
        self.assertIn(("eyeBlinkLeft", 0.1), frame.blendshapes)
        self.assertIn(("mouthFunnel", 0.1), frame.blendshapes)

    def test_missing_face_has_only_timing_and_presence(self):
        result = SimpleNamespace(
            face_landmarks=[],
            face_blendshapes=[],
            facial_transformation_matrixes=[],
        )

        frame = extract_feature_frame(result, 13.0, 9)

        self.assertEqual(frame.timestamp_s, 13.0)
        self.assertEqual(frame.frame_index, 9)
        self.assertFalse(frame.face_visible)
        self.assertIsNone(frame.head_yaw_deg)
        self.assertIsNone(frame.blink)

    def test_missing_blendshape_does_not_use_category_position(self):
        frame = extract_feature_frame(
            visible_result(omit={"eyeBlinkRight", "mouthPucker"}),
            1.0,
            0,
        )

        self.assertEqual(frame.blink_left, 0.1)
        self.assertIsNone(frame.blink_right)
        self.assertIsNone(frame.blink)
        self.assertIsNone(frame.mouth_pucker)
        self.assertIsNone(frame.mouth_activity)

    def test_malformed_or_missing_matrix_leaves_orientation_blank(self):
        malformed = extract_feature_frame(visible_result(matrix=np.eye(2)), 0.0, 0)
        result = visible_result()
        result.facial_transformation_matrixes = []
        missing = extract_feature_frame(result, 0.0, 0)

        self.assertIsNone(malformed.head_yaw_deg)
        self.assertIsNone(missing.head_pitch_deg)


class EulerAngleTests(unittest.TestCase):
    def rotation(self, axis, degrees):
        angle = math.radians(degrees)
        c, s = math.cos(angle), math.sin(angle)
        if axis == "x":
            return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
        if axis == "y":
            return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
        return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])

    def test_identity_and_single_axis_rotations(self):
        self.assertEqual(matrix_to_euler_degrees(np.eye(4)), (0.0, 0.0, 0.0))
        yaw, pitch, roll = matrix_to_euler_degrees(self.rotation("y", 15))
        self.assertAlmostEqual(yaw, 15.0, places=2)
        self.assertAlmostEqual(pitch, 0.0, places=2)
        self.assertAlmostEqual(roll, 0.0, places=2)

        yaw, pitch, roll = matrix_to_euler_degrees(self.rotation("x", -12))
        self.assertAlmostEqual(pitch, -12.0, places=2)
        yaw, pitch, roll = matrix_to_euler_degrees(self.rotation("z", 9))
        self.assertAlmostEqual(roll, 9.0, places=2)

    def test_gimbal_lock_returns_finite_angles(self):
        angles = matrix_to_euler_degrees(self.rotation("y", 90))

        self.assertTrue(all(math.isfinite(value) for value in angles))


class FeaturePresentationTests(unittest.TestCase):
    def test_gaze_label_uses_threshold_and_strongest_direction(self):
        centered = extract_feature_frame(visible_result(), 0.0, 0)
        centered = centered.__class__(
            **{
                **vars(centered),
                "gaze_left": 0.1,
                "gaze_right": 0.12,
                "gaze_up": 0.19,
                "gaze_down": 0.05,
            }
        )

        self.assertEqual(gaze_label(centered), "Center")
        self.assertEqual(gaze_label(extract_feature_frame(visible_result(), 0, 0)), "Left")

    def test_latest_slot_coalesces_and_clears(self):
        slot = LatestFeatureFrame()
        first = extract_feature_frame(visible_result(), 1.0, 1)
        latest = extract_feature_frame(visible_result(), 2.0, 2)

        slot.publish(first)
        slot.publish(latest)
        self.assertIs(slot.take(), latest)
        self.assertIsNone(slot.take())
        slot.publish(first)
        slot.clear()
        self.assertIsNone(slot.take())


if __name__ == "__main__":
    unittest.main()
