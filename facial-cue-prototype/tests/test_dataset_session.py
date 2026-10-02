import json
from pathlib import Path
import tempfile
import unittest
import csv
from src.feature_data import FeatureFrame
from src.action_types import ActionEvent
from unittest.mock import patch

from src.capture_types import CaptureRegion
from src.dataset_session import DatasetSession
from src.session_clock import SessionClock
from src.session_types import SessionOptions


class DatasetSessionTests(unittest.TestCase):
    def test_manifest_init_failure_closes_csv_and_removes_only_new_session(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = SessionClock(); clock.start()
            with patch.object(DatasetSession, "_write_manifest", side_effect=OSError("manifest failed")):
                with self.assertRaisesRegex(OSError, "manifest failed"):
                    DatasetSession.create(Path(directory), SessionOptions(consent_confirmed=True),
                                          CaptureRegion(0, 0, 4, 3), clock)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_consecutive_drop_details_are_coalesced_by_source(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = SessionClock(); clock.start()
            session = DatasetSession.create(Path(directory), SessionOptions(consent_confirmed=True),
                                            CaptureRegion(0, 0, 4, 3), clock)
            for i in range(100):
                for source in ("microphone", "system_audio"):
                    session.mark_drop(source, start_s=i * .1, end_s=(i + 1) * .1, reason="test")
            session.close()
            metadata = json.loads(session.session_path.read_text("utf-8"))
            self.assertEqual(len(metadata["drop_details"]), 2)
            self.assertEqual(metadata["drops"]["microphone"], 100)

    def test_events_append_without_rewriting_manifest_until_close(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = SessionClock(); clock.start()
            session = DatasetSession.create(Path(directory), SessionOptions(consent_confirmed=True),
                                            CaptureRegion(0, 0, 4, 3), clock)
            with patch.object(session, "_write_manifest", wraps=session._write_manifest) as write:
                session.write_event(ActionEvent(0., .1, "blinking", .1, .8, "completed"))
                session.write_event(ActionEvent(1., 1.1, "blinking", .1, .9, "completed"))
                count = write.call_count
            session.close()
            self.assertEqual(count, 0)
            metadata = json.loads(session.session_path.read_text("utf-8"))
            self.assertEqual(len(metadata["observable_events"]), 2)
            self.assertEqual({p.name for p in session.directory.iterdir()}, {"features.csv", "session.json"})

    def test_csv_indices_are_finalized_from_successful_video_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = SessionClock(); clock.start()
            session = DatasetSession.create(Path(directory), SessionOptions(video=True, consent_confirmed=True),
                                            CaptureRegion(0, 0, 4, 3), clock)
            session.write_feature(FeatureFrame(0., 0, False))
            session.write_feature(FeatureFrame(.1, 1, False))
            session.record_video_mapping(1, 2)
            session.close()
            with session.raw_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([r["video_frame_index"] for r in rows], ["", "2"])
            self.assertEqual({p.name for p in session.directory.iterdir()}, {"features.csv", "session.json"})

    def test_allocates_directory_and_writes_compact_session_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = SessionClock(clock=lambda: 10.0)
            clock.start()
            session = DatasetSession.create(
                Path(directory), SessionOptions(consent_confirmed=True),
                CaptureRegion(1, 2, 300, 200), clock,
            )
            metadata = json.loads(session.session_path.read_text("utf-8"))
            self.assertEqual(session.directory.name, "session_001")
            self.assertEqual(session.raw_path.name, "features.csv")
            self.assertEqual({p.name for p in session.directory.iterdir()}, {"features.csv", "session.json"})
            self.assertEqual(metadata["schema_version"], "3.0")
            self.assertEqual(metadata["status"], "recording")
            self.assertTrue(metadata["consent"]["confirmed"])
            self.assertEqual(metadata["region"]["width"], 300)
            session.record_audio_interval({"session_start_s": 0.0, "session_end_s": 5.0,
                                           "wav_start_frame": 0, "wav_end_frame": 240000})
            self.assertEqual(session.snapshot()["audio"]["intervals"][0]["wav_end_frame"], 240000)
            session.close()
            self.assertEqual(
                json.loads(session.session_path.read_text("utf-8"))["status"],
                "closed",
            )

    def test_uses_next_available_number(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "session_003").mkdir()
            clock = SessionClock(clock=lambda: 1.0)
            clock.start()
            session = DatasetSession.create(
                Path(directory), SessionOptions(consent_confirmed=True),
                CaptureRegion(0, 0, 10, 10), clock,
            )
            self.assertEqual(session.directory.name, "session_004")
            session.close()

    def test_empty_failed_start_can_remove_session_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = SessionClock(clock=lambda: 1.0); clock.start()
            session = DatasetSession.create(Path(directory), SessionOptions(consent_confirmed=True), CaptureRegion(0, 0, 10, 10), clock)
            path = session.directory
            session.close(status="failed", remove_if_empty=True)
            self.assertFalse(path.exists())


if __name__ == "__main__": unittest.main()
