"""Canonical serialization and read-only application resources."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

_source_root = Path(__file__).resolve().parents[2]
_bundled_root = Path(__file__).resolve().parent / 'resources'
ROOT = Path(os.environ.get('ASRLAB_HOME', _source_root if (_source_root/'config/model_registry.json').is_file() else _bundled_root))


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def sha256(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write_json(path, value, exclusive=False):
    with Path(path).open('x' if exclusive else 'w', encoding='utf-8') as f:
        f.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def registry():
    return read_json(ROOT / 'config/model_registry.json')


def model_record(model_id):
    for m in registry()['models']:
        if model_id in (m['key'], m['canonical_model_id']):
            return m
    raise ValueError('Checkpoint is outside the configured candidate registry scope')
