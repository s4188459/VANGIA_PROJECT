import json
from pathlib import Path
import tempfile
import unittest

from src.audio_recorder import AudioSource
from src.transcription import TranscriptSegment
from src.transcript_writer import TranscriptStore


class TranscriptWriterTests(unittest.TestCase):
    def test_writes_one_live_jsonl_without_srt(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = TranscriptStore(Path(directory) / "x.jsonl")
            writer.append_live(TranscriptSegment(1, 1.2, 2.4, AudioSource.MICROPHONE, "You", "Hi", "en"))
            writer.close()
            row = json.loads((Path(directory) / "x.jsonl").read_text("utf-8"))
            self.assertEqual(row["speaker"], "You")
            self.assertEqual((row["phase"], row["status"]), ("live", "committed"))
            self.assertFalse((Path(directory) / "x.srt").exists())

    def test_replacing_final_discards_previous_final_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.jsonl"
            path.write_text('{"phase":"live","text":"live"}\n{"phase":"final","text":"old"}\n', encoding="utf-8")
            from src.transcript_writer import replace_transcript_with_final
            replace_transcript_with_final(path, [
                TranscriptSegment(2, 1, 2, AudioSource.MICROPHONE, "You", "new", phase="final", status="canonical")
            ])
            rows = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
            self.assertEqual([row["text"] for row in rows], ["live", "new"])


if __name__ == "__main__": unittest.main()
