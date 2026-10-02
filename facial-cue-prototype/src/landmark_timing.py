"""Bounded, session-relative diagnostics; no file I/O during capture or render."""
from __future__ import annotations

from collections import Counter
import csv
from threading import RLock


STAGES = (
    "capture_start_s", "capture_end_s", "conversion_end_s",
    "inference_start_s", "inference_end_s", "features_end_s",
    "overlay_callback_s", "overlay_published_s", "ui_consumed_s",
    "bitmap_end_s", "render_end_s",
)
FIELDS = ("frame_index", *STAGES, "outcome", "order_valid")


class FrameTiming:
    def __init__(self, owner, frame_index):
        self._owner = owner
        self.values = {"frame_index": frame_index}

    def mark(self, stage):
        if stage not in STAGES:
            raise ValueError(f"Unknown landmark timing stage: {stage}")
        with self._owner._lock:
            if not self._owner._closed and "outcome" not in self.values:
                self.values.setdefault(stage, self._owner._clock.elapsed_s())

    def finish(self, outcome):
        with self._owner._lock:
            if not self._owner._closed:
                self.values.setdefault("outcome", outcome)


class LandmarkTimingRecorder:
    def __init__(self, clock, *, max_frames=20000):
        self._clock = clock
        self._lock = RLock()
        self._frames = []
        self._max_frames = max_frames
        self._omitted = 0
        self._closed = False
        self._summary = None

    def begin(self, frame_index):
        with self._lock:
            if self._closed:
                return None
            if len(self._frames) >= self._max_frames:
                self._omitted += 1
                return None
            frame = FrameTiming(self, frame_index)
            frame.mark("capture_start_s")
            self._frames.append(frame)
            return frame

    def close(self, directory):
        # Called after tracker.stop(), on the UI thread: rendering cannot overlap.
        with self._lock:
            if self._closed:
                return self._summary
            self._closed = True
            rows = []
            for frame in self._frames:
                row = dict(frame.values)
                row.setdefault("outcome", "not_rendered_at_close")
                times = [row[key] for key in STAGES if key in row]
                row["order_valid"] = all(a <= b for a, b in zip(times, times[1:]))
                rows.append(row)
            filename = "landmark-timing.csv" if rows else None
            if filename:
                with (directory / filename).open("x", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=FIELDS)
                    writer.writeheader()
                    writer.writerows(rows)
            self._summary = {
                "file": filename, "clock": "session_elapsed_monotonic_seconds",
                "max_frames": self._max_frames, "recorded_frames": len(rows),
                "omitted_frames": self._omitted, "finalized": True,
                "outcomes": dict(Counter(row["outcome"] for row in rows)),
                "invalid_order_frames": sum(not row["order_valid"] for row in rows),
                "render_boundary": "Tk canvas itemconfigure returned; not physical presentation",
            }
            self._frames.clear()
            return self._summary
