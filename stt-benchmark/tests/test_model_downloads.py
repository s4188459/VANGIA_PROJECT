import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.extra_adapters import local_snapshot


class ModelDownloadTests(unittest.TestCase):
    def test_mms_fetches_weights_and_only_requested_language(self):
        download = Mock(return_value='snapshot')
        with patch.dict(sys.modules, huggingface_hub=SimpleNamespace(snapshot_download=download)):
            local_snapshot(dict(model='facebook/mms-1b-all', backend='transformers-ctc',
                                languages=['en'], allow_download=True))
        patterns = download.call_args.kwargs['allow_patterns']
        self.assertIn('model.safetensors', patterns)
        self.assertIn('adapter.eng.safetensors', patterns)
        self.assertNotIn('adapter.vie.safetensors', patterns)
        self.assertNotIn('*.safetensors', patterns)

    def test_windows_privilege_failure_retries_regular_file_download(self):
        error = OSError('symlink privilege missing')
        error.winerror = 1314
        download = Mock(side_effect=[error, 'regular-files'])
        with patch.dict(sys.modules, huggingface_hub=SimpleNamespace(snapshot_download=download)):
            result = local_snapshot(dict(model='Qwen/Qwen3-ASR-1.7B', backend='qwen-asr',
                                         allow_download=True))
        self.assertEqual(result, 'regular-files')
        self.assertIn('local_dir', download.call_args.kwargs)
        self.assertEqual(download.call_count, 2)

    def test_unrelated_io_error_is_not_retried(self):
        download = Mock(side_effect=OSError('disk full'))
        with patch.dict(sys.modules, huggingface_hub=SimpleNamespace(snapshot_download=download)):
            with self.assertRaisesRegex(OSError, 'disk full'):
                local_snapshot(dict(model='Qwen/Qwen3-ASR-1.7B', backend='qwen-asr',
                                    allow_download=True))
        self.assertEqual(download.call_count, 1)
