"""Optional backends. Imports stay lazy so the original tool remains lightweight."""
import gc
import json
import os
from pathlib import Path
import wave


def local_snapshot(config):
    path = Path(config['model']).expanduser()
    if path.is_dir():
        return str(path.resolve())
    from huggingface_hub import snapshot_download
    return snapshot_download(config['model'], local_files_only=not config['allow_download'])


def samples(path):
    import numpy as np
    with wave.open(str(path), 'rb') as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
            raise ValueError('Backend cần WAV PCM16 mono 16 kHz; hãy import lại dataset.')
        return np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2').astype('float32') / 32768


class TorchAdapter:
    def __init__(self, config):
        self.config, self.model = config, None

    def setup(self):
        import torch
        torch.set_num_threads(self.config['cpu_threads'])
        if self.config['device'] == 'cuda' and not torch.cuda.is_available():
            raise ValueError('CUDA không khả dụng trong môi trường backend này.')
        return torch, getattr(torch, self.config['compute_type'])

    def close(self):
        self.model = None
        self.processor = None
        gc.collect()
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


class TransformersAdapter(TorchAdapter):
    def load(self):
        from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq, AutoModelForCTC
        torch, dtype = self.setup()
        target = local_snapshot(self.config)
        self.target = target
        self.processor = AutoProcessor.from_pretrained(target, local_files_only=True, trust_remote_code=False)
        cls = AutoModelForSpeechSeq2Seq if self.config['backend'] == 'transformers-whisper' else AutoModelForCTC
        self.model = cls.from_pretrained(target, local_files_only=True, trust_remote_code=False,
                                        torch_dtype=dtype).to(self.config['device']).eval()
        self.is_mms = self.model.config.model_type == 'wav2vec2' and getattr(self.model.config, 'adapter_attn_dim', None) is not None
        self.current_language = None

    def transcribe(self, audio_path, language):
        import torch
        if self.is_mms and self.current_language != language:
            lang = {'en': 'eng', 'vi': 'vie'}[language]
            self.processor.tokenizer.set_target_lang(lang)
            self.model.load_adapter(lang, local_files_only=True)
            self.current_language = language
        audio = samples(audio_path)
        texts = []
        # Explicit 30s blocks avoid silent Whisper feature truncation on long files.
        for start in range(0, len(audio), 30 * 16000):
            inputs = self.processor(audio[start:start + 30 * 16000], sampling_rate=16000, return_tensors='pt')
            inputs = {k: v.to(device=self.config['device'], dtype=self.model.dtype) if v.is_floating_point()
                      else v.to(self.config['device']) for k, v in inputs.items()}
            with torch.inference_mode():
                if self.config['backend'] == 'transformers-whisper':
                    ids = self.model.generate(**inputs, language=language, task='transcribe',
                                              num_beams=self.config['beam_size'], do_sample=False)
                else:
                    ids = self.model(**inputs).logits.argmax(dim=-1)
            texts.append(self.processor.batch_decode(ids, skip_special_tokens=True)[0])
        return {'text': ' '.join(texts), 'detected_language': None}


class QwenAdapter(TorchAdapter):
    def load(self):
        from qwen_asr import Qwen3ASRModel
        _, dtype = self.setup()
        self.model = Qwen3ASRModel.from_pretrained(local_snapshot(self.config), dtype=dtype,
                    device_map=self.config['device'], max_inference_batch_size=1, max_new_tokens=4096)

    def transcribe(self, audio_path, language):
        rows = self.model.transcribe(audio=str(audio_path), language={'en': 'English', 'vi': 'Vietnamese'}[language])
        return {'text': ' '.join(r.text for r in rows), 'detected_language': None}


class NemoAdapter(TorchAdapter):
    def load(self):
        import nemo.collections.asr as asr
        _, dtype = self.setup()
        target = Path(self.config['model']).expanduser()
        if not target.is_file():
            folder = Path(local_snapshot(self.config))
            weights = list(folder.glob('*.nemo'))
            if len(weights) != 1:
                raise ValueError('Cần thư mục chứa đúng một .nemo hoặc đường dẫn file .nemo.')
            target = weights[0]
        self.model = asr.models.ASRModel.restore_from(str(target), map_location=self.config['device'])
        self.model = self.model.to(device=self.config['device'], dtype=dtype).eval()

    def transcribe(self, audio_path, language):
        kwargs = {'batch_size': 1}
        if 'canary' in self.config['model'].lower() or 'canary' in type(self.model).__name__.lower():
            kwargs.update(source_lang=language, target_lang=language)
        result = self.model.transcribe([str(audio_path)], **kwargs)
        if isinstance(result, tuple):
            result = result[0]
        return {'text': ' '.join(r if isinstance(r, str) else r.text for r in result)}


