import unittest
from pathlib import Path
import tempfile
import json
import numpy as np
import cv2
import csv
from src.dataset_session import DatasetSession
from src.session_clock import SessionClock
from src.audio_recorder import AudioChunk, AudioSource
from src.video_recorder import VideoStats
from src.video_recorder import CapturedVideoFrame
from src.feature_data import FeatureFrame

from src.capture_types import CaptureRegion
from src.session_orchestrator import SessionOrchestrator
from src.session_types import SessionOptions


class FakeDataset:
    directory = Path("session_001")
    def __init__(self): self.closed = False; self.audio = {}; self.intervals = []
    def update_component(self, status): pass
    def add_error(self, component, text): pass
    def set_audio_metadata(self, value): self.audio = value
    def record_audio_interval(self, value): self.intervals.append(value)
    def record_video_mapping(self, *args): pass
    def set_transcription_metadata(self, value): pass
    def record_media_stats(self, component, stats): pass
    def mark_drop(self, *args, **kwargs): pass
    def close(self, **kwargs): self.closed = True


class FakeWorker:
    def __init__(self): self.calls = []
    def start(self): self.calls.append("start")
    def pause(self, *_): self.calls.append("pause")
    def resume(self, *_): self.calls.append("resume")
    def stop(self, *_args, **_kwargs): self.calls.append("stop")
    def submit(self, _item): return True


class FailingStopWorker(FakeWorker):
    def stop(self, *_args, **_kwargs): raise RuntimeError("writer stuck")


