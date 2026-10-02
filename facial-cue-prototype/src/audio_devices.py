from __future__ import annotations

from dataclasses import dataclass

from .audio_recorder import AudioSource


class AudioDeviceUnavailable(RuntimeError): pass


@dataclass(frozen=True)
class AudioDeviceInfo:
    index: int
    name: str
    sample_rate: int
    channels: int
    loopback: bool = False


def _device(info, loopback: bool) -> AudioDeviceInfo:
    channels = int(info.get("maxInputChannels", 0))
    if channels < 1: raise AudioDeviceUnavailable(f"Audio device has no input channels: {info.get('name', 'unknown')}")
    return AudioDeviceInfo(int(info["index"]), str(info["name"]), int(info["defaultSampleRate"]), channels, loopback)


def discover_default_devices(pyaudio_factory=None) -> dict[AudioSource, AudioDeviceInfo]:
    if pyaudio_factory is None:
        try: import pyaudiowpatch as pyaudio
        except ImportError as exc: raise AudioDeviceUnavailable("PyAudioWPatch is not installed") from exc
        pyaudio_factory = pyaudio.PyAudio
    audio = pyaudio_factory()
    try:
        devices = {}
        try: devices[AudioSource.SYSTEM_AUDIO] = _device(audio.get_default_wasapi_loopback(), True)
        except Exception: pass
        try: devices[AudioSource.MICROPHONE] = _device(audio.get_default_input_device_info(), False)
        except Exception: pass
        return devices
    finally: audio.terminate()


def open_input_stream(device: AudioDeviceInfo, frames_per_buffer: int):
    import pyaudiowpatch as pyaudio
    owner = pyaudio.PyAudio()
    try:
        stream = owner.open(format=pyaudio.paInt16, channels=device.channels,
                            rate=device.sample_rate, input=True,
                            input_device_index=device.index,
                            frames_per_buffer=frames_per_buffer)
    except Exception:
        owner.terminate()
        raise
    class OwnedStream:
        def read(self, *args, **kwargs): return stream.read(*args, **kwargs)
        def get_read_available(self): return stream.get_read_available()
        def stop_stream(self): return stream.stop_stream()
        def close(self):
            try: stream.close()
            finally: owner.terminate()
    return OwnedStream()
