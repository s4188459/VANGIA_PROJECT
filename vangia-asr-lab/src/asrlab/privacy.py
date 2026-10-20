"""Aggregate-only export and explicitly scoped evidence deletion."""
import shutil
from pathlib import Path
from .common import read_json,write_json
from .storage import audit


def export_redacted(run_dir,out):
    path=Path(run_dir)
    if not audit(path)['ok']:raise ValueError('Cannot export corrupted evidence')
    manifest=read_json(path/'manifest.json');metrics=read_json(path/'metrics.json')
    allowed=('sample_count','configuration_count','completed','failed','reference_words','duration_s',
             'missing_audio_count','live_lag_p95_s','rtf','rtfx','load_s','inference_service_s','offline_turnaround_s',
             'completion_fraction','peak_worker_rss_bytes','error_count')
    result={'input_mode':manifest['input_mode'],'dataset_split':manifest['dataset_split'],
            'evidence_class':manifest['evidence_class'],'scientific_status':'INSUFFICIENT EVIDENCE',
            'provisional_targets':'15% WER / 3s P95: not validated',
            'metrics':{k:metrics[k] for k in allowed if k in metrics},
            'redaction':'transcripts, IDs, local paths, error strings, reviewers and raw audio excluded'}
    for policy in ('raw','normalized'):
        if policy in metrics:result[policy]={k:metrics[policy].get(k) for k in ('wer_micro','wer_macro_utterance','S','D','I','numerator','denominator','cer')}
    write_json(out,result,exclusive=True);return result


def delete_run(run_dir,confirmed_run_id):
    path=Path(run_dir).resolve()
    manifest=read_json(path/'manifest.json')
    if not confirmed_run_id or confirmed_run_id!=manifest['run_id']:raise ValueError('Exact run ID confirmation required')
    if path==path.anchor or not (path/'checksums.json').is_file():raise ValueError('Only a sealed run directory can be deleted')
    # Original recordings referenced elsewhere are never removed by deleting an evidence run.
    shutil.rmtree(path)
    return {'deleted_run_id':confirmed_run_id,'original_external_audio_deleted':False}
