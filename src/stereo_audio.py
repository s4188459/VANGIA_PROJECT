from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
from threading import Lock
import wave

import numpy as np
from scipy.signal import resample_poly

from .audio_recorder import AudioChunk, AudioSource


@dataclass(frozen=True)
class AudioInterval:
    session_start_s: float
    session_end_s: float
    wav_start_frame: int
    wav_end_frame: int


@dataclass(frozen=True)
class StereoAudioStats:
    sample_rate: int
    written_frames: int
    intervals: tuple[AudioInterval, ...]
    source_failures: tuple[str, ...] = ()


class StereoAudioWriter:
    def __init__(self, path: Path, *, sample_rate: int = 48000, flush_delay_s: float = 0.5,
                 interval_callback=lambda _interval: None, level_callback=lambda _source, _samples: None,
                 status_callback=lambda _component, _state, _message: None) -> None:
        self.path = Path(path); self.sample_rate = int(sample_rate)
        self._delay_frames = max(0, round(flush_delay_s * self.sample_rate))
        self._interval_callback = interval_callback; self._level_callback = level_callback
        self._status_callback = status_callback; self._lock = Lock(); self._wave = None
        self._active = False; self._session_start = 0.0; self._wav_start = 0
        self._buffer_start = 0; self._channels = [np.empty(0, np.float32), np.empty(0, np.float32)]
        self._max_frame = 0; self._written = 0; self._intervals: list[AudioInterval] = []

    def start(self, session_start_s: float = 0.0) -> None:
        self._wave = wave.open(str(self.path), "wb")
        self._wave.setnchannels(2); self._wave.setsampwidth(2); self._wave.setframerate(self.sample_rate)
        self._active = True; self._session_start = float(session_start_s); self._wav_start = self._written

    def _resample(self, chunk: AudioChunk) -> np.ndarray:
        values = np.asarray(chunk.samples, np.float32)
        if chunk.sample_rate == self.sample_rate: return values
        divisor = math.gcd(chunk.sample_rate, self.sample_rate)
        return resample_poly(values, self.sample_rate // divisor, chunk.sample_rate // divisor).astype(np.float32)

    def submit(self, chunk: AudioChunk) -> bool:
        with self._lock:
            if not self._active or self._wave is None: return False
            values = self._resample(chunk); self._level_callback(chunk.source, values)
            start = round((chunk.start_s - self._session_start) * self.sample_rate)
            if start < self._buffer_start: return False
            relative = start - self._buffer_start; end = relative + len(values)
            for index in range(2):
                if len(self._channels[index]) < end:
                    self._channels[index] = np.pad(self._channels[index], (0, end - len(self._channels[index])))
            channel = 0 if chunk.source is AudioSource.MICROPHONE else 1
            self._channels[channel][relative:end] = values
            self._max_frame = max(self._max_frame, self._buffer_start + end)
            self._flush_to(max(self._buffer_start, self._max_frame - self._delay_frames))
            return True

    def _flush_to(self, absolute_frame: int) -> None:
        count = max(0, absolute_frame - self._buffer_start)
        if count <= 0: return
        for index in range(2):
            if len(self._channels[index]) < count:
                self._channels[index] = np.pad(self._channels[index], (0, count - len(self._channels[index])))
        stereo = np.column_stack((self._channels[0][:count], self._channels[1][:count]))
        pcm = np.clip(stereo, -1.0, 1.0)
        self._wave.writeframes(np.rint(pcm * 32767.0).astype(np.int16).tobytes())
        self._channels = [values[count:] for values in self._channels]
        self._buffer_start += count; self._written += count

    def pause(self, timestamp_s: float) -> None:
        with self._lock:
            if not self._active: return
            self._flush_to(self._max_frame)
            interval = AudioInterval(self._session_start, float(timestamp_s), self._wav_start, self._written)
            self._intervals.append(interval); self._interval_callback(asdict(interval)); self._active = False

    def resume(self, timestamp_s: float) -> None:
        with self._lock:
            self._active = True; self._session_start = float(timestamp_s); self._wav_start = self._written
            self._buffer_start = 0; self._max_frame = 0
            self._channels = [np.empty(0, np.float32), np.empty(0, np.float32)]

    def stop(self, timestamp_s: float | None = None) -> StereoAudioStats:
        with self._lock:
            try:
                if self._wave is not None and self._active:
                    self._flush_to(self._max_frame)
                    end = float(timestamp_s) if timestamp_s is not None else self._session_start + (self._written - self._wav_start) / self.sample_rate
                    interval = AudioInterval(self._session_start, end, self._wav_start, self._written)
                    self._intervals.append(interval); self._interval_callback(asdict(interval))
            finally:
                self._active = False
                output = self._wave
                self._wave = None
                if output is not None: output.close()
            return StereoAudioStats(self.sample_rate, self._written, tuple(self._intervals))
