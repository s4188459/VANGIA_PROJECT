from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile


WINDOW_TITLE = "Multimodal Dataset Collector"

os.environ.setdefault(
    "MPLCONFIGDIR",
    os.path.join(tempfile.gettempdir(), "facial-cue-prototype-mpl"),
)

try:
    import cv2  # noqa: F401
except ImportError as exc:
    raise SystemExit(
        "OpenCV is not installed. Install dependencies with: "
        "python -m pip install -r requirements.txt"
    ) from exc

try:
    import mediapipe  # noqa: F401
except ImportError as exc:
    raise SystemExit(
        "MediaPipe is not installed. Install dependencies with: "
        "python -m pip install -r requirements.txt"
    ) from exc

try:
    from mss import MSS  # noqa: F401
except ImportError as exc:
    raise SystemExit(
        "MSS is not installed. Install dependencies with: "
        "python -m pip install -r requirements.txt"
    ) from exc

try:
    import tkinter as tk
except ImportError as exc:
    raise SystemExit("Tkinter is unavailable in this Python installation.") from exc

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.app_controller import AppController
    from src.control_panel import ControlPanel
    from src.windows_dpi import enable_windows_dpi_awareness
else:
    from .app_controller import AppController
    from .control_panel import ControlPanel
    from .windows_dpi import enable_windows_dpi_awareness


def run() -> int:
    enable_windows_dpi_awareness()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Error: could not open the application window. Details: {exc}", file=sys.stderr)
        return 1

    panel = ControlPanel(root)
    controller = AppController(panel)
    panel.bind_actions(
        controller.select_region,
        controller.choose_save_folder,
        controller.start,
        controller.toggle_pause,
        controller.stop,
        controller.shutdown,
        controller.generate_final_transcript,
    )

    try:
        root.mainloop()
    except KeyboardInterrupt:
        controller.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
