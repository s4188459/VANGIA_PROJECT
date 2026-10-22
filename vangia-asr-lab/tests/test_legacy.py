import csv
import importlib.util
import json
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / 'Vangia_ASR_Selection_Codex_Package'
JSON = PACKAGE / 'data/legacy/STT-EN(1).json'
CSV = PACKAGE / 'data/legacy/Testing_STT_Model_English_Version(1).csv'


def importer():
    assert importlib.util.find_spec('asrlab.legacy'), 'historical importer is not implemented'
    from asrlab.legacy import import_legacy
    return import_legacy


def test_original_evidence_parity(tmp_path):
    result = importer()(JSON, CSV, tmp_path / 'run')
    assert result['sample_count'] == 100
    assert result['configuration_count'] == 27
    assert result['completed'] == 25
    assert result['failed'] == 2
    assert result['reference_words'] == 5024
    assert result['duration_s'] == pytest.approx(3111.93575)
    assert result['live_lag_p95_s'] is None
    assert result['missing_audio_count'] == 100
    rows = {r['label']: r for r in result['configurations']}
    expected = {'parakeet-tdt-0.6b-v2': .11285828025477707,
                'parakeet-tdt-0.6b-v3 [catalog]': .12679140127388536,
                'Qwen3-ASR-0.6B': .10071656050955415,
                'small.en': .15187101910828024, 'small [catalog]': .15425955414012738,
                'large-v3 [catalog]': .09136146496815287,
                'large-v2 [catalog]': .09812898089171974,
                'canary-1b-v2 [catalog]': .10151273885350319,
                'turbo [catalog]': .10688694267515923}
    for label, value in expected.items():
        assert rows[label]['wer'] == pytest.approx(value, abs=1e-12)
    for label in ['Qwen3-ASR-1.7B [catalog]', 'mms-1b-all [catalog]']:
        assert rows[label]['wer'] is None
        assert rows[label]['error']
    assert len(result['candidates']) == 11
    assert sum('live' in c['roles'] for c in result['candidates']) == 5
    assert sum('offline' in c['roles'] for c in result['candidates']) == 6
    assert (tmp_path/'run/report.html').is_file()
    assert (tmp_path/'run/evidence.sqlite').is_file()
    from asrlab.storage import audit
    assert audit(tmp_path/'run')['ok']
    (tmp_path/'run/metrics.json').write_text('{}')
    assert not audit(tmp_path/'run')['ok']


def test_csv_disagreement_is_rejected(tmp_path):
    rows = list(csv.DictReader(CSV.open(encoding='utf-8-sig')))
    rows[0]['wer'] = '0.001'
    bad = tmp_path/'bad.csv'
    with bad.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0])
        writer.writeheader(); writer.writerows(rows)
    with pytest.raises(ValueError, match='reconciliation'):
        importer()(JSON, bad, tmp_path/'run')


def test_duplicate_samples_rejected(tmp_path):
    data = json.loads(JSON.read_text(encoding='utf-8'))
    data['dataset']['samples'][1]['id'] = 'EN001'
    bad = tmp_path/'bad.json'
    bad.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='sample'):
        importer()(bad, CSV, tmp_path/'run')


def test_import_cannot_overwrite_evidence(tmp_path):
    importer()(JSON, CSV, tmp_path/'run')
    with pytest.raises(FileExistsError):
        importer()(JSON, CSV, tmp_path/'run')
