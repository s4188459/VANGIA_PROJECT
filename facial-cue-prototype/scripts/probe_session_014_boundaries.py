"""Replay only the already-transcribed boundary in session 014; never edit raw data."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from multiprocessing.reduction import ForkingPickler
from pathlib import Path
import sys
import time
import wave

import numpy as np

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from src.audio_recorder import AudioChunk, AudioSource
from src.transcription import LocalEnglishTranscriber, endpoint_audio_context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    session = APP.parent / 'test-results' / 'session_014'
    output = args.output.resolve()
    if output == session or session in output.parents:
        parser.error('Output must be outside the raw session directory.')
    if output.exists():
        parser.error('Output already exists; choose a new report path.')
    raw_names = ('audio.wav', 'features.csv', 'landmark-timing.csv', 'session.json', 'transcript.jsonl')
    hashes = {name: hashlib.sha256((session/name).read_bytes()).hexdigest() for name in raw_names}
    with wave.open(str(session/'audio.wav')) as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (48000, 2, 2)
        rate = wav.getframerate()
        audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').reshape(-1, 2)[:, 1]
        audio = audio.astype(np.float32) / 32768
    historical = [json.loads(line) for line in (session/'transcript.jsonl').read_text().splitlines()]
    decoder = LocalEnglishTranscriber(APP/'models'/'faster-whisper-small-en')
    windows = []
    # The 12 s windows with 0.75 s overlap reproduce saved segments 3 and 4.
    # Do not transcribe the intentionally unprocessed tail or produce a final transcript.
    for i, start in enumerate((17.361913333333035, 28.611913333333035)):
        samples = audio[round(start*rate):round(start*rate)+12*rate]
        chunk = AudioChunk(AudioSource.SYSTEM_AUDIO, i, start, start+12, rate, 1, samples)
        started = time.perf_counter()
        rows = decoder.transcribe(chunk)
        windows.append({'start_s': start, 'end_s': start+12,
                        'decode_wall_s': time.perf_counter()-started,
                        'historical_text': historical[i+2]['text'],
                        'replayed_segments': [asdict(row) for row in rows]})
    assert windows[0]['replayed_segments'][0]['text'] == historical[2]['text']
    assert windows[1]['replayed_segments'][0]['text'] == historical[3]['text'].removeprefix('to read your ')

    # Serialization-only microbenchmark, not IPC round-trip or end-to-end UI latency.
    full = audio[:12*rate]
    bounded = endpoint_audio_context(full, rate, pause_s=.6)
    benchmark = {}
    for label, samples in (('full_buffer', full), ('bounded_context', bounded)):
        payload = ('boundary', (samples, rate, .6))
        for _ in range(10):
            ForkingPickler.dumps(payload)
        elapsed = []
        for _ in range(200):
            started = time.perf_counter()
            serialized = ForkingPickler.dumps(payload)
            elapsed.append((time.perf_counter()-started)*1000)
        benchmark[label] = {'samples': len(samples), 'audio_bytes': samples.nbytes,
                            'serialized_bytes': len(serialized),
                            'mean_ms': float(np.mean(elapsed)),
                            'p95_ms': float(np.percentile(elapsed, 95))}
    assert all(hashlib.sha256((session/name).read_bytes()).hexdigest() == value
               for name, value in hashes.items())
    report = {'scope': 'Offline replay of two previously transcribed windows; no UI or hardware capture.',
              'comparison': 'Historical saved text; pre-change replay also reproduced both texts during investigation.',
              'configuration': decoder.configuration, 'raw_sha256': hashes,
              'windows': windows, 'serialization_benchmark': benchmark,
              'limitations': ['No WER without a verified reference.',
                              'Serialization timing excludes process transport, VAD, UI and concurrent face tracking.',
                              'Boundary heuristic is conservative, not a guarantee against all repetition.']}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'report': str(output), 'boundary_text': windows[1]['replayed_segments'][0]['text'],
                      'serialization_benchmark': benchmark}, indent=2))


if __name__ == '__main__':
    main()
