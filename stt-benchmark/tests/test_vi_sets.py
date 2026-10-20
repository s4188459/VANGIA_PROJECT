import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.catalog import catalog
from benchmark.adapters import validate_config, FasterWhisperAdapter
from benchmark.extra_adapters import FunASRMLTAdapter
from test_benchmark import wav_bytes


class VietnameseSetsTests(unittest.TestCase):
    def test_cached_whisper_id_can_load_without_download_permission(self):
        calls = []
        def constructor(target, **kwargs):
            calls.append((target, kwargs))
            return object()
        cfg = validate_config({'label':'small', 'model':'small', 'allow_download':False})
        with patch.dict(sys.modules, {'faster_whisper':SimpleNamespace(WhisperModel=constructor)}):
            adapter = FasterWhisperAdapter(cfg)
            adapter.load()
        self.assertIsNotNone(adapter.model)
        self.assertEqual(calls[0][0], 'small')
        self.assertTrue(calls[0][1]['local_files_only'])

    def test_mlt_transcribes_with_vietnamese_prompt_and_preserves_english_terms(self):
        calls = []
        class Model:
            def generate(self, **kwargs):
                calls.append(kwargs)
                return [{'text': 'Giảm learning rate'}]
        adapter = FunASRMLTAdapter({})
        adapter.model = Model()
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / 'sample.wav'
            audio.write_bytes(wav_bytes())
            result = adapter.transcribe(audio, 'vi')
        self.assertEqual(result['text'], 'Giảm learning rate')
        self.assertEqual(calls[0]['language'], '越南语')
        self.assertFalse(calls[0]['itn'])
        self.assertEqual(calls[0]['llm_kwargs'], {'do_sample': False})
        self.assertEqual(len(calls[0]['input']), 16000)

    def test_exact_video_and_live_sets(self):
        rows = catalog()
        actual = lambda group: {r['model'] for r in rows if group in r.get('sets', [])}
        self.assertEqual(actual('vi-video'), {'large-v3', 'large-v2', 'Qwen/Qwen3-ASR-1.7B',
                                            'Qwen/Qwen3-ASR-0.6B', 'vinai/PhoWhisper-large'})
        self.assertEqual(actual('vi-live'), {'small', 'medium', 'Qwen/Qwen3-ASR-0.6B',
                                           'vinai/PhoWhisper-small', 'FunAudioLLM/Fun-ASR-MLT-Nano-2512'})
        for row in rows:
            if row.get('sets'):
                self.assertIn('vi', row['languages'])

    def test_fun_asr_configuration(self):
        value = dict(label='MLT', model='FunAudioLLM/Fun-ASR-MLT-Nano-2512',
                     backend='fun-asr-mlt', compute_type='float32', beam_size=1, vad_filter=False)
        self.assertEqual(validate_config(value)['backend'], 'fun-asr-mlt')
        with self.assertRaises(ValueError):
            validate_config({**value, 'compute_type': 'int8'})


if __name__ == '__main__':
    unittest.main()
