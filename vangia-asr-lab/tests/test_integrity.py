import json
import threading
from pathlib import Path
import pytest
from test_core import module,event,wav
from asrlab.common import read_json,sha256


def test_historical_normalizer_reproduces_all_saved_tokens():
    from test_legacy import JSON
    from asrlab.metrics import normalize,score
    data=read_json(JSON)
    for model in data['models']:
        if model['status']!='completed':continue
        for row in model['samples']:
            assert normalize(row['reference'])==row['normalized_reference']
            assert normalize(row['hypothesis'])==row['normalized_hypothesis']
            value=score(row['reference'],row['hypothesis'])
            assert value['errors']==row['errors']
            assert value['character_errors']==row['character_errors']


def test_review_keeps_audit_valid_and_rejects_unknown_sample(tmp_path):
    from asrlab.runner import run
    from asrlab.review import annotate,sign_off
    from asrlab.storage import audit
    from asrlab.common import digest
    path=tmp_path/'run';run({'mode':'synthetic_fixture','out':str(path)})
    manifest=read_json(path/'manifest.json')
    a=dict(annotation_id='a',run_id=manifest['run_id'],sample_id='fixture-1',reference_revision=digest('the sample is synthetic'),
           reviewer_id='reviewer',category='other',severity='minor',review_status='first_review')
    annotate(path,a)
    assert audit(path)['ok']
    with pytest.raises(ValueError,match='sample'):annotate(path,{**a,'annotation_id':'b','sample_id':'unknown'})
    sign_off(path,'reviewer','Fixture review only')
    assert audit(path)['ok']


def test_audit_rejects_semantically_invalid_events_even_when_resealed(tmp_path):
    from asrlab.runner import run
    from asrlab.storage import audit,seal
    path=tmp_path/'run';run({'mode':'synthetic_fixture','out':str(path)})
    with (path/'events.jsonl').open('a') as f:f.write(json.dumps(event())+'\n')
    seal(path)
    assert not audit(path)['ok']


def test_redacted_summary_has_no_transcripts_paths_ids(tmp_path):
    m=module('privacy')
    from asrlab.runner import run
    path=tmp_path/'run';run({'mode':'synthetic_fixture','out':str(path)})
    out=tmp_path/'redacted.json';m.export_redacted(path,out)
    text=out.read_text()
    assert 'the sample is synthetic' not in text
    assert str(path) not in text
    assert 'fixture-1' not in text
    assert 'SYNTHETIC' in text


def test_provenance_file_tamper_is_blocked(tmp_path):
    from asrlab.adapters import preflight
    folder=tmp_path/'weights';folder.mkdir();weight=folder/'model.bin';weight.write_bytes(b'weights')
    provenance=tmp_path/'provenance.json'
    provenance.write_text(json.dumps({'model_id':'openai/whisper-small.en','revision':'commit123','files':{'model.bin':sha256(weight)}}))
    cfg={'model_id':'openai/whisper-small.en','weights_path':str(folder),'artifact_provenance':str(provenance)}
    weight.write_bytes(b'changed')
    assert any('hash mismatch' in r for r in preflight(cfg)['reasons'])


def test_vad_adaptive_boundaries_preserve_complete_audio():
    m=module('audio')
    assert hasattr(m,'adaptive_windows'),'adaptive energy VAD is not implemented'
    from array import array
    pcm=array('h',[8000]*8000+[0]*8000+[8000]*8000).tobytes()
    chunks=list(m.adaptive_windows(pcm,16000,min_s=.25,max_s=1.2,silence_s=.1,threshold=.01))
    assert len(chunks)>=2
    assert chunks[0]['start_sample']==0 and chunks[-1]['end_sample']==24000
    assert all(a['end_sample']==b['start_sample'] for a,b in zip(chunks,chunks[1:]))
    assert b''.join(c['pcm'] for c in chunks)==pcm


def test_invalid_run_options_rejected_before_output(tmp_path):
    from asrlab.runner import run
    with pytest.raises(ValueError,match='chunk'):
        run({'model_id':'openai/whisper-small.en','mode':'paced_replay','chunk_seconds':0,'out':str(tmp_path/'bad')})
    assert not (tmp_path/'bad').exists()
