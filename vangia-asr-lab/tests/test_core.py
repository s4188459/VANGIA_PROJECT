import importlib.util
import json
import wave
from copy import deepcopy
import pytest


def module(name):
    assert importlib.util.find_spec('asrlab.'+name), f'{name} is not implemented'
    return __import__('asrlab.'+name, fromlist=['*'])


def event(kind='inference_queued', t=100, ident='e1', **kw):
    return dict(run_id='r', session_id='s', event_id=ident, event_type=kind,
                utc_iso8601='2026-10-15T00:00:00+00:00', monotonic_ns=t, clock_id='host',
                source='worker', payload={}, provenance_type='real_measurement',
                input_mode='batch_file', chunk_id='c1', **kw)


def test_events_duplicate_and_order_and_recovery(tmp_path):
    m=module('events'); log=m.EventLog(tmp_path/'events.jsonl')
    log.append(event())
    with pytest.raises(ValueError,match='duplicate'): log.append(event())
    with pytest.raises(ValueError,match='order'): log.append(event('inference_started',99,'e2'))
    with pytest.raises(ValueError,match='started'): log.append(event('inference_finished',110,'e3'))
    log.append(event('inference_started',120,'e2'))
    log.append(event('inference_finished',130,'e3'))
    with (tmp_path/'events.jsonl').open('ab') as f: f.write(b'{broken')
    log=m.EventLog(tmp_path/'events.jsonl')
    assert log.recovery['valid_events']==3
    assert log.recovery['corrupt_tail_preserved']
    log.append(event('run_finished',140,'e4'))
    assert len(log.events)==4
    assert (tmp_path/'events.jsonl').read_bytes().endswith(b'{broken')


def test_schema_and_synthetic_provenance(tmp_path):
    m=module('events'); log=m.EventLog(tmp_path/'events.jsonl')
    e=event(); e['source']='synthetic_fixture'
    with pytest.raises(ValueError,match='synthetic'): log.append(e)
    e=event('caption_presentation_verified'); e['trace_quality']='measured'
    with pytest.raises(ValueError,match='verification'): log.append(e)
    e=event('chunk_created',audio_start_sample=20,audio_end_sample=10,sample_rate_hz=16000)
    with pytest.raises(ValueError,match='sample'): log.append(e)


def test_cross_clock_uncertainty_and_proxy():
    m=module('timing')
    a=event(t=1000000000); b=event('caption_update_requested',2000000000,'e2')
    assert m.interval(a,b)['value']==1
    b['clock_id']='worker'
    assert m.interval(a,b)['missing_reason']=='clock_unsynchronized'
    assert m.interval(a,b,{'worker':{'offset_to_host_ns':-100000000,'uncertainty_ns':2000000}})['value']==.9
    refs=[{'word':'hello','end_ns':1000000000,'reviewed':True,'clock_id':'host'},
          {'word':'world','end_ns':1100000000,'reviewed':True,'clock_id':'host'}]
    updates=[dict(event('caption_update_requested',2000000000),reference_word_index=0)]
    assert m.word_lag(refs,updates,'caption_presentation_verified')['n_matched']==0
    updates[0]['event_type']='caption_paint_ack'
    result=m.word_lag(refs,updates,'caption_paint_ack')
    assert result['coverage']==.5 and result['p95']==1
    assert result['observations'][1]['value'] is None
    assert result['endpoint']=='paint_proxy'
    refs[0]['reviewed']=False
    assert m.word_lag(refs,updates,'caption_paint_ack')['n_matched']==0


def test_backlog_over_long_session_and_stability():
    m=module('timing')
    rows=[{'elapsed_s':i*60,'pending_audio_s':i*2,'oldest_pending_age_s':i*3} for i in range(20)]
    assert m.backlog(rows)['slope_s_per_min']==pytest.approx(2)
    assert m.backlog(rows)['sustained_growth']
    result=m.stability(['we may go','we must go','we must go now'],[0,3,3])
    assert result['changed_tokens']==2
    assert result['post_commit_modifications']==0
    assert m.stability(['we must go','we may go'],[3,3])['post_commit_modifications']==1


