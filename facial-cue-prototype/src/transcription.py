from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from types import SimpleNamespace
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
LIVE_ENDPOINT_PAUSE_S = 0.6
LIVE_MAX_WINDOW_S = 12.0


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


def endpoint_audio_context(samples: np.ndarray, sample_rate: int, *, pause_s: float) -> np.ndarray:
    """Keep the same recent context in local and process-backed endpoint checks."""
    return samples[-round(sample_rate * (pause_s + 1.0)):]


def speech_has_ended(samples: np.ndarray, sample_rate: int, *, pause_s: float = UTTERANCE_PAUSE_S) -> bool:
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    # Endpoint detection needs recent speech context, not the whole utterance.
    samples = endpoint_audio_context(samples, sample_rate, pause_s=pause_s)
    if sample_rate != 16000:
        divisor = math.gcd(sample_rate, 16000)
        samples = resample_poly(samples, 16000 // divisor, sample_rate // divisor).astype(np.float32)
    audio, _gain = prepare_inference_audio(samples)
    spans = get_speech_timestamps(
        audio, VadOptions(threshold=0.35, min_silence_duration_ms=round(pause_s * 1000), speech_pad_ms=0),
    )
    return not spans or len(audio) - spans[-1]["end"] >= round(16000 * pause_s)


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
        self._word_history = {}
        self.rejected_segments = 0
        self.configuration = {
            "model": Path(model_path).name, "device": "cpu", "compute_type": "int8",
            "cpu_threads": cpu_threads, "num_workers": 1, "beam_size": beam_size,
            "language": "en", "word_timestamps": True, "vad_threshold": .35,
            "utterance_pause_s": UTTERANCE_PAUSE_S,
            "temperature": 0.0, "condition_on_previous_text": False,
            "hallucination_silence_threshold": 1.0,
            "segment_min_avg_logprob": -1.0, "segment_max_compression_ratio": 2.4,
            "overlap_deduplication": "timed_suffix_prefix_v2",
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
            temperature=0.0, condition_on_previous_text=False,
            hallucination_silence_threshold=1.0,
        )
        output = []
        speaker = "Student" if chunk.source is AudioSource.SYSTEM_AUDIO else "You"
        segments = self._accepted_segments(segments)
        if self._phase == "live":
            segments = self._deduplicate_overlap(segments, chunk)
        for start, end, value in pause_grouped_segments(segments):
            if not value: continue
            status = "canonical" if self._phase == "final" else "committed"
            output.append(TranscriptSegment(self._next_id, chunk.start_s + start, chunk.start_s + end,
                                            chunk.source, speaker, value, phase=self._phase, status=status))
            self._next_id += 1
        return tuple(output)


    def _accepted_segments(self, segments):
        for segment in segments:
            logprob = getattr(segment, "avg_logprob", None)
            ratio = getattr(segment, "compression_ratio", None)
            if ((logprob is not None and (not math.isfinite(logprob) or logprob < -1.0))
                    or (ratio is not None and (not math.isfinite(ratio) or ratio > 2.4))):
                self.rejected_segments += 1
                continue
            yield segment

    def _deduplicate_overlap(self, segments, chunk):
        segments = list(segments)
        # Missing word timestamps cannot safely support word-level trimming.
        if any(not getattr(segment, "words", None) for segment in segments):
            self._word_history.pop(chunk.source, None)
            return segments
        words = [w for segment in segments for w in segment.words if w.word.strip()]
        previous_end, previous = self._word_history.get(chunk.source, (float("-inf"), []))
        def key(text):
            return " ".join(re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower()))
        current = [(chunk.start_s+w.start, chunk.start_s+w.end, key(w.word)) for w in words]
        trim = 0
        def same_audio(a, b):
            return (abs((a[0]+a[1]-b[0]-b[1])/2) <= .35
                    and a[1] >= chunk.start_s-.35 and b[0] < previous_end)

        def negation(token):
            return token in {"no", "not", "never", "cannot"} or token.endswith("n't")

        if chunk.start_s < previous_end:
            # Match only the published suffix to the new prefix at the same audio time.
            # Midpoint tolerance allows modest Whisper alignment jitter, not later repeats.
            for count in range(min(len(previous), len(current)), 0, -1):
                left, right = previous[-count:], current[:count]
                exact = all(a[2] and a[2] == b[2] and same_audio(a, b)
                            for a,b in zip(left,right))
                # A forced window can start inside a word (e.g. "gonna" -> "to").
                # Allow only that clipped first word to differ, with two or more
                # exact, time-aligned anchors. Preserve ambiguous negation edits.
                clipped = (count >= 3 and left[0][2] and right[0][2]
                           and left[0][2] != right[0][2]
                           and left[0][0] < chunk.start_s < left[0][1]
                           and right[0][0] <= chunk.start_s + .05
                           and min(left[0][1], right[0][1]) > max(left[0][0], right[0][0])
                           and same_audio(left[0], right[0])
                           and not negation(left[0][2]) and not negation(right[0][2])
                           and all(a[2] and a[2] == b[2] and same_audio(a, b)
                                   for a,b in zip(left[1:], right[1:])))
                if exact or clipped:
                    trim = count
                    break
        retained = words[trim:]
        history = (previous if chunk.start_s < previous_end else []) + current[trim:]
        self._word_history[chunk.source] = (chunk.end_s, history[-64:])
        return [SimpleNamespace(words=retained)] if retained else []


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
        self._pending_intervals = {}
        self._phase = "idle"
        self._phase_at_stop = None
        self._stop_stats = None
        self._last_metrics = None
        self._cancel = threading.Event()
        self._publish_lock = threading.Lock()
        self.dropped_chunks = 0; self.lag_s = 0.0

    def start(self) -> None:
        self._accepting = True
        self._thread = threading.Thread(target=self._run, name="english-transcription", daemon=True); self._thread.start()

    def submit(self, chunk: AudioChunk) -> bool:
        with self._submit_lock:
            accepted = self._submit(chunk)
            if accepted:
                ranges = self._pending_intervals.setdefault(chunk.source.value, [])
                if ranges and abs(ranges[-1][1] - chunk.start_s) < 1e-5:
                    ranges[-1][1] = chunk.end_s
                else:
                    ranges.append([chunk.start_s, chunk.end_s])
            return accepted

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
            if not self._cancel.is_set():
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
            self._phase = "waiting_audio"
            item = self._queue.get()
            if self._cancel.is_set(): return
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
                    self._phase = "endpoint"
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
        self._phase = "inference"
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
        with self._submit_lock:
            # Successful decode coverage, including silence; not the last spoken word.
            self._pending_intervals[combined.source.value] = [
                [max(start, combined.end_s), end]
                for start, end in self._pending_intervals.get(combined.source.value, [])
                if end > combined.end_s + 1e-6
            ]
        self._phase = "waiting_audio"
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

    def request_stop(self) -> None:
        if self._phase_at_stop is not None:
            return
        self._phase_at_stop = self._phase
        self._cancel.set()
        with self._submit_lock:
            self._accepting = False
        cancel = getattr(self._transcriber, "cancel", None)
        if cancel is not None:
            cancel()
        # Wake an idle worker. A full queue already provides a wakeup.
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

    def _stop_cancelled(self):
        if self._stop_stats is not None:
            return self._stop_stats
        if self._thread:
            self._thread.join(1.0)
        alive = bool(self._thread and self._thread.is_alive())
        close = getattr(self._transcriber, "close", None)
        if close is not None:
            close()
        self._stop_stats = {
            "failure": self.failure or ("Transcript worker did not exit after cancellation" if alive else None),
            "stop_policy": "cancel_without_flush", "phase_at_stop": self._phase_at_stop,
            "dropped_chunks": self.dropped_chunks, "last_metrics": self._last_metrics,
            "unprocessed_audio_intervals": self._pending_intervals,
            "coverage_complete": not any(self._pending_intervals.values()) and not self.dropped_chunks and not self.failure,
        }
        return self._stop_stats

    def stop(self, grace_s: float = 10.0) -> None:
        if self._phase_at_stop is not None:
            return self._stop_cancelled()
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
