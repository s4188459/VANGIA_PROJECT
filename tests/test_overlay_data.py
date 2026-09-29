import unittest
from dataclasses import fields
from types import SimpleNamespace

from src.overlay_data import (
    LatestOverlayFrame,
    OverlayFrame,
    connection_segments,
    landmarks_to_pixels,
)


class OverlayDataTests(unittest.TestCase):
    def test_landmarks_are_rounded_and_clamped_to_region(self):
        landmarks = [
            SimpleNamespace(x=0.0, y=0.0),
            SimpleNamespace(x=1.0, y=1.0),
            SimpleNamespace(x=0.5, y=0.5),
            SimpleNamespace(x=-0.2, y=1.4),
        ]

        points = landmarks_to_pixels(landmarks, width=100, height=50)

        self.assertEqual(points, ((0, 0), (99, 49), (50, 24), (0, 49)))

    def test_landmark_conversion_rejects_non_positive_dimensions(self):
        landmark = SimpleNamespace(x=0.5, y=0.5)

        with self.assertRaises(ValueError):
            landmarks_to_pixels([landmark], width=0, height=10)
        with self.assertRaises(ValueError):
            landmarks_to_pixels([landmark], width=10, height=-1)

    def test_connections_ignore_invalid_point_indices(self):
        points = ((1, 2), (3, 4), (5, 6))

        segments = connection_segments(points, ((0, 1), (1, 2), (-1, 0), (2, 8)))

        self.assertEqual(segments, ((1, 2, 3, 4), (3, 4, 5, 6)))

    def test_latest_slot_coalesces_frames_and_take_consumes_value(self):
        slot = LatestOverlayFrame()
        first = OverlayFrame(((1, 1),), True, 10.0)
        latest = OverlayFrame(((2, 2),), True, 20.0)

        slot.publish(first)
        slot.publish(latest)

        self.assertIs(slot.take(), latest)
        self.assertIsNone(slot.take())

    def test_clear_discards_pending_frame(self):
        slot = LatestOverlayFrame()
        slot.publish(OverlayFrame((), False, 0.0))

        slot.clear()

        self.assertIsNone(slot.take())

    def test_overlay_frame_uses_immutable_action_snapshot_not_legacy_strings(self):
        names = {field.name for field in fields(OverlayFrame)}
        self.assertIn("action_snapshot", names)
        self.assertNotIn("actions", names)


if __name__ == "__main__":
    unittest.main()
