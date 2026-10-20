import json
import os
import psutil
from asrlab.progress import snapshot

def fixture(tmp_path):
    (tmp_path/'benchmark.json').write_text(json.dumps({'samples':[{}, {}, {}], 'jobs':[
        {'job_id':'a','run_path':'jobs/a','repeat_id':1,'config':{'model_id':'model-a'}},
        {'job_id':'b','run_path':'jobs/b','repeat_id':1,'config':{'model_id':'model-b'}}]}))
    d=tmp_path/'jobs/a';d.mkdir(parents=True)
    (tmp_path/'ACTIVE').write_text(json.dumps({'pid':os.getpid(),'created':psutil.Process().create_time()}))
    (d/'state.json').write_text('{"status":"running"}')
    return d

def test_live_counts_partial_write_and_stage(tmp_path):
    d=fixture(tmp_path)
    (d/'prediction_attempts.jsonl').write_text('{"sample_id":"1","status":"completed"}\n{"sample_id":"2","status":"failed","error":"timeout"}\n{"partial":')
    (d/'events.jsonl').write_text('{"event_type":"inference_started","chunk_id":"3","utc_iso8601":"2026-10-18T00:00:00+00:00"}\n')
    s=snapshot(tmp_path)
    assert s['completed']==1 and s['failed']==1 and s['pending']==4
    assert s['active']['sample']=='3' and s['active']['phase']=='Transcribing'
    assert s['active']['error']=='timeout'

def test_cancelled_unstarted_not_counted_success(tmp_path):
    fixture(tmp_path);(tmp_path/'ACTIVE').unlink()
    (tmp_path/'jobs/a/state.json').write_text('{"status":"cancelled"}')
    (tmp_path/'state.json').write_text('{"status":"cancelled","jobs":[{"job_id":"b","status":"cancelled"}]}')
    s=snapshot(tmp_path)
    assert s['completed']==0 and s['cancelled']==6 and s['pending']==0

def test_stale_lock_and_stopping(tmp_path):
    fixture(tmp_path);(tmp_path/'CANCEL').touch()
    assert snapshot(tmp_path)['status']=='stopping'
    (tmp_path/'ACTIVE').write_text(json.dumps({'pid':os.getpid(),'created':0}))
    (tmp_path/'state.json').write_text('{"status":"running"}')
    s=snapshot(tmp_path)
    assert s['status']=='interrupted' and not s['alive']
