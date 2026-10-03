import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np

from src.audio_recorder import AudioChunk, AudioSource
from src.transcription import TranscriptSegment, TranscriptionWorker
from src.live_inference_process import ProcessEnglishTranscriber
from src.session_clock import SessionClock
from src.session_types import SessionOptions
from src.capture_types import CaptureRegion, AppState
from src.dataset_session import DatasetSession
from src.session_orchestrator import SessionOrchestrator
from src.app_controller import AppController
from tests.test_app_controller import FakeView, TrackerFactory


class BlockingModel:
    def __init__(self, path): self.path = Path(path)
    def transcribe(self, chunk):
        (self.path / "inference_started").write_text("started")
        time.sleep(60)
        (self.path / "inference_finished").write_text("finished")
        return ()


class EchoModel:
    def __init__(self, path): pass
    def transcribe(self, chunk):
        return (TranscriptSegment(1, chunk.start_s, chunk.end_s, chunk.source, "Student", "hello"),)


class BrokenModel:
    def __init__(self, path): raise RuntimeError("model failed to load")


def chunk(source=AudioSource.SYSTEM_AUDIO, start=0., duration=.1):
    return AudioChunk(source, 0, start, start+duration, 16000, 1, np.zeros(round(16000*duration), np.float32))


class ImmediateStopTests(unittest.TestCase):
    def test_stop_terminates_active_native_owner_without_draining(self):
        with tempfile.TemporaryDirectory() as folder:
            model = ProcessEnglishTranscriber(folder, model_factory=BlockingModel)
            rows=[]
            worker=TranscriptionWorker(model, rows.append, window_s=.1, overlap_s=0.)
            worker.start(); worker.submit(chunk())
            try:
                deadline=time.monotonic()+15
                while not (Path(folder)/"inference_started").exists() and time.monotonic()<deadline:
                    time.sleep(.01)
                self.assertTrue((Path(folder)/"inference_started").exists())
                worker.submit(chunk(start=.1))
                started=time.monotonic(); worker.request_stop(); stats=worker.stop()
                self.assertLess(time.monotonic()-started, 2.)
                self.assertEqual(rows, [])
                self.assertFalse((Path(folder)/"inference_finished").exists())
                self.assertFalse(worker._thread.is_alive())
                self.assertTrue(model._closed)
                self.assertFalse(stats['coverage_complete'])
                self.assertEqual(stats['unprocessed_audio_intervals']['system_audio'], [[0., .2]])
                self.assertFalse(worker.submit(chunk(start=.2)))
                self.assertIs(worker.stop(), stats)
                model.close()
            finally:
                worker.request_stop(); worker.stop()

    def test_completed_text_survives_and_partial_buffer_is_not_decoded(self):
        with tempfile.TemporaryDirectory() as folder:
            model=ProcessEnglishTranscriber(folder, model_factory=EchoModel)
            published=threading.Event(); rows=[]
            def publish(row): rows.append(row); published.set()
            worker=TranscriptionWorker(model,publish,window_s=.1,overlap_s=0.)
            worker.start(); worker.submit(chunk())
            try:
                self.assertTrue(published.wait(15))
                # Wait for coverage acknowledgement after callback publication.
                deadline=time.monotonic()+2
                while worker._last_metrics is None and time.monotonic()<deadline: time.sleep(.005)
                worker.submit(chunk(start=.1,duration=.04))
                worker.submit(chunk(AudioSource.MICROPHONE,start=1.,duration=.03))
                worker.request_stop();stats=worker.stop()
                self.assertEqual([s.text for s in rows],['hello'])
                self.assertEqual(stats['unprocessed_audio_intervals']['system_audio'],[[.1,.14]])
                self.assertEqual(stats['unprocessed_audio_intervals']['microphone'],[[1.,1.03]])
                self.assertIsNotNone(stats['last_metrics'])
            finally: worker.request_stop();worker.stop()

    def test_child_startup_failure_is_reported_and_reaped(self):
        model=ProcessEnglishTranscriber('unused', model_factory=BrokenModel)
        try:
            with self.assertRaisesRegex(RuntimeError,'model failed to load'):
                model.transcribe(chunk())
        finally: model.close()
        self.assertTrue(model._closed)

    def test_cancel_idle_worker_never_flushes(self):
        class NoDecode:
            def transcribe(self, chunk): raise AssertionError('must not flush')
        worker=TranscriptionWorker(NoDecode(),lambda _:None,window_s=1.,overlap_s=0.)
        worker.start();worker.submit(chunk());worker.request_stop();stats=worker.stop()
        self.assertIsNone(stats['failure'])
        self.assertFalse(worker._thread.is_alive())
        self.assertFalse(stats['coverage_complete'])

    def test_session_duration_stops_at_click_not_file_close(self):
        now=[0.];clock=SessionClock(clock=lambda:now[0]);clock.start()
        now[0]=5.;clock.stop();now[0]=50.
        self.assertEqual(clock.elapsed_s(),5.)
        clock.stop();self.assertEqual(clock.elapsed_s(),5.)

    def test_manifest_records_intentional_partial_transcript_without_timeout(self):
        with tempfile.TemporaryDirectory() as folder:
            clock=SessionClock();clock.start()
            options=SessionOptions(transcript=True,consent_confirmed=True)
            region=CaptureRegion(0,0,4,4)
            dataset=DatasetSession.create(Path(folder),options,region,clock)
            class NoDecode:
                def transcribe(self, chunk): raise AssertionError('must not decode after stop')
            orchestrator=SessionOrchestrator(dataset,options,region,clock,
                                             transcriber_factory=lambda _:NoDecode())
            orchestrator.start();orchestrator._transcription.submit(chunk())
            orchestrator.request_stop();orchestrator.stop()
            metadata=json.loads(dataset.session_path.read_text())
            self.assertEqual(metadata['status'],'closed')
            self.assertEqual(metadata['errors'],[])
            stats=metadata['media_stats']['transcript']
            self.assertEqual(stats['stop_policy'],'cancel_without_flush')
            self.assertFalse(stats['coverage_complete'])
            self.assertEqual((dataset.directory/'transcript.jsonl').read_text(),'')

    def test_ui_returns_before_cleanup_and_blocks_restart_and_late_updates(self):
        operations=[]
        view=FakeView(operations)
        background=[]
        view.run_background=lambda op,done: background.append((op,done))
        factory=TrackerFactory(operations)
        with tempfile.TemporaryDirectory() as folder:
            controller=AppController(view,tracker_factory=factory)
            controller.region=CaptureRegion(0,0,4,4);controller.save_folder=Path(folder)
            controller._set_state(AppState.READY,'Ready');controller.start()
            generation=controller._generation
            controller.stop()
            self.assertEqual(controller.state,AppState.STOPPING)
            self.assertEqual(factory.created[0].stop_count,0)
            controller.start();controller.stop()
            self.assertEqual(len(background),1)
            late=[];controller._schedule_session(lambda:late.append(1),generation)
            self.assertEqual(late,[])
            controller.shutdown()
            self.assertFalse(controller._closed)
            operation,done=background.pop();done(operation())
            self.assertTrue(controller._closed)
            self.assertEqual(view.close_count,1)
