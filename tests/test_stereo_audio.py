import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock

import numpy as np

from src.audio_recorder import AudioChunk, AudioSource
from src.stereo_audio import StereoAudioWriter


def chunk(source, start, samples, rate=4):
    values = np.asarray(samples, np.float32)
    return AudioChunk(source, 0, start, start + len(values) / rate, rate, 1, values)


class StereoAudioTests(unittest.TestCase):
    def test_flush_failure_still_closes_wav(self):
        writer = StereoAudioWriter(Path("unused.wav"), sample_rate=4)
        output = Mock(); output.writeframes.side_effect = OSError("disk full")
        writer._wave = output; writer._active = True; writer._max_frame = 1
        with self.assertRaisesRegex(OSError, "disk full"):
            writer.stop()
        output.close.assert_called_once()
        self.assertIsNone(writer._wave)

    def test_writes_microphone_left_and_system_right(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio.wav"
            writer = StereoAudioWriter(path, sample_rate=4)
            writer.start()
            writer.submit(chunk(AudioSource.MICROPHONE, 0.0, [.1, .2]))
            writer.submit(chunk(AudioSource.SYSTEM_AUDIO, 0.0, [.7, .8]))
            stats = writer.stop()
            with wave.open(str(path), "rb") as source:
                data = np.frombuffer(source.readframes(source.getnframes()), np.int16).reshape(-1, 2) / 32768.0
            np.testing.assert_allclose(data[:2, 0], [.1, .2], atol=1/32768)
            np.testing.assert_allclose(data[:2, 1], [.7, .8], atol=1/32768)
            self.assertEqual(stats.written_frames, 2)

    def test_missing_source_is_silence_and_pause_creates_intervals(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = StereoAudioWriter(Path(directory) / "audio.wav", sample_rate=4)
            writer.start()
            writer.submit(chunk(AudioSource.MICROPHONE, 0.0, [.2, .2]))
            writer.pause(0.5)
            writer.resume(2.0)
            writer.submit(chunk(AudioSource.MICROPHONE, 2.0, [.3, .3]))
            stats = writer.stop()
            self.assertEqual(len(stats.intervals), 2)
            self.assertEqual(stats.intervals[1].session_start_s, 2.0)
            with wave.open(str(Path(directory) / "audio.wav"), "rb") as source:
                data = np.frombuffer(source.readframes(source.getnframes()), np.int16).reshape(-1, 2)
            self.assertTrue(np.all(data[:, 1] == 0))

    def test_late_chunk_is_rejected_instead_of_shifted_forward(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = StereoAudioWriter(Path(directory) / "audio.wav", sample_rate=4, flush_delay_s=0)
            writer.start()
            self.assertTrue(writer.submit(chunk(AudioSource.MICROPHONE, 0.0, [.2, .2])))
            self.assertFalse(writer.submit(chunk(AudioSource.SYSTEM_AUDIO, 0.0, [.7, .7])))
            writer.stop()
            with wave.open(str(Path(directory) / "audio.wav"), "rb") as source:
                data = np.frombuffer(source.readframes(source.getnframes()), np.int16).reshape(-1, 2)
            self.assertEqual(len(data), 2)
            self.assertTrue(np.all(data[:, 1] == 0))


if __name__ == "__main__": unittest.main()
