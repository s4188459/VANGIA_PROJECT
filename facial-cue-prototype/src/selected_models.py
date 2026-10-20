"""Historical experiment model resolvers; these are not current model selections."""
import os
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
CACHE = APP.parent / 'stt-benchmark' / 'data' / 'hf-cache'


def resolve_selected_model(repo, local_name, env_name):
    override = os.environ.get(env_name)
    local = Path(override) if override else APP / 'models' / local_name
    if local.is_dir():
        return local
    if not override:
        from huggingface_hub import snapshot_download
        try:
            patterns = ['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.*',
                        'preprocessor_config.json'] if repo.startswith('Systran/') else None
            return Path(snapshot_download(repo, cache_dir=str(CACHE), local_files_only=True,
                                          allow_patterns=patterns))
        except Exception:
            pass
    raise RuntimeError(f'Missing local model {repo}. Set {env_name} to its downloaded directory.')


def resolve_qwen_model():
    return resolve_selected_model('Qwen/Qwen3-ASR-0.6B', 'Qwen3-ASR-0.6B', 'FACIAL_QWEN_MODEL')


def resolve_large_model():
    return resolve_selected_model('Systran/faster-whisper-large-v3', 'faster-whisper-large-v3',
                                  'FACIAL_WHISPER_MODEL')
