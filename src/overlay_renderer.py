from __future__ import annotations

from collections.abc import Iterable

import cv2
import mediapipe as mp
import numpy as np

from .action_types import ActionMode
from .app_utils import format_fps
from .overlay_data import OverlayFrame


TRANSPARENT_RGB = (1, 2, 3)
_TASK_CONNECTIONS = mp.tasks.vision.FaceLandmarksConnections
TESSELLATION_CONNECTIONS = tuple(
    sorted(
        {
            tuple(sorted((edge.start, edge.end)))
            for edge in _TASK_CONNECTIONS.FACE_LANDMARKS_TESSELATION
        }
    )
)
CONTOUR_CONNECTIONS = tuple(
    (edge.start, edge.end) for edge in _TASK_CONNECTIONS.FACE_LANDMARKS_CONTOURS
)
TESSELLATION_INDICES = np.asarray(TESSELLATION_CONNECTIONS, dtype=np.int32)
CONTOUR_INDICES = np.asarray(CONTOUR_CONNECTIONS, dtype=np.int32)


def _segments(
    points: tuple[tuple[int, int], ...],
    connections: Iterable[tuple[int, int]],
) -> np.ndarray:
    if not points:
        return np.empty((0, 2, 2), dtype=np.int32)
    point_array = np.asarray(points, dtype=np.int32)
    if isinstance(connections, np.ndarray):
        indices = connections
    else:
        indices = np.asarray(tuple(connections), dtype=np.int32)
    if indices.size == 0:
        return np.empty((0, 2, 2), dtype=np.int32)
    indices = indices.reshape(-1, 2)
    valid = np.all((indices >= 0) & (indices < len(point_array)), axis=1)
    return point_array[indices[valid]]


def render_overlay_rgb(
    frame: OverlayFrame,
    width: int,
    height: int,
    *,
    tessellation: Iterable[tuple[int, int]] = TESSELLATION_INDICES,
    contours: Iterable[tuple[int, int]] = CONTOUR_INDICES,
) -> np.ndarray:
    if width <= 0 or height <= 0:
        raise ValueError("Overlay dimensions must be positive")

    image = np.full((height, width, 3), TRANSPARENT_RGB, dtype=np.uint8)
    mesh_lines = _segments(frame.points, tessellation)
    if len(mesh_lines):
        cv2.polylines(image, mesh_lines, False, (49, 197, 218), 1, cv2.LINE_AA)
    contour_lines = _segments(frame.points, contours)
    if len(contour_lines):
        cv2.polylines(image, contour_lines, False, (57, 223, 135), 2, cv2.LINE_AA)

    snapshot = frame.action_snapshot
    if frame.paused or (snapshot is not None and snapshot.mode is ActionMode.PAUSED):
        rows = ("Paused",)
    elif snapshot is not None and snapshot.mode is ActionMode.CALIBRATING:
        rows = (f"Calibrating... {round(snapshot.calibration_progress * 100)}%",)
    elif snapshot is not None and snapshot.mode is ActionMode.FACE_MISSING:
        rows = ("Face not detected",)
    elif snapshot is not None and snapshot.face_reacquired:
        rows = ("Face detected again",)
    elif snapshot is not None and snapshot.actions:
        rows = tuple(
            f"{action.label}  {action.duration_s:.1f}s"
            for action in snapshot.actions[:4]
        )
    elif not frame.face_detected:
        rows = ("Face not detected",)
    else:
        rows = ("No observable action",)

    panel_right = min(width - 1, 367)
    panel_bottom = min(height - 1, 151)
    if panel_right > 8 and panel_bottom > 8:
        panel = image[8 : panel_bottom + 1, 8 : panel_right + 1]
        yy, xx = np.indices(panel.shape[:2])
        panel[(xx + yy) % 2 == 0] = (17, 17, 17)
        cv2.putText(
            image,
            "Observable actions",
            (18, min(30, panel_bottom - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (243, 244, 246),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            image,
            format_fps(frame.fps),
            (18, min(54, panel_bottom - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (57, 223, 135),
            1,
            cv2.LINE_AA,
        )
        for index, row in enumerate(rows[:4]):
            y = 80 + index * 22
            if y > panel_bottom - 4:
                break
            cv2.putText(
                image,
                row,
                (18, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.46,
                (243, 244, 246),
                1,
                cv2.LINE_AA,
            )
    return image


def rgb_to_ppm(image: np.ndarray) -> bytes:
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("PPM input must be an RGB image")
    height, width = image.shape[:2]
    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    return header + np.ascontiguousarray(image, dtype=np.uint8).tobytes()


def render_overlay_ppm(frame: OverlayFrame, width: int, height: int) -> bytes:
    return rgb_to_ppm(render_overlay_rgb(frame, width, height))
