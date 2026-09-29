from __future__ import annotations

from pathlib import Path
import json
import threading
import wave

import numpy as np

from .audio_recorder import AudioChunk, AudioSource
from .stereo_audio import AudioInterval
from .transcript_writer import replace_transcript_with_final
from .transcription import LocalEnglishTranscriber


DEFAULT_FINAL_MODEL = Path(__file__).resolve().parents[1] / "models" / "faster-whisper-medium-en"


def resolve_final_model(root: Path = DEFAULT_FINAL_MODEL.parent) -> Path | None:
    root = Path(root)
    for name in ("faster-whisper-medium-en", "faster-whisper-small-en", "faster-whisper-base-en"):
        candidate = root / name
        if candidate.is_dir(): return candidate
    return None


def update_final_status(session_path: Path, status: str, message: str, model: str | None) -> None:
    session_path = Path(session_path)
    value = json.loads(session_path.read_text("utf-8"))
    value.setdefault("transcription", {})["final"] = {
        "status": status, "message": message, "model": model,
    }
    temporary = session_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")
    temporary.replace(session_path)


def map_wav_time_to_session(offset_s: float, sample_rate: int,
                            intervals: tuple[AudioInterval, ...]) -> float | None:
    frame = round(offset_s * sample_rate)
    for interval in intervals:
        if interval.wav_start_frame <= frame <= interval.wav_end_frame:
            return interval.session_start_s + (frame - interval.wav_start_frame) / sample_rate
    return None


class FinalTranscriptionJob:
    def __init__(self, audio_path: Path, intervals, transcript_path: Path, *, model_path=None,
                 transcriber_factory=None, progress_callback=lambda _value: None,
                 completion_callback=lambda _ok, _message: None) -> None:
        self.audio_path = Path(audio_path); self.intervals = tuple(intervals)
        self.transcript_path = Path(transcript_path)
        selected_model = Path(model_path) if model_path is not None else resolve_final_model()
        if selected_model is None and transcriber_factory is None:
            raise RuntimeError("No local Whisper model is installed")
        self.model_path = selected_model
        self._factory = transcriber_factory or (
            lambda: LocalEnglishTranscriber(self.model_path, phase="final")
        )
        self._progress = progress_callback; self._complete = completion_callback
        self._cancel = threading.Event(); self._thread = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive(): raise RuntimeError("Final transcription is already running")
        self._thread = threading.Thread(target=self._run, name="final-transcription", daemon=True)
        self._thread.start()

    def cancel(self) -> None: self._cancel.set()
    def join(self, timeout_s: float | None = None) -> None:
        if self._thread: self._thread.join(timeout_s)

    def _run(self) -> None:
        try:
            replace_transcript_with_final(self.transcript_path, self._segments())
            self._complete(True, "Final transcript ready")
        except Exception as exc:
            self.transcript_path.with_suffix(self.transcript_path.suffix + ".tmp").unlink(missing_ok=True)
            self._complete(False, str(exc))

    def _segments(self):
        transcriber = self._factory()
        total = max(1, sum(i.wav_end_frame - i.wav_start_frame for i in self.intervals))
        done = 0
        with wave.open(str(self.audio_path), "rb") as source:
            if source.getnchannels() != 2 or source.getsampwidth() != 2:
                raise ValueError("Final transcription requires a PCM16 stereo WAV")
            rate = source.getframerate()
            window = rate * 30
            overlap = round(rate * .75)
            index = 0
            for interval in self.intervals:
                if not 0 <= interval.wav_start_frame <= interval.wav_end_frame <= source.getnframes():
                    raise ValueError("Audio interval is outside the WAV file")
                offset = interval.wav_start_frame
                cutoff = interval.session_start_s
                while offset < interval.wav_end_frame:
                    if self._cancel.is_set(): raise InterruptedError("Final transcription cancelled")
                    count = min(window, interval.wav_end_frame - offset)
                    source.setpos(offset)
                    audio = np.frombuffer(source.readframes(count), np.int16).reshape(-1, 2).astype(np.float32) / 32768.0
                    start_s = interval.session_start_s + (offset - interval.wav_start_frame) / rate
                    end_s = start_s + count / rate
                    output = []
                    for channel, source_id in ((0, AudioSource.MICROPHONE), (1, AudioSource.SYSTEM_AUDIO)):
                        if self._cancel.is_set(): raise InterruptedError("Final transcription cancelled")
                        chunk = AudioChunk(source_id, index, start_s, end_s, rate, 1, audio[:, channel].copy())
                        output.extend(segment for segment in transcriber.transcribe(chunk) if segment.end_s > cutoff + 1e-6)
                    if self._cancel.is_set(): raise InterruptedError("Final transcription cancelled")
                    yield from sorted(output, key=lambda item: (item.start_s, item.source.value))
                    stride = count if offset + count == interval.wav_end_frame else count - overlap
                    offset += stride; done += stride; index += 1
                    cutoff = end_s
                    self._progress(min(1., done / total))
        if self._cancel.is_set(): raise InterruptedError("Final transcription cancelled")
