from __future__ import annotations

import cv2
import numpy as np

from .app_utils import format_fps


def prepare_frames(bgr_frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    preview = bgr_frame.copy()
    rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
    return preview, rgb


def draw_overlay(
    frame: np.ndarray,
    status: str,
    fps: float,
    paused: bool = False,
) -> None:
    visible_status = "Paused" if paused else status
    if paused:
        status_color = (0, 210, 255)
    elif status == "Face detected":
        status_color = (40, 220, 40)
    else:
        status_color = (40, 40, 230)

    cv2.rectangle(frame, (8, 8), (328, 82), (0, 0, 0), thickness=-1)
    cv2.putText(
        frame,
        visible_status,
        (20, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        status_color,
        2,
    )
    cv2.putText(
        frame,
        format_fps(fps),
        (20, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (230, 230, 230),
        2,
    )