class SenseVoiceAdapter(TorchAdapter):
    def load(self):
        from funasr import AutoModel
        import funasr.models.sense_voice.model
        self.setup()
        self.model = AutoModel(model=local_snapshot(self.config), device=self.config['device'],
                               disable_update=True, trust_remote_code=False)

    def transcribe(self, audio_path, language):
        import re
        audio = samples(audio_path)
        rows = []
        for start in range(0, len(audio), 30 * 16000):
            rows.extend(self.model.generate(input=audio[start:start + 30 * 16000], cache={},
                                            language=language, use_itn=False, batch_size_s=30))
        return {'text': ' '.join(re.sub(r'<\|[^|]*\|>', '', r['text']).strip() for r in rows)}


class VoskAdapter:
    def __init__(self, config):
        self.config, self.model = config, None

    def load(self):
        from vosk import Model
        target = Path(self.config['model']).expanduser()
        if not target.is_dir():
            raise ValueError('Vosk cần đường dẫn model đã giải nén từ https://alphacephei.com/vosk/models .')
        self.model = Model(str(target.resolve()))

    def transcribe(self, audio_path, language):
        from vosk import KaldiRecognizer
        texts = []
        with wave.open(str(audio_path), 'rb') as audio:
            if (audio.getnchannels(), audio.getsampwidth()) != (1, 2):
                raise ValueError('Vosk cần WAV PCM16 mono.')
            rec = KaldiRecognizer(self.model, audio.getframerate())
            while True:
                data = audio.readframes(4000)
                if not data:
                    break
                if rec.AcceptWaveform(data):
                    texts.append(json.loads(rec.Result()).get('text', ''))
            texts.append(json.loads(rec.FinalResult()).get('text', ''))
        return {'text': ' '.join(texts).strip()}

    def close(self):
        self.model = None
        gc.collect()


class ElevenLabsAdapter:
    def __init__(self, config):
        self.config = config

    def load(self):
        import requests
        if not os.environ.get('ELEVENLABS_API_KEY'):
            raise ValueError('Thiếu biến môi trường ELEVENLABS_API_KEY của server.')

    def transcribe(self, audio_path, language):
        import requests
        with open(audio_path, 'rb') as audio:
            response = requests.post('https://api.elevenlabs.io/v1/speech-to-text',
                headers={'xi-api-key': os.environ['ELEVENLABS_API_KEY']},
                files={'file': (Path(audio_path).name, audio, 'audio/wav')},
                data={'model_id': self.config['model'], 'language_code': {'en': 'eng', 'vi': 'vie'}[language],
                      'tag_audio_events': 'false', 'diarize': 'false'}, timeout=(15, 600))
        if not response.ok:
            raise ValueError(f'ElevenLabs HTTP {response.status_code}; kiểm tra key, quota và model.')
        result = response.json()
        return {'text': result['text'], 'detected_language': result.get('language_code')}

    def close(self):
        pass


class GoogleChirpAdapter:
    def __init__(self, config):
        self.config = config

    def load(self):
        from google.cloud import speech_v2
        from google.api_core.client_options import ClientOptions
        self.project = os.environ.get('GOOGLE_CLOUD_PROJECT')
        self.location = os.environ.get('GOOGLE_CLOUD_LOCATION')
        if not self.project or not self.location:
            raise ValueError('Cần GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION và Google ADC.')
        self.client = speech_v2.SpeechClient(client_options=ClientOptions(api_endpoint=f'{self.location}-speech.googleapis.com'))

    def transcribe(self, audio_path, language):
        from google.cloud.speech_v2.types import cloud_speech
        with wave.open(str(audio_path), 'rb') as audio:
            if audio.getnframes() / audio.getframerate() > 60:
                raise ValueError('Chirp synchronous giới hạn 60 giây/mẫu; dùng dataset đoạn ngắn.')
        config = cloud_speech.RecognitionConfig(auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
                    language_codes=[{'en': 'en-US', 'vi': 'vi-VN'}[language]], model=self.config['model'])
        result = self.client.recognize(request=cloud_speech.RecognizeRequest(
            recognizer=f'projects/{self.project}/locations/{self.location}/recognizers/_',
            config=config, content=Path(audio_path).read_bytes()), timeout=600)
        return {'text': ' '.join(r.alternatives[0].transcript for r in result.results if r.alternatives)}

    def close(self):
        if hasattr(self, 'client'):
            self.client.transport.close()
