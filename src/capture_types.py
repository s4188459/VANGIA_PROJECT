from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


@dataclass(frozen=True)
class CaptureRegion:
    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Capture region width and height must be positive")

    def as_mss_region(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }


class AppState(Enum):
    NO_REGION = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    FINALIZING = auto()
    SHUTTING_DOWN = auto()