def test_scoring_sdi_raw_normalized_and_silence():
    m=module('metrics')
    r=m.score('a b c','a x c d')
    assert (r['S'],r['D'],r['I'],r['N'])==(1,0,1,3)
    assert r['wer']==pytest.approx(2/3)
    assert len(r['alignment'])==4
    assert m.score('Hello, WORLD!','hello world')['wer']==0
    assert m.score('Hello, WORLD!','hello world',normalize=False)['wer']==1
    assert m.score('', 'hallucination')['wer'] is None
    assert m.score('', 'hallucination')['hallucinated_words']==1
    assert m.normalize("Don't use twenty-four cm².")=="don't use twenty four cm2"
    assert m.score('twenty-four','24')['wer']!=0
    assert m.score('square centimeters','cm')['wer']!=0
    assert m.score('a b','')['D']==2


def test_corpus_micro_macro_missing_and_unpaired():
    m=module('metrics')
    ref=[{'sample_id':'a','text':'one','domain':'short'}, {'sample_id':'b','text':'one two three','domain':'long'}]
    pred=[{'sample_id':'a','text':'wrong'},{'sample_id':'b','text':'one two three'}]
    r=m.corpus_score(ref,pred)
    assert r['normalized']['wer_micro']==.25
    assert r['normalized']['wer_macro_utterance']==.5
    assert r['normalized']['wer_macro_domain']==.5
    with pytest.raises(ValueError,match='paired'): m.corpus_score(ref,pred[:1])
    with pytest.raises(ValueError,match='duplicate'): m.corpus_score(ref+[ref[0]],pred)
    pred[1]={'sample_id':'b','status':'failed','error':'timeout'}
    r=m.corpus_score(ref,pred)
    assert r['completion_fraction']==.5
    assert r['normalized']['wer_micro'] is None
    assert r['conditional_success']['wer_micro']==1


def wav(path):
    with wave.open(str(path),'wb') as f:
        f.setparams((1,2,16000,0,'NONE','not compressed')); f.writeframes(b'\x00\x00'*1600)


def test_dataset_consent_audio_only_split_leakage_and_lock(tmp_path):
    m=module('datasets'); audio=tmp_path/'a.wav'; wav(audio)
    item=dict(sample_id='a',audio=str(audio),text='hello',language='en',speaker_id='p',session_id='s',domain='test',
              consent_record_id='consent-1',provenance_type='real_measurement',reference_quality='reviewed',split='development')
    manager=m.DatasetRegistry(tmp_path/'data')
    manager.add(item)
    with pytest.raises(ValueError,match='duplicate'): manager.add(item)
    other={**item,'sample_id':'b','split':'holdout'}
    with pytest.raises(ValueError,match='contamination'): manager.add(other)
    with pytest.raises(ValueError,match='consent'): manager.add({**item,'sample_id':'c','consent_record_id':''})
    with pytest.raises(ValueError,match='audio'): manager.add({**item,'sample_id':'d','audio':'movie.mp4'})
    with pytest.raises(ValueError,match='English'): manager.add({**item,'sample_id':'e','language':'vi'})
    manager.lock('development')
    with pytest.raises(ValueError,match='locked'): manager.add({**item,'sample_id':'f'})
    assert manager.samples()[0]['audio_sha256']
    rev=manager.correct_reference('a','hello again','reviewer-1')
    assert rev['parent_revision'] and rev['reference_revision']!=rev['parent_revision']


def test_seam_merge_does_not_discard_repeated_nonoverlap():
    m=module('audio')
    assert m.merge('we go','go now',overlap=True)['text']=='we go now'
    assert m.merge('go','go now',overlap=False)['text']=='go go now'
    assert m.merge('a b','c d',overlap=True)['deduplicated_tokens']==0


def test_paced_replay_uses_elapsed_clock(tmp_path):
    m=module('audio'); audio=tmp_path/'a.wav'; wav(audio)
    import time
    start=time.monotonic()
    chunks=list(m.paced_chunks(audio,chunk_s=.04,overlap_s=.01))
    assert time.monotonic()-start>=.095
    assert chunks[-1]['end_sample']==1600
    assert chunks[1]['start_sample']==480
    assert all(c['input_mode']=='paced_replay' for c in chunks)