class SessionOrchestratorTests(unittest.TestCase):
    def test_audio_runtime_error_is_not_overwritten_by_stopped_status(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = SessionClock(); clock.start()
            options = SessionOptions(microphone=True, consent_confirmed=True)
            region = CaptureRegion(0, 0, 4, 3)
            dataset = DatasetSession.create(Path(directory), options, region, clock)
            callbacks = []
            def factory(source, device, accept, status, *a, **k):
                worker = FakeWorker(); worker.source = source; callbacks.append(status); return worker
            orchestrator = SessionOrchestrator(dataset, options, region, clock, audio_factory=factory,
                stereo_factory=lambda *a, **k: FakeWorker(),
                device_discovery=lambda: {AudioSource.MICROPHONE: type("D", (), {"name": "test"})()})
            orchestrator.start()
            callbacks[0]("microphone", "error", "device lost")
            orchestrator.stop()
            metadata = dataset.snapshot()
            self.assertEqual(metadata["components"]["microphone"]["state"], "error")
            self.assertEqual(metadata["status"], "incomplete")

    def test_real_mp4_and_csv_share_the_session_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [0.]
            clock = SessionClock(clock=lambda: now[0]); clock.start()
            options = SessionOptions(video=True, consent_confirmed=True)
            region = CaptureRegion(0, 0, 16, 16)
            dataset = DatasetSession.create(Path(directory), options, region, clock)
            orchestrator = SessionOrchestrator(dataset, options, region, clock)
            orchestrator.start()
            for index, timestamp in enumerate((0., .15, .32)):
                orchestrator.submit_video(CapturedVideoFrame(index, timestamp, np.full((16, 16, 3), 40 + index * 60, np.uint8)))
                dataset.write_feature(FeatureFrame(timestamp, index, False))
            now[0] = .5
            orchestrator.stop()
            capture = cv2.VideoCapture(str(dataset.directory / "video.mp4"))
            try:
                self.assertTrue(capture.isOpened())
                fps = capture.get(cv2.CAP_PROP_FPS)
                decoded = []
                while True:
                    ok, frame = capture.read()
                    if not ok: break
                    decoded.append(frame)
                self.assertEqual(len(decoded), 10)
                self.assertAlmostEqual(len(decoded) / fps, .5)
                self.assertGreater(decoded[6].mean(), decoded[3].mean())
            finally: capture.release()
            with dataset.raw_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([r["video_frame_index"] for r in rows], ["0", "3", "6"])
            self.assertFalse((dataset.directory / "video-map.tmp").exists())

    def test_real_manifest_records_audio_rejection_and_video_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = SessionClock(); clock.start()
            region = CaptureRegion(0, 0, 4, 3)
            options = SessionOptions(microphone=True, video=True, consent_confirmed=True)
            dataset = DatasetSession.create(Path(directory), options, region, clock)
            class Rejecting(FakeWorker):
                def submit(self, _): return False
            class BrokenVideo(FakeWorker):
                def stop(self, *args, **kwargs):
                    return VideoStats(0, 1, "mp4v", "disk full")
            def capture(source, device, callback, *args, **kwargs):
                worker = FakeWorker()
                worker.start = lambda: callback(AudioChunk(source, 0, 0., .1, 10, 1, np.zeros(1)))
                return worker
            orchestrator = SessionOrchestrator(dataset, options, region, clock,
                stereo_factory=lambda *a, **k: Rejecting(), audio_factory=capture,
                video_factory=lambda *a, **k: BrokenVideo(),
                device_discovery=lambda: {AudioSource.MICROPHONE: type("D", (), {"name": "test"})()})
            orchestrator.start(); orchestrator.stop()
            metadata = json.loads(dataset.session_path.read_text("utf-8"))
            self.assertEqual(metadata["drops"]["audio.microphone"], 1)
            self.assertEqual(metadata["media_stats"]["video"]["failure"], "disk full")
            self.assertEqual(metadata["status"], "incomplete")

    def test_live_transcription_checks_short_utterances_for_pauses(self):
        dataset = FakeDataset(); created = {}

        class FakeTranscriptWorker(FakeWorker):
            def __init__(self, transcriber, callback, **kwargs):
                super().__init__(); created.update(kwargs)

        with tempfile.TemporaryDirectory() as directory:
            dataset.directory = Path(directory)
            orchestrator = SessionOrchestrator(
                dataset,
                SessionOptions(transcript=True, microphone=True, consent_confirmed=True),
                CaptureRegion(0, 0, 10, 10),
                clock=type("C", (), {"elapsed_s": lambda self: 0.0})(),
                transcriber_factory=lambda _path: object(),
                transcription_worker_factory=FakeTranscriptWorker,
                stereo_factory=lambda *_args, **_kwargs: FakeWorker(),
                device_discovery=lambda: {},
            )
            orchestrator.start(); orchestrator.stop()

        self.assertEqual(created["window_s"], 1.2)
        self.assertEqual(created["overlap_s"], 0.75)
        self.assertEqual(created["max_window_s"], 12.0)
        self.assertTrue(callable(created["speech_boundary"]))

    def test_transcription_metrics_callback_reaches_worker(self):
        dataset = FakeDataset(); created = {}; received = []

        class FakeTranscriptWorker(FakeWorker):
            def __init__(self, transcriber, callback, **kwargs):
                super().__init__(); created.update(kwargs)

        with tempfile.TemporaryDirectory() as directory:
            dataset.directory = Path(directory)
            orchestrator = SessionOrchestrator(
                dataset,
                SessionOptions(transcript=True, consent_confirmed=True),
                CaptureRegion(0, 0, 10, 10),
                clock=type("C", (), {"elapsed_s": lambda self: 0.0})(),
                transcriber_factory=lambda _path: object(),
                transcription_worker_factory=FakeTranscriptWorker,
                transcript_metrics_callback=received.append,
            )
            orchestrator.start(); orchestrator.stop()

        marker = object()
        created["metrics_callback"](marker)
        self.assertEqual(received, [marker])

    def test_two_sources_share_one_stereo_writer(self):
        dataset = FakeDataset(); stereo = FakeWorker(); captures = []
        devices = {
            __import__("src.audio_recorder", fromlist=["AudioSource"]).AudioSource.SYSTEM_AUDIO: type("D", (), {"name": "speakers"})(),
            __import__("src.audio_recorder", fromlist=["AudioSource"]).AudioSource.MICROPHONE: type("D", (), {"name": "mic"})(),
        }
        def capture_factory(*args, **kwargs):
            worker = FakeWorker(); captures.append(worker); return worker
        orchestrator = SessionOrchestrator(
            dataset, SessionOptions(system_audio=True, microphone=True, consent_confirmed=True),
            CaptureRegion(0, 0, 10, 10), clock=type("C", (), {"elapsed_s": lambda self: 0.0})(),
            audio_factory=capture_factory, stereo_factory=lambda *_args, **_kwargs: stereo,
            device_discovery=lambda: devices,
        )
        orchestrator.start(); orchestrator.stop()
        self.assertEqual(len(captures), 2)
        self.assertEqual(stereo.calls, ["start", "stop"])
        self.assertEqual(dataset.audio["file"], "audio.wav")

    def test_starts_only_requested_video_and_stops_cleanly(self):
        video = FakeWorker(); dataset = FakeDataset()
        orchestrator = SessionOrchestrator(
            dataset, SessionOptions(video=True, consent_confirmed=True),
            CaptureRegion(0, 0, 10, 10), clock=type("C", (), {"elapsed_s": lambda self: 1.0})(),
            video_factory=lambda *_args, **_kwargs: video,
        )
        orchestrator.start(); orchestrator.stop()
        self.assertEqual(video.calls, ["start", "stop"])
        self.assertTrue(dataset.closed)

    def test_worker_stop_failure_still_closes_dataset(self):
        dataset = FakeDataset()
        orchestrator = SessionOrchestrator(
            dataset, SessionOptions(video=True, consent_confirmed=True),
            CaptureRegion(0, 0, 10, 10), clock=type("C", (), {"elapsed_s": lambda self: 1.0})(),
            video_factory=lambda *_args, **_kwargs: FailingStopWorker(),
        )
        orchestrator.start(); orchestrator.stop()
        self.assertTrue(dataset.closed)


if __name__ == "__main__": unittest.main()
