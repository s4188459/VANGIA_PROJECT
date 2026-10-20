import json
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from src.audio_recorder import AudioChunk, AudioSource
from src.qwen_transcription import QwenEnglishTranscriber


class QwenTests(unittest.TestCase):
    def make_decoder(self, response):
        child = MagicMock()
        child.stdout.readline.side_effect = [json.dumps({'ready': True}) + '\n', json.dumps(response) + '\n']
        with patch('src.qwen_transcription.subprocess.Popen', return_value=child), \
             patch('src.qwen_transcription.Path.is_file', return_value=True):
            return QwenEnglishTranscriber('model'), child

    def chunk(self):
        return AudioChunk(AudioSource.MICROPHONE, 0, 10, 12, 48000, 1,
                          np.ones(96000, dtype=np.float32) * .1)

    @patch('faster_whisper.vad.get_speech_timestamps', return_value=[{'start': 0, 'end': 32000}])
    def test_preserves_chunk_time_and_resamples(self, _vad):
        decoder, child = self.make_decoder({'text': 'Hello teacher.'})
        row, = decoder.transcribe(self.chunk())
        self.assertEqual((row.start_s, row.end_s, row.text, row.speaker),
                         (10, 12, 'Hello teacher.', 'You'))
        import base64
        request = json.loads(child.stdin.write.call_args.args[0])
        self.assertEqual(len(base64.b64decode(request['audio'])), 32000 * 4)
        self.assertFalse(decoder.configuration['word_timestamps'])
        decoder.close()

    @patch('faster_whisper.vad.get_speech_timestamps', return_value=[])
    def test_silence_does_not_reach_model(self, _vad):
        decoder, child = self.make_decoder({'text': 'hallucination'})
        self.assertEqual(decoder.transcribe(self.chunk()), ())
        child.stdin.write.assert_not_called()
        decoder.close()

    @patch('faster_whisper.vad.get_speech_timestamps', return_value=[{'start': 0, 'end': 32000}])
    def test_worker_errors_are_visible_and_cancel_rejects_work(self, _vad):
        decoder, child = self.make_decoder({'error': 'load failed'})
        with self.assertRaisesRegex(RuntimeError, 'load failed'):
            decoder.transcribe(self.chunk())
        decoder.cancel()
        with self.assertRaisesRegex(RuntimeError, 'cancelled'):
            decoder.transcribe(self.chunk())
        decoder.close()
