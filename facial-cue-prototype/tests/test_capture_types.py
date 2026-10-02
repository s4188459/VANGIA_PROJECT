import unittest

from src.capture_types import AppState, CaptureRegion


class CaptureRegionTests(unittest.TestCase):
    def test_valid_region_converts_to_mss_dictionary(self):
        region = CaptureRegion(left=100, top=200, width=640, height=360)

        self.assertEqual(
            region.as_mss_region(),
            {"left": 100, "top": 200, "width": 640, "height": 360},
        )

    def test_zero_or_negative_dimensions_are_rejected(self):
        for width, height in ((0, 10), (10, 0), (-1, 10), (10, -1)):
            with self.subTest(width=width, height=height):
                with self.assertRaises(ValueError):
                    CaptureRegion(0, 0, width, height)

    def test_application_states_are_distinct(self):
        self.assertEqual(len(AppState), 6)
        self.assertIsNot(AppState.FINALIZING, AppState.READY)


if __name__ == "__main__":
    unittest.main()
