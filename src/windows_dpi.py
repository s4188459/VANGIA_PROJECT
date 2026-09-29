from __future__ import annotations

import ctypes
import sys


def enable_windows_dpi_awareness(
    *,
    platform: str | None = None,
    set_context=None,
    set_legacy=None,
) -> bool:
    if (platform or sys.platform) != "win32":
        return False

    if set_context is None:
        set_context = ctypes.windll.user32.SetProcessDpiAwarenessContext
    if set_legacy is None:
        set_legacy = ctypes.windll.user32.SetProcessDPIAware

    try:
        result = set_context(-4)  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        if result == 0:
            raise OSError("Per-monitor DPI awareness was rejected")
        return True
    except (AttributeError, OSError):
        try:
            set_legacy()
            return True
        except (AttributeError, OSError):
            return False
