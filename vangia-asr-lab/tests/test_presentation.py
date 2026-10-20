import threading
import pytest
from asrlab.events import EventLog
from test_core import event


def test_presenter_ack_records_only_proxy_and_uses_same_run(tmp_path):
    from asrlab import timing
    assert hasattr(timing,'present_caption')
    log=EventLog(tmp_path/'events.jsonl')
    request=event('caption_update_requested',100,'request',caption_text='hello')
    log.append(request)
    def redraw(text,ack):
        assert text=='hello'
        ack()
    result=timing.present_caption(request,log,redraw,timeout=.1)
    assert result['acknowledged']
    ack=log.events[-1]
    assert ack['event_type']=='caption_paint_ack' and ack['trace_quality']=='paint_proxy'
    assert ack['payload']['physical_presentation_verified'] is False
    assert ack['run_id']=='r'


def test_presenter_timeout_does_not_invent_ack(tmp_path):
    from asrlab import timing
    assert hasattr(timing,'present_caption')
    log=EventLog(tmp_path/'events.jsonl');request=event('caption_update_requested',100)
    log.append(request)
    result=timing.present_caption(request,log,lambda text,ack:None,timeout=.01)
    assert not result['acknowledged'] and len(log.events)==1


def test_presenter_rejects_late_ack_after_timeout(tmp_path):
    from asrlab import timing
    assert hasattr(timing,'present_caption')
    log=EventLog(tmp_path/'events.jsonl');request=event('caption_update_requested',100)
    log.append(request);pending=[]
    timing.present_caption(request,log,lambda text,ack:pending.append(ack),timeout=.01)
    pending[0]()
    assert len(log.events)==1
