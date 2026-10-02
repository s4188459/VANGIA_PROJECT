import unittest
from unittest.mock import patch

import numpy as np

from src.action_types import ActionDisplay, ActionMode, ActionSnapshot
from src.overlay_data import OverlayFrame
from src.overlay_renderer import (
    CONTOUR_CONNECTIONS,
    TESSELLATION_CONNECTIONS,
    TRANSPARENT_RGB,
    render_overlay_rgb,
    rgb_to_ppm,
)


class OverlayRendererTests(unittest.TestCase):
    def test_tasks_connection_sets_are_available_as_index_pairs(self):
        self.assertGreater(len(TESSELLATION_CONNECTIONS), 0)
        self.assertGreater(len(CONTOUR_CONNECTIONS), 0)
        self.assertTrue(all(len(edge) == 2 for edge in TESSELLATION_CONNECTIONS))

    def test_render_has_fixed_dimensions_and_transparent_background(self):
        frame = OverlayFrame((), False, 12.5)

        image = render_overlay_rgb(frame, 320, 180, tessellation=(), contours=())

        self.assertEqual(image.shape, (180, 320, 3))
        self.assertEqual(image.dtype, np.uint8)
        np.testing.assert_array_equal(image[-1, -1], TRANSPARENT_RGB)

    def test_render_draws_connections_from_landmark_points(self):
        frame = OverlayFrame(((250, 120), (300, 160)), True, 30.0)

        image = render_overlay_rgb(
            frame,
            320,
            180,
            tessellation=((0, 1),),
            contours=(),
        )

        self.assertFalse(np.array_equal(image[140, 275], TRANSPARENT_RGB))

    def test_render_lists_snapshot_actions_with_durations_and_limit(self):
        actions = tuple(
            ActionDisplay(f"a{index}", f"Action {index}", index + 0.25, 1.0)
            for index in range(5)
        )
        with patch("src.overlay_renderer.cv2.putText", wraps=None) as put_text:
            render_overlay_rgb(
                OverlayFrame(
                    (), True, 30.0,
                    action_snapshot=ActionSnapshot(ActionMode.TRACKING, actions=actions),
                ),
                640,
                360,
                tessellation=(),
                contours=(),
            )
        texts = [call.args[1] for call in put_text.call_args_list]
        self.assertIn("Action 0  0.2s", texts)
        self.assertIn("Action 3  3.2s", texts)
        self.assertNotIn("Action 4  4.2s", texts)

    def test_render_special_snapshot_states(self):
        cases = (
            (ActionSnapshot(ActionMode.CALIBRATING, 0.64), "Calibrating... 64%"),
            (ActionSnapshot(ActionMode.FACE_MISSING), "Face not detected"),
            (ActionSnapshot(ActionMode.TRACKING, face_reacquired=True), "Face detected again"),
            (ActionSnapshot(ActionMode.TRACKING), "No observable action"),
            (ActionSnapshot(ActionMode.PAUSED), "Paused"),
        )
        for snapshot, expected in cases:
            with self.subTest(expected=expected):
                with patch("src.overlay_renderer.cv2.putText", wraps=None) as put_text:
                    render_overlay_rgb(
                        OverlayFrame((), True, 30.0, action_snapshot=snapshot),
                        640, 360, tessellation=(), contours=(),
                    )
                self.assertIn(expected, [call.args[1] for call in put_text.call_args_list])

    def test_panel_is_bounded_and_has_dithered_background(self):
        for width, height in ((160, 90), (320, 180), (1920, 1080)):
            with self.subTest(size=(width, height)):
                image = render_overlay_rgb(
                    OverlayFrame(
                        (), True, 30.0,
                        action_snapshot=ActionSnapshot(ActionMode.TRACKING),
                    ),
                    width, height, tessellation=(), contours=(),
                )
                self.assertEqual(image.shape, (height, width, 3))
                panel = image[8:min(height, 80), 8:min(width, 150)]
                colors = {tuple(pixel) for row in panel for pixel in row}
                self.assertIn(TRANSPARENT_RGB, colors)
                self.assertIn((17, 17, 17), colors)

    def test_ppm_encoding_contains_one_complete_rgb_bitmap(self):
        image = np.full((2, 3, 3), TRANSPARENT_RGB, dtype=np.uint8)

        encoded = rgb_to_ppm(image)

        self.assertTrue(encoded.startswith(b"P6\n3 2\n255\n"))
        self.assertEqual(len(encoded), len(b"P6\n3 2\n255\n") + 18)


if __name__ == "__main__":
    unittest.main()
