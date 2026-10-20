import json
from pathlib import Path
import pytest
from asrlab.common import read_json,write_json,digest


def test_preregistration_detects_same_path_artifact_replacement(tmp_path):
    from asrlab.governance import preregister,check_registration
    identity=tmp_path/'identity.json';write_json(identity,{'revision':'a','files':{'model.bin':'hash-a'}})
    config={'model_id':'openai/whisper-small.en','artifact_provenance':str(identity)}
    dataset={'split':'holdout','sha256':'dataset'}
    record=preregister(tmp_path/'registered.json',dataset,[config],['wer'],'owner')
    write_json(identity,{'revision':'b','files':{'model.bin':'hash-b'}})
    with pytest.raises(ValueError,match='frozen'):check_registration(record,dataset,config)


def test_score_export_is_consumable_by_paired_comparison():
    from asrlab.metrics import corpus_score
    from asrlab.experiments import paired_bootstrap
    refs=[{'sample_id':'a','session_id':'session','pcm_sha256':'pcm','reference_revision':'ref','text':'hello world'}]
    a=corpus_score(refs,[{'sample_id':'a','text':'hello'}])['normalized']['per_sample']
    b=corpus_score(refs,[{'sample_id':'a','text':'hello world'}])['normalized']['per_sample']
    assert paired_bootstrap(a,b)['difference_b_minus_a']==-.5


def test_recover_interrupted_run_from_append_only_attempts(tmp_path):
    from asrlab import storage
    assert hasattr(storage,'recover_run')
    from asrlab.runner import run
    from asrlab.common import sha256
    path=tmp_path/'run';run({'mode':'synthetic_fixture','out':str(path)})
    # Model an interrupted writer: immutable witnesses remain, terminal seal absent,
    # attempts survived but the derived predictions snapshot and final event are truncated.
    (path/'checksums.json').unlink()
    write_json(path/'state.json',{'status':'running'})
    with (path/'prediction_attempts.jsonl').open('w') as f:
        f.write(json.dumps({'sample_id':'fixture-1','text':'recovered','status':'completed'})+'\n')
        f.write('{partial')
    (path/'predictions.jsonl').write_text('{partial')
    with (path/'events.jsonl').open('a') as f:f.write('{partial')
    result=storage.recover_run(path)
    assert result['status']=='failed'
    assert storage.read_jsonl(path/'predictions.jsonl')[0]['text']=='recovered'
    assert storage.audit(path)['ok']
    assert (path/'recovery/predictions.jsonl.original').read_text()=='{partial'


def test_recovery_refuses_changed_immutable_manifest(tmp_path):
    from asrlab import storage
    assert hasattr(storage,'recover_run')
    from asrlab.runner import run
    path=tmp_path/'run';run({'mode':'synthetic_fixture','out':str(path)})
    (path/'checksums.json').unlink();m=read_json(path/'manifest.json');m['language']='vi';write_json(path/'manifest.json',m)
    with pytest.raises(ValueError,match='immutable'):storage.recover_run(path)


def test_inline_holdout_members_cannot_be_relabelled_development(tmp_path):
    from asrlab.runner import run
    cfg={'model_id':'openai/whisper-small.en','out':str(tmp_path/'run'),'mode':'batch_file',
         'samples':[{'sample_id':'heldout-1','split':'holdout','audio':'missing.wav','text':'secret'}]}
    with pytest.raises(ValueError,match='split'):run(cfg)


def test_paired_export_keeps_shared_failed_samples():
    from asrlab import metrics
    from asrlab.experiments import paired_bootstrap
    assert hasattr(metrics,'paired_score_rows')
    refs=[{'sample_id':sid,'session_id':'session','pcm_sha256':'pcm-'+sid,
           'reference_revision':'ref','text':'hello world'} for sid in ('a','b')]
    preds=[{'sample_id':'a','status':'completed','text':'hello'},
           {'sample_id':'b','status':'failed','error':'timeout'}]
    rows=metrics.paired_score_rows(refs,preds)
    assert len(rows)==2 and rows[1]['errors'] is None
    with pytest.raises(ValueError,match='Incomplete'):
        paired_bootstrap(rows,rows)
