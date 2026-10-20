from asrlab import timing
import pytest


def test_backlog_and_stability_are_aggregated_within_each_session():
    assert hasattr(timing,'session_trace_metrics')
    rows=[{'session_id':'a','elapsed_s':1,'pending_audio_s':0,'oldest_pending_age_s':0,'capture_active':True},
          {'session_id':'a','elapsed_s':61,'pending_audio_s':2,'oldest_pending_age_s':3,'capture_active':True},
          {'session_id':'a','elapsed_s':121,'pending_audio_s':0,'oldest_pending_age_s':0,'capture_active':False},
          {'session_id':'b','elapsed_s':1,'pending_audio_s':0,'oldest_pending_age_s':0,'capture_active':True},
          {'session_id':'b','elapsed_s':61,'pending_audio_s':3,'oldest_pending_age_s':4,'capture_active':True}]
    revisions=[{'session_id':'a','text':'first session'},{'session_id':'b','text':'second session'}]
    result=timing.session_trace_metrics(rows,revisions)
    assert result['backlog']['sessions']['a']['slope_s_per_min']==pytest.approx(2)
    assert result['backlog']['sessions']['b']['slope_s_per_min']==pytest.approx(3)
    assert result['stability']['sessions']['a']['changed_tokens']==0
    assert result['stability']['sessions']['b']['changed_tokens']==0


def test_pending_audio_counts_unique_pcm_not_overlap():
    assert hasattr(timing,'pending_audio_seconds')
    chunks=[{'start_sample':0,'end_sample':32000},{'start_sample':24000,'end_sample':56000}]
    assert timing.pending_audio_seconds(chunks,16000)==3.5
