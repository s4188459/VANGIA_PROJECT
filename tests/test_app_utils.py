import unittest

from src.app_utils import (
    EXIT_KEYS,
    PreviewAction,
    face_status_text,
    format_fps,
    preview_action,
    should_exit,
)


class AppUtilsTests(unittest.TestCase):
    def test_face_status_text_reports_detected_face(self):
        self.assertEqual(face_status_text(True), "Face detected")

    def test_face_status_text_reports_missing_face(self):
        self.assertEqual(face_status_text(False), "Face not detected")

    def test_format_fps_uses_fixed_width_layout(self):
        self.assertEqual(format_fps(7.456), "FPS: 007.5")
        self.assertEqual(format_fps(123.456), "FPS: 123.5")

    def test_should_exit_accepts_q_escape_and_ignores_other_keys(self):
        self.assertTrue(should_exit(ord("q")))
        self.assertTrue(should_exit(ord("Q")))
        self.assertTrue(should_exit(27))
        self.assertFalse(should_exit(ord("x")))
        self.assertFalse(should_exit(-1))
        self.assertEqual(EXIT_KEYS, {ord("q"), ord("Q"), 27})

    def test_preview_action_maps_control_keys(self):
        self.assertEqual(preview_action(ord("s")), PreviewAction.TOGGLE_PAUSE)
        self.assertEqual(preview_action(ord("S")), PreviewAction.TOGGLE_PAUSE)
        self.assertEqual(preview_action(ord("r")), PreviewAction.RESELECT)
        self.assertEqual(preview_action(ord("R")), PreviewAction.RESELECT)
        self.assertEqual(preview_action(ord("q")), PreviewAction.QUIT)
        self.assertEqual(preview_action(ord("Q")), PreviewAction.QUIT)
        self.assertEqual(preview_action(27), PreviewAction.QUIT)
        self.assertEqual(preview_action(ord("x")), PreviewAction.NONE)


if __name__ == "__main__":
    unittest.main()
