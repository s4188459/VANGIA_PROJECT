import time
from test_core import wav
from asrlab.events import EventLog
from asrlab.runner import _run_paced


def test_enqueue_occurs_at_capture_before_slow_decoder_completion(tmp_path):
    source=tmp_path/'audio.wav';wav(source)
    log=EventLog(tmp_path/'events.jsonl');backlog=[];revisions=[]
    def emit(kind,session='s',**kw):
        return log.emit(kind,'r',session,'synthetic_fixture',**kw)
    class SlowDecoder:
        def request(self,*args,**kwargs):
            time.sleep(.06)
            return {'service_ns':60000000,'result':{'text':'test'}}
    cfg={'mode':'paced_replay','model_id':'openai/whisper-small.en','chunk_seconds':.02,'overlap_seconds':0}
    _run_paced({'sample_id':'s','audio':str(source)},cfg,tmp_path,SlowDecoder(),emit,lambda:False,backlog,revisions)
    queued=[e for e in log.events if e['event_type']=='inference_queued']
    finished=[e for e in log.events if e['event_type']=='inference_finished']
    assert len(queued)==5
    assert queued[1]['monotonic_ns']<finished[0]['monotonic_ns']
    assert max(r['oldest_pending_age_s'] for r in backlog)>.1
