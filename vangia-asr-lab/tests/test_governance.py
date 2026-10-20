import pytest
from test_core import module


def test_preregistration_freezes_dataset_configuration_and_primary_outcomes(tmp_path):
    m=module('governance')
    dataset={'split':'holdout','sha256':'dataset-hash'}
    config={'model_id':'openai/whisper-small.en','mode':'paced_replay','chunk_seconds':2,'normalization':'legacy'}
    record=m.preregister(tmp_path/'registration.json',dataset,[config],['wer_micro','paint_proxy_p95'],'owner-1')
    m.check_registration(record,dataset,config)
    with pytest.raises(ValueError,match='frozen'):m.check_registration(record,dataset,{**config,'chunk_seconds':3})
    with pytest.raises(ValueError,match='dataset'):m.check_registration(record,{**dataset,'sha256':'changed'},config)
    with pytest.raises(ValueError,match='holdout'):m.preregister(tmp_path/'bad.json',{'split':'legacy_development','sha256':'d'},[config],['wer'],'owner')


def test_study_requires_consent_and_does_not_infer_comprehension_from_wer(tmp_path):
    m=module('study')
    item={'response_id':'r1','participant_id':'p1','consent_record_id':'consent','task_id':'task1','stimulus_run_id':'run1',
          'stimulus_sha256':'hash','task_score':.5,'readability_rating':3,'lag_annoyance_rating':4,'group':'learners'}
    m.add_response(tmp_path,item)
    with pytest.raises(ValueError,match='duplicate'):m.add_response(tmp_path,item)
    with pytest.raises(ValueError,match='consent'):m.add_response(tmp_path,{**item,'response_id':'r2','consent_record_id':''})
    result=m.summarize(tmp_path)
    assert result['participants']==1 and result['task_score_mean']==.5
    assert result['validated'] is False


def test_reviewer_agreement_uses_paired_units():
    m=module('study')
    a={'s1':'critical','s2':'minor','s3':'critical','s4':'minor'}
    b={'s1':'critical','s2':'minor','s3':'minor','s4':'critical'}
    result=m.agreement(a,b)
    assert result['observed_agreement']==.5 and result['cohens_kappa']==0
    with pytest.raises(ValueError,match='paired'):m.agreement(a,{'s1':'critical'})


def test_single_dual_architecture_comparison_requires_actual_matched_totals():
    m=module('experiments')
    assert hasattr(m,'compare_architectures')
    a={'architecture':'single','dataset_hash':'d','session_ids':['s1'],'live_wer':.2,'offline_wer':.2,
       'total_turnaround_s':10,'measured_combined_peak_rss_bytes':100,'critical_errors':0,'evidence_class':'E-LOCAL'}
    b={**a,'architecture':'dual','offline_wer':.1,'total_turnaround_s':20,'measured_combined_peak_rss_bytes':200}
    r=m.compare_architectures(a,b)
    assert r['offline_wer_difference_dual_minus_single']==pytest.approx(-.1)
    assert r['turnaround_difference_s']==10
    assert r['decision']=='HUMAN REVIEW REQUIRED'
    with pytest.raises(ValueError,match='matched'):m.compare_architectures(a,{**b,'dataset_hash':'other'})
