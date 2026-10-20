import pytest
from asrlab.common import read_json,write_json,sha256
from test_zip_dataset import archive,wav_bytes


def dataset(tmp_path):
    from asrlab.zip_dataset import import_zip
    z=archive(tmp_path,[('a.wav',wav_bytes()),('a.txt','hello world')])
    import_zip(z,tmp_path/'data','consent')
    return tmp_path/'data/dataset.json'


def test_campaign_blocked_jobs_repeats_and_resume_keep_plan(tmp_path):
    from asrlab.benchmark import create_benchmark,run_benchmark,preset
    source=dataset(tmp_path);out=tmp_path/'campaign'
    plan=create_benchmark(source,[preset('openai/whisper-small.en')],out,repeats=2)
    assert len(plan['jobs'])==2
    assert len({j['repeat_id'] for j in plan['jobs']})==2
    assert all(j['temperature']=='cold_model_load' for j in plan['jobs'])
    before=sha256(out/'benchmark.json')
    result=run_benchmark(out)
    assert len(result['jobs'])==2 and all(r['status']=='blocked' for r in result['jobs'])
    assert all((out/j['run_path']/'manifest.json').exists() for j in plan['jobs'])
    assert sha256(out/'benchmark.json')==before
    run_benchmark(out,resume=True)
    assert sha256(out/'benchmark.json')==before


def test_campaign_cancel_keeps_all_planned_jobs_and_resume_detects_tamper(tmp_path):
    from asrlab.benchmark import create_benchmark,run_benchmark,cancel_benchmark,preset
    source=dataset(tmp_path);out=tmp_path/'campaign'
    create_benchmark(source,[preset('openai/whisper-small.en')],out,repeats=2)
    cancel_benchmark(out)
    result=run_benchmark(out)
    assert len(result['jobs'])==2 and all(r['status']=='cancelled' for r in result['jobs'])
    plan=read_json(out/'benchmark.json');plan['jobs'][0]['config']['beam_size']=123
    write_json(out/'benchmark.json',plan)
    with pytest.raises(ValueError,match='integrity'):run_benchmark(out,resume=True)


def test_presets_exact_scope_deferred_and_separate_worker_config(tmp_path):
    from asrlab.benchmark import preset,create_benchmark
    from asrlab.runner import decoder_config
    with pytest.raises(ValueError):preset('openai/whisper-base')
    cfg=preset('Qwen/Qwen3-ASR-1.7B')
    with pytest.raises(ValueError,match='opt-in'):create_benchmark(dataset(tmp_path),[cfg],tmp_path/'campaign')
    clean=decoder_config({'model_id':'openai/whisper-small.en','samples':[{'text':'SECRET'}],
        'reference':'SECRET','dataset_manifest':'SECRET','beam_size':5,'weights_path':'weights'})
    assert 'SECRET' not in str(clean) and clean['beam_size']==5


def test_unresolved_input_is_blocked_with_planned_samples(tmp_path):
    from asrlab.zip_dataset import import_zip
    from asrlab.benchmark import create_benchmark,run_benchmark,preset
    z=archive(tmp_path,[('a.wav',wav_bytes())])
    import_zip(z,tmp_path/'data','consent')
    plan=create_benchmark(tmp_path/'data/dataset.json',[preset('openai/whisper-small.en')],tmp_path/'bench')
    result=run_benchmark(tmp_path/'bench')
    assert result['jobs'][0]['status']=='blocked'
    assert plan['samples'][0]['text'] is None
    assert 'input_errors' in str(result['jobs'][0]['reasons'])
