import csv
import json
import zipfile
import pytest
from asrlab.common import read_json,write_json,digest,sha256
from asrlab.storage import create_run,write_jsonl,seal


def evidence(tmp_path,failed=False):
    path=tmp_path/'run'
    refs=[{'sample_id':'a','text':'one two','session_id':'s','speaker_id':'p','domain':'=BAD()',
           'pcm_sha256':'a','reference_revision':digest('one two'),'duration_s':1},
          {'sample_id':'b','text':'one two three four five six eight nine','session_id':'s','speaker_id':'p','domain':'=BAD()',
           'pcm_sha256':'b','reference_revision':digest('one two three four five six eight nine'),'duration_s':3}]
    create_run(path,{'run_id':'test-run','schema_version':'1.0','language':'en','dataset_id':'d','dataset_split':'synthetic_fixture',
        'input_mode':'synthetic_fixture','created_utc':'2026-10-16T00:00:00Z','evidence_class':'SYNTHETIC','status':'planned',
        'model_config_id':'c','dataset_hash':digest(refs),'config':{'samples':refs}})
    write_jsonl(path/'reference.jsonl',refs)
    write_jsonl(path/'predictions.jsonl',[{'sample_id':'a','text':'one','status':'completed','service_s':.1},
        {'sample_id':'b','text':None if failed else refs[1]['text'],'status':'failed' if failed else 'completed','error':'timeout' if failed else None}])
    write_json(path/'state.json',{'status':'failed' if failed else 'completed'})
    write_json(path/'metrics.json',{'rtf':None,'live_lag_p95_s':None})
    seal(path);return path


def test_export_parity_micro_macro_dictionary_and_source_immutable(tmp_path):
    from asrlab.analysis_export import export_analysis,validate_bundle
    source=evidence(tmp_path);before=sha256(source/'checksums.json');out=tmp_path/'export'
    export_analysis(source,out)
    assert validate_bundle(out)['ok']
    data=read_json(out/'results.json');run=data['runs'][0]
    assert run['normalized_wer_micro']==.1
    assert run['normalized_wer_macro_utterance']==.25
    assert run['metrics']['normalized_wer_micro']['numerator']==1
    assert run['metrics']['normalized_wer_micro']['denominator']==10
    assert run['metrics']['word_first_presented_lag_p95_s']['value'] is None
    assert run['metrics']['word_first_presented_lag_p95_s']['missing_reason']
    assert (out/'sample_metrics.csv').read_bytes().startswith(b'\xef\xbb\xbf')
    rows=list(csv.DictReader((out/'sample_metrics.csv').open(encoding='utf-8-sig')))
    assert len(rows)==2 and rows[0]['domain']=="'=BAD()"
    assert float(rows[0]['normalized_wer'])==.5
    assert sha256(source/'checksums.json')==before
    assert len(data['transcripts'])==len(data['samples'])==2
    assert data['groups'][0]['normalized_denominator']==10
    dictionary=list(csv.DictReader((out/'data_dictionary.csv').open(encoding='utf-8-sig')))
    assert any(r['column']=='normalized_wer' and r['unit']=='ratio' for r in dictionary)
    with pytest.raises(FileExistsError):export_analysis(source,out)
    with pytest.raises(ValueError,match='source'):export_analysis(source,source/'export')


def test_failures_stay_in_denominators_and_transcripts_not_empty_success(tmp_path):
    from asrlab.analysis_export import export_analysis
    source=evidence(tmp_path,True);out=tmp_path/'export';export_analysis(source,out)
    data=read_json(out/'results.json');run=data['runs'][0]
    assert run['planned']==2 and run['completed']==1 and run['failed']==1
    assert run['normalized_wer_micro'] is None
    assert run['conditional_normalized_wer_micro']==.5 and run['completion_fraction']==.5
    assert len(data['samples'])==2 and data['samples'][1]['normalized_wer'] is None
    assert data['transcripts'][1]['hypothesis'] is None
    assert data['groups'][0]['normalized_wer_micro'] is None
    assert data['failures'][0]['sample_id']=='b'
    rows=list(csv.DictReader((out/'sample_metrics.csv').open(encoding='utf-8-sig')))
    assert rows[1]['normalized_wer']==''


def test_cancelled_campaign_exports_all_planned_samples(tmp_path):
    from test_benchmark import dataset
    from asrlab.benchmark import create_benchmark,cancel_benchmark,run_benchmark,preset
    from asrlab.analysis_export import export_analysis
    source=dataset(tmp_path);campaign=tmp_path/'campaign'
    create_benchmark(source,[preset('openai/whisper-small.en')],campaign,repeats=2)
    cancel_benchmark(campaign);run_benchmark(campaign)
    export_analysis(campaign,tmp_path/'out.zip')
    with zipfile.ZipFile(tmp_path/'out.zip') as z:data=json.loads(z.read('results.json'))
    assert len(data['runs'])==2 and len(data['samples'])==2
    assert all(s['status']=='cancelled' for s in data['samples'])
    assert all(s['normalized_wer'] is None for s in data['samples'])


def test_integrity_and_schema_validation_reject_tampered_or_nonfinite_export(tmp_path):
    from asrlab.analysis_export import export_analysis,validate_bundle
    source=evidence(tmp_path);out=tmp_path/'export';export_analysis(source,out)
    with (out/'sample_metrics.csv').open('a') as f:f.write('tampered')
    assert not validate_bundle(out)['ok']
    write_json(source/'state.json',{'status':'changed'})
    with pytest.raises(ValueError,match='integrity'):export_analysis(source,tmp_path/'other')


def test_sample_group_metric_envelopes_and_legacy_resource_gaps(tmp_path):
    from asrlab.analysis_export import collect_results
    source=evidence(tmp_path)
    write_json(source/'metrics.json',{'peak_worker_rss_bytes':1234,'resource_samples':2})
    seal(source)
    data=collect_results(source)
    assert data['samples'][0]['metrics']['normalized_wer']['value']==.5
    assert data['samples'][0]['metrics']['normalized_wer']['denominator']==2
    assert data['groups'][0]['metrics']['normalized_wer_micro']['value']==.1
    assert data['runs'][0]['peak_worker_rss_bytes'] is None
    assert data['runs'][0]['metrics']['peak_worker_rss_bytes']['missing_reason']=='resource_scope_unverified'


def test_export_cannot_write_into_other_sealed_evidence(tmp_path):
    from asrlab.analysis_export import export_analysis
    source=evidence(tmp_path);other=tmp_path/'other';other.mkdir()
    write_json(other/'manifest.json',{'run_id':'other'});write_json(other/'checksums.json',{})
    with pytest.raises(ValueError,match='evidence'):export_analysis(source,other/'new-export')


def test_compare_runs_rejects_modes_and_failure_subsets_and_keeps_unknown_clusters(tmp_path):
    from asrlab.analysis_export import compare_runs
    source=evidence(tmp_path)
    result=compare_runs(source,'test-run','c',source,'test-run','c')
    assert result['clusters']==1 and result['difference_b_minus_a']==0
    manifest=read_json(source/'manifest.json');manifest['input_mode']='batch_file';write_json(source/'manifest.json',manifest);seal(source)
    # Unlike mode comparisons should not be silently pooled; explicit same-mode input is required.
    second=tmp_path/'second';second.mkdir()
    import shutil
    shutil.copytree(source,second/'run')
    manifest['input_mode']='paced_replay';write_json(second/'run/manifest.json',manifest);seal(second/'run')
    with pytest.raises(ValueError,match='mode'):compare_runs(source,'test-run','c',second/'run','test-run','c')
