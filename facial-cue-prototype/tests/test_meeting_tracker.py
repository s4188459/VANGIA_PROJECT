import threading
import time
import unittest
import math
from types import SimpleNamespace

import numpy as np

from src.capture_types import CaptureRegion
from src.action_types import ActionEvent, ActionMode, ActionSnapshot
from src.meeting_tracker import MeetingTracker, TrackerEventKind
from src.overlay_data import OverlayFrame


class FakeScreenshot:
    def __init__(self):
        self.frame = np.array([[[10, 20, 30, 255]]], dtype=np.uint8)

    def __array__(self, dtype=None, copy=None):
        return np.asarray(self.frame, dtype=dtype)


class FakeScreen:
    def __init__(self, fail=False):
        self.fail = fail
        self.grab_regions = []
        self.grabbed = threading.Event()
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def grab(self, region):
        if self.fail:
            raise RuntimeError("capture failed")
        self.grab_regions.append(region)
        self.grabbed.set()
        return FakeScreenshot()


def empty_result():
    return SimpleNamespace(
        face_landmarks=[],
        face_blendshapes=[],
        facial_transformation_matrixes=[],
    )


def face_result(*points):
    landmarks = [SimpleNamespace(x=x, y=y, z=0.0) for x, y in points]
    return SimpleNamespace(
        face_landmarks=[landmarks],
        face_blendshapes=[[]],
        facial_transformation_matrixes=[np.eye(4)],
    )


class FakeLandmarker:
    def __init__(self, results=None, fail=False, delay_s=0.0):
        self.results = list(results or [empty_result()])
        self.fail = fail
        self.delay_s = delay_s
        self.images = []
        self.timestamps = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def detect_for_video(self, image, timestamp_ms):
        if self.fail:
            raise RuntimeError("inference failed")
        if self.delay_s:
            time.sleep(self.delay_s)
        self.images.append(image.numpy_view().copy())
        self.timestamps.append(timestamp_ms)
        index = min(len(self.images) - 1, len(self.results) - 1)
        return self.results[index]


