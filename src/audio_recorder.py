from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import threading
import wave

import numpy as np


class AudioSource(str, Enum):
    SYSTEM_AUDIO = "system_audio"
    MICROPHONE = "microphone"


@dataclass(frozen=True)
class AudioChunk:
    source: AudioSource
    segment_index: int
    start_s: float
    end_s: float
    sample_rate: int
    channels: int
    samples: np.ndarray


def pcm16_to_mono(data: bytes, channels: int) -> np.ndarray:
    values = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    if channels > 1:
        usable = len(values) - (len(values) % channels)
        values = values[:usable].reshape(-1, channels).mean(axis=1)
    return values / 32768.0


def wait_if_paused(pause_event, stop_event, interval_s: float = 0.02) -> bool:
    if not pause_event.is_set():
        return False
    stop_event.wait(interval_s)
    return True


class AudioRecorder:
    def __init__(self, source, device, wav_path: Path, chunk_callback, status_callback,
                 clock, *, stream_factory, frames_per_buffer: int = 1024) -> None:
        self.source, self.device, self.wav_path = source, device, Path(wav_path)
        self._chunk_callback, self._status_callback, self._clock = chunk_callback, status_callback, clock
        self._stream_factory, self._fpb = stream_factory, frames_per_buffer
        self._stop = threading.Event(); self._paused = threading.Event(); self._thread = None; self._stream = None

    def start(self) -> None:
        self._stream = self._stream_factory(self.device, self._fpb)
        self._thread = threading.Thread(target=self._run, name=f"audio-{self.source.value}", daemon=True); self._thread.start()

    def _run(self) -> None:
        segment = 0
        try:
            with wave.open(str(self.wav_path), "wb") as output:
                output.setnchannels(self.device.channels); output.setsampwidth(2); output.setframerate(int(self.device.sample_rate))
                while not self._stop.is_set():
                    if wait_if_paused(self._paused, self._stop): continue
                    start = self._clock.elapsed_s(); data = self._stream.read(self._fpb, exception_on_overflow=False); end = self._clock.elapsed_s()
                    output.writeframes(data)
                    samples = pcm16_to_mono(data, self.device.channels)
                    self._chunk_callback(AudioChunk(self.source, segment, start, end, int(self.device.sample_rate), self.device.channels, samples)); segment += 1
        except Exception as exc: self._status_callback(self.source.value, "error", str(exc))

    def pause(self, timestamp_s: float) -> None: self._paused.set()
    def resume(self, timestamp_s: float) -> None: self._paused.clear()
    def stop(self, timeout_s: float = 2.0) -> None:
        self._stop.set()
        if self._stream:
            try: self._stream.stop_stream()
            except Exception: pass
            try: self._stream.close()
            except Exception: pass
        if self._thread and self._thread is not threading.current_thread(): self._thread.join(timeout_s)


class AudioCaptureWorker:
    def __init__(self, source, device, chunk_callback, status_callback, clock, *, stream_factory,
                 frames_per_buffer: int = 1024) -> None:
        self.source, self.device = source, device
        self._chunk_callback, self._status_callback, self._clock = chunk_callback, status_callback, clock
        self._stream_factory, self._fpb = stream_factory, frames_per_buffer
        self._stop = threading.Event(); self._paused = threading.Event(); self._thread = None; self._stream = None

    def start(self) -> None:
        self._stream = self._stream_factory(self.device, self._fpb)
        self._thread = threading.Thread(target=self._run, name=f"audio-{self.source.value}", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        segment = 0
        try:
            while not self._stop.is_set():
                if wait_if_paused(self._paused, self._stop): continue
                start = self._clock.elapsed_s()
                data = self._stream.read(self._fpb, exception_on_overflow=False)
                end = self._clock.elapsed_s()
                samples = pcm16_to_mono(data, self.device.channels)
                self._chunk_callback(AudioChunk(self.source, segment, start, end, int(self.device.sample_rate),
                                                self.device.channels, samples))
                segment += 1
        except Exception as exc:
            self._status_callback(self.source.value, "error", str(exc))

    def pause(self, _timestamp_s: float) -> None: self._paused.set()
    def resume(self, _timestamp_s: float) -> None: self._paused.clear()
    def stop(self, timeout_s: float = 2.0) -> None:
        self._stop.set()
        if self._stream:
            try: self._stream.stop_stream()
            except Exception: pass
            try: self._stream.close()
            except Exception: pass
        if self._thread and self._thread is not threading.current_thread(): self._thread.join(timeout_s)
