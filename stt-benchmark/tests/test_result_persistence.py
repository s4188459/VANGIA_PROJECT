import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.datasets import write_json


class ResultPersistenceTests(unittest.TestCase):
    def test_windows_reader_lock_does_not_lose_results(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'run.json'
            write_json(path, {'completed': 70})
            replace = Path.replace
            calls = []

            def briefly_locked(source, destination):
                calls.append(1)
                if len(calls) < 3:
                    self.assertEqual(json.loads(path.read_text()), {'completed': 70})
                    error = PermissionError('reader temporarily holds the destination')
                    error.winerror = 5
                    raise error
                return replace(source, destination)

            with patch.object(Path, 'replace', briefly_locked), patch('benchmark.datasets.time.sleep'):
                write_json(path, {'completed': 71})
            self.assertEqual(json.loads(path.read_text()), {'completed': 71})
            self.assertEqual(len(calls), 3)

    def test_persistent_denial_preserves_old_and_pending_results(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'run.json'
            write_json(path, {'completed': 70})
            error = PermissionError('persistent access denial')
            error.winerror = 5
            with patch.object(Path, 'replace', side_effect=error) as replace, patch('benchmark.datasets.time.sleep'):
                with self.assertRaises(PermissionError):
                    write_json(path, {'completed': 71})
            self.assertEqual(replace.call_count, 51)
            self.assertEqual(json.loads(path.read_text()), {'completed': 70})
            self.assertEqual(json.loads(path.with_suffix('.tmp').read_text()), {'completed': 71})
