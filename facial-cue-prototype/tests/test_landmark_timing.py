from contextlib import ExitStack
import csv
import json
from pathlib import Path
import tempfile
import unittest

from src.capture_types import CaptureRegion
from src.dataset_session import DatasetSession
from src.overlay_data import LatestOverlayFrame, OverlayFrame
from src.session_clock import SessionClock
from src.session_types import SessionOptions
from src.landmark_timing import LandmarkTimingRecorder


class LandmarkTimingTests(unittest.TestCase):
    def test_storage_failure_marks_session_incomplete_and_still_closes_features(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as cleanup:
            session = self.make_session(folder)
            cleanup.callback(session.close)
            session.landmark_timing.begin(0)
            path = session.directory / 'landmark-timing.csv'
            path.write_text('existing data')
            from src.session_recorder import RecordingError
            with self.assertRaises(RecordingError):
                session.close()
            metadata = json.loads(session.session_path.read_text())
            self.assertEqual(metadata['status'], 'incomplete')
            self.assertFalse(metadata['landmark_timing']['finalized'])
            self.assertEqual(path.read_text(), 'existing data')
            # On Windows, rename fails if the CSV writer is still open.
            session.raw_path.rename(session.directory / 'closed-features.csv')

    def test_capacity_is_bounded_and_late_callbacks_cannot_change_output(self):
        with tempfile.TemporaryDirectory() as folder:
            clock = SessionClock(lambda: 5)
            clock.start()
            recorder = LandmarkTimingRecorder(clock, max_frames=1)
            timing = recorder.begin(0)
            self.assertIsNone(recorder.begin(1))
            summary = recorder.close(Path(folder))
            path = Path(folder) / 'landmark-timing.csv'
            before = path.read_bytes()
            timing.mark('render_end_s')
            timing.finish('rendered')
            self.assertEqual(recorder.close(Path(folder)), summary)
            self.assertEqual(summary['omitted_frames'], 1)
            self.assertEqual(path.read_bytes(), before)

    def make_session(self, folder):
        self.now = 10.0
        clock = SessionClock(lambda: self.now)
        clock.start()
        return DatasetSession.create(Path(folder), SessionOptions(consent_confirmed=True),
                                     CaptureRegion(0, 0, 10, 10), clock)

    def test_replaced_and_unrendered_frames_survive_session_close(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as cleanup:
            session = self.make_session(folder)
            cleanup.callback(session.close)
            self.assertTrue(hasattr(session, 'landmark_timing'), 'Session must own timing finalization')
            first = session.landmark_timing.begin(4)
            self.now = 10.1
            first.mark('capture_end_s')
            pending = LatestOverlayFrame()
            pending.publish(OverlayFrame((), False, 0, timing=first))
            second = session.landmark_timing.begin(5)
            pending.publish(OverlayFrame((), False, 0, timing=second))
            session.close()
            with (session.directory / 'landmark-timing.csv').open(newline='') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([r['frame_index'] for r in rows], ['4', '5'])
            self.assertEqual([r['outcome'] for r in rows], ['replaced', 'not_rendered_at_close'])
            self.assertAlmostEqual(float(rows[0]['capture_end_s']), .1)
            self.assertEqual(rows[0]['render_end_s'], '')
            metadata = json.loads(session.session_path.read_text())['landmark_timing']
            self.assertEqual(metadata['recorded_frames'], 2)
            self.assertTrue(metadata['finalized'])

    def test_rendered_record_is_not_overwritten_and_invalid_order_is_flagged(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as cleanup:
            session = self.make_session(folder)
            cleanup.callback(session.close)
            self.assertTrue(hasattr(session, 'landmark_timing'))
            timing = session.landmark_timing.begin(0)
            self.now = 11
            timing.mark('ui_consumed_s')
            self.now = 10.5
            timing.mark('render_end_s')
            timing.finish('rendered')
            timing.finish('replaced')
            session.close()
            with (session.directory / 'landmark-timing.csv').open(newline='') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]['outcome'], 'rendered')
            self.assertEqual(rows[0]['order_valid'], 'False')


if __name__ == '__main__':
    unittest.main()
