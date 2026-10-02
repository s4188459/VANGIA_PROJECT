import unittest

import numpy as np

from src.audio_quality import AudioLevelState, analyze_level, prepare_inference_audio


class AudioQualityTests(unittest.TestCase):
    def test_gain_does_not_flatten_speech_peaks(self):
        source = np.full(16000, .002, np.float32)
        source[::1000] = .4
        prepared, gain = prepare_inference_audio(source)
        np.testing.assert_allclose(prepared, source * gain, atol=1e-7)
        self.assertLessEqual(float(np.max(np.abs(prepared))), .980001)

    def test_classifies_no_signal_quiet_good_and_clipping(self):
        self.assertIs(analyze_level(np.zeros(100, np.float32)).state, AudioLevelState.NO_SIGNAL)
        self.assertIs(analyze_level(np.full(100, .003, np.float32)).state, AudioLevelState.TOO_QUIET)
        self.assertIs(analyze_level(np.full(100, .1, np.float32)).state, AudioLevelState.GOOD)
        self.assertIs(analyze_level(np.array([0, 1.0], np.float32)).state, AudioLevelState.CLIPPING)

    def test_preparation_caps_gain_limits_peak_and_does_not_mutate_input(self):
        source = np.full(1600, .002, np.float32)
        original = source.copy()
        prepared, gain = prepare_inference_audio(source, max_gain=4.0)
        self.assertEqual(gain, 4.0)
        self.assertLessEqual(float(np.max(np.abs(prepared))), .98)
        np.testing.assert_array_equal(source, original)

    def test_silence_is_not_amplified(self):
        prepared, gain = prepare_inference_audio(np.zeros(20, np.float32))
        np.testing.assert_array_equal(prepared, np.zeros(20, np.float32))
        self.assertEqual(gain, 1.0)


if __name__ == "__main__": unittest.main()
