import tempfile
import threading
import unittest
import wave
from itertools import cycle
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from src.audio_recorder import AudioCaptureWorker, AudioSource
from src.stereo_audio import StereoAudioWriter


class AudioCaptureRegressionTests(unittest.TestCase):
    def test_jittered_reads_preserve_exact_pcm_sequence_in_wav(self):
        # Uneven scheduling used to introduce both holes and overwrites.
        clock_values = cycle([0., .013, .041, .042, .081, .082, .100, .101, .120, .121])
        signal = np.arange(1, 51, dtype=np.int16) * 100
        chunks = []
        errors = []
        class Stream:
            offset = 0
            def read(self, *args, **kwargs):
                data = signal[self.offset:self.offset + 10].tobytes()
                self.offset += 10
                return data
            def stop_stream(self): pass
            def close(self): pass
        device = SimpleNamespace(sample_rate=1000, channels=1)
        worker = AudioCaptureWorker(AudioSource.SYSTEM_AUDIO, device, None,
            lambda *args: errors.append(args), SimpleNamespace(elapsed_s=lambda: next(clock_values)),
            stream_factory=lambda *args: Stream(), frames_per_buffer=10)
        def accept(chunk):
            chunks.append(chunk)
            if len(chunks) == 5: worker._stop.set()
        worker._chunk_callback = accept
        worker.start(); worker._thread.join(2); worker.stop()
        self.assertEqual(errors, [])
        self.assertEqual(len(chunks), 5)
        for left, right in zip(chunks, chunks[1:]):
            self.assertAlmostEqual(left.end_s, right.start_s)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'audio.wav'
            writer = StereoAudioWriter(path, sample_rate=1000)
            writer.start()
            for chunk in chunks: writer.submit(chunk)
            writer.stop()
            with wave.open(str(path), 'rb') as source:
                audio = np.frombuffer(source.readframes(source.getnframes()), np.int16).reshape(-1, 2)
            np.testing.assert_array_equal(audio[:, 1], np.rint(signal.astype(float) / 32768 * 32767).astype(np.int16))
            self.assertTrue(np.all(audio[:, 0] == 0))

    def test_stop_never_closes_stream_during_read(self):
        entered = threading.Event(); release = threading.Event(); closed = threading.Event()
        class Stream:
            def read(self, *args, **kwargs):
                entered.set(); release.wait(2)
                return np.ones(10, np.int16).tobytes()
            def stop_stream(self):
                if not release.is_set(): raise AssertionError('closed during read')
            def close(self): closed.set()
        worker = AudioCaptureWorker(AudioSource.SYSTEM_AUDIO,
            SimpleNamespace(sample_rate=1000, channels=1), lambda _: self.fail('published after Stop'),
            lambda *args: None, SimpleNamespace(elapsed_s=lambda: 0.), stream_factory=lambda *args: Stream())
        worker.start()
        self.assertTrue(entered.wait(1))
        try:
            with self.assertRaisesRegex(RuntimeError, 'timeout'): worker.stop(.01)
            self.assertFalse(closed.is_set())
        finally:
            release.set(); worker.stop(2)
        self.assertTrue(closed.is_set())

    def test_idle_native_stream_can_stop_without_blocking_read(self):
        polled = threading.Event(); closed = threading.Event()
        class Stream:
            def get_read_available(self): polled.set(); return 0
            def read(self, *args, **kwargs): raise AssertionError('read without available samples')
            def stop_stream(self): pass
            def close(self): closed.set()
        worker = AudioCaptureWorker(AudioSource.SYSTEM_AUDIO, SimpleNamespace(sample_rate=48000, channels=1),
            lambda _: None, lambda *args: None, SimpleNamespace(elapsed_s=lambda: 0.),
            stream_factory=lambda *args: Stream())
        worker.start(); self.assertTrue(polled.wait(1)); worker.stop()
        self.assertTrue(closed.is_set())
