import pytest
from asrlab import timing


def event(kind, seconds, **extra):
    return {'event_id':kind+str(seconds),'event_type':kind,'monotonic_ns':int(seconds*1e9),
            'clock_id':'host-1','session_id':'s','chunk_id':'c','attempt_id':'a','payload':{},**extra}


def test_trace_stage_summary_has_missing_proxy_coverage_and_keeps_word_lag_null():
    assert hasattr(timing,'trace_summary')
    events=[event('inference_queued',1),event('inference_started',3),event('inference_finished',7),
            event('caption_update_requested',8,event_id='req1'),
            event('caption_update_requested',9,event_id='req2'),
            event('caption_paint_ack',10,payload={'request_event_id':'req1'},trace_quality='paint_proxy')]
    result=timing.trace_summary(events)
    assert result['queue_dwell_s']['p95']==2
    assert result['host_inference_roundtrip_s']['p95']==4
    assert result['ui_request_to_paint_proxy_s']['p95']==2
    assert result['ui_request_to_paint_proxy_s']['coverage']==.5
    assert result['ui_request_to_paint_proxy_s']['n_total']==2
    assert result['word_first_presented_lag_p95_s'] is None


def test_stage_summary_does_not_subtract_unsynchronized_clocks_or_pair_attempts():
    assert hasattr(timing,'trace_summary')
    events=[event('inference_queued',1),event('inference_started',3,clock_id='other'),
            event('inference_finished',7,attempt_id='different')]
    result=timing.trace_summary(events)
    assert result['queue_dwell_s']['p95'] is None
    assert result['queue_dwell_s']['observations'][0]['missing_reason']=='clock_unsynchronized'
    assert result['host_inference_roundtrip_s']['coverage']==0


def test_first_caption_timing_is_per_session_and_named_emission_not_visible():
    assert hasattr(timing,'trace_summary')
    events=[event('audio_frame_captured',2,payload={'capture_origin_ns':0}),
            event('hypothesis_emitted',4,caption_text=''),
            event('hypothesis_emitted',5,caption_text='hello'),
            event('audio_frame_captured',10,session_id='b',payload={'capture_origin_ns':int(8e9)}),
            event('hypothesis_emitted',11,session_id='b',caption_text='next')]
    result=timing.trace_summary(events)
    assert result['source_start_to_first_nonempty_emission_s']['n_total']==2
    assert result['source_start_to_first_nonempty_emission_s']['p50']==4
