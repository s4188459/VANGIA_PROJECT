import csv
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from src.feature_data import FeatureFrame
from src.session_recorder import (
    CSV_FIELDS,
    CsvSessionRecorder,
    RecordingError,
    next_session_name,
)


class SessionRecorderTests(unittest.TestCase):
    def test_next_name_uses_max_matching_number(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.assertEqual(next_session_name(folder), "session_001.csv")
            (folder / "session_001.csv").touch()
            (folder / "session_003.csv").touch()
            (folder / "session_notes.csv").touch()

            self.assertEqual(next_session_name(folder), "session_004.csv")

    def test_next_name_reserves_orphan_event_file_number(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "session_009_events.csv").write_text("header", encoding="utf-8")
            self.assertEqual(next_session_name(folder), "session_010.csv")

    def test_exclusive_creation_retries_after_race(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            real_open = open
            attempts = []

            def racing_open(path, *args, **kwargs):
                attempts.append(Path(path).name)
                if len(attempts) == 1:
                    (folder / Path(path).name).touch()
                    raise FileExistsError(path)
                return real_open(path, *args, **kwargs)

            recorder = CsvSessionRecorder.create(folder, open_func=racing_open)
            recorder.close()

            self.assertEqual(attempts, ["session_001.csv", "session_002.csv"])
            self.assertEqual(recorder.path.name, "session_002.csv")

    def test_writes_stable_header_values_and_missing_face_row(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = CsvSessionRecorder.create(Path(directory))
            visible = FeatureFrame(
                timestamp_s=1.23456,
                frame_index=7,
                face_visible=True,
                head_yaw_deg=8.23456,
                blink=0.12555,
                video_frame_index=3,
                action_mode="tracking",
                active_action_ids="blink|brow_raise",
                active_action_strengths="0.8000|0.6000",
            )
            missing = FeatureFrame(2.5, 8, False)

            recorder.write(visible)
            recorder.write(missing)
            output_path = recorder.path
            recorder.close()

            with output_path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)

            self.assertEqual(tuple(reader.fieldnames), CSV_FIELDS)
            self.assertEqual(rows[0]["timestamp_s"], "1.235")
            self.assertEqual(rows[0]["face_visible"], "true")
            self.assertEqual(rows[0]["confidence"], "")
            self.assertEqual(rows[0]["head_yaw_deg"], "8.2346")
            self.assertEqual(rows[0]["blink"], "0.1255")
            self.assertEqual(rows[0]["video_frame_index"], "3")
            self.assertEqual(rows[0]["action_mode"], "tracking")
            self.assertEqual(rows[0]["active_action_ids"], "blink|brow_raise")
            self.assertEqual(rows[1]["face_visible"], "false")
            self.assertEqual(rows[1]["head_yaw_deg"], "")
            self.assertEqual(recorder.row_count, 2)
            self.assertTrue(recorder.closed)

    def test_empty_error_session_can_be_removed_but_data_session_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            empty = CsvSessionRecorder.create(folder)
            empty_path = empty.path
            empty.close(remove_if_empty=True)
            self.assertFalse(empty_path.exists())

            populated = CsvSessionRecorder.create(folder)
            populated.write(FeatureFrame(0.0, 0, False))
            populated_path = populated.path
            populated.close(remove_if_empty=True)
            self.assertTrue(populated_path.exists())

    def test_close_is_idempotent_and_write_after_close_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = CsvSessionRecorder.create(Path(directory))
            recorder.close()
            recorder.close()

            with self.assertRaisesRegex(RecordingError, "closed"):
                recorder.write(FeatureFrame(0.0, 0, False))

    def test_invalid_directory_has_readable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"

            with self.assertRaisesRegex(RecordingError, "directory"):
                CsvSessionRecorder.create(missing)


if __name__ == "__main__":
    unittest.main()
class FailedFlushTests(unittest.TestCase):
    def test_flush_failure_still_attempts_close_for_both_csv_writers(self):
        from src.session_recorder import CsvSessionRecorder, RecordingError
        from src.action_event_recorder import ActionEventRecorder
        from pathlib import Path
        for recorder_type in (CsvSessionRecorder, ActionEventRecorder):
            handle = Mock()
            recorder = recorder_type(Path("unused.csv"), handle)
            handle.flush.side_effect = OSError("disk full")
            with self.assertRaises(RecordingError): recorder.close()
            handle.close.assert_called_once()
