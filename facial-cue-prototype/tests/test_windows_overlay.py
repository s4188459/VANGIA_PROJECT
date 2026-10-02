import unittest

from src.capture_types import CaptureRegion
from src.windows_overlay import (
    GWL_EXSTYLE,
    WDA_EXCLUDEFROMCAPTURE,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TRANSPARENT,
    OverlayConfigurationError,
    configure_capture_excluded_window,
    exclude_window_from_capture,
    overlay_geometry,
)


class FakeUser32:
    def __init__(self, *, style=0x20, affinity_result=1, style_result=1):
        self.style = style
        self.affinity_result = affinity_result
        self.style_result = style_result
        self.calls = []

    def GetAncestor(self, hwnd, flag):
        self.calls.append(("get_ancestor", hwnd, flag))
        return hwnd + 1000

    def GetWindowLongPtrW(self, hwnd, index):
        self.calls.append(("get_style", hwnd, index))
        return self.style

    def SetWindowLongPtrW(self, hwnd, index, style):
        self.calls.append(("set_style", hwnd, index, style))
        return self.style_result

    def SetWindowDisplayAffinity(self, hwnd, affinity):
        self.calls.append(("set_affinity", hwnd, affinity))
        return self.affinity_result


class WindowsOverlayTests(unittest.TestCase):
    def test_geometry_supports_negative_desktop_coordinates(self):
        region = CaptureRegion(left=-1820, top=40, width=640, height=360)

        self.assertEqual(overlay_geometry(region), "640x360-1820+40")

    def test_overlay_configuration_adds_styles_and_capture_exclusion(self):
        user32 = FakeUser32(style=0x200)

        configure_capture_excluded_window(123, user32=user32, platform_name="win32")

        expected_style = 0x200 | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        self.assertEqual(
            user32.calls,
            [
                ("get_ancestor", 123, 2),
                ("get_style", 1123, GWL_EXSTYLE),
                ("set_style", 1123, GWL_EXSTYLE, expected_style),
                ("set_affinity", 1123, WDA_EXCLUDEFROMCAPTURE),
            ],
        )

    def test_control_panel_exclusion_does_not_change_window_styles(self):
        user32 = FakeUser32()

        exclude_window_from_capture(456, user32=user32, platform_name="win32")

        self.assertEqual(
            user32.calls,
            [
                ("get_ancestor", 456, 2),
                ("set_affinity", 1456, WDA_EXCLUDEFROMCAPTURE),
            ],
        )

    def test_non_windows_platform_has_readable_error(self):
        with self.assertRaisesRegex(OverlayConfigurationError, "Windows"):
            exclude_window_from_capture(1, user32=FakeUser32(), platform_name="linux")

    def test_failed_capture_exclusion_reports_error_code(self):
        with self.assertRaisesRegex(OverlayConfigurationError, "error 5"):
            exclude_window_from_capture(
                1,
                user32=FakeUser32(affinity_result=0),
                platform_name="win32",
                get_last_error=lambda: 5,
            )

    def test_failed_style_write_prevents_capture_exclusion(self):
        user32 = FakeUser32(style_result=0)

        with self.assertRaisesRegex(OverlayConfigurationError, "error 87"):
            configure_capture_excluded_window(
                1,
                user32=user32,
                platform_name="win32",
                get_last_error=lambda: 87,
            )

        self.assertFalse(any(call[0] == "set_affinity" for call in user32.calls))


if __name__ == "__main__":
    unittest.main()
