import csv
import tempfile
import unittest
from pathlib import Path

from src.action_event_recorder import ActionEventRecorder, EVENT_CSV_FIELDS
from src.action_types import ActionEvent
from src.feature_data import FeatureFrame
from src.recording_session import RecordingSession
from src.session_recorder import RecordingError


class ActionEventRecorderTests(unittest.TestCase):
    def test_exact_header_row_validation_and_close(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.csv"
            handle = open(path, "x", encoding="utf-8", newline="", buffering=1)
            recorder = ActionEventRecorder(path, handle)
            recorder.write(ActionEvent(12.4, 14.1, "eyes_looking_down", 1.7, 0.72, "completed"))
            recorder.close()
            recorder.close()
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], ",".join(EVENT_CSV_FIELDS))
            self.assertEqual(lines[1], "12.400,14.100,eyes_looking_down,1.700,0.7200,completed")
            with self.assertRaisesRegex(RecordingError, "closed"):
                recorder.write(ActionEvent(1, 2, "x", 1, 1, "completed"))

    def test_rejects_invalid_events(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.csv"
            recorder = ActionEventRecorder(path, open(path, "x", encoding="utf-8", newline=""))
            for event in (
                ActionEvent(1, 2, "x", 1, 1, "unknown"),
                ActionEvent(2, 1, "x", 1, 1, "completed"),
                ActionEvent(1, 2, "x", -1, 1, "completed"),
            ):
                with self.subTest(event=event):
                    with self.assertRaises(RecordingError):
                        recorder.write(event)
            recorder.close()


class RecordingSessionTests(unittest.TestCase):
    def test_creates_matching_pair_and_routes_both_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            session = RecordingSession.create(Path(directory))
            self.assertEqual(session.raw_path.name, "session_001.csv")
            self.assertEqual(session.event_path.name, "session_001_events.csv")
            session.write_feature(FeatureFrame(0.0, 0, False))
            session.write_event(ActionEvent(0, 0.1, "blinking", 0.1, 1.2, "completed"))
            session.close()
            self.assertEqual(session.raw_row_count, 1)
            self.assertEqual(session.event_row_count, 1)
            self.assertTrue(session.closed)
            with session.raw_path.open(newline="", encoding="utf-8") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 1)

    def test_orphan_files_reserve_numbers_and_empty_pair_can_be_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "session_002_events.csv").write_text("existing", encoding="utf-8")
            (folder / "session_004.csv").write_text("existing", encoding="utf-8")
            session = RecordingSession.create(folder)
            self.assertEqual(session.raw_path.name, "session_005.csv")
            raw_path, event_path = session.raw_path, session.event_path
            session.close(remove_if_empty=True)
            self.assertFalse(raw_path.exists())
            self.assertFalse(event_path.exists())
            self.assertTrue((folder / "session_002_events.csv").exists())


if __name__ == "__main__":
    unittest.main()
