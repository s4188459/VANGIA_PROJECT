import json
import pytest
from test_core import module


def test_frame_stream_chunking_preserves_sample_clock():
    m=module('audio')
    assert hasattr(m,'frame_windows'),'live frame scheduler missing'
    frames=[b'\x01\x00'*320 for _ in range(10)]
    chunks=list(m.frame_windows(frames,16000,.06,.02))
    assert chunks[0]['start_sample']==0
    assert chunks[1]['start_sample']==640
    assert chunks[-1]['end_sample']==3200
    assert all(c['end_sample']-c['start_sample']<=960 for c in chunks)


def test_live_run_requires_explicit_capture_consent(tmp_path):
    from asrlab.runner import run
    cfg={'model_id':'openai/whisper-small.en','mode':'live_microphone','out':str(tmp_path/'live'),
         'capture_duration_s':1,'samples':[]}
    r=run(cfg)
    assert r['status']=='blocked'
    assert any('capture consent' in reason for reason in r['reasons'])


def test_noise_augmentation_is_reproducible_and_labeled(tmp_path):
    m=module('audio')
    assert hasattr(m,'augment_noise'),'controlled noise transform missing'
    from array import array
    from asrlab.audio import write_pcm
    source=tmp_path/'clean.wav';noise=tmp_path/'noise.wav'
    write_pcm(source,array('h',[1000,-1000]*800).tobytes())
    write_pcm(noise,array('h',[100,-50,50,-100]*400).tobytes())
    a=m.augment_noise(source,noise,tmp_path/'a.wav',10,42)
    b=m.augment_noise(source,noise,tmp_path/'b.wav',10,42)
    assert a['audio_sha256']==b['audio_sha256']
    assert a['provenance_type']=='derived_audio' and a['parent_audio_sha256']
    assert a['requested_snr_db']==10


def test_human_term_and_semantic_metrics():
    m=module('metrics')
    assert hasattr(m,'term_metrics'),'term occurrence metrics missing'
    result=m.term_metrics('neural network and neural network','neural network',{'neural network':['neural net']})
    assert result['TP']==1 and result['FN']==1 and result['recall']==.5
    assert result['precision']==1
    assert hasattr(m,'semantic_metrics')
    a=[{'category':'negation','severity':'critical','review_status':'adjudicated','reviewer_id':'r','adjudicator_id':'a'}]
    assert m.semantic_metrics(a,100)['meaning_changing_errors_per_1000_words']==10
