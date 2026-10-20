import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch

from test_benchmark import FakeAdapter, config, import_zip, make_zip, wav_bytes
from benchmark.datasets import write_json
from benchmark.runner import Runner
from server import make_server


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        entries = {f'{sid}.{ext}': data for sid in ('EN001', 'EN002')
                   for ext, data in [('wav', wav_bytes()), ('txt', 'hello class')]}
        dataset = import_zip(make_zip(entries), self.root / 'datasets', 'pilot', 'en')
        self.runner = Runner(self.root, {'faster-whisper': FakeAdapter})
        run = self.runner.start(dataset['id'], [config('done'), config('remaining')])
        self.runner.thread.join(10)
        self.run = self.runner.get(run['id'])
        self.run.update(status='interrupted', completed_tasks=3)
        self.run.pop('finished_at', None)
        self.run['models'][1].update(status='interrupted')
        self.run['models'][1]['samples'].pop()
        self.path = self.root / 'runs' / run['id'] / 'run.json'
        write_json(self.path, self.run)
        self.before = self.path.read_bytes()

    def test_resume_preserves_rows_skips_finished_model_and_backs_up(self):
        calls = []
        class RecordingAdapter(FakeAdapter):
            def load(self):
                calls.append(('load', self.config['label']))
            def transcribe(self, audio, language):
                calls.append(('sample', audio.stem))
                return super().transcribe(audio, language)
        self.runner.adapters = {'faster-whisper': RecordingAdapter}
        self.runner.resume(self.run['id'])
        self.runner.thread.join(10)
        final = self.runner.get(self.run['id'])
        self.assertEqual(final['status'], 'completed')
        self.assertEqual(final['completed_tasks'], 4)
        self.assertEqual(calls, [('load', 'remaining'), ('sample', 'EN002')])
        self.assertEqual(final['models'][0], self.run['models'][0])
        self.assertEqual(final['models'][1]['samples'][0], self.run['models'][1]['samples'][0])
        self.assertEqual(final['options'], self.run['options'])
        self.assertEqual(final['environment'], self.run['environment'])
        backups = list(self.path.parent.glob('run.before-resume-*.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), self.before)

    def test_changed_dataset_rejected_without_modifying_run(self):
        folder = self.root / 'datasets' / self.run['dataset']['id']
        (folder / 'transcripts/EN001.txt').write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.runner.resume(self.run['id'])
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_backup_failure_leaves_original_untouched(self):
        original_open = Path.open
        def blocked_backup(path, mode='r', *args, **kwargs):
            if mode == 'xb':
                raise PermissionError('backup blocked')
            return original_open(path, mode, *args, **kwargs)
        with patch('pathlib.Path.open', blocked_backup):
            with self.assertRaises(PermissionError):
                self.runner.resume(self.run['id'])
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_existing_error_row_is_kept(self):
        row = {'id': 'EN001', 'status': 'error', 'error': 'original error', 'duration_s': 1}
        self.run['models'][1]['samples'][0] = row
        write_json(self.path, self.run)
        self.runner.resume(self.run['id'])
        self.runner.thread.join(10)
        result = self.runner.get(self.run['id'])
        self.assertEqual(result['status'], 'completed_with_errors')
        self.assertEqual(result['models'][1]['samples'][0], row)
        self.assertEqual(result['completed_tasks'], 4)

    def test_http_resume_after_restart_preserves_progress(self):
        self.run['status'] = 'running'
        write_json(self.path, self.run)
        server = make_server(self.root, 0)
        server.runner.adapters = {'faster-whisper': FakeAdapter}
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}/api/resume'
        body = json.dumps({'run_id': self.run['id']}).encode()
        try:
            bad = urllib.request.Request(url, data=body, headers={
                'Content-Type': 'application/json', 'Origin': 'http://other.test'})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(bad, timeout=5)
            self.assertEqual(error.exception.code, 400)
            request = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=5) as response:
                resumed = json.load(response)
            self.assertEqual(resumed['id'], self.run['id'])
            self.assertEqual(resumed['completed_tasks'], 3)
            server.runner.thread.join(10)
            final = server.runner.get(self.run['id'])
            self.assertEqual(final['completed_tasks'], 4)
            self.assertEqual(final['models'][0], self.run['models'][0])
        finally:
            if server.runner.thread:
                server.runner.thread.join(10)
            server.shutdown()
            server.server_close()
            thread.join(5)

    def test_completed_run_cannot_resume(self):
        self.run['status'] = 'completed'
        write_json(self.path, self.run)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'interrupted'):
            self.runner.resume(self.run['id'])
        self.assertEqual(self.path.read_bytes(), before)

    def test_second_resume_is_rejected_while_active(self):
        entered, release = threading.Event(), threading.Event()
        class SlowAdapter(FakeAdapter):
            def load(self):
                entered.set()
                release.wait(5)
        self.runner.adapters = {'faster-whisper': SlowAdapter}
        try:
            self.runner.resume(self.run['id'])
            self.assertTrue(entered.wait(5))
            with self.assertRaisesRegex(ValueError, 'active'):
                self.runner.resume(self.run['id'])
        finally:
            release.set()
            self.runner.thread.join(10)


if __name__ == '__main__':
    unittest.main()
