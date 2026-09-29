import unittest
import numpy as np
from unittest.mock import Mock
import time
from src.audio_recorder import AudioCaptureWorker, AudioSource

from src.audio_recorder import pcm16_to_mono, wait_if_paused


class AudioConversionTests(unittest.TestCase):
    def test_pause_drains_device_without_publishing_audio(self):
        reads = []; chunks = []
        class Stream:
            def read(self, *_args, **_kwargs):
                reads.append(1); time.sleep(.005); return np.ones(4, np.int16).tobytes()
            def stop_stream(self): pass
            def close(self): pass
        device = type("D", (), {"sample_rate": 100, "channels": 1})()
        clock = type("C", (), {"elapsed_s": lambda _: time.perf_counter()})()
        worker = AudioCaptureWorker(AudioSource.MICROPHONE, device, chunks.append, lambda *a: None,
                                    clock, stream_factory=lambda *a: Stream(), frames_per_buffer=4)
        worker.pause(0.)
        worker.start()
        try:
            deadline = time.perf_counter() + .3
            while len(reads) < 3 and time.perf_counter() < deadline: time.sleep(.005)
            self.assertGreaterEqual(len(reads), 3)
            self.assertEqual(chunks, [])
        finally: worker.stop()

    def test_stop_closes_stream_even_if_stop_stream_fails(self):
        stream = Mock(); stream.stop_stream.side_effect = OSError("disconnected")
        worker = AudioCaptureWorker(AudioSource.MICROPHONE, None, lambda _: None, lambda *a: None,
                                    None, stream_factory=lambda *a: stream)
        worker._stream = stream
        worker.stop()
        stream.close.assert_called_once()

    def test_stereo_pcm_is_downmixed_to_mono_frames(self):
        pcm = np.array([1000, -1000, 2000, 0], dtype=np.int16).tobytes()
        mono = pcm16_to_mono(pcm, 2)
        np.testing.assert_allclose(mono, [0.0, 1000 / 32768.0], atol=1e-6)

    def test_paused_audio_waits_instead_of_busy_spinning(self):
        class Flag:
            def is_set(self): return True
        class Stop:
            def __init__(self): self.waits = []
            def wait(self, seconds): self.waits.append(seconds)
        stop = Stop()
        self.assertTrue(wait_if_paused(Flag(), stop, 0.02))
        self.assertEqual(stop.waits, [0.02])


if __name__ == "__main__": unittest.main()
