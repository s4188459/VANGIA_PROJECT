from __future__ import annotations

import tkinter as tk
from typing import Callable

from mss import MSS

from .capture_types import CaptureRegion


def absolute_region(
    monitor_left: int,
    monitor_top: int,
    roi: tuple[int, int, int, int],
) -> CaptureRegion | None:
    x, y, width, height = (int(value) for value in roi)
    if width <= 0 or height <= 0:
        return None
    return CaptureRegion(
        left=int(monitor_left) + x,
        top=int(monitor_top) + y,
        width=width,
        height=height,
    )


def drag_region(
    desktop_left: int,
    desktop_top: int,
    start: tuple[int, int],
    end: tuple[int, int],
) -> CaptureRegion | None:
    left = min(start[0], end[0])
    top = min(start[1], end[1])
    width = abs(end[0] - start[0])
    height = abs(end[1] - start[1])
    return absolute_region(desktop_left, desktop_top, (left, top, width, height))


def _virtual_desktop() -> dict[str, int]:
    with MSS() as screen:
        monitor = screen.monitors[0]
        return {
            "left": int(monitor["left"]),
            "top": int(monitor["top"]),
            "width": int(monitor["width"]),
            "height": int(monitor["height"]),
        }


def _geometry(monitor: dict[str, int]) -> str:
    left = monitor["left"]
    top = monitor["top"]
    x = f"+{left}" if left >= 0 else str(left)
    y = f"+{top}" if top >= 0 else str(top)
    return f'{monitor["width"]}x{monitor["height"]}{x}{y}'


def select_screen_region(
    parent,
    *,
    monitor_provider: Callable[[], dict[str, int]] = _virtual_desktop,
    window_factory=tk.Toplevel,
    canvas_factory=tk.Canvas,
) -> CaptureRegion | None:
    monitor = monitor_provider()
    result: CaptureRegion | None = None
    start: tuple[int, int] | None = None
    active = True

    parent.withdraw()
    window = None
    try:
        window = window_factory(parent)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.attributes("-alpha", 0.22)
        window.geometry(_geometry(monitor))
        window.configure(bg="black")

        canvas = canvas_factory(
            window,
            width=monitor["width"],
            height=monitor["height"],
            bg="black",
            cursor="crosshair",
            highlightthickness=0,
            borderwidth=0,
        )
        canvas.pack(fill=tk.BOTH, expand=True)
        selection = canvas.create_rectangle(
            0,
            0,
            0,
            0,
            outline="#00ffff",
            width=3,
            fill="white",
        )

        def begin(event) -> None:
            nonlocal start
            start = (event.x, event.y)
            canvas.coords(selection, event.x, event.y, event.x, event.y)

        def move(event) -> None:
            if start is not None:
                canvas.coords(selection, start[0], start[1], event.x, event.y)

        def finish(event) -> None:
            nonlocal result, active
            if start is not None:
                result = drag_region(
                    monitor["left"],
                    monitor["top"],
                    start,
                    (event.x, event.y),
                )
            active = False
            window.grab_release()
            window.destroy()

        def cancel(_event=None) -> None:
            nonlocal active
            active = False
            window.grab_release()
            window.destroy()

        canvas.bind("<ButtonPress-1>", begin)
        canvas.bind("<B1-Motion>", move)
        canvas.bind("<ButtonRelease-1>", finish)
        window.bind("<Escape>", cancel)
        window.focus_force()
        window.grab_set()
        window.wait_window()
    finally:
        if active and window is not None:
            try:
                window.grab_release()
                window.destroy()
            except tk.TclError:
                pass
        parent.deiconify()
        parent.lift()

    return result
