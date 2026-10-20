import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.experiments import realtime_replay, app_modules
from benchmark.replay import validate_options
from benchmark.runner import aggregate, export_csv
from benchmark.runner import Runner, export_summary_csv
from test_benchmark import import_zip, make_zip, wav_bytes, FakeAdapter
from benchmark.datasets import write_json


class ExperimentTests(unittest.TestCase):
    def test_offline_pilot_export_and_resume_preserve_saved_sample(self):
        import json
        class Adapter(FakeAdapter):
            def __init__(self, config, mode): super().__init__(config)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entries = {f'{sid}.{ext}': data for sid in ('EN001','EN002','EN003')
                       for ext,data in [('wav',wav_bytes()),('txt','hello class')]}
            dataset = import_zip(make_zip(entries), root/'datasets', 'pilot', 'en')
            runner = Runner(root)
            with patch('benchmark.experiments.ExperimentAdapter', Adapter):
                run = runner.start(dataset['id'], [], {'mode':'experiment3','sample_limit':2})
                runner.thread.join(10)
                saved = runner.get(run['id'])
                self.assertEqual(saved['status'], 'completed')
                self.assertEqual(saved['total_tasks'], 2)
                self.assertEqual(saved['models'][0]['config']['model'], 'large-v3')
                self.assertIn(b'wall_s', export_csv(saved))
                self.assertIn(b'wall_s_p95', export_summary_csv(saved))
                first = saved['models'][0]['samples'][0].copy()
                saved['models'][0]['samples'].pop()
                saved['status'] = 'interrupted'
                path = root/'runs'/run['id']/'run.json'
                write_json(path, saved)
                original = path.read_bytes()
                runner.resume(run['id'])
                runner.thread.join(10)
                final = runner.get(run['id'])
                self.assertEqual(final['status'], 'completed')
                self.assertEqual(final['models'][0]['samples'][0], first)
                self.assertEqual(len(final['models'][0]['load_sessions']), 2)
                self.assertEqual(next(path.parent.glob('run.before-resume-*.json')).read_bytes(), original)

    def test_experiments_reject_non_english(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ds = import_zip(make_zip({'EN001.wav':wav_bytes(), 'EN001.txt':'hello'}), root/'datasets', 'test', 'vi')
            with self.assertRaisesRegex(ValueError, 'English'):
                Runner(root).start(ds['id'], [], {'mode':'experiment2'})

    def test_protocols_and_limit_validation(self):
        self.assertEqual(validate_options({'mode':'experiment2'})['protocol'], 'app-qwen-realtime-packets-v1')
        self.assertEqual(validate_options({'mode':'experiment3'})['protocol'], 'app-whisper-offline-v1')
        with self.assertRaises(ValueError):
            validate_options({'sample_limit':-1})

    def test_causal_replay_drains_eof_and_scores_complete_text(self):
        import numpy as np
        t, a = app_modules()
        class Decoder:
            def transcribe(self, chunk):
                return (t.TranscriptSegment(1, chunk.start_s, chunk.end_s, chunk.source, 'You', 'hello'),)
            def speech_boundary(self, *args, **kwargs): return True
            def cancel(self): pass
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'test.wav'
            with wave.open(str(path), 'wb') as wav:
                wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                wav.writeframes(np.ones(4800, dtype='<i2').tobytes())
            with patch('faster_whisper.vad.get_speech_timestamps', return_value=[{'start':0,'end':4800}]):
                result = realtime_replay(Decoder(), path)
            self.assertEqual(result['text'], 'hello')
            self.assertGreaterEqual(result['chunks'][0]['emitted_at_s'], .3)
            self.assertGreaterEqual(result['wall_s'], .3)
            self.assertIsNone(result['replay_metrics']['word_latency_s'])
            with self.assertRaises(InterruptedError):
                realtime_replay(Decoder(), path, cancelled=lambda: True)

    def test_timing_summary_distinguishes_compute_and_wall(self):
        rows = [dict(status='ok', reference_words=1, errors=0, duration_s=10,
                     elapsed_s=2, wall_s=12, replay_metrics={'finalization_from_eof_s':2})]
        summary = aggregate(rows)
        self.assertEqual(summary['rtf'], .2)
        self.assertEqual(summary['wall_s_p95'], 12)
        self.assertEqual(summary['finalization_from_eof_s_p95'], 2)
