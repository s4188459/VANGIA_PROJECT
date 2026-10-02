import unittest
from types import SimpleNamespace

from src.capture_types import CaptureRegion
from src.region_selector import absolute_region, drag_region, select_screen_region


class RegionGeometryTests(unittest.TestCase):
    def test_adds_monitor_origin_to_relative_roi(self):
        self.assertEqual(
            absolute_region(100, 50, (20, 30, 640, 360)),
            CaptureRegion(120, 80, 640, 360),
        )

    def test_drag_region_normalizes_reverse_drag_on_negative_desktop(self):
        self.assertEqual(
            drag_region(-1920, -100, (500, 300), (100, 50)),
            CaptureRegion(-1820, -50, 400, 250),
        )

    def test_zero_size_selection_is_cancelled(self):
        self.assertIsNone(drag_region(0, 0, (10, 20), (10, 20)))


class FakeParent:
    def __init__(self):
        self.calls = []

    def withdraw(self):
        self.calls.append("withdraw")

    def deiconify(self):
        self.calls.append("deiconify")

    def lift(self):
        self.calls.append("lift")


class FakeWindow:
    def __init__(self, parent):
        self.parent = parent
        self.calls = []
        self.bindings = {}
        self.canvas = None
        self.destroyed = False

    def overrideredirect(self, value):
        self.calls.append(("overrideredirect", value))

    def attributes(self, *args):
        self.calls.append(("attributes", *args))

    def geometry(self, value):
        self.calls.append(("geometry", value))

    def configure(self, **kwargs):
        self.calls.append(("configure", kwargs))

    def bind(self, name, callback):
        self.bindings[name] = callback

    def focus_force(self):
        self.calls.append(("focus_force",))

    def grab_set(self):
        self.calls.append(("grab_set",))

    def grab_release(self):
        self.calls.append(("grab_release",))

    def wait_window(self):
        self.canvas.bindings["<ButtonPress-1>"](SimpleNamespace(x=500, y=300))
        self.canvas.bindings["<B1-Motion>"](SimpleNamespace(x=100, y=50))
        self.canvas.bindings["<ButtonRelease-1>"](SimpleNamespace(x=100, y=50))

    def destroy(self):
        self.destroyed = True


class FakeCanvas:
    def __init__(self, window, **kwargs):
        self.window = window
        self.kwargs = kwargs
        self.bindings = {}
        self.coords_calls = []
        window.canvas = self

    def pack(self, **_kwargs):
        pass

    def bind(self, name, callback):
        self.bindings[name] = callback

    def create_rectangle(self, *_args, **_kwargs):
        return 7

    def coords(self, item, *coords):
        self.coords_calls.append((item, coords))


class DesktopSelectionTests(unittest.TestCase):
    def test_window_creation_failure_restores_parent(self):
        parent = FakeParent()
        def fail(_): raise RuntimeError("window failed")
        with self.assertRaisesRegex(RuntimeError, "window failed"):
            select_screen_region(parent, monitor_provider=lambda: {"left": 0, "top": 0, "width": 10, "height": 10},
                                 window_factory=fail)
        self.assertEqual(parent.calls, ["withdraw", "deiconify", "lift"])

    def test_selects_directly_on_virtual_desktop_without_screen_capture(self):
        parent = FakeParent()
        created = []

        def window_factory(root):
            window = FakeWindow(root)
            created.append(window)
            return window

        result = select_screen_region(
            parent,
            monitor_provider=lambda: {
                "left": -1920,
                "top": -100,
                "width": 3840,
                "height": 1180,
            },
            window_factory=window_factory,
            canvas_factory=FakeCanvas,
        )

        self.assertEqual(result, CaptureRegion(-1820, -50, 400, 250))
        self.assertEqual(parent.calls, ["withdraw", "deiconify", "lift"])
        self.assertIn(("geometry", "3840x1180-1920-100"), created[0].calls)
        self.assertTrue(created[0].destroyed)


if __name__ == "__main__":
    unittest.main()
