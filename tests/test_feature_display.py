import unittest

from src.control_panel import format_feature_display
from src.feature_data import FeatureFrame


class FeatureDisplayTests(unittest.TestCase):
    def test_visible_feature_values_are_compact_and_readable(self):
        frame = FeatureFrame(
            12.4,
            247,
            True,
            head_yaw_deg=8.2,
            head_pitch_deg=-2.1,
            head_roll_deg=1.4,
            gaze_up=0.71,
            blink=0.12,
            brow_raise=0.63,
            mouth_activity=0.44,
            processing_ms=18.25,
        )

        display = format_feature_display(frame, 248, "session_001.csv")

        self.assertEqual(display["recording"], "session_001.csv")
        self.assertEqual(display["elapsed"], "12.40 s")
        self.assertEqual(display["face"], "Visible")
        self.assertEqual(display["head"], "Yaw 8.20 | Pitch -2.10 | Roll 1.40")
        self.assertEqual(display["gaze"], "Up 0.71")
        self.assertEqual(display["blink"], "0.12")
        self.assertEqual(display["brow"], "0.63")
        self.assertEqual(display["mouth"], "0.44")
        self.assertEqual(display["landmark_latency"], "18.2 ms")
        self.assertEqual(display["rows"], "248")

    def test_missing_face_uses_blank_feature_markers(self):
        display = format_feature_display(
            FeatureFrame(3.0, 8, False), 9, "session_002.csv"
        )

        self.assertEqual(display["face"], "Not detected")
        for name in ("head", "gaze", "blink", "brow", "mouth"):
            self.assertEqual(display[name], "--")
        self.assertEqual(display["landmark_latency"], "--")

    def test_long_filename_is_shortened_only_for_display(self):
        filename = "session_with_a_very_long_descriptive_filename_001.csv"
        display = format_feature_display(FeatureFrame(0, 0, False), 0, filename)

        self.assertLessEqual(len(display["recording"]), 40)
        self.assertTrue(display["recording"].startswith("session_"))
        self.assertTrue(display["recording"].endswith("001.csv"))


if __name__ == "__main__":
    unittest.main()
