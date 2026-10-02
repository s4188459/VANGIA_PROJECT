import unittest
from unittest.mock import patch

from src.capture_types import CaptureRegion
from src.overlay_data import OverlayFrame
from src.overlay_window import LandmarkOverlay
from src.windows_overlay import OverlayConfigurationError


class FakeToplevel:
    instances = []

    def __init__(self, root):
        self.root = root
        self.calls = []
        self.destroyed = False
        self.__class__.instances.append(self)

    def overrideredirect(self, value):
        self.calls.append(("overrideredirect", value))

    def attributes(self, *args):
        self.calls.append(("attributes", *args))

    def configure(self, **kwargs):
        self.calls.append(("configure", kwargs))

    def geometry(self, value):
        self.calls.append(("geometry", value))

    def update_idletasks(self):
        self.calls.append(("update_idletasks",))

    def winfo_id(self):
        return 321

    def destroy(self):
        self.destroyed = True
        self.calls.append(("destroy",))


class FakeCanvas:
    instances = []

    def __init__(self, parent, **kwargs):
        self.parent = parent
        self.kwargs = kwargs
        self.calls = []
        self.__class__.instances.append(self)

    def pack(self, **kwargs):
        self.calls.append(("pack", kwargs))

    def delete(self, tag):
        self.calls.append(("delete", tag))

    def create_line(self, *coords, **kwargs):
        self.calls.append(("line", coords, kwargs))

    def create_rectangle(self, *coords, **kwargs):
        self.calls.append(("rectangle", coords, kwargs))

    def create_text(self, *coords, **kwargs):
        self.calls.append(("text", coords, kwargs))

    def create_image(self, *coords, **kwargs):
        self.calls.append(("image", coords, kwargs))
        return 42

    def itemconfigure(self, item, **kwargs):
        self.calls.append(("itemconfigure", item, kwargs))


class FakePhotoImage:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.__class__.instances.append(self)


class OverlayWindowTests(unittest.TestCase):
    def test_render_timestamps_and_pause_redraw_do_not_reuse_capture_timing(self):
        from src.landmark_timing import LandmarkTimingRecorder
        from src.session_clock import SessionClock
        clock = SessionClock()
        clock.start()
        timing = LandmarkTimingRecorder(clock).begin(8)
        overlay = LandmarkOverlay(object(), CaptureRegion(0, 0, 20, 20),
                                  configure_native=lambda _: None)
        overlay.publish(OverlayFrame((), False, 0, timing=timing))
        overlay.draw_pending()
        self.assertEqual(timing.values.get('outcome'), 'rendered')
        self.assertLessEqual(timing.values['ui_consumed_s'], timing.values['bitmap_end_s'])
        self.assertLessEqual(timing.values['bitmap_end_s'], timing.values['render_end_s'])
        original = dict(timing.values)
        overlay.set_paused(True)
        self.assertIsNone(overlay._pending.take().timing)
        self.assertEqual(timing.values, original)
        overlay.destroy()

    def test_render_failure_does_not_claim_render_completion(self):
        from src.landmark_timing import LandmarkTimingRecorder
        from src.session_clock import SessionClock
        clock = SessionClock()
        clock.start()
        timing = LandmarkTimingRecorder(clock).begin(9)
        overlay = LandmarkOverlay(object(), CaptureRegion(0, 0, 20, 20),
                                  configure_native=lambda _: None)
        overlay.publish(OverlayFrame((), False, 0, timing=timing))
        with patch('src.overlay_window.render_overlay_ppm', side_effect=RuntimeError('render failed')):
            with self.assertRaises(RuntimeError):
                overlay.draw_pending()
        self.assertEqual(timing.values.get('outcome'), 'render_error')
        self.assertNotIn('render_end_s', timing.values)
        overlay.destroy()

    def setUp(self):
        FakeToplevel.instances.clear()
        FakeCanvas.instances.clear()
        FakePhotoImage.instances.clear()
        self.toplevel_patch = patch("src.overlay_window.tk.Toplevel", FakeToplevel)
        self.canvas_patch = patch("src.overlay_window.tk.Canvas", FakeCanvas)
        self.photo_patch = patch("src.overlay_window.tk.PhotoImage", FakePhotoImage)
        self.toplevel_patch.start()
        self.canvas_patch.start()
        self.photo_patch.start()

    def tearDown(self):
        self.photo_patch.stop()
        self.canvas_patch.stop()
        self.toplevel_patch.stop()

    def test_constructor_configures_transparent_window_at_exact_region(self):
        configured = []
        region = CaptureRegion(-1820, 40, 640, 360)

        LandmarkOverlay(object(), region, configure_native=configured.append)

        window = FakeToplevel.instances[0]
        self.assertIn(("geometry", "640x360-1820+40"), window.calls)
        self.assertIn(("overrideredirect", True), window.calls)
        self.assertIn(("attributes", "-topmost", True), window.calls)
        self.assertIn(("attributes", "-transparentcolor", "#010203"), window.calls)
        self.assertEqual(configured, [321])

    def test_native_configuration_failure_destroys_partial_window(self):
        def fail(_hwnd):
            raise OverlayConfigurationError("native failure")

        with self.assertRaisesRegex(OverlayConfigurationError, "native failure"):
            LandmarkOverlay(
                object(), CaptureRegion(0, 0, 320, 240), configure_native=fail
            )

        self.assertTrue(FakeToplevel.instances[0].destroyed)

    def test_draw_pending_renders_only_latest_frame(self):
        overlay = LandmarkOverlay(
            object(), CaptureRegion(0, 0, 320, 240), configure_native=lambda _hwnd: None
        )
        overlay.publish(OverlayFrame(((1, 1), (2, 2)), True, 10.0))
        overlay.publish(OverlayFrame(((11, 12), (21, 22)), True, 25.0))

        with patch(
            "src.overlay_window.render_overlay_ppm",
            side_effect=lambda frame, _width, _height: str(frame.fps).encode(),
        ):
            self.assertTrue(overlay.draw_pending())

        canvas = FakeCanvas.instances[0]
        self.assertEqual(sum(call[0] == "image" for call in canvas.calls), 1)
        updates = [call for call in canvas.calls if call[0] == "itemconfigure"]
        self.assertEqual(len(updates), 1)
        self.assertEqual(FakePhotoImage.instances[-1].kwargs["data"], b"25.0")
        self.assertFalse(overlay.draw_pending())

    def test_destroy_clears_pending_frame_and_blocks_future_drawing(self):
        overlay = LandmarkOverlay(
            object(), CaptureRegion(0, 0, 320, 240), configure_native=lambda _hwnd: None
        )
        overlay.publish(OverlayFrame((), False, 0.0))

        overlay.destroy()

        self.assertFalse(overlay.draw_pending())
        self.assertTrue(FakeToplevel.instances[0].destroyed)


if __name__ == "__main__":
    unittest.main()
