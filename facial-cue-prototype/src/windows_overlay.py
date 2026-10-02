from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable

from .capture_types import CaptureRegion


GWL_EXSTYLE = -20
GA_ROOT = 2
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011


class OverlayConfigurationError(RuntimeError):
    pass


def overlay_geometry(region: CaptureRegion) -> str:
    x = f"+{region.left}" if region.left >= 0 else str(region.left)
    y = f"+{region.top}" if region.top >= 0 else str(region.top)
    return f"{region.width}x{region.height}{x}{y}"


def _windows_user32(platform_name: str):
    if platform_name != "win32":
        raise OverlayConfigurationError(
            "The transparent capture overlay requires Windows 10 version 2004 or later"
        )

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    long_ptr = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = long_ptr
    user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, long_ptr]
    user32.SetWindowLongPtrW.restype = long_ptr
    user32.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user32.SetWindowDisplayAffinity.restype = ctypes.c_int
    user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user32.GetAncestor.restype = ctypes.c_void_p
    return user32


def _last_error_reader(
    get_last_error: Callable[[], int] | None,
) -> Callable[[], int]:
    return get_last_error or ctypes.get_last_error


def _top_level_hwnd(api, hwnd: int) -> int:
    top_level = api.GetAncestor(hwnd, GA_ROOT)
    if not top_level:
        raise OverlayConfigurationError("Could not find the native top-level window")
    return top_level


def _set_capture_affinity(
    api,
    hwnd: int,
    get_last_error: Callable[[], int] | None,
) -> None:
    if not api.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
        error_code = _last_error_reader(get_last_error)()
        raise OverlayConfigurationError(
            f"Could not exclude the window from screen capture (Windows error {error_code})"
        )


def exclude_window_from_capture(
    hwnd: int,
    *,
    user32=None,
    platform_name: str = sys.platform,
    get_last_error: Callable[[], int] | None = None,
) -> None:
    if platform_name != "win32":
        raise OverlayConfigurationError(
            "The transparent capture overlay requires Windows 10 version 2004 or later"
        )
    api = user32 or _windows_user32(platform_name)
    top_level = _top_level_hwnd(api, hwnd)
    _set_capture_affinity(api, top_level, get_last_error)


def configure_capture_excluded_window(
    hwnd: int,
    *,
    user32=None,
    platform_name: str = sys.platform,
    get_last_error: Callable[[], int] | None = None,
) -> None:
    if platform_name != "win32":
        raise OverlayConfigurationError(
            "The transparent capture overlay requires Windows 10 version 2004 or later"
        )
    api = user32 or _windows_user32(platform_name)
    top_level = _top_level_hwnd(api, hwnd)
    current_style = api.GetWindowLongPtrW(top_level, GWL_EXSTYLE)
    overlay_style = current_style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE

    if get_last_error is None:
        ctypes.set_last_error(0)
    result = api.SetWindowLongPtrW(top_level, GWL_EXSTYLE, overlay_style)
    error_code = _last_error_reader(get_last_error)()
    if result == 0 and error_code != 0:
        raise OverlayConfigurationError(
            f"Could not configure the transparent overlay (Windows error {error_code})"
        )

    _set_capture_affinity(api, top_level, get_last_error)
