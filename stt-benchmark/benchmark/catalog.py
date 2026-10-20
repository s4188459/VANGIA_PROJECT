"""Curated checkpoints, not a promise that weights/dependencies are installed."""
import importlib.util
import os
import json
from pathlib import Path

BACKENDS = {
    'faster-whisper': ('faster_whisper', 'faster-whisper==1.2.1'),
    'transformers-whisper': ('transformers', 'transformers torch soundfile'),
    'transformers-ctc': ('transformers', 'transformers torch soundfile'),
    'qwen-asr': ('qwen_asr', 'qwen-asr'),
    'nemo': ('nemo.collections.asr', 'nemo_toolkit[asr]'),
    'sensevoice': ('funasr', 'funasr torch torchaudio'),
    'fun-asr-mlt': ('funasr.models.fun_asr_nano.model', 'funasr>=1.4.1 torch torchaudio transformers tiktoken'),
    'vosk': ('vosk', 'vosk'),
    'elevenlabs': ('requests', 'requests'),
    'google-chirp': ('google.cloud.speech_v2', 'google-cloud-speech'),
}


def backend_status():
    result = {}
    checks_path = Path(__file__).resolve().parents[1] / 'data' / 'backend-checks.json'
    try:
        checks = json.loads(checks_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        checks = {}
    for name, (module, install) in BACKENDS.items():
        try:
            available = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError, AttributeError):
            available = False
        result[name] = {'installed': available, 'install': install,
                        'note': 'Library detected; weights and GPU availability not verified.' if available else 'Library is not installed in the server Python environment.'}
        env = Path(__file__).resolve().parents[1] / '.backends' / name
        python = env / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if name == 'fun-asr-mlt' and not python.is_file():
            python = env.parent / 'sensevoice' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        result[name]['python_executable'] = str(python) if python.is_file() else ''
        checked = checks.get(name)
        if checked and checked.get('python_executable') == (str(python) if python.is_file() else __import__('sys').executable):
            result[name]['import_checked'] = checked['import_ok']
            result[name]['note'] = 'Backend import verified; model weights are checked separately.' if checked['import_ok'] else checked.get('error', 'Backend import failed')[-1200:]
    result['elevenlabs']['credentials'] = bool(os.environ.get('ELEVENLABS_API_KEY'))
    result['google-chirp']['credentials'] = bool(os.environ.get('GOOGLE_CLOUD_PROJECT') and os.environ.get('GOOGLE_CLOUD_LOCATION'))
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
        add('Qwen/Qwen3-ASR-' + size, 'qwen-asr', ['en', 'vi'], 'A separate qwen-asr environment is recommended.')
    for name, languages in [('parakeet-tdt-0.6b-v2', ['en']), ('parakeet-tdt-0.6b-v3', ['en']),
                            ('parakeet-ctc-0.6b-Vietnamese', ['vi']), ('canary-1b-v2', ['en'])]:
        add('nvidia/' + name, 'nemo', languages, 'NeMo: Linux/GPU is generally recommended; Parakeet v2 has also been tested on this Windows CPU.')
    add('FunAudioLLM/SenseVoiceSmall', 'sensevoice', ['en'])
    add('FunAudioLLM/Fun-ASR-MLT-Nano-2512', 'fun-asr-mlt', ['en', 'vi'],
        'MLT checkpoint only. Experimental CPU candidate; mixed-language quality and live latency are not verified.')
    add('facebook/wav2vec2-large-960h-lv60-self', 'transformers-ctc', ['en'])
    add('nguyenvulebinh/wav2vec2-base-vietnamese-250h', 'transformers-ctc', ['vi'], 'Greedy CTC decoding; no external language model.')
    add('facebook/mms-1b-all', 'transformers-ctc', ['en', 'vi'], 'Selects the eng/vie adapter for the dataset; CC-BY-NC.')
    for name, lang in [('vosk-model-small-en-us-0.15', 'en'), ('vosk-model-en-us-0.22', 'en'),
                       ('vosk-model-small-vn-0.4', 'vi'), ('vosk-model-vn-0.4', 'vi')]:
        add(name, 'vosk', [lang], 'Uses the local cache; when downloads are enabled, official models are downloaded and extracted from alphacephei.com.')
    add('scribe_v2', 'elevenlabs', ['en', 'vi'], 'Paid cloud service; requires ELEVENLABS_API_KEY. Audio is sent to ElevenLabs.')
    add('chirp_3', 'google-chirp', ['en', 'vi'], 'Paid cloud service; requires ADC, GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION. This adapter accepts files up to 60 seconds.')
    groups = {
        'vi-video': {'large-v3', 'large-v2', 'Qwen/Qwen3-ASR-1.7B',
                     'Qwen/Qwen3-ASR-0.6B', 'vinai/PhoWhisper-large'},
        'vi-live': {'small', 'medium', 'Qwen/Qwen3-ASR-0.6B',
                    'vinai/PhoWhisper-small', 'FunAudioLLM/Fun-ASR-MLT-Nano-2512'},
    }
    for row in rows:
        row['sets'] = [name for name, models in groups.items() if row['model'] in models]
    return rows


def catalog_with_cache_status():
    """Read-only hints, never proof that a downloaded snapshot is complete."""
    rows = catalog()
    root = Path(__file__).resolve().parents[1]
    for row in rows:
        repo = row['model']
        if row['backend'] == 'faster-whisper' and '/' not in repo:
            repo = 'mobiuslabsgmbh/faster-whisper-large-v3-turbo' if repo == 'turbo' else 'Systran/faster-whisper-' + repo
        cache_name = 'models--' + repo.replace('/', '--')
        roots = [root / 'data' / 'hf-cache', Path.home() / '.cache' / 'huggingface' / 'hub']
        found = any((cache / cache_name / 'snapshots').is_dir() and
                    any((cache / cache_name / 'snapshots').iterdir()) for cache in roots)
        row['weight_status'] = 'Cache detected; completeness checked at load' if found else 'No cache detected; enable downloads or use a local configuration'
    return rows


def supported_languages(config):
    declared = config.get('languages', ['en', 'vi'])
    match = next((r for r in catalog() if r['backend'] == config['backend'] and r['model'] == config['model']), None)
    languages = match['languages'] if match else declared
    name = config['model'].replace('\\', '/').rstrip('/').split('/')[-1].lower()
    if config['backend'] in ('faster-whisper', 'transformers-whisper') and (name.endswith(('.en', '-en')) or 'distil-' in name):
        languages = ['en']
    return languages
