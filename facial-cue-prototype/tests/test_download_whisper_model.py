import unittest
from pathlib import Path

from scripts.download_whisper_model import model_output_path


class WhisperModelSetupTests(unittest.TestCase):
    def test_model_output_path_is_deterministic(self):
        self.assertEqual(model_output_path("medium.en"), Path("models/faster-whisper-medium-en"))
        self.assertEqual(model_output_path("small.en"), Path("models/faster-whisper-small-en"))

    def test_rejects_unsupported_model(self):
        with self.assertRaises(ValueError): model_output_path("unknown")


if __name__ == "__main__": unittest.main()
