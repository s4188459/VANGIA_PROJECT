import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

from src.app_controller import AppController
from src.action_types import ActionEvent
from src.capture_types import AppState, CaptureRegion
from src.feature_data import FeatureFrame
from src.meeting_tracker import TrackerEvent, TrackerEventKind
from src.session_recorder import RecordingError
from src.session_types import SessionOptions


class FakeView:
    def __init__(self, operations, folders=(), overlay_error=None, options=None):
        self.operations = operations
        self.folders = list(folders)
        self.overlay_error = overlay_error
        self.renders = []
        self.folder_displays = []
        self.feature_displays = []
        self.clear_count = 0
        self.close_count = 0
        self.hide_count = 0
        self.options = options or SessionOptions(consent_confirmed=True)
        self.transcript_metrics = []

    def render(self, state, status):
        self.renders.append((state, status))

    def ask_save_folder(self):
        return self.folders.pop(0)

    def show_save_folder(self, path, next_name):
        self.folder_displays.append((Path(path), next_name))

    def publish_features(self, frame, row_count, filename):
        self.feature_displays.append((frame, row_count, filename))

    def clear_features(self):
        self.clear_count += 1

    def schedule(self, callback):
        callback()

    def show_overlay(self, region):
        self.operations.append(("show_overlay", region))
        if self.overlay_error:
            raise self.overlay_error

    def publish_overlay(self, _frame):
        pass

    def pause_overlay(self):
        self.operations.append(("pause_overlay",))

    def hide_overlay(self):
        self.operations.append(("hide_overlay",))
        self.hide_count += 1

    def close(self):
        self.close_count += 1

    def get_session_options(self): return self.options
    def show_transcript_panel(self, region): self.operations.append(("show_transcript", region))
    def hide_transcript_panel(self): self.operations.append(("hide_transcript",))
    def publish_transcript(self, segment): pass
    def publish_component_status(self, status): pass
    def publish_transcript_metrics(self, metrics): self.transcript_metrics.append(metrics)


class FakeTracker:
    def __init__(self, region, callback, overlay_callback, feature_callback, action_event_callback, operations):
        self.region = region
        self.callback = callback
        self.overlay_callback = overlay_callback
        self.feature_callback = feature_callback
        self.action_event_callback = action_event_callback
        self.operations = operations
        self.pause_count = 0
        self.resume_count = 0
        self.stop_count = 0

    def start(self):
        self.operations.append(("start_worker", self.region))

    def pause(self):
        self.pause_count += 1

    def resume(self):
        self.resume_count += 1

    def stop(self):
        self.operations.append(("stop_worker", self.region))
        self.action_event_callback(ActionEvent(0, 0.1, "blinking", 0.1, 1.0, "interrupted"))
        self.operations.append(("stop_finished", self.region))
        self.stop_count += 1


class TrackerFactory:
    def __init__(self, operations):
        self.operations = operations
        self.created = []

    def __call__(self, region, callback, overlay_callback, feature_callback, action_event_callback):
        self.operations.append(("create_worker", region))
        tracker = FakeTracker(
            region, callback, overlay_callback, feature_callback, action_event_callback, self.operations
        )
        self.created.append(tracker)
        return tracker


class FakeRecorder:
    def __init__(self, path, operations, fail_write=False):
        self.path = Path(path)
        self.operations = operations
        self.fail_write = fail_write
        self.row_count = 0
        self.event_row_count = 0
        self.closed = False
        self.close_args = []

    @property
    def raw_path(self):
        return self.path

    def write_feature(self, frame):
        if self.fail_write:
            raise RecordingError("disk full")
        self.operations.append(("write", frame.frame_index))
        self.row_count += 1

    def write_event(self, event):
        self.operations.append(("write_event", event.action))
        self.event_row_count += 1

    @property
    def raw_row_count(self):
        return self.row_count

    def close(self, *, remove_if_empty=False):
        if self.closed:
            return
        self.closed = True
        self.close_args.append(remove_if_empty)
        self.operations.append(("close_recorder", remove_if_empty))


class RecorderFactory:
    def __init__(self, operations, error=None, fail_write=False):
        self.operations = operations
        self.error = error
        self.fail_write = fail_write
        self.created = []

    def __call__(self, folder):
        self.operations.append(("create_recorder", Path(folder)))
        if self.error:
            raise self.error
        recorder = FakeRecorder(
            Path(folder) / "session_001.csv", self.operations, self.fail_write
        )
        self.created.append(recorder)
        return recorder


