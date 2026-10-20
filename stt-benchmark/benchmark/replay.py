"""Sequential, causal fixed-chunk replay. No microphone or native streaming claims."""
import math
from pathlib import Path
import tempfile
import time
import wave


def validate_options(value=None):
    value = {} if value is None else value
    if not isinstance(value, dict):
        raise ValueError('Benchmark options must be an object.')
    mode = value.get('mode', 'final')
    chunk = value.get('chunk_seconds', 3)
    if mode not in ('final', 'live_replay', 'experiment2', 'experiment3'):
        raise ValueError('Mode must be final or live_replay.')
    if type(chunk) not in (float, int) or not math.isfinite(chunk) or not 1 <= chunk <= 15:
        raise ValueError('Simulated chunks must be between 1 and 15 seconds.')
    cloud = value.get('allow_cloud', False)
    if type(cloud) is not bool:
        raise ValueError('allow_cloud must be a boolean.')
    limit = value.get('sample_limit', 0)
    if type(limit) is not int or not 0 <= limit <= 1000:
        raise ValueError('Sample limit must be 0 (all) or 1–1000.')
    return {'mode': mode, 'chunk_seconds': chunk, 'allow_cloud': cloud, 'sample_limit': limit,
            'protocol': {'live_replay': 'fixed-chunks-no-overlap-v1',
                'experiment2': 'app-qwen-realtime-packets-v1',
                'experiment3': 'app-whisper-offline-v1'}.get(mode, 'full-file-v1')}


def percentile(values, fraction=.95):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def replay(adapter, audio_path, language, chunk_seconds, cancelled=lambda: False, clock=time.perf_counter):
    rows, segments, texts = [], [], []
    finished = 0.0
    with wave.open(str(audio_path), 'rb') as audio, tempfile.TemporaryDirectory(prefix='stt-replay-') as temp:
        rate = audio.getframerate()
        step = max(1, round(chunk_seconds * rate))
        total, offset = audio.getnframes(), 0
        while offset < total:
            if cancelled():
                raise InterruptedError('Cancelled between simulated chunks; this sample has not been scored.')
            count = min(step, total - offset)
            started = clock()
            path = Path(temp) / 'chunk.wav'
            with wave.open(str(path), 'wb') as chunk:
                chunk.setparams(audio.getparams())
                chunk.writeframes(audio.readframes(count))
            prediction = adapter.transcribe(path, language)
            elapsed = clock() - started
            start, end = offset / rate, (offset + count) / rate
            # Each chunk is available only at its end. Single worker queues any backlog.
            finished = max(end, finished) + elapsed
            rows.append({'start_s': start, 'end_s': end, 'elapsed_s': elapsed,
                         'emitted_at_s': finished, 'lag_s': finished - end, 'text': prediction['text']})
            texts.append(prediction['text'])
            segments.append({'start_s': start, 'end_s': end, 'text': prediction['text']})
            offset += count
    nonempty = [r for r in rows if r['text'].strip()]
    return {'text': ' '.join(texts).strip(), 'segments': segments, 'chunks': rows,
            'replay_metrics': {'chunk_count': len(rows),
                'first_text_s': nonempty[0]['emitted_at_s'] if nonempty else None,
                'chunk_p95_s': percentile([r['elapsed_s'] for r in rows]),
                'lag_p95_s': percentile([r['lag_s'] for r in rows]),
                'max_lag_s': max((r['lag_s'] for r in rows), default=0),
                'deadline_misses': sum(r['elapsed_s'] > r['end_s'] - r['start_s'] for r in rows)}}
