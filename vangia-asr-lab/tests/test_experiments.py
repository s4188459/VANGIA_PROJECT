import importlib.util
from copy import deepcopy
import pytest
from test_core import module, wav


def test_worker_scope_and_missing_requirements(tmp_path):
    m=module('adapters')
    config={'model_id':'openai/whisper-small.en','mode':'batch_file','language':'en'}
    result=m.preflight(config)
    assert result['status']=='BLOCKED' and 'weights' in str(result['reasons'])
    with pytest.raises(ValueError,match='scope'):m.preflight({**config,'model_id':'openai/whisper-base'})
    with pytest.raises(ValueError,match='opt-in'):m.preflight({**config,'model_id':'facebook/mms-1b-all'})
    result=m.preflight({**config,'mode':'native_streaming'})
    assert 'native_streaming' in str(result['reasons'])
    assert result['capabilities']['native_streaming'] is False


def test_fixture_runner_is_synthetic_resumable_and_auditable(tmp_path):
    m=module('runner')
    cfg={'mode':'synthetic_fixture','out':str(tmp_path/'fixture'),'random_seed':7}
    result=m.run(cfg)
    assert result['status']=='completed' and result['evidence_class']=='SYNTHETIC'
    from asrlab.storage import audit,read_jsonl
    from asrlab.common import read_json
    assert audit(tmp_path/'fixture')['ok']
    assert read_json(tmp_path/'fixture/manifest.json')['dataset_split']=='synthetic_fixture'
    events=read_jsonl(tmp_path/'fixture/events.jsonl')
    assert events and all(e['provenance_type']=='simulated_fixture' for e in events)
    assert not any(e['event_type']=='caption_presentation_verified' for e in events)
    with pytest.raises(FileExistsError):m.run(cfg)
    assert m.run({**cfg,'resume':True})['status']=='completed'
    assert len(read_jsonl(tmp_path/'fixture/events.jsonl'))==len(events)


def test_real_run_missing_audio_is_blocked_not_invented(tmp_path):
    m=module('runner')
    cfg={'mode':'batch_file','out':str(tmp_path/'run'),'model_id':'openai/whisper-small.en',
         'language':'en','samples':[{'sample_id':'a','audio':'missing.wav','text':'hello'}]}
    r=m.run(cfg)
    assert r['status']=='blocked'
    from asrlab.storage import read_jsonl
    assert read_jsonl(tmp_path/'run/predictions.jsonl')==[]


def test_paired_bootstrap_rejects_unmatched_audio_and_failures():
    m=module('experiments')
    a=[{'sample_id':'a','session_id':'s1','pcm_sha256':'pcm1','reference_revision':'r1','N':10,'errors':2},
       {'sample_id':'b','session_id':'s2','pcm_sha256':'pcm2','reference_revision':'r2','N':10,'errors':4}]
    b=[{**r,'errors':r['errors']-1} for r in a]
    r=m.paired_bootstrap(a,b,seed=3,replicates=2000)
    assert r['difference_b_minus_a']==pytest.approx(-.1)
    assert r['ci95']==pytest.approx([-.1,-.1])
    assert r['clusters']==2 and r['unstable']
    b[0]['pcm_sha256']='different'
    with pytest.raises(ValueError,match='paired'):m.paired_bootstrap(a,b)
    with pytest.raises(ValueError,match='paired'):m.paired_bootstrap(a,b[:1])


def test_progressive_plan_never_adds_candidates_or_deferred_by_default():
    m=module('experiments')
    from asrlab.common import ROOT
    p=m.plan(ROOT/'config/experiment_matrix.json',seed=42)
    assert p['seed']==42
    assert len({j['job_id'] for j in p['jobs']})==len(p['jobs'])
    assert all(j.get('model_key') != 'mms_1b' for j in p['jobs'])
    assert any(j.get('model_key') == 'qwen_17' for j in p['jobs'])
    assert len(p['jobs'])<100
    assert p==m.plan(ROOT/'config/experiment_matrix.json',seed=42)


def test_annotations_and_signoff_cannot_validate_legacy(tmp_path):
    m=module('review')
    annotation=dict(annotation_id='a1',run_id='r',sample_id='s',reference_revision='ref',reviewer_id='human',
                    category='negation',severity='critical',review_status='first_review')
    m.annotate(tmp_path,annotation)
    with pytest.raises(ValueError,match='duplicate'):m.annotate(tmp_path,annotation)
    with pytest.raises(ValueError,match='adjudicator'):m.annotate(tmp_path,{**annotation,'annotation_id':'a2','review_status':'adjudicated'})
    r=m.decision({'input_mode':'historical_whole_file','dataset_split':'legacy_development'},
                 {'wer':.1,'p95':1},signoff={'reviewer':'human'})
    assert r['status']=='INSUFFICIENT EVIDENCE'
    assert r['validated'] is False


def test_pareto_requires_matched_modes_and_exposes_missingness():
    m=module('experiments')
    rows=[{'id':'a','mode':'batch_file','dataset_hash':'d','wer':.2,'turnaround_s':4},
          {'id':'b','mode':'batch_file','dataset_hash':'d','wer':.1,'turnaround_s':3},
          {'id':'c','mode':'batch_file','dataset_hash':'d','wer':None,'turnaround_s':2}]
    result=m.pareto(rows,['wer','turnaround_s'])
    assert result['frontier']==['b'] and result['missing']==['c']
    rows[1]['mode']='paced_replay'
    with pytest.raises(ValueError,match='mode'):m.pareto(rows,['wer','turnaround_s'])