class FakeOrchestrator:
    def __init__(self, *_args, **_kwargs): self.stop_count = 0
    def start(self): pass
    def stop(self): self.stop_count += 1
    def pause(self): pass
    def resume(self): pass
    def submit_video(self, _frame): return True


class Selector:
    def __init__(self, *results):
        self.results = list(results)

    def __call__(self):
        return self.results.pop(0)


class AppControllerTests(unittest.TestCase):
    def test_stop_flushes_timing_after_tracker_finishes_with_and_without_audio(self):
        import csv
        import json
        from src.session_orchestrator import SessionOrchestrator
        for audio in (False, True):
            with self.subTest(audio=audio), tempfile.TemporaryDirectory() as directory:
                view = FakeView([], options=SessionOptions(system_audio=audio, consent_confirmed=True))

                class TimingTracker:
                    def __init__(self, *args, timing_recorder, **kwargs):
                        self.timing = timing_recorder
                        self.feature_callback = args[3]

                    def start(self):
                        self.timing.begin(0)
                        self.feature_callback(FeatureFrame(0, 0, False))

                    def stop(self):
                        # A final worker frame must be retained before dataset close.
                        self.timing.begin(1)

                controller = AppController(view, tracker_factory=TimingTracker,
                    orchestrator_factory=lambda *a, **kw: SessionOrchestrator(
                        *a, **kw, device_discovery=lambda: {}))
                controller.region = self.region
                controller.save_folder = Path(directory)
                controller.state = AppState.READY
                try:
                    controller.start()
                    self.assertEqual(controller.state, AppState.RUNNING)
                finally:
                    controller.stop()
                folder = Path(directory) / 'session_001'
                with (folder / 'landmark-timing.csv').open(newline='') as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual([row['frame_index'] for row in rows], ['0', '1'])
                metadata = json.loads((folder / 'session.json').read_text())
                self.assertTrue(metadata['landmark_timing']['finalized'])
                self.assertEqual(controller.state, AppState.READY)

    def test_stop_optional_capture_remembers_real_dataset_for_final(self):
        with tempfile.TemporaryDirectory() as directory:
            self.view.options = SessionOptions(microphone=True, consent_confirmed=True)
            from src.session_orchestrator import SessionOrchestrator
            controller = AppController(self.view, tracker_factory=self.trackers,
                                       orchestrator_factory=lambda *a, **kw: SessionOrchestrator(
                                           *a, **kw, device_discovery=lambda: {}))
            controller.region = self.region
            controller.save_folder = Path(directory)
            controller.state = AppState.READY
            controller.start()
            dataset = controller._recorder
            controller.stop()
            self.assertEqual(controller._last_session_directory, dataset.directory)
            self.assertEqual(self.view.renders[-1][1], "Ready")
            jobs = []
            class FinalJob:
                def __init__(self, *args, **kwargs): jobs.append(self); self.complete = kwargs["completion_callback"]
                def start(self): pass
            controller._final_job_factory = FinalJob
            controller.generate_final_transcript()
            self.assertEqual(controller.state, AppState.FINALIZING)
            count = len(self.trackers.created)
            controller.start()
            self.assertEqual(len(self.trackers.created), count)
            jobs[0].complete(False, "test completion")
            self.assertEqual(controller.state, AppState.READY)

    def test_stop_surfaces_orchestrator_failure(self):
        controller = self.make_controller(self.region)
        controller._orchestrator_factory = FakeOrchestrator
        self.view.options = SessionOptions(video=True, consent_confirmed=True)
        self.prepare(controller); controller.start()
        with patch.object(controller._orchestrator, "stop", return_value="disk full"):
            controller.stop()
        self.assertIn("disk full", self.view.renders[-1][1])

    def test_overlay_failure_stops_started_orchestrator(self):
        created = []
        def factory(*args, **kwargs):
            worker = FakeOrchestrator(*args, **kwargs)
            created.append(worker)
            return worker
        self.view.options = SessionOptions(microphone=True, consent_confirmed=True)
        self.view.overlay_error = RuntimeError("overlay unavailable")
        controller = self.make_controller(self.region)
        controller._orchestrator_factory = factory
        self.prepare(controller)
        controller.start()
        self.assertEqual(created[0].stop_count, 1)
        self.assertIsNone(controller._orchestrator)
        self.assertIn("overlay unavailable", self.view.renders[-1][1])

    def test_start_is_blocked_while_final_job_exists(self):
        controller = self.make_controller(self.region)
        self.prepare(controller)
        controller._final_job = object()
        controller.start()
        self.assertEqual(self.trackers.created, [])

    def test_tracker_stop_exception_still_cleans_other_resources(self):
        controller = self.make_controller(self.region)
        self.prepare(controller)
        controller.start()
        with patch.object(controller._tracker, "stop", side_effect=RuntimeError("tracker stuck")):
            controller.stop()
        self.assertTrue(self.recorders.created[0].closed)
        self.assertIn("tracker stuck", self.view.renders[-1][1])

    def setUp(self):
        self.region = CaptureRegion(10, 20, 300, 200)
        self.folder = Path("C:/sessions")
        self.operations = []
        self.view = FakeView(self.operations, [str(self.folder)])
        self.trackers = TrackerFactory(self.operations)
        self.recorders = RecorderFactory(self.operations)

    def make_controller(self, *selections):
        return AppController(
            self.view,
            selector=Selector(*selections),
            tracker_factory=self.trackers,
            recorder_factory=self.recorders,
            next_name_func=lambda _folder: "session_001.csv",
        )

    def prepare(self, controller):
        controller.select_region()
        controller.choose_save_folder()

    def test_start_requires_region_and_save_folder(self):
        controller = self.make_controller(self.region)
        controller.select_region()
        controller.start()
        self.assertEqual(self.recorders.created, [])
        self.assertEqual(self.trackers.created, [])
        self.assertEqual(controller.state, AppState.READY)

    def test_start_requires_consent(self):
        self.view.options = SessionOptions(consent_confirmed=False)
        controller = self.make_controller(self.region)
        self.prepare(controller)
        controller.start()
        self.assertEqual(self.recorders.created, [])
        self.assertIn("consent", self.view.renders[-1][1].lower())

    def test_tracker_error_stops_optional_media_orchestrator(self):
        self.view.options = SessionOptions(video=True, consent_confirmed=True)
        created = []
        def factory(*args, **kwargs):
            value = FakeOrchestrator(*args, **kwargs); created.append(value); return value
        controller = AppController(
            self.view, selector=Selector(self.region), tracker_factory=self.trackers,
            recorder_factory=self.recorders, next_name_func=lambda _folder: "session_001.csv",
            orchestrator_factory=factory,
        )
        self.prepare(controller); controller.start()
        self.trackers.created[0].callback(TrackerEvent(TrackerEventKind.ERROR, "capture failed"))
        self.assertEqual(created[0].stop_count, 1)

    def test_transcript_metrics_are_scheduled_to_view(self):
        self.view.options = SessionOptions(
            transcript=True, microphone=True, consent_confirmed=True
        )
        callbacks = {}

        def factory(*args, **kwargs):
            callbacks.update(kwargs)
            return FakeOrchestrator()

        controller = AppController(
            self.view, selector=Selector(self.region), tracker_factory=self.trackers,
            recorder_factory=self.recorders, next_name_func=lambda _folder: "session_001.csv",
            orchestrator_factory=factory,
        )
        self.prepare(controller); controller.start()
        marker = object()
        callbacks["transcript_metrics_callback"](marker)

        self.assertEqual(self.view.transcript_metrics, [marker])

    def test_cancelled_folder_choice_preserves_previous_folder(self):
        self.view.folders.append("")
        controller = self.make_controller(self.region)
        controller.select_region()
        controller.choose_save_folder()
        controller.choose_save_folder()
        self.assertEqual(controller.save_folder, self.folder)
        self.assertEqual(self.view.folder_displays[-1], (self.folder, "session_001.csv"))

    def test_start_creates_recorder_before_worker_and_wires_features(self):
        controller = self.make_controller(self.region)
        self.prepare(controller)
        controller.start()
        frame = FeatureFrame(0.1, 0, False)
        self.trackers.created[0].feature_callback(frame)
        self.assertEqual(
            self.operations[:4],
            [
                ("create_recorder", self.folder),
                ("show_overlay", self.region),
                ("create_worker", self.region),
                ("start_worker", self.region),
            ],
        )
        self.assertEqual(self.view.feature_displays, [(frame, 1, "session_001.csv")])

    def test_recorder_creation_error_does_not_open_overlay_or_worker(self):
        self.recorders.error = RecordingError("folder is read-only")
        controller = self.make_controller(self.region)
        self.prepare(controller)
        controller.start()
        self.assertFalse(any(op[0] == "show_overlay" for op in self.operations))
        self.assertEqual(self.trackers.created, [])
        self.assertEqual(self.view.renders[-1], (AppState.READY, "Ready - folder is read-only"))

    def test_stop_closes_once_hides_clears_and_returns_ready(self):
        controller = self.make_controller(self.region)
        self.prepare(controller)
        controller.start()
        tracker = self.trackers.created[0]
        recorder = self.recorders.created[0]
        controller.stop()
        controller.stop()
        self.assertEqual(tracker.stop_count, 1)
        self.assertEqual(recorder.close_args, [False])
        stop_index = self.operations.index(("stop_worker", self.region))
        self.assertEqual(
            self.operations[stop_index:stop_index + 4],
            [
                ("stop_worker", self.region),
                ("write_event", "blinking"),
                ("stop_finished", self.region),
                ("close_recorder", False),
            ],
        )
        self.assertEqual(self.view.hide_count, 1)
        self.assertEqual(self.view.clear_count, 1)
        self.assertEqual(controller.state, AppState.READY)

    def test_pause_resume_keeps_same_recorder(self):
        controller = self.make_controller(self.region)
        self.prepare(controller)
        controller.start()
        recorder = self.recorders.created[0]
        controller.toggle_pause()
        controller.toggle_pause()
        self.assertFalse(recorder.closed)
        self.assertEqual(len(self.recorders.created), 1)

    def test_reselect_stops_session_before_selector_and_cancel_stays_ready(self):
        controller = self.make_controller(self.region, None)
        self.prepare(controller)
        controller.start()
        controller.select_region()
        self.assertTrue(self.recorders.created[0].closed)
        self.assertEqual(controller.state, AppState.READY)
        self.assertEqual(len(self.trackers.created), 1)

    def test_error_cleanup_depends_on_written_rows_and_retains_status(self):
        for publish_row, expected_remove in ((False, True), (True, False)):
            with self.subTest(publish_row=publish_row):
                self.operations.clear()
                self.view = FakeView(self.operations, [str(self.folder)])
                self.trackers = TrackerFactory(self.operations)
                self.recorders = RecorderFactory(self.operations)
                controller = self.make_controller(self.region)
                self.prepare(controller)
                controller.start()
                tracker = self.trackers.created[0]
                if publish_row:
                    tracker.feature_callback(FeatureFrame(0.1, 0, False))
                tracker.callback(TrackerEvent(TrackerEventKind.ERROR, "capture failed"))
                tracker.callback(TrackerEvent(TrackerEventKind.STOPPED))
                self.assertEqual(self.recorders.created[0].close_args, [expected_remove])
                self.assertEqual(self.view.renders[-1][1], "Ready - capture failed")

    def test_stale_feature_callback_is_ignored_after_stop(self):
        controller = self.make_controller(self.region)
        self.prepare(controller)
        controller.start()
        callback = self.trackers.created[0].feature_callback
        recorder = self.recorders.created[0]
        controller.stop()
        callback(FeatureFrame(1.0, 5, False))
        self.assertEqual(recorder.row_count, 0)
        self.assertEqual(self.view.feature_displays, [])

    def test_write_error_propagates_for_worker_error_handling(self):
        self.recorders.fail_write = True
        controller = self.make_controller(self.region)
        self.prepare(controller)
        controller.start()
        with self.assertRaisesRegex(RecordingError, "disk full"):
            self.trackers.created[0].feature_callback(FeatureFrame(0.0, 0, False))

    def test_shutdown_is_idempotent(self):
        controller = self.make_controller(self.region)
        self.prepare(controller)
        controller.start()
        controller.shutdown()
        controller.shutdown()
        self.assertEqual(controller.state, AppState.SHUTTING_DOWN)
        self.assertEqual(self.view.close_count, 1)
        self.assertEqual(self.recorders.created[0].close_args, [False])


if __name__ == "__main__":
    unittest.main()
