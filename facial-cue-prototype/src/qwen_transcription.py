"""Killable Qwen inference in its separate environment; chunk-level timestamps."""
import base64
import json
import math
import os
from pathlib import Path
import subprocess
import threading

import numpy as np
from scipy.signal import resample_poly

from .audio_recorder import AudioSource
from .audio_quality import prepare_inference_audio
from .selected_models import APP
from .transcription import TranscriptSegment, speech_has_ended


class QwenEnglishTranscriber:
    def __init__(self, model_path, *, python_executable=None):
        python = Path(python_executable or os.environ.get('FACIAL_QWEN_PYTHON', str(
            APP.parent / 'stt-benchmark' / '.backends' / 'qwen-asr' / 'Scripts' / 'python.exe')))
        if not python.is_file():
            raise RuntimeError('Missing Qwen environment. Set FACIAL_QWEN_PYTHON to its python.exe.')
        self.configuration = dict(model='Qwen/Qwen3-ASR-0.6B', model_path=str(model_path),
            device='cpu', compute_type='float32', cpu_threads=4, language='en',
            execution='subprocess', timestamps='audio_chunk_bounds', word_timestamps=False,
            streaming='utterance_chunks', overlap_s=0, stop_policy='cancel_without_flush')
        self._lock = threading.Lock()
        self._closed = False
        self._cancelled = threading.Event()
        self._next_id = 1
        self._ready = False
        self._process = subprocess.Popen([str(python), '-u', str(Path(__file__).with_name('qwen_worker.py')),
                                         str(model_path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def wait_ready(self):
        with self._lock:
            self._read_ready()

    def _read_ready(self):
        if self._ready:
            return
        line = self._process.stdout.readline()
        value = json.loads(line) if line else {'error': 'Qwen worker exited during loading'}
        if value.get('ready') is not True:
            raise RuntimeError(value.get('error', 'Invalid Qwen startup response'))
        self._ready = True

    @staticmethod
    def speech_boundary(samples, sample_rate, *, pause_s):
        return speech_has_ended(samples, sample_rate, pause_s=pause_s)

    def transcribe(self, chunk):
        if self._cancelled.is_set():
            raise RuntimeError('LIVE inference cancelled')
        audio = chunk.samples
        if chunk.sample_rate != 16000:
            divisor = math.gcd(chunk.sample_rate, 16000)
            audio = resample_poly(audio, 16000 // divisor, chunk.sample_rate // divisor)
        audio, _gain = prepare_inference_audio(np.asarray(audio, dtype=np.float32))
        from faster_whisper.vad import get_speech_timestamps, VadOptions
        if not get_speech_timestamps(audio, VadOptions(threshold=.35)):
            return ()
        with self._lock:
            if self._cancelled.is_set():
                raise RuntimeError('LIVE inference cancelled')
            self._read_ready()
            self._process.stdin.write(json.dumps({'audio': base64.b64encode(
                audio.astype('<f4').tobytes()).decode('ascii')}) + '\n')
            self._process.stdin.flush()
            line = self._process.stdout.readline()
            if not line:
                raise RuntimeError('Qwen worker exited or was cancelled')
            response = json.loads(line)
            if 'error' in response:
                raise RuntimeError(response['error'])
            if self._cancelled.is_set():
                raise RuntimeError('LIVE inference cancelled')
            text = response['text'].strip()
            if not text:
                return ()
            segment = TranscriptSegment(self._next_id, chunk.start_s, chunk.end_s, chunk.source,
                'Student' if chunk.source is AudioSource.SYSTEM_AUDIO else 'You', text)
            self._next_id += 1
            return (segment,)

    def cancel(self):
        self._cancelled.set()
        if self._process.poll() is None:
            self._process.kill()

    def close(self):
        if self._closed:
            return
        self.cancel()
        self._process.wait(timeout=5)
        with self._lock:
            self._process.stdin.close()
            self._process.stdout.close()
            self._closed = True
