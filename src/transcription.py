from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
import queue
import threading
import time

import numpy as np
from scipy.signal import resample_poly

from .audio_recorder import AudioChunk, AudioSource
from .audio_quality import prepare_inference_audio


class TranscriptionUnavailable(RuntimeError): pass


UTTERANCE_PAUSE_S = 1.0
ENDPOINT_CHECK_S = 0.1


@dataclass(frozen=True)
class TranscriptSegment:
    segment_id: int
    start_s: float
    end_s: float
    source: AudioSource
    speaker: str
    text: str
    language: str = "en"
    phase: str = "live"
    status: str = "committed"


@dataclass(frozen=True)
class TranscriptionMetrics:
    lag_s: float
    dropped_chunks: int
    source: str = ""
    rtf: float = 0.0
    queued_duration_s: dict[str, float] = field(default_factory=dict)


def speech_has_ended(samples: np.ndarray, sample_rate: int) -> bool:
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    # Endpoint detection needs recent speech context, not the whole utterance.
    samples = samples[-round(sample_rate * (UTTERANCE_PAUSE_S + 1.0)):]
    if sample_rate != 16000:
        divisor = math.gcd(sample_rate, 16000)
        samples = resample_poly(samples, 16000 // divisor, sample_rate // divisor).astype(np.float32)
    audio, _gain = prepare_inference_audio(samples)
    spans = get_speech_timestamps(
        audio, VadOptions(threshold=0.35, min_silence_duration_ms=round(UTTERANCE_PAUSE_S * 1000), speech_pad_ms=0),
    )
    return not spans or len(audio) - spans[-1]["end"] >= round(16000 * UTTERANCE_PAUSE_S)


def pause_grouped_segments(segments):
    words = []
    for segment in segments:
        timed_words = getattr(segment, "words", None)
        if not timed_words:
            if words:
                yield words[0].start, words[-1].end, "".join(w.word for w in words).strip()
                words = []
            if segment.text.strip():
                yield segment.start, segment.end, segment.text.strip()
            continue
        for word in timed_words:
            if not word.word.strip():
                continue
            if words and word.start - words[-1].end >= UTTERANCE_PAUSE_S - 1e-6:
                yield words[0].start, words[-1].end, "".join(w.word for w in words).strip()
                words = []
            words.append(word)
    if words:
        yield words[0].start, words[-1].end, "".join(w.word for w in words).strip()


class LocalEnglishTranscriber:
    def __init__(self, model_path, *, model=None, model_factory=None, beam_size: int = 5,
                 phase: str = "live", cpu_threads: int = 4) -> None:
        if model is None:
            path = Path(model_path)
            if not path.is_dir(): raise TranscriptionUnavailable(f"Missing local Whisper model: {path}")
            if model_factory is None:
                try: from faster_whisper import WhisperModel
                except ImportError as exc: raise TranscriptionUnavailable("faster-whisper is not installed") from exc
                model_factory = WhisperModel
            model = model_factory(
                str(path),
                device="cpu",
                compute_type="int8",
                cpu_threads=cpu_threads,
                num_workers=1,
            )
        self._model = model; self._next_id = 1; self._beam_size = beam_size; self._phase = phase
        self.configuration = {
            "model": Path(model_path).name, "device": "cpu", "compute_type": "int8",
            "cpu_threads": cpu_threads, "num_workers": 1, "beam_size": beam_size,
            "language": "en", "word_timestamps": True, "vad_threshold": .35,
            "utterance_pause_s": UTTERANCE_PAUSE_S,
        }

    def transcribe(self, chunk: AudioChunk) -> tuple[TranscriptSegment, ...]:
        audio = chunk.samples
        if chunk.sample_rate != 16000:
            divisor = math.gcd(chunk.sample_rate, 16000)
            audio = resample_poly(audio, 16000 // divisor, chunk.sample_rate // divisor).astype(np.float32)
        audio, _gain = prepare_inference_audio(audio)
        segments, _info = self._model.transcribe(
            audio, language="en", task="transcribe", vad_filter=True,
            vad_parameters={"threshold": 0.35, "min_silence_duration_ms": round(UTTERANCE_PAUSE_S * 1000)},
            word_timestamps=True,
            beam_size=self._beam_size,
        )
        output = []
        speaker = "Student" if chunk.source is AudioSource.SYSTEM_AUDIO else "You"
        for start, end, value in pause_grouped_segments(segments):
            if not value: continue
            status = "canonical" if self._phase == "final" else "committed"
            output.append(TranscriptSegment(self._next_id, chunk.start_s + start, chunk.start_s + end,
                                            chunk.source, speaker, value, phase=self._phase, status=status))
            self._next_id += 1
        return tuple(output)


@dataclass
class _AudioBuffer:
    source: AudioSource
    segment_index: int
    start_s: float
    end_s: float
    sample_rate: int
    channels: int
    samples: np.ndarray
    processed_until_s: float
    next_boundary_samples: int = 0


class TranscriptionWorker:
    def __init__(self, transcriber, segment_callback, *, window_s: float = 4.0,
                 overlap_s: float = 0.75, queue_size: int = 4096, clock=time.monotonic,
                 metrics_callback=lambda _metrics: None, max_window_s: float | None = None,
                 speech_boundary=None, error_callback=lambda _error: None,
                 drop_callback=lambda _chunk, _reason: None) -> None:
        if window_s <= 0 or overlap_s < 0 or overlap_s >= window_s:
            raise ValueError("Transcript overlap must be non-negative and shorter than the window")
        self._transcriber = transcriber; self._callback = segment_callback
        self._window_s = window_s; self._overlap_s = overlap_s
        self._max_window_s = window_s if max_window_s is None else max_window_s
        if self._max_window_s < window_s or queue_size <= 0:
            raise ValueError("Maximum window must cover the minimum window; queue must be bounded")
        self._speech_boundary = speech_boundary
        self._queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self._clock = clock; self._thread = None; self._accepting = False
        self._metrics_callback = metrics_callback
        self._error_callback = error_callback
        self._drop_callback = drop_callback
        self._submit_lock = threading.Lock()
        self.failure = None
        self._current = None
        self._last_metrics = None
        self._cancel = threading.Event()
        self._publish_lock = threading.Lock()
        self.dropped_chunks = 0; self.lag_s = 0.0

    def start(self) -> None:
        self._accepting = True
        self._thread = threading.Thread(target=self._run, name="english-transcription", daemon=True); self._thread.start()

    def submit(self, chunk: AudioChunk) -> bool:
        with self._submit_lock:
            return self._submit(chunk)

    def _drop(self, chunk, reason):
        if chunk is not None:
            self.dropped_chunks += 1
            self._drop_callback(chunk, reason)

    def _submit(self, chunk: AudioChunk) -> bool:
        if not self._accepting: return False
        try: self._queue.put_nowait(chunk); return True
        except queue.Full:
            try:
                self._drop(self._queue.get_nowait(), "queue_full")
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(chunk)
                return True
            except queue.Full:
                self._drop(chunk, "queue_full")
                return False

    def _run(self) -> None:
        try:
            self._process_queue()
        except Exception as exc:
            self._report_failure(exc, "worker", self._current)
        finally:
            self._accepting = False

    def _report_failure(self, exc, stage, chunk) -> None:
        self.failure = str(exc)
        self._accepting = False
        self._cancel.set()
        value = {"stage": stage, "message": str(exc), "fatal": True}
        if chunk is not None:
            value.update(source=chunk.source.value, start_s=chunk.start_s, end_s=chunk.end_s)
        try:
            self._error_callback(value)
        except Exception:
            import logging
            logging.exception("Could not publish transcript worker failure")

    def _process_queue(self) -> None:
        buffers: dict[AudioSource, _AudioBuffer] = {}
        while not self._cancel.is_set():
            item = self._queue.get()
            if item is None:
                for buffer in buffers.values():
                    if buffer.end_s > buffer.processed_until_s + 1e-6:
                        self._transcribe_buffer(buffer, len(buffer.samples), buffer.processed_until_s)
                break
            self._current = item
            buffer = buffers.get(item.source)
            incompatible = buffer is not None and (
                buffer.sample_rate != item.sample_rate
                or item.start_s - buffer.end_s > 0.25
                or item.segment_index != buffer.segment_index + 1
            )
            if incompatible:
                if buffer.end_s > buffer.processed_until_s + 1e-6:
                    self._transcribe_buffer(buffer, len(buffer.samples), buffer.processed_until_s)
                buffer = None
            if buffer is None:
                buffer = _AudioBuffer(item.source, item.segment_index, item.start_s, item.start_s,
                                      item.sample_rate, item.channels, np.empty(0, np.float32), item.start_s)
                buffers[item.source] = buffer
            buffer.samples = np.concatenate((buffer.samples, item.samples))
            buffer.end_s = item.end_s
            buffer.segment_index = item.segment_index
            window_samples = max(1, round(buffer.sample_rate * self._window_s))
            max_samples = max(1, round(buffer.sample_rate * self._max_window_s))
            while len(buffer.samples) >= window_samples:
                if self._cancel.is_set():
                    return
                sample_count = min(len(buffer.samples), max_samples)
                boundary = False
                if self._speech_boundary is not None and sample_count < max_samples:
                    if sample_count < buffer.next_boundary_samples:
                        break
                    boundary = self._speech_boundary(buffer.samples[:sample_count], buffer.sample_rate)
                    buffer.next_boundary_samples = sample_count + max(1, round(buffer.sample_rate * ENDPOINT_CHECK_S))
                    if not boundary:
                        break
                # Retain overlap only when forced to split ongoing speech.
                stride = sample_count if boundary else max(
                    1, sample_count - round(buffer.sample_rate * self._overlap_s)
                )
                cutoff = buffer.processed_until_s
                self._transcribe_buffer(buffer, sample_count, cutoff)
                buffer.processed_until_s = buffer.start_s + sample_count / buffer.sample_rate
                buffer.samples = buffer.samples[stride:]
                buffer.start_s += stride / buffer.sample_rate
                buffer.next_boundary_samples = 0

    def _transcribe_buffer(self, buffer: _AudioBuffer, sample_count: int, cutoff_s: float) -> None:
        combined = AudioChunk(buffer.source, buffer.segment_index, buffer.start_s,
                              buffer.start_s + sample_count / buffer.sample_rate,
                              buffer.sample_rate, buffer.channels, buffer.samples[:sample_count].copy())
        started = time.perf_counter()
        try:
            for segment in self._transcriber.transcribe(combined):
                with self._publish_lock:
                    if self._cancel.is_set():
                        return
                    if segment.end_s > cutoff_s + 1e-6:
                        self._callback(segment)
        except Exception as exc:
            if not self._cancel.is_set():
                self._drop(combined, "inference_failure")
                self._report_failure(exc, "transcribe", combined)
            return
        if self._cancel.is_set(): return
        self.lag_s = max(0.0, self._clock() - combined.end_s)
        queued = {source.value: 0.0 for source in AudioSource}
        with self._queue.mutex:
            for chunk in self._queue.queue:
                if chunk is not None:
                    queued[chunk.source.value] += len(chunk.samples) / chunk.sample_rate
        rtf = (time.perf_counter() - started) / max(sample_count / buffer.sample_rate, 1e-6)
        self._last_metrics = TranscriptionMetrics(self.lag_s, self.dropped_chunks, combined.source.value, rtf, queued)
        try:
            self._metrics_callback(self._last_metrics)
        except Exception:
            pass

    def stop(self, grace_s: float = 10.0) -> None:
        with self._submit_lock:
            self._accepting = False
            try: self._queue.put_nowait(None)
            except queue.Full:
                try: self._drop(self._queue.get_nowait(), "stop_queue_full")
                except queue.Empty: pass
                self._queue.put_nowait(None)
        if self._thread: self._thread.join(grace_s)
        if self._thread and self._thread.is_alive():
            with self._publish_lock:
                self._cancel.set()
            raise RuntimeError("Live transcription timed out on Stop; use final transcription for remaining audio")
        return {"failure": self.failure, "dropped_chunks": self.dropped_chunks,
                "last_metrics": self._last_metrics}
