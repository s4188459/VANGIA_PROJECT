"""English experiments using the desktop app's decoder and live scheduler."""
from dataclasses import asdict
from functools import partial
from pathlib import Path
import sys
import hashlib
import threading
import time
import wave

from .replay import percentile

APP = Path(__file__).resolve().parents[2] / 'facial-cue-prototype'


def app_modules():
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    from src import transcription, audio_recorder
    return transcription, audio_recorder


class ExperimentAdapter:
    def __init__(self, config, mode):
        self.config, self.mode, self.decoder = config, mode, None

    def load(self):
        transcription, _ = app_modules()
        from src.selected_models import resolve_qwen_model, resolve_large_model
        if self.mode == 'experiment2':
            from src.qwen_transcription import QwenEnglishTranscriber
            self.decoder = QwenEnglishTranscriber(resolve_qwen_model(),
                python_executable=self.config.get('python_executable') or None)
            self.decoder.wait_ready()
        else:
            self.decoder = transcription.LocalEnglishTranscriber(resolve_large_model(), phase='final')
        paths = [Path(__file__), APP/'src/transcription.py', APP/'src/qwen_transcription.py', APP/'src/qwen_worker.py']
        return {'configuration': self.decoder.configuration,
                'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                'timing': 'model loading separate; no extra warmup; first sample flagged'}

    def transcribe(self, path, language):
        import numpy as np
        _, audio_types = app_modules()
        with wave.open(str(path), 'rb') as audio:
            rate = audio.getframerate()
            samples = np.frombuffer(audio.readframes(audio.getnframes()), '<i2').astype('float32') / 32768
        chunk = audio_types.AudioChunk(audio_types.AudioSource.MICROPHONE, 0, 0,
                                      len(samples) / rate, rate, 1, samples)
        rows = self.decoder.transcribe(chunk)
        return {'text': ' '.join(row.text for row in rows),
                'segments': [dict(start_s=r.start_s, end_s=r.end_s, text=r.text) for r in rows]}

    def close(self):
        if self.decoder is not None and hasattr(self.decoder, 'close'):
            self.decoder.close()
        self.decoder = None


def realtime_replay(decoder, path, cancelled=lambda: False, packet_s=.1):
    import numpy as np
    transcription, audio_types = app_modules()
    rows, outputs, queue_log, errors, dropped = [], [], [], [], []
    with wave.open(str(path), 'rb') as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
            raise ValueError('Replay requires normalized mono PCM16 16 kHz audio')
        samples = np.frombuffer(source.readframes(source.getnframes()), '<i2').astype('float32') / 32768
        rate = source.getframerate()
    # Preflight VAD provides explicitly estimated speech boundaries, not gold timestamps.
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    spans = get_speech_timestamps(samples, VadOptions(threshold=.35, speech_pad_ms=0))
    speech_start = spans[0]['start'] / rate if spans else None
    speech_end = spans[-1]['end'] / rate if spans else None
    origin = time.perf_counter()
    clock = lambda: time.perf_counter() - origin

    class TimedDecoder:
        def transcribe(self, chunk):
            start = clock()
            result = decoder.transcribe(chunk)
            end = clock()
            rows.append(dict(start_s=chunk.start_s, end_s=chunk.end_s,
                elapsed_s=end-start, emitted_at_s=end, lag_s=max(0, end-chunk.end_s),
                queue_wait_s=max(0, start-chunk.end_s), text=' '.join(r.text for r in result)))
            return result

    def publish(segment):
        outputs.append(dict(start_s=segment.start_s, end_s=segment.end_s,
                            text=segment.text, emitted_at_s=clock()))

    worker = transcription.TranscriptionWorker(TimedDecoder(), publish, window_s=1.2,
        max_window_s=transcription.LIVE_MAX_WINDOW_S, overlap_s=0, clock=clock,
        speech_boundary=partial(decoder.speech_boundary, pause_s=transcription.LIVE_ENDPOINT_PAUSE_S),
        metrics_callback=lambda m: queue_log.append(dict(at_s=clock(), **asdict(m))),
        error_callback=errors.append, drop_callback=lambda c, reason: dropped.append(reason))
    worker.start()
    duration = len(samples) / rate
    step = round(packet_s * rate)
    try:
        for index, offset in enumerate(range(0, len(samples), step)):
            end = min(offset + step, len(samples))
            while clock() < end / rate:
                if cancelled():
                    raise InterruptedError('Replay cancelled; incomplete sample is not scored')
                time.sleep(min(.02, max(0, end / rate - clock())))
            if cancelled():
                raise InterruptedError('Replay cancelled; incomplete sample is not scored')
            if errors:
                raise RuntimeError(str(errors[-1]))
            if not worker.submit(audio_types.AudioChunk(audio_types.AudioSource.MICROPHONE,
                    index, offset/rate, end/rate, rate, 1, samples[offset:end].copy())):
                raise RuntimeError('Replay worker rejected audio')
        # Drain after EOF, unlike the desktop Stop button which intentionally cancels.
        done = threading.Event()
        def drain():
            try:
                worker.stop(grace_s=600)
            except Exception as exc:
                errors.append(str(exc))
            finally:
                done.set()
        threading.Thread(target=drain, daemon=True).start()
        while not done.wait(.05):
            if cancelled():
                raise InterruptedError('Replay cancelled during finalization')
        if errors or dropped:
            raise RuntimeError(f'Replay incomplete: errors={errors}; drops={dropped}')
        ready = clock()
    finally:
        if worker._thread and worker._thread.is_alive():
            worker.request_stop()
            decoder.cancel()
            worker._thread.join(5)
    first = next((r['emitted_at_s'] for r in outputs if r['text'].strip()), None)
    return {'text': ' '.join(r['text'] for r in outputs), 'segments': outputs, 'chunks': rows,
        'queue_log': queue_log, 'wall_s': ready, 'inference_s': sum(r['elapsed_s'] for r in rows),
        'replay_metrics': dict(chunk_count=len(rows), first_text_s=first,
            first_text_from_vad_s=None if first is None or speech_start is None else first-speech_start,
            speech_start_vad_s=speech_start, speech_end_vad_s=speech_end,
            finalization_from_eof_s=max(0, ready-duration),
            finalization_from_vad_s=None if speech_end is None else max(0, ready-speech_end),
            chunk_p95_s=percentile([r['elapsed_s'] for r in rows]),
            lag_p95_s=percentile([r['lag_s'] for r in rows]),
            max_lag_s=max((r['lag_s'] for r in rows), default=0),
            deadline_misses=sum(r['elapsed_s'] > r['end_s']-r['start_s'] for r in rows),
            max_queue_s=max((sum(r['queued_duration_s'].values()) for r in queue_log), default=0),
            word_latency_s=None, timestamp_basis='VAD-estimated speech; chunk bounds; no word alignment')}
