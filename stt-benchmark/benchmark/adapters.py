"""Add a backend by implementing load/transcribe/close and registering its name."""
import gc
from pathlib import Path
from .extra_adapters import (TransformersAdapter, QwenAdapter, NemoAdapter, SenseVoiceAdapter,
                             VoskAdapter, ElevenLabsAdapter, GoogleChirpAdapter, FunASRMLTAdapter)


class FasterWhisperAdapter:
    def __init__(self, config):
        self.config = config
        self.model = None

    def load(self):
        from faster_whisper import WhisperModel
        config = self.config
        target = config["model"]
        local = Path(target).expanduser()
        if local.is_dir():
            target = str(local.resolve())
        self.model = WhisperModel(target, device=config["device"], compute_type=config["compute_type"],
                                  cpu_threads=config["cpu_threads"], num_workers=1,
                                  download_root=str(Path(__file__).resolve().parents[1] / 'data' / 'hf-cache'),
                                  local_files_only=not config["allow_download"])

    def transcribe(self, audio_path, language):
        if language != "en" and not self.model.model.is_multilingual:
            raise ValueError("Vietnamese datasets require a multilingual model; the loaded model supports English only.")
        segments, info = self.model.transcribe(
            str(audio_path), language=language, task="transcribe",
            beam_size=self.config["beam_size"], vad_filter=self.config["vad_filter"],
            temperature=0.0, condition_on_previous_text=False,
        )
        # faster-whisper decodes lazily: consume the generator inside the timer.
        rows = [{"start_s": s.start, "end_s": s.end, "text": s.text} for s in segments]
        return {"text": " ".join(s["text"].strip() for s in rows).strip(),
                "segments": rows, "detected_language": info.language}

    def close(self):
        self.model = None
        gc.collect()


ADAPTERS = {"faster-whisper": FasterWhisperAdapter,
            "transformers-whisper": TransformersAdapter, "transformers-ctc": TransformersAdapter,
            "qwen-asr": QwenAdapter, "nemo": NemoAdapter, "sensevoice": SenseVoiceAdapter,
            "fun-asr-mlt": FunASRMLTAdapter,
            "vosk": VoskAdapter, "elevenlabs": ElevenLabsAdapter, "google-chirp": GoogleChirpAdapter}


def validate_config(value):
    if not isinstance(value, dict):
        raise ValueError("Invalid model configuration.")
    backend = value.get("backend", "faster-whisper")
    if backend not in ADAPTERS:
        raise ValueError("Unsupported backend.")
    if not isinstance(value.get("model"), str) or not isinstance(value.get("label"), str):
        raise ValueError("Configuration label and model path must be strings.")
    model = value["model"].strip()
    label = value["label"].strip()
    if not model or not label or len(model) > 2000 or len(label) > 100:
        raise ValueError("Enter a valid configuration label and model path/ID.")
    device, compute = value.get("device", "cpu"), value.get("compute_type", "int8")
    if device not in ("cpu", "cuda") or compute not in ("int8", "float32", "float16", "int8_float16"):
        raise ValueError("Invalid device or compute type.")
    if device == "cpu" and compute in ("float16", "int8_float16"):
        raise ValueError("CPU: select int8 or float32.")
    beam, threads = value.get("beam_size", 5), value.get("cpu_threads", 4)
    if type(beam) is not int or type(threads) is not int:
        raise ValueError("Beam size and thread count must be integers.")
    if any(type(value.get(key, default)) is not bool for key, default in (("vad_filter", True), ("allow_download", False))):
        raise ValueError("VAD and download permission must be true or false.")
    if not 1 <= beam <= 10 or not 1 <= threads <= 64:
        raise ValueError("Beam size: 1–10; threads: 1–64.")
    languages = value.get('languages', ['en', 'vi'])
    if not isinstance(languages, list) or not languages or any(x not in ('en', 'vi') for x in languages):
        raise ValueError('Model languages must be en and/or vi.')
    if backend != 'faster-whisper':
        if compute not in ('float32', 'float16'):
            raise ValueError('This backend does not support INT8 in this tool; choose float32 or CUDA float16.')
        if value.get('vad_filter', True):
            raise ValueError('Configurable VAD is supported only by faster-whisper; disable it for this backend.')
        if backend != 'transformers-whisper' and beam != 1:
            raise ValueError('This backend uses its default decoder; set beam=1 (custom beam size does not apply).')
    if backend in ('vosk', 'sensevoice', 'fun-asr-mlt', 'elevenlabs', 'google-chirp') and compute != 'float32':
        raise ValueError('This backend does not support selecting float16 in this tool.')
    if backend in ('vosk', 'elevenlabs', 'google-chirp') and device != 'cpu':
        raise ValueError('This backend does not use local CUDA through this tool.')
    python = value.get('python_executable', '')
    if not isinstance(python, str) or len(python) > 2000:
        raise ValueError('Invalid Python executable path.')
    if python and not Path(python).is_file():
        raise ValueError('Backend Python executable not found.')
    if python:
        python = str(Path(python).resolve())
    return {"backend": backend, "model": model, "label": label, "device": device,
            "python_executable": python,
            "compute_type": compute, "beam_size": beam, "cpu_threads": threads,
            "languages": sorted(set(languages)),
            "vad_filter": value.get("vad_filter", True) is True,
            "allow_download": value.get("allow_download", False) is True}
