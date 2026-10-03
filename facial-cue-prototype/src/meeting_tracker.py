from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, auto
import os
import tempfile
import threading
import time
from typing import Callable

import numpy as np
import cv2
from mss import MSS

os.environ.setdefault(
    "MPLCONFIGDIR",
    os.path.join(tempfile.gettempdir(), "facial-cue-prototype-mpl"),
)
import mediapipe as mp

from .app_utils import face_status_text
from .action_detection import ActionDetector
from .action_types import ActionEvent, ActionMode
from .capture_types import CaptureRegion
from .face_landmarker import create_face_landmarker
from .feature_data import FeatureFrame, extract_feature_frame
from .frame_processing import prepare_capture_frame
from .overlay_data import OverlayFrame, landmarks_to_pixels
from .video_recorder import CapturedVideoFrame


class TrackerEventKind(Enum):
    FACE_STATUS = auto()
    PAUSED = auto()
    RESUMED = auto()
    RESELECT = auto()
    STOPPED = auto()
    ERROR = auto()
    QUIT = auto()


@dataclass(frozen=True)
class TrackerEvent:
    kind: TrackerEventKind
    message: str = ""


class MeetingTracker:
    def __init__(
        self,
        region: CaptureRegion,
        event_callback: Callable[[TrackerEvent], None],
        overlay_callback: Callable[[OverlayFrame], None],
        feature_callback: Callable[[FeatureFrame], None],
        action_event_callback: Callable[[ActionEvent], None],
        *,
        detector_factory: Callable[[], object] = ActionDetector,
        mss_factory: Callable[[], object] = MSS,
        landmarker_factory: Callable[[], object] = create_face_landmarker,
        clock: Callable[[], float] = time.perf_counter,
        sleep_func: Callable[[float], None] = time.sleep,
        frame_callback: Callable[[CapturedVideoFrame], None] | None = None,
        session_clock=None,
        timing_recorder=None,
    ) -> None:
        self.region = region
        self._event_callback = event_callback
        self._overlay_callback = overlay_callback
        self._feature_callback = feature_callback
        self._action_event_callback = action_event_callback
        self._detector_factory = detector_factory
        self._mss_factory = mss_factory
        self._landmarker_factory = landmarker_factory
        self._clock = clock
        self._sleep = sleep_func
        self._frame_callback = frame_callback
        self._session_clock = session_clock
        self._timing_recorder = timing_recorder
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.is_alive():
            raise RuntimeError("Tracker is already running")
        self._stop_event.clear()
        self._pause_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="meeting-region-tracker",
            daemon=True,
        )
        self._thread.start()

    def pause(self) -> None:
        self._pause_event.set()
        self._emit(TrackerEventKind.PAUSED)

    def resume(self) -> None:
        self._pause_event.clear()
        self._emit(TrackerEventKind.RESUMED)

    def request_stop(self) -> None:
        self._stop_event.set()

    def stop(self) -> None:
        self.request_stop()
        if (
            self._thread is not None
            and self._thread.is_alive()
            and threading.current_thread() is not self._thread
        ):
            self._thread.join()

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _emit(self, kind: TrackerEventKind, message: str = "") -> None:
        self._event_callback(TrackerEvent(kind, message))

    def _run(self) -> None:
        session_start = self._clock() if self._session_clock is None else None
        previous_timestamp_ms: int | None = None
        frame_index = 0
        last_status: str | None = None
        last_overlay: OverlayFrame | None = None
        pause_published = False
        detector = None
        last_processed_timestamp_s: float | None = None
        failure: Exception | None = None
        timing = None

        try:
            detector = self._detector_factory()
            with self._mss_factory() as screen, self._landmarker_factory() as landmarker:
                while not self._stop_event.is_set():
                    if self._pause_event.is_set():
                        if not pause_published:
                            if last_processed_timestamp_s is not None:
                                snapshot, events = detector.interrupt(
                                    last_processed_timestamp_s, ActionMode.PAUSED
                                )
                                for event in events:
                                    self._action_event_callback(event)
                            else:
                                snapshot = None
                            paused = replace(
                                last_overlay or OverlayFrame((), False, 0.0),
                                paused=True,
                                action_snapshot=snapshot,
                                timing=None,
                            )
                            self._overlay_callback(paused)
                            pause_published = True
                        self._sleep(0.02)
                        continue

                    pause_published = False
                    timing = self._timing_recorder.begin(frame_index) if self._timing_recorder is not None else None
                    processing_start = self._clock()
                    screenshot = screen.grab(self.region.as_mss_region())
                    if timing is not None:
                        timing.mark("capture_end_s")
                    if self._stop_event.is_set():
                        if timing is not None: timing.finish("stopped")
                        break
                    raw_frame = np.asarray(screenshot)
                    if raw_frame.ndim != 3 or raw_frame.shape[2] != 4:
                        raise ValueError("MSS returned an unexpected frame format")

                    rgb_frame, bgr_frame = prepare_capture_frame(raw_frame, include_bgr=self._frame_callback is not None)
                    if timing is not None:
                        timing.mark("conversion_end_s")
                    elapsed_s = (self._clock() - session_start) if self._session_clock is None else self._session_clock.elapsed_s()
                    candidate_timestamp_ms = int(elapsed_s * 1000)
                    timestamp_ms = max(
                        candidate_timestamp_ms,
                        0 if previous_timestamp_ms is None else previous_timestamp_ms + 1,
                    )
                    elapsed_ms = (
                        0
                        if previous_timestamp_ms is None
                        else timestamp_ms - previous_timestamp_ms
                    )
                    previous_timestamp_ms = timestamp_ms
                    video_frame_index = None
                    if self._frame_callback is not None:
                        video_frame_index = self._frame_callback(CapturedVideoFrame(frame_index, timestamp_ms / 1000.0, bgr_frame.copy()))

                    image = mp.Image(
                        image_format=mp.ImageFormat.SRGB,
                        data=rgb_frame,
                    )
                    if timing is not None:
                        timing.mark("inference_start_s")
                    results = landmarker.detect_for_video(image, timestamp_ms)
                    if timing is not None:
                        timing.mark("inference_end_s")
                    if self._stop_event.is_set():
                        if timing is not None: timing.finish("stopped")
                        break
                    faces = results.face_landmarks or []
                    detected = bool(faces)
                    status = face_status_text(detected)
                    if status != last_status:
                        self._emit(TrackerEventKind.FACE_STATUS, status)
                        last_status = status

                    points = ()
                    if faces:
                        points = landmarks_to_pixels(
                            faces[0],
                            self.region.width,
                            self.region.height,
                        )

                    feature_frame = extract_feature_frame(
                        results,
                        timestamp_ms / 1000.0,
                        frame_index,
                    )
                    feature_frame = replace(
                        feature_frame,
                        processing_ms=max(0.0, (self._clock() - processing_start) * 1000.0),
                        frame_gap_ms=float(elapsed_ms),
                    )
                    last_processed_timestamp_s = feature_frame.timestamp_s
                    if timing is not None:
                        timing.mark("features_end_s")
                    snapshot, action_events = detector.update(feature_frame)
                    feature_frame = replace(
                        feature_frame,
                        video_frame_index=video_frame_index if isinstance(video_frame_index, int) and not isinstance(video_frame_index, bool) else None,
                        action_mode=snapshot.mode.value,
                        action_calibration_progress=snapshot.calibration_progress,
                        active_action_ids="|".join(action.action_id for action in snapshot.actions),
                        active_action_strengths="|".join(f"{action.strength:.4f}" for action in snapshot.actions),
                    )
                    fps = 1000.0 / elapsed_ms if elapsed_ms > 0 else 0.0
                    last_overlay = OverlayFrame(
                        points,
                        detected,
                        fps,
                        action_snapshot=snapshot,
                        timing=timing,
                    )
                    if timing is not None:
                        timing.mark("overlay_callback_s")
                    self._overlay_callback(last_overlay)
                    self._feature_callback(feature_frame)
                    for event in action_events:
                        self._action_event_callback(event)
                    frame_index += 1
        except Exception as exc:
            if timing is not None:
                timing.finish("tracker_error")
            failure = exc
        finally:
            if detector is not None and last_processed_timestamp_s is not None:
                try:
                    _snapshot, final_events = detector.interrupt(
                        last_processed_timestamp_s, ActionMode.TRACKING
                    )
                    for event in final_events:
                        self._action_event_callback(event)
                except Exception as exc:
                    failure = failure or exc
            if failure is not None:
                self._emit(TrackerEventKind.ERROR, str(failure))
            self._emit(TrackerEventKind.STOPPED)
