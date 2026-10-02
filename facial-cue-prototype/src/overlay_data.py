from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Iterable, Protocol

from .action_types import ActionSnapshot
from .landmark_timing import FrameTiming


class NormalizedLandmark(Protocol):
    x: float
    y: float


@dataclass(frozen=True)
class OverlayFrame:
    points: tuple[tuple[int, int], ...]
    face_detected: bool
    fps: float
    paused: bool = False
    action_snapshot: ActionSnapshot | None = None
    timing: FrameTiming | None = None


def landmarks_to_pixels(
    landmarks: Iterable[NormalizedLandmark],
    width: int,
    height: int,
) -> tuple[tuple[int, int], ...]:
    if width <= 0 or height <= 0:
        raise ValueError("Overlay dimensions must be positive")

    max_x = width - 1
    max_y = height - 1
    return tuple(
        (
            min(max(round(float(landmark.x) * max_x), 0), max_x),
            min(max(round(float(landmark.y) * max_y), 0), max_y),
        )
        for landmark in landmarks
    )


def connection_segments(
    points: tuple[tuple[int, int], ...],
    connections: Iterable[tuple[int, int]],
) -> tuple[tuple[int, int, int, int], ...]:
    segments = []
    for start_index, end_index in connections:
        if not (0 <= start_index < len(points) and 0 <= end_index < len(points)):
            continue
        start_x, start_y = points[start_index]
        end_x, end_y = points[end_index]
        segments.append((start_x, start_y, end_x, end_y))
    return tuple(segments)


class LatestOverlayFrame:
    def __init__(self) -> None:
        self._lock = Lock()
        self._frame: OverlayFrame | None = None

    def publish(self, frame: OverlayFrame) -> None:
        with self._lock:
            if self._frame is not None and self._frame.timing is not None:
                self._frame.timing.finish("replaced")
            if frame.timing is not None:
                frame.timing.mark("overlay_published_s")
            self._frame = frame

    def take(self) -> OverlayFrame | None:
        with self._lock:
            frame = self._frame
            self._frame = None
            if frame is not None and frame.timing is not None:
                frame.timing.mark("ui_consumed_s")
        return frame

    def clear(self) -> None:
        with self._lock:
            if self._frame is not None and self._frame.timing is not None:
                self._frame.timing.finish("cleared")
            self._frame = None
