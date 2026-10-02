import unittest

import numpy as np

from src.frame_processing import draw_overlay, prepare_frames


class FrameProcessingTests(unittest.TestCase):
    def test_prepare_frames_preserves_bgr_and_creates_rgb(self):
        source = np.array(
            [
                [[10, 20, 30], [40, 50, 60]],
                [[70, 80, 90], [100, 110, 120]],
            ],
            dtype=np.uint8,
        )

        preview, rgb = prepare_frames(source)

        np.testing.assert_array_equal(preview, source)
        np.testing.assert_array_equal(rgb[0, 0], [30, 20, 10])
        self.assertEqual(preview.shape, (2, 2, 3))
        self.assertEqual(rgb.shape, (2, 2, 3))
        self.assertFalse(np.shares_memory(source, preview))
        self.assertFalse(np.shares_memory(preview, rgb))

    def test_overlay_preserves_frame_dimensions(self):
        frame = np.zeros((120, 400, 3), dtype=np.uint8)

        draw_overlay(frame, "Face not detected", 7.5)

        self.assertEqual(frame.shape, (120, 400, 3))
        self.assertGreater(int(frame.sum()), 0)

    def test_paused_overlay_preserves_frame_dimensions(self):
        frame = np.zeros((120, 400, 3), dtype=np.uint8)

        draw_overlay(frame, "Face detected", 30.0, paused=True)

        self.assertEqual(frame.shape, (120, 400, 3))
        self.assertGreater(int(frame.sum()), 0)


if __name__ == "__main__":
    unittest.main()
class CaptureConversionTests(unittest.TestCase):
    def test_bgra_conversion_preserves_pixels_and_skips_unused_video_copy(self):
        from src.frame_processing import prepare_capture_frame
        import numpy as np
        raw = np.array([[[10, 20, 30, 255]]], np.uint8)
        rgb, bgr = prepare_capture_frame(raw, include_bgr=False)
        np.testing.assert_array_equal(rgb, [[[30, 20, 10]]])
        self.assertIsNone(bgr)
        rgb, bgr = prepare_capture_frame(raw, include_bgr=True)
        np.testing.assert_array_equal(bgr, [[[10, 20, 30]]])
        self.assertFalse(np.shares_memory(raw, bgr))
