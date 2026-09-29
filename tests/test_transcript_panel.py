import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from src.capture_types import CaptureRegion
from src.transcript_panel import TranscriptPanel, transcript_panel_geometry


class TranscriptPanelGeometryTests(unittest.TestCase):
    def test_closed_transcript_panel_ignores_late_updates(self):
        window = Mock(); text = Mock()
        with patch("src.transcript_panel.tk.Toplevel", return_value=window), \
             patch("src.transcript_panel.tk.Frame"), patch("src.transcript_panel.tk.Label"), \
             patch("src.transcript_panel.tk.StringVar"), patch("src.transcript_panel.tk.Text", return_value=text):
            root = Mock(); root.winfo_screenwidth.return_value = 1920; root.winfo_screenheight.return_value = 1080
            panel = TranscriptPanel(root, CaptureRegion(0, 0, 300, 300), exclude_native=lambda _: None)
            window.protocol.assert_called_with("WM_DELETE_WINDOW", panel.destroy)
            panel.destroy()
            text.reset_mock()
            panel.publish(SimpleNamespace(speaker="You", start_s=0., text="late"))
            self.assertFalse(panel.draw_pending())
            text.configure.assert_not_called()

    def test_exclusion_failure_destroys_unprotected_transcript_window(self):
        window = Mock()
        with patch("src.transcript_panel.tk.Toplevel", return_value=window), \
             patch("src.transcript_panel.tk.Frame"), patch("src.transcript_panel.tk.Label"), \
             patch("src.transcript_panel.tk.StringVar"), patch("src.transcript_panel.tk.Text"):
            root = Mock(); root.winfo_screenwidth.return_value = 1920; root.winfo_screenheight.return_value = 1080
            def fail(_): raise RuntimeError("exclusion failed")
            with self.assertRaisesRegex(RuntimeError, "exclusion failed"):
                TranscriptPanel(root, CaptureRegion(0, 0, 300, 300), exclude_native=fail)
            window.destroy.assert_called_once()

    def test_prefers_right_and_falls_back_left(self):
        self.assertEqual(transcript_panel_geometry(CaptureRegion(100, 100, 400, 300), (320, 300), (0, 0, 1920, 1080)), "320x300+508+100")
        self.assertEqual(transcript_panel_geometry(CaptureRegion(1500, 100, 400, 300), (320, 300), (0, 0, 1920, 1080)), "320x300+1172+100")


if __name__ == "__main__": unittest.main()
