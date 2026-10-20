"""Strict import of the supplied historical whole-file experiment."""
import csv
import math
import shutil
from pathlib import Path

from .common import digest, read_json, registry, sha256, utcnow, write_json
from .storage import create_run, index_evidence, seal, write_jsonl


def _equal(a, b):
    if a is None:
        return b in ('', None)
    if isinstance(a, (float, int)):
        return b not in ('', None) and math.isclose(float(a), float(b), rel_tol=1e-11, abs_tol=1e-11)
    return a == b


def import_legacy(json_path, csv_path, out):
    original = read_json(json_path)
    with Path(csv_path).open(encoding='utf-8-sig', newline='') as f:
        csv_rows = list(csv.DictReader(f))
    samples = original['dataset']['samples']
    ids = [s['id'] for s in samples]
    expected_ids = {f'EN{i:03}' for i in range(1, 101)}
    if len(ids) != 100 or set(ids) != expected_ids:
        raise ValueError('Historical sample IDs must be unique EN001..EN100')
    if original['options']['mode'] != 'final' or original['options']['protocol'] != 'full-file-v1':
        raise ValueError('Expected historical full-file-v1 final protocol')
    if original['normalization'] != 'nfkc-casefold-punctuation-to-space-v1':
        raise ValueError('Historical normalization changed')
    if original['cer_normalization'] != 'same-as-wer-without-whitespace-v1':
        raise ValueError('Historical CER normalization changed')
    models = original['models']
    labels = [m['config']['label'] for m in models]
    csv_labels = [r['model'] for r in csv_rows]
    if len(models) != 27 or len(set(labels)) != 27 or len(csv_rows) != 27 or set(csv_labels) != set(labels):
        raise ValueError('Historical configuration reconciliation: expected 27 unique matching rows')
    if (sum(m['status'] == 'completed' for m in models), sum(m['status'] == 'error' for m in models)) != (25, 2):
        raise ValueError('Expected 25 completed and 2 errors')
    duration = original['dataset']['duration_s']
    if not math.isclose(sum(s['duration_s'] for s in samples), 3111.93575, abs_tol=1e-7) or not math.isclose(duration, 3111.93575):
        raise ValueError('Historical sample duration mismatch')
    if sum(s['reference_words'] for s in samples) != 5024:
        raise ValueError('Historical reference words mismatch')
    by_csv = {r['model']: r for r in csv_rows}
    candidates = registry()['models']
    selected = {m['legacy_label']: m for m in candidates}
    configurations, predictions = [], []
    references = {}
    for model in models:
        config, summary = model['config'], model['summary']
        label = config['label']
        row = by_csv[label]
        fields = {**summary, 'backend': config['backend'], 'mode': 'final', 'language': 'en',
                  'status': model['status'], 'load_s': model['load_s'], 'error': model.get('error', ''),
                  'common_sample_count': original['common_sample_count'],
                  'common_wer': model['common_summary']['wer'], 'common_cer': model['common_summary']['cer']}
        for key in row:
            if key != 'model' and (key not in fields or not _equal(fields[key], row[key])):
                raise ValueError(f'CSV reconciliation mismatch: {label}/{key}')
        config_id = digest(config)
        c = selected.get(label)
        if c:
            for metric in ('wer', 'cer', 'rtf'):
                if not _equal(summary[metric], c['legacy_'+metric]):
                    raise ValueError(f'Registry reconciliation mismatch: {label}/{metric}')
        if model['status'] == 'completed':
            model_ids = [s['id'] for s in model['samples']]
            if len(model_ids) != 100 or set(model_ids) != expected_ids:
                raise ValueError(f'Invalid model sample IDs: {label}')
            for field in ('reference_words', 'errors', 'character_errors', 'reference_characters'):
                if sum(s[field] for s in model['samples']) != summary[field]:
                    raise ValueError(f'Historical aggregate mismatch: {label}/{field}')
            for sample in model['samples']:
                if sample['id'] in references and references[sample['id']]['text'] != sample['reference']:
                    raise ValueError('Reference mismatch across configurations')
                references[sample['id']] = {'sample_id': sample['id'], 'text': sample['reference'],
                    'reference_revision': digest(sample['reference']), 'quality': 'unverified',
                    'word_alignment': None, 'missing_reason': 'missing_audio'}
                predictions.append({'config_id': config_id, 'sample_id': sample['id'],
                                    'provenance_type': 'historical_import', **sample})
        elif summary['wer'] is not None or not model.get('error'):
            raise ValueError('Failed configuration cannot have a WER')
        configurations.append({'config_id': config_id, 'label': label, 'config': config,
            'model_id': c['canonical_model_id'] if c else None,
            'candidate': bool(c), 'roles': c['roles'] if c else ['archive_only'],
            'status': model['status'], 'error': model.get('error'), 'load_s': model['load_s'],
            'checkpoint_resolution_status': c['checkpoint_resolution_status'] if c else 'archive_only',
            **summary, 'live_lag_p95_s': None, 'live_missing_reason': 'not_measured',
            'evidence_class': 'E-LOCAL', 'input_mode': 'historical_whole_file'})
    hashes = {'legacy.json': sha256(json_path), 'legacy.csv': sha256(csv_path)}
    manifest = {'run_id': original['id'], 'schema_version': '1.0', 'language': 'en',
        'dataset_id': original['dataset']['id'], 'dataset_split': 'legacy_development',
        'input_mode': 'historical_whole_file', 'created_utc': utcnow(), 'evidence_class': 'E-LOCAL',
        'status': 'completed', 'normalization_version': original['normalization'],
        'source_hashes': hashes, 'historical_environment': original['environment'],
        'historical_options': original['options'], 'source_urls': [c['model_card_url'] for c in candidates],
        'missing_reasons': ['missing_audio', 'no_reference_alignment', 'live_timing_not_measured', 'unverified_weight_revision']}
    path = create_run(out, manifest)
    shutil.copyfile(json_path, path/'legacy.json')
    shutil.copyfile(csv_path, path/'legacy.csv')
    metrics = {'sample_count': 100, 'configuration_count': 27, 'completed': 25, 'failed': 2,
        'reference_words': 5024, 'duration_s': duration, 'missing_audio_count': 100,
        'live_lag_p95_s': None, 'configurations': configurations, 'candidates': candidates,
        'evidence_class': 'E-LOCAL', 'status': 'INSUFFICIENT EVIDENCE',
        'input_mode': 'historical_whole_file', 'normalization_version': original['normalization'],
        'provisional_gates': {'wer': .15, 'p95_live_lag_s': 3, 'validated': False},
        'source_hashes': hashes}
    write_json(path/'metrics.json', metrics)
    write_json(path/'samples.json', samples)
    write_jsonl(path/'reference.jsonl', references.values())
    write_jsonl(path/'predictions.jsonl', predictions)
    index_evidence(path, configurations, samples)
    from .reports import report
    report(path)
    seal(path)
    return metrics
