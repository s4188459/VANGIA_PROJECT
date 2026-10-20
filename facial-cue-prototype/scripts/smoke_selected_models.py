"""Historical model-pair smoke test; does not establish a current model selection."""
from pathlib import Path
import sys
import time
import wave
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.audio_recorder import AudioChunk, AudioSource
from src.selected_models import resolve_qwen_model, resolve_large_model
from src.qwen_transcription import QwenEnglishTranscriber
from src.transcription import LocalEnglishTranscriber


def main():
    with wave.open(sys.argv[1], 'rb') as wav:
        assert wav.getsampwidth() == 2
        rate = wav.getframerate()
        samples = np.frombuffer(wav.readframes(rate * 4), '<i2').reshape(-1, wav.getnchannels())
        samples = samples.astype(np.float32).mean(axis=1) / 32768
    chunk = AudioChunk(AudioSource.MICROPHONE, 0, 0, len(samples) / rate, rate, 1, samples)
    for name, factory, path in (
        ('Qwen live', QwenEnglishTranscriber, resolve_qwen_model()),
        ('Whisper final', lambda p: LocalEnglishTranscriber(p, phase='final'), resolve_large_model()),
    ):
        start = time.perf_counter()
        decoder = factory(path)
        try:
            rows = decoder.transcribe(chunk)
            assert rows and any(row.text.strip() for row in rows), f'{name}: empty output'
            print(name, 'OK', round(time.perf_counter() - start, 2), 'seconds including load', flush=True)
        finally:
            if hasattr(decoder, 'close'):
                decoder.close()


if __name__ == '__main__':
    main()