def wait_until(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


class MeetingTrackerTests(unittest.TestCase):
    def test_capture_conversion_preserves_all_rgb_and_video_bgr_pixels(self):
        pixels = np.array([[[0, 17, 255, 0], [250, 128, 3, 255]],
                           [[7, 8, 9, 42], [100, 200, 50, 99]]], dtype=np.uint8)

        class Screen(FakeScreen):
            def grab(self, region):
                return pixels

        for video_enabled in (False, True):
            with self.subTest(video_enabled=video_enabled):
                video = []
                landmarker = FakeLandmarker()
                tracker = self.make_tracker(Screen(), landmarker,
                    frame_callback=video.append if video_enabled else None)
                tracker._feature_callback = lambda frame: tracker._stop_event.set()
                tracker._run()
                self.assertEqual(len(landmarker.images), 1)
                np.testing.assert_array_equal(landmarker.images[0], pixels[:, :, [2, 1, 0]])
                if video_enabled:
                    np.testing.assert_array_equal(video[0].bgr, pixels[:, :, :3])
                    self.assertFalse(np.shares_memory(video[0].bgr, pixels))

    def test_stage_timestamps_follow_the_same_frame_and_session_clock(self):
        from src.landmark_timing import LandmarkTimingRecorder
        from src.session_clock import SessionClock
        clock = SessionClock()
        clock.start()
        timings = LandmarkTimingRecorder(clock)
        self.assertIn('timing_recorder', __import__('inspect').signature(MeetingTracker).parameters)
        tracker = self.make_tracker(FakeScreen(), FakeLandmarker(delay_s=.02),
                                    session_clock=clock, timing_recorder=timings)
        tracker.start()
        try:
            self.assertTrue(wait_until(lambda: bool(self.feature_frames)))
        finally:
            tracker.stop()
        values = self.overlay_frames[0].timing.values
        self.assertEqual(values['frame_index'], self.feature_frames[0].frame_index)
        stages = ('capture_start_s', 'capture_end_s', 'conversion_end_s',
                  'inference_start_s', 'inference_end_s', 'features_end_s', 'overlay_callback_s')
        times = [values[key] for key in stages]
        self.assertEqual(times, sorted(times))
        self.assertGreaterEqual(values['inference_end_s'] - values['inference_start_s'], .015)
        self.assertLessEqual(values['overlay_callback_s'], clock.elapsed_s())

    def test_overlay_is_published_before_slow_recording_callback(self):
        entered = threading.Event()
        release = threading.Event()
        def save(_frame):
            entered.set()
            release.wait(2)
        tracker = MeetingTracker(
            self.region, self.events.append, self.overlay_frames.append,
            save, self.action_events.append,
            mss_factory=FakeScreen, landmarker_factory=FakeLandmarker,
        )
        tracker.start()
        try:
            self.assertTrue(entered.wait(1))
            self.assertTrue(self.overlay_frames)
        finally:
            release.set()
            tracker.stop()

    def setUp(self):
        self.region = CaptureRegion(100, 200, 640, 360)
        self.events = []
        self.overlay_frames = []
        self.feature_frames = []
        self.action_events = []

    def make_tracker(self, screen, landmarker, **kwargs):
        return MeetingTracker(
            self.region,
            self.events.append,
            self.overlay_frames.append,
            self.feature_frames.append,
            self.action_events.append,
            mss_factory=lambda: screen,
            landmarker_factory=lambda: landmarker,
            sleep_func=lambda seconds: time.sleep(min(seconds, 0.005)),
            **kwargs,
        )

    def test_visible_result_publishes_rgb_landmarks_and_features(self):
        screen = FakeScreen()
        landmarker = FakeLandmarker([face_result((0.0, 0.0), (1.0, 1.0))])
        tracker = self.make_tracker(screen, landmarker)

        tracker.start()
        self.assertTrue(wait_until(lambda: bool(self.feature_frames)))
        tracker.stop()

        self.assertTrue(all(r == self.region.as_mss_region() for r in screen.grab_regions))
        np.testing.assert_array_equal(landmarker.images[0][0, 0], [30, 20, 10])
        self.assertEqual(self.overlay_frames[0].points, ((0, 0), (639, 359)))
        self.assertTrue(self.feature_frames[0].face_visible)
        self.assertEqual(self.feature_frames[0].frame_index, 0)
        self.assertFalse(
            any(isinstance(value, np.ndarray) for value in vars(self.feature_frames[0]).values())
        )
        self.assertTrue(screen.closed)
        self.assertTrue(landmarker.closed)

    def test_processing_time_includes_landmark_inference(self):
        tracker = self.make_tracker(
            FakeScreen(), FakeLandmarker(delay_s=0.02)
        )

        tracker.start()
        self.assertTrue(wait_until(lambda: bool(self.feature_frames)))
        tracker.stop()

        self.assertGreaterEqual(self.feature_frames[0].processing_ms, 15.0)

    def test_video_callback_receives_bgr_frame_with_feature_timestamp(self):
        video_frames = []
        tracker = self.make_tracker(FakeScreen(), FakeLandmarker(), frame_callback=video_frames.append)
        tracker.start()
        self.assertTrue(wait_until(lambda: bool(self.feature_frames) and bool(video_frames)))
        tracker.stop()
        self.assertEqual(video_frames[0].timestamp_s, self.feature_frames[0].timestamp_s)
        np.testing.assert_array_equal(video_frames[0].bgr[0, 0], [10, 20, 30])

    def test_detector_snapshot_and_events_reach_callbacks(self):
        result = face_result((0.5, 0.5))
        result.face_blendshapes = [[
            SimpleNamespace(category_name="eyeBlinkLeft", score=0.8),
            SimpleNamespace(category_name="eyeBlinkRight", score=0.8),
            SimpleNamespace(category_name="eyeLookInLeft", score=0.7),
            SimpleNamespace(category_name="eyeLookOutRight", score=0.7),
        ]]
        angle = math.radians(20)
        result.facial_transformation_matrixes = [np.array(
            [
                [math.cos(angle), 0, math.sin(angle), 0],
                [0, 1, 0, 0],
                [-math.sin(angle), 0, math.cos(angle), 0],
                [0, 0, 0, 1],
            ]
        )]
        snapshot = ActionSnapshot(ActionMode.TRACKING)
        action_event = ActionEvent(0.0, 0.1, "blinking", 0.1, 1.0, "completed")

        class Detector:
            def update(_self, frame):
                return snapshot, (action_event,)

            def interrupt(_self, timestamp, mode):
                return ActionSnapshot(mode), ()

        tracker = self.make_tracker(
            FakeScreen(), FakeLandmarker([result]), detector_factory=Detector
        )

        tracker.start()
        self.assertTrue(wait_until(lambda: bool(self.overlay_frames)))
        tracker.stop()

        self.assertIs(self.overlay_frames[0].action_snapshot, snapshot)
        self.assertEqual(self.feature_frames[0].action_mode, "tracking")
        self.assertEqual(self.action_events[0], action_event)

    def test_missing_face_continues_and_publishes_empty_landmarks(self):
        tracker = self.make_tracker(FakeScreen(), FakeLandmarker([empty_result()]))

        tracker.start()
        self.assertTrue(wait_until(lambda: len(self.feature_frames) >= 2))
        tracker.stop()

        self.assertTrue(all(not frame.face_visible for frame in self.feature_frames))
        self.assertTrue(all(frame.points == () for frame in self.overlay_frames))
        statuses = [e.message for e in self.events if e.kind is TrackerEventKind.FACE_STATUS]
        self.assertEqual(statuses, ["Face not detected"])

    def test_task_timestamps_are_strictly_increasing_when_clock_repeats(self):
        landmarker = FakeLandmarker()
        tracker = self.make_tracker(FakeScreen(), landmarker, clock=lambda: 10.0)

        tracker.start()
        self.assertTrue(wait_until(lambda: len(landmarker.timestamps) >= 3))
        tracker.stop()

        self.assertEqual(landmarker.timestamps[:3], [0, 1, 2])
        self.assertEqual(
            [frame.timestamp_s for frame in self.feature_frames[:3]],
            [0.0, 0.001, 0.002],
        )

    def test_pause_produces_no_rows_and_resume_keeps_elapsed_gap(self):
        screen = FakeScreen()
        now = [0.0]
        tracker = self.make_tracker(screen, FakeLandmarker(), clock=lambda: now[0])
        # Fast fake capture can advance monotonic task timestamps ahead of real
        # time. Control both the clock and frame count instead of timing sleep().
        def publish(frame):
            self.feature_frames.append(frame)
            if len(self.feature_frames) == 1:
                tracker.pause()
            else:
                tracker.request_stop()
        tracker._feature_callback = publish
        tracker.start()
        try:
            self.assertTrue(wait_until(lambda: any(frame.paused for frame in self.overlay_frames)))
            paused_grabs = len(screen.grab_regions)
            paused_rows = len(self.feature_frames)
            before_pause_timestamp = self.feature_frames[-1].timestamp_s
            now[0] = 5.0
            time.sleep(0.02)  # Allow paused worker iterations; not a timestamp measurement.
            self.assertEqual(len(screen.grab_regions), paused_grabs)
            self.assertEqual(len(self.feature_frames), paused_rows)
            tracker.resume()
            self.assertTrue(wait_until(lambda: len(self.feature_frames) > paused_rows))
            self.assertAlmostEqual(self.feature_frames[-1].timestamp_s - before_pause_timestamp, 5.0)
        finally:
            tracker.stop()

    def test_callback_error_is_reported_and_worker_stops(self):
        def fail(_frame):
            raise RuntimeError("csv write failed")

        tracker = MeetingTracker(
            self.region,
            self.events.append,
            self.overlay_frames.append,
            fail,
            self.action_events.append,
            mss_factory=FakeScreen,
            landmarker_factory=FakeLandmarker,
        )

        tracker.start()
        self.assertTrue(wait_until(lambda: not tracker.is_alive()))

        self.assertEqual(self.events[-2].kind, TrackerEventKind.ERROR)
        self.assertIn("csv write failed", self.events[-2].message)
        self.assertEqual(self.events[-1].kind, TrackerEventKind.STOPPED)

    def test_capture_and_inference_errors_are_reported(self):
        for screen, landmarker, message in (
            (FakeScreen(fail=True), FakeLandmarker(), "capture failed"),
            (FakeScreen(), FakeLandmarker(fail=True), "inference failed"),
        ):
            with self.subTest(message=message):
                self.events.clear()
                tracker = self.make_tracker(screen, landmarker)
                tracker.start()
                self.assertTrue(wait_until(lambda: not tracker.is_alive()))
                self.assertIn(message, self.events[-2].message)
                self.assertEqual(self.events[-1].kind, TrackerEventKind.STOPPED)

    def test_start_rejects_second_live_worker(self):
        tracker = self.make_tracker(FakeScreen(), FakeLandmarker())
        tracker.start()
        self.assertTrue(wait_until(tracker.is_alive))

        with self.assertRaisesRegex(RuntimeError, "already running"):
            tracker.start()
        tracker.stop()

    def test_stop_waits_for_worker_completion_before_returning(self):
        tracker = self.make_tracker(FakeScreen(), FakeLandmarker())

        class JoinProbe:
            def __init__(self):
                self.joined = False

            def is_alive(self):
                return True

            def join(self):
                self.joined = True

        probe = JoinProbe()
        tracker._thread = probe
        tracker.stop()
        self.assertTrue(probe.joined)


if __name__ == "__main__":
    unittest.main()
