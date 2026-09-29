from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import queue
import threading
import math

import cv2
import numpy as np


class VideoRecorderUnavailable(RuntimeError): pass


@dataclass(frozen=True)
class CapturedVideoFrame:
    source_frame_index: int
    timestamp_s: float
    bgr: np.ndarray


@dataclass(frozen=True)
class VideoStats:
    written_frames: int
    dropped_frames: int
    codec: str
    failure: str | None = None
    fps: float = 20.0
    resampled_frames: int = 0
    duplicated_frames: int = 0


class VideoRecorder:
    def __init__(self, video_path: Path, size: tuple[int, int],
                 fps: float = 20.0, *, writer_factory=cv2.VideoWriter, queue_size: int = 8,
                 mapping_callback=lambda _source, _written: None) -> None:
        if fps <= 0 or not math.isfinite(fps) or queue_size <= 0:
            raise ValueError("Video FPS and queue size must be positive")
        self.video_path, self.size, self.fps = Path(video_path), size, fps
        self._writer_factory = writer_factory
        self._queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self._writer = None; self._thread = None; self._accepting = False
        self._written = 0; self._dropped = 0; self._failure = None; self.codec = "mp4v"
        self._mapping_callback = mapping_callback
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._abort = threading.Event()
        self._stop_timestamp = None
        self._resampled = 0; self._duplicated = 0
        self._previous = np.zeros((size[1], size[0], 3), np.uint8)

    def start(self) -> None:
        fourcc = cv2.VideoWriter_fourcc(*self.codec)
        self._writer = self._writer_factory(str(self.video_path), fourcc, self.fps, self.size)
        if not self._writer.isOpened():
            self._writer.release(); raise VideoRecorderUnavailable("Could not open MP4 video writer")
        self._accepting = True
        self._thread = threading.Thread(target=self._run, name="video-writer", daemon=True); self._thread.start()

    def submit(self, frame: CapturedVideoFrame) -> int | None:
        with self._lock:
            if not self._accepting: return None
            try:
                self._queue.put_nowait(frame)
            except queue.Full:
                self._dropped += 1
        # CSV indices are finalized from successful writes, never reservations.
        return None

    def _fill_until(self, count: int) -> None:
        while self._written < count and not self._abort.is_set():
            self._writer.write(self._previous)
            self._written += 1
            self._duplicated += 1

    def _run(self) -> None:
        try:
            while not self._abort.is_set():
                try:
                    item = self._queue.get(timeout=.05)
                except queue.Empty:
                    if self._stop.is_set(): break
                    continue
                if isinstance(item, tuple):
                    self._fill_until(math.ceil(item[1] * self.fps - 1e-8))
                    self._previous = np.zeros_like(self._previous)
                    continue
                if not math.isfinite(item.timestamp_s) or item.timestamp_s < 0:
                    raise ValueError("Video timestamp must be finite and non-negative")
                if item.bgr.shape[:2] != (self.size[1], self.size[0]): raise ValueError("Video frame size changed")
                target = math.floor(item.timestamp_s * self.fps + 1e-8)
                if target < self._written:
                    self._resampled += 1
                    continue
                self._fill_until(target)
                if self._abort.is_set(): break
                self._writer.write(item.bgr)
                self._mapping_callback(item.source_frame_index, self._written)
                self._written += 1
                self._previous = item.bgr
            if self._stop_timestamp is not None and not self._abort.is_set():
                self._fill_until(math.ceil(self._stop_timestamp * self.fps - 1e-8))
        except Exception as exc:
            self._failure = str(exc)
            self._dropped += 1 + self._queue.qsize()
        finally:
            self._accepting = False
            self._writer.release()

    def pause(self, timestamp_s: float) -> None:
        with self._lock:
            self._accepting = False
            if self._failure is None and not self._stop.is_set():
                self._queue.put(("pause", timestamp_s), timeout=5.)
    def resume(self, timestamp_s: float) -> None:
        with self._lock:
            if self._failure is None and not self._stop.is_set(): self._accepting = True
    def stop(self, timeout_s: float = 5.0, *, timestamp_s: float | None = None) -> VideoStats:
        with self._lock:
            self._accepting = False
            self._stop_timestamp = timestamp_s
            self._stop.set()
        if self._thread: self._thread.join(timeout_s)
        if self._thread and self._thread.is_alive():
            self._abort.set()
            raise RuntimeError("Video writer timed out; recording is incomplete")
        return VideoStats(self._written, self._dropped, self.codec, self._failure,
                          self.fps, self._resampled, self._duplicated)
