"""Small dependency-free integrity check; does not perform ASR inference."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "data/legacy/STT-EN(1).json"
CSV_PATH = ROOT / "data/legacy/Testing_STT_Model_English_Version(1).csv"


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    experiment = json.loads(JSON_PATH.read_text(encoding='utf-8'))
    with CSV_PATH.open(encoding='utf-8-sig', newline='') as f:
        summary = {row['model']: row for row in csv.DictReader(f)}
    models = experiment['models']
    assert len(experiment['dataset']['samples']) == 100
    assert len(models) == 27
    assert sum(model['status'] == 'completed' for model in models) == 25
    assert sum(model['status'] == 'error' for model in models) == 2
    assert experiment['options']['mode'] == 'final'
    assert experiment['options']['protocol'] == 'full-file-v1'
    assert abs(experiment['dataset']['duration_s'] - 3111.93575) < 1e-7
    checks = {'parakeet-tdt-0.6b-v2': 0.11285828025477707,
              'parakeet-tdt-0.6b-v3 [catalog]': 0.12679140127388536,
              'Qwen3-ASR-0.6B': 0.10071656050955415,
              'small.en': 0.15187101910828024,
              'small [catalog]': 0.15425955414012738,
              'large-v3 [catalog]': 0.09136146496815287,
              'large-v2 [catalog]': 0.09812898089171974,
              'canary-1b-v2 [catalog]': 0.10151273885350319,
              'turbo [catalog]': 0.10688694267515923}
    for label, expected_wer in checks.items():
        assert abs(float(summary[label]['wer']) - expected_wer) < 1e-11
    for failed in ('Qwen3-ASR-1.7B [catalog]', 'mms-1b-all [catalog]'):
        assert summary[failed]['status'] == 'error' and not summary[failed]['wer']
    registry = json.loads((ROOT/'config/model_registry.json').read_text())
    assert len([x for x in registry['models'] if 'diagnostic_retry' not in x['roles']]) == 9
    assert len([x for x in registry['models'] if 'diagnostic_retry' in x['roles']]) == 2
    print('PASS: 100 samples, 27 configs, 25 complete, 2 error, original whole-file protocol')
    print('PASS: all 9 primary + 2 deferred labels and historic metrics verified')
    print('sha256:', JSON_PATH.name, sha256(JSON_PATH))
    print('sha256:', CSV_PATH.name, sha256(CSV_PATH))
    print('NOTE: No playable audio, current live caption latency, or model weights included.')


if __name__ == '__main__':
    main()
