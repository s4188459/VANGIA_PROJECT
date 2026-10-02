from __future__ import annotations

from dataclasses import replace
import tkinter as tk

from .capture_types import CaptureRegion
from .overlay_data import LatestOverlayFrame, OverlayFrame
from .overlay_renderer import render_overlay_ppm
from .windows_overlay import configure_capture_excluded_window, overlay_geometry


TRANSPARENT_COLOR = "#010203"
class LandmarkOverlay:
    def __init__(
        self,
        root,
        region: CaptureRegion,
        *,
        configure_native=configure_capture_excluded_window,
    ) -> None:
        self._pending = LatestOverlayFrame()
        self._last_frame: OverlayFrame | None = None
        self._destroyed = False
        self._width = region.width
        self._height = region.height
        self._photo = None
        self._window = tk.Toplevel(root)

        try:
            self._window.overrideredirect(True)
            self._window.attributes("-topmost", True)
            self._window.attributes("-transparentcolor", TRANSPARENT_COLOR)
            self._window.configure(bg=TRANSPARENT_COLOR)
            self._window.geometry(overlay_geometry(region))
            self._canvas = tk.Canvas(
                self._window,
                width=region.width,
                height=region.height,
                bg=TRANSPARENT_COLOR,
                highlightthickness=0,
                borderwidth=0,
            )
            self._canvas.pack(fill=tk.BOTH, expand=True)
            self._image_item = self._canvas.create_image(0, 0, anchor="nw")
            self._window.update_idletasks()
            configure_native(self._window.winfo_id())
        except Exception:
            self._window.destroy()
            self._destroyed = True
            raise

    def publish(self, frame: OverlayFrame) -> None:
        if not self._destroyed:
            self._pending.publish(frame)

    def draw_pending(self) -> bool:
        if self._destroyed:
            return False
        frame = self._pending.take()
        if frame is None:
            return False

        self._last_frame = frame
        try:
            bitmap = render_overlay_ppm(frame, self._width, self._height)
            if frame.timing is not None:
                frame.timing.mark("bitmap_end_s")
            self._photo = tk.PhotoImage(data=bitmap, format="PPM")
            self._canvas.itemconfigure(
                self._image_item,
                image=self._photo,
            )
            if frame.timing is not None:
                frame.timing.mark("render_end_s")
                frame.timing.finish("rendered")
        except Exception:
            if frame.timing is not None:
                frame.timing.finish("render_error")
            raise
        return True

    def set_paused(self, paused: bool) -> None:
        base = self._last_frame or OverlayFrame((), False, 0.0)
        self.publish(replace(base, paused=paused, timing=None))

    def destroy(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        self._pending.clear()
        self._window.destroy()
