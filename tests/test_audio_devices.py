import unittest
from unittest.mock import patch, Mock

from src.audio_devices import AudioDeviceInfo, discover_default_devices, open_input_stream
from src.audio_recorder import AudioSource


class FakePyAudio:
    def get_default_wasapi_loopback(self):
        return {"index": 4, "name": "Speakers [Loopback]", "defaultSampleRate": 48000, "maxInputChannels": 2}

    def get_default_input_device_info(self):
        return {"index": 2, "name": "Mic", "defaultSampleRate": 44100, "maxInputChannels": 1}

    def terminate(self): pass


class AudioDeviceTests(unittest.TestCase):
    def test_failed_stream_open_terminates_pyaudio_owner(self):
        owner = Mock()
        owner.open.side_effect = OSError("device disconnected")
        with patch("pyaudiowpatch.PyAudio", return_value=owner):
            with self.assertRaisesRegex(OSError, "disconnected"):
                open_input_stream(AudioDeviceInfo(0, "mic", 48000, 1, False), 1024)
        owner.terminate.assert_called_once()

    def test_discovers_separate_default_devices(self):
        devices = discover_default_devices(lambda: FakePyAudio())
        self.assertEqual(devices[AudioSource.SYSTEM_AUDIO], AudioDeviceInfo(4, "Speakers [Loopback]", 48000, 2, True))
        self.assertEqual(devices[AudioSource.MICROPHONE].name, "Mic")


if __name__ == "__main__": unittest.main()
