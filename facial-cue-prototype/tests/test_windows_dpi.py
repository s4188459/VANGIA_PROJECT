import unittest

from src.windows_dpi import enable_windows_dpi_awareness


class WindowsDpiTests(unittest.TestCase):
    def test_non_windows_platform_is_a_no_op(self):
        calls = []

        enabled = enable_windows_dpi_awareness(
            platform="linux",
            set_context=calls.append,
            set_legacy=lambda: calls.append("legacy"),
        )

        self.assertFalse(enabled)
        self.assertEqual(calls, [])

    def test_prefers_per_monitor_v2_context(self):
        calls = []

        enabled = enable_windows_dpi_awareness(
            platform="win32",
            set_context=lambda context: calls.append(("context", context)),
            set_legacy=lambda: calls.append(("legacy", None)),
        )

        self.assertTrue(enabled)
        self.assertEqual(calls, [("context", -4)])

    def test_falls_back_to_legacy_awareness(self):
        calls = []

        def fail_context(_context):
            raise OSError("unsupported")

        enabled = enable_windows_dpi_awareness(
            platform="win32",
            set_context=fail_context,
            set_legacy=lambda: calls.append("legacy"),
        )

        self.assertTrue(enabled)
        self.assertEqual(calls, ["legacy"])

    def test_false_context_result_also_uses_legacy_fallback(self):
        calls = []

        enabled = enable_windows_dpi_awareness(
            platform="win32",
            set_context=lambda _context: 0,
            set_legacy=lambda: calls.append("legacy") or 1,
        )

        self.assertTrue(enabled)
        self.assertEqual(calls, ["legacy"])


if __name__ == "__main__":
    unittest.main()
