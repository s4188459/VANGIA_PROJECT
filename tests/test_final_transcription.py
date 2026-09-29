import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from src.audio_recorder import AudioSource
from src.final_transcription import FinalTranscriptionJob, map_wav_time_to_session, resolve_final_model, update_final_status
from src.stereo_audio import AudioInterval
from src.transcription import TranscriptSegment


class FinalTranscriptionTests(unittest.TestCase):
    def test_long_wav_uses_bounded_windows_and_session_time_after_pause(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); audio = folder / "audio.wav"
            with wave.open(str(audio), "wb") as output:
                output.setnchannels(2); output.setsampwidth(2); output.setframerate(10)
                output.writeframes(np.zeros((650, 2), np.int16).tobytes())
            chunks = []; completed = []
            class Decoder:
                def transcribe(self, chunk): chunks.append(chunk); return ()
            job = FinalTranscriptionJob(audio, (AudioInterval(5, 65, 0, 600), AudioInterval(80, 85, 600, 650)),
                folder / "transcript.jsonl", transcriber_factory=Decoder,
                completion_callback=lambda ok, message: completed.append((ok, message)))
            job.start(); job.join(3)
            self.assertTrue(completed[0][0], completed)
            self.assertLessEqual(max(len(c.samples) for c in chunks), 300)
            self.assertEqual({c.start_s for c in chunks if c.start_s >= 80}, {80.})
            self.assertEqual(max(c.end_s for c in chunks), 85.)

    def test_updates_final_status_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            path.write_text('{"transcription":{"final":{"status":"not_started"}}}', encoding="utf-8")
            update_final_status(path, "completed", "ready", "small.en")
            import json
            value = json.loads(path.read_text("utf-8"))["transcription"]["final"]
            self.assertEqual(value, {"status": "completed", "message": "ready", "model": "small.en"})
            self.assertFalse(path.with_suffix(".json.tmp").exists())
    def test_resolves_strongest_installed_model_with_base_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "faster-whisper-base-en").mkdir()
            self.assertEqual(resolve_final_model(root).name, "faster-whisper-base-en")
            (root / "faster-whisper-small-en").mkdir()
            self.assertEqual(resolve_final_model(root).name, "faster-whisper-small-en")
    def test_maps_wav_offsets_across_pause_gap(self):
        intervals = (AudioInterval(0, 5, 0, 80000), AudioInterval(10, 15, 80000, 160000))
        self.assertEqual(map_wav_time_to_session(7.0, 16000, intervals), 12.0)
        self.assertIsNone(map_wav_time_to_session(11.0, 16000, intervals))

    def test_writes_canonical_records_for_both_channels(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); audio = folder / "audio.wav"; transcript = folder / "transcript.jsonl"
            transcript.write_text('{"phase":"live","text":"old"}\n', encoding="utf-8")
            with wave.open(str(audio), "wb") as output:
                output.setnchannels(2); output.setsampwidth(2); output.setframerate(4)
                output.writeframes(np.array([[1000, 2000], [1000, 2000]], np.int16).tobytes())
            class FakeTranscriber:
                def transcribe(self, chunk):
                    speaker = "You" if chunk.source is AudioSource.MICROPHONE else "Student"
                    return (TranscriptSegment(1, chunk.start_s, chunk.end_s, chunk.source, speaker, speaker,
                                              phase="final", status="canonical"),)
            completed = []
            job = FinalTranscriptionJob(audio, (AudioInterval(0, .5, 0, 2),), transcript,
                                        transcriber_factory=lambda: FakeTranscriber(),
                                        completion_callback=lambda ok, message: completed.append(ok))
            job.start(); job.join(2)
            text = transcript.read_text("utf-8")
            self.assertIn('"speaker": "You"', text)
            self.assertIn('"speaker": "Student"', text)
            self.assertEqual(completed, [True])

    def test_failure_preserves_live_file(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); audio = folder / "audio.wav"; transcript = folder / "transcript.jsonl"
            original = b'{"phase":"live","text":"safe"}\n'; transcript.write_bytes(original)
            with wave.open(str(audio), "wb") as output:
                output.setnchannels(2); output.setsampwidth(2); output.setframerate(4)
                output.writeframes(np.zeros((2, 2), np.int16).tobytes())
            class Failing:
                def transcribe(self, _chunk): raise RuntimeError("model failed")
            job = FinalTranscriptionJob(audio, (AudioInterval(0, .5, 0, 2),), transcript,
                                        transcriber_factory=lambda: Failing())
            job.start(); job.join(2)
            self.assertEqual(transcript.read_bytes(), original)
            self.assertFalse(transcript.with_suffix(".jsonl.tmp").exists())


if __name__ == "__main__": unittest.main()
