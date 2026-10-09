"""Curated checkpoints, not a promise that weights/dependencies are installed."""
import importlib.util
import os
from pathlib import Path

BACKENDS = {
    'faster-whisper': ('faster_whisper', 'faster-whisper==1.2.1'),
    'transformers-whisper': ('transformers', 'transformers torch soundfile'),
    'transformers-ctc': ('transformers', 'transformers torch soundfile'),
    'qwen-asr': ('qwen_asr', 'qwen-asr'),
    'nemo': ('nemo.collections.asr', 'nemo_toolkit[asr]'),
    'sensevoice': ('funasr', 'funasr torch torchaudio'),
    'vosk': ('vosk', 'vosk'),
    'elevenlabs': ('requests', 'requests'),
    'google-chirp': ('google.cloud.speech_v2', 'google-cloud-speech'),
}


def backend_status():
    result = {}
    for name, (module, install) in BACKENDS.items():
        try:
            available = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError, AttributeError):
            available = False
        result[name] = {'installed': available, 'install': install,
                        'note': 'Phát hiện thư viện; chưa xác nhận weights/GPU.' if available else 'Chưa cài thư viện trong Python của server.'}
        env = Path(__file__).resolve().parents[1] / '.backends' / name
        python = env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        result[name]['python_executable'] = str(python) if python.is_file() else ''
    result['elevenlabs']['credentials'] = bool(os.environ.get('ELEVENLABS_API_KEY'))
    result['google-chirp']['credentials'] = bool(os.environ.get('GOOGLE_CLOUD_PROJECT'))
    return result


def catalog():
    rows = []
    def add(model, backend, languages, note='', label=None):
        rows.append({'model': model, 'label': label or model.split('/')[-1],
                     'backend': backend, 'languages': languages, 'note': note})
    for name in ('tiny.en', 'base.en', 'small.en', 'medium.en'):
        add(name, 'faster-whisper', ['en'])
    for name in ('tiny', 'base', 'small', 'medium', 'large-v1', 'large-v2', 'large-v3', 'turbo'):
        add(name, 'faster-whisper', ['en', 'vi'])
    for name in ('distil-small.en', 'distil-medium.en', 'distil-large-v2', 'distil-large-v3'):
        add(name, 'faster-whisper', ['en'])
    add('distil-whisper/distil-large-v3.5-ct2', 'faster-whisper', ['en'])
    for size in ('tiny', 'base', 'small', 'medium', 'large'):
        add('vinai/PhoWhisper-' + size, 'transformers-whisper', ['vi'])
    for size in ('0.6B', '1.7B'):
        add('Qwen/Qwen3-ASR-' + size, 'qwen-asr', ['en', 'vi'], 'Môi trường qwen-asr riêng được khuyến nghị.')
    for name, languages in [('parakeet-tdt-0.6b-v2', ['en']), ('parakeet-tdt-0.6b-v3', ['en']),
                            ('parakeet-ctc-0.6b-Vietnamese', ['vi']), ('canary-1b-v2', ['en'])]:
        add('nvidia/' + name, 'nemo', languages, 'NeMo: nên dùng môi trường Linux/WSL có GPU; kiểm tra cài đặt trước.')
    add('FunAudioLLM/SenseVoiceSmall', 'sensevoice', ['en'])
    add('facebook/wav2vec2-large-960h-lv60-self', 'transformers-ctc', ['en'])
    add('nguyenvulebinh/wav2vec2-base-vietnamese-250h', 'transformers-ctc', ['vi'], 'CTC greedy; chưa dùng language model ngoài.')
    add('facebook/mms-1b-all', 'transformers-ctc', ['en', 'vi'], 'Chọn adapter eng/vie theo dataset; CC-BY-NC.')
    for name, lang in [('vosk-model-small-en-us-0.15', 'en'), ('vosk-model-en-us-0.22', 'en'),
                       ('vosk-model-small-vn-0.4', 'vi'), ('vosk-model-vn-0.4', 'vi')]:
        add(name, 'vosk', [lang], 'Tải/giải nén từ alphacephei.com/vosk/models rồi thay tên bằng đường dẫn local.')
    add('scribe_v2', 'elevenlabs', ['en', 'vi'], 'Cloud có phí; cần ELEVENLABS_API_KEY. Audio gửi ElevenLabs.')
    add('chirp_3', 'google-chirp', ['en', 'vi'], 'Cloud có phí; cần ADC, GOOGLE_CLOUD_PROJECT và GOOGLE_CLOUD_LOCATION. File tối đa 60 giây trong adapter này.')
    return rows


def supported_languages(config):
    declared = config.get('languages', ['en', 'vi'])
    match = next((r for r in catalog() if r['backend'] == config['backend'] and r['model'] == config['model']), None)
    languages = match['languages'] if match else declared
    name = config['model'].replace('\\', '/').rstrip('/').split('/')[-1].lower()
    if config['backend'] in ('faster-whisper', 'transformers-whisper') and (name.endswith(('.en', '-en')) or 'distil-' in name):
        languages = ['en']
    return languages
