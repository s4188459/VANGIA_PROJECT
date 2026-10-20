import json
import sys
import time
import pytest
from asrlab.common import read_json,sha256,digest
from test_core import wav


def test_resumed_run_rejects_changed_artifact_provenance(tmp_path):
    from asrlab.runner import run
    folder=tmp_path/'weights';folder.mkdir();(folder/'model.bin').write_bytes(b'dummy')
    identity={'model_id':'openai/whisper-small.en','revision':'commit-a','files':{'model.bin':sha256(folder/'model.bin')}}
    provenance=tmp_path/'identity.json';provenance.write_text(json.dumps(identity))
    cfg={'model_id':'openai/whisper-small.en','mode':'batch_file','out':str(tmp_path/'run'),
         'weights_path':str(folder),'artifact_provenance':str(provenance)}
    assert run(cfg)['status']=='blocked'
    identity['revision']='commit-b';provenance.write_text(json.dumps(identity))
    with pytest.raises(ValueError,match='artifact'):run({**cfg,'resume':True})


def test_forged_pcm_hash_and_duration_rejected_before_worker(tmp_path):
    from asrlab.runner import run
    audio=tmp_path/'audio.wav';wav(audio)
    s={'sample_id':'s','audio':str(audio),'text':'hello','language':'en','consent_record_id':'c',
       'audio_sha256':sha256(audio),'pcm_sha256':'forged','duration_s':999,'session_id':'s','speaker_id':'p',
       'reference_revision':digest('hello'),'reference_quality':'reviewed','provenance_type':'real_measurement'}
    r=run({'model_id':'openai/whisper-small.en','mode':'batch_file','samples':[s],'out':str(tmp_path/'run')})
    assert any('PCM' in reason for reason in r['reasons'])
    assert any('duration' in reason for reason in r['reasons'])


def test_worker_failure_does_not_return_predictions(tmp_path):
    from asrlab.worker_client import WorkerClient
    worker=WorkerClient(sys.executable,tmp_path)
    try:
        with pytest.raises(RuntimeError,match='scope'):
            worker.request('load',timeout=10,config={'model_id':'unauthorized/model'})
    finally:worker.close()
    assert worker.process.poll() is not None


def test_worker_cancellation_terminates_process(tmp_path):
    from asrlab.worker_client import WorkerClient
    worker=WorkerClient(sys.executable,tmp_path,lambda:True)
    with pytest.raises(InterruptedError):worker.request('unload',timeout=10)
    assert worker.process.poll() is not None


def test_live_capture_cannot_resume_ambiguous_partial_recording(tmp_path):
    from asrlab.runner import run
    cfg={'model_id':'openai/whisper-small.en','mode':'live_microphone','out':str(tmp_path/'live')}
    run(cfg)
    with pytest.raises(ValueError,match='live capture'):run({**cfg,'resume':True})


def test_provisional_model_status_distinguishes_missing_failed_and_boundary():
    from asrlab import review
    assert hasattr(review,'candidate_status')
    assert review.candidate_status({'status':'blocked'}, {})['status']=='BLOCKED'
    assert review.candidate_status({'status':'failed'}, {})['status']=='FAILED'
    assert review.candidate_status({'status':'completed'}, {})['status']=='NOT MEASURED'
    assert review.candidate_status({'status':'completed'},{'wer':.151,'p95_paint_proxy_s':2,'coverage':1})['status']=='BORDERLINE'
    result=review.candidate_status({'status':'completed'},{'wer':.1,'p95_paint_proxy_s':2,'coverage':1})
    assert result['status']=='INSUFFICIENT EVIDENCE' and not result['validated']
