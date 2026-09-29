from __future__ import annotations

from datetime import datetime
import time
from typing import Callable


class SessionClock:
    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock
        self._origin: float | None = None
        self.started_at_local: str | None = None

    def start(self) -> None:
        if self._origin is not None:
            raise RuntimeError("Session clock is already started")
        self._origin = self._clock()
        self.started_at_local = datetime.now().astimezone().isoformat()

    def elapsed_s(self) -> float:
        if self._origin is None:
            raise RuntimeError("Session clock has not started")
        return max(0.0, self._clock() - self._origin)
