import os
import time
import pytest
from asrlab.common import read_json
from test_zip_dataset import archive,wav_bytes
from test_benchmark import dataset


def test_total_decode_budget_blocks_remaining_audio_without_writing_excess(tmp_path):
    from asrlab.zip_dataset import import_zip
    z=archive(tmp_path,[(f'{i}.wav',wav_bytes(.1)) for i in range(4)]+[(f'{i}.txt','hello') for i in range(4)])
    result=import_zip(z,tmp_path/'data','consent',limits={'max_total_duration_s':.15})
    assert sum(r['duration_s'] or 0 for r in result['samples'])<=.15
    assert len(list((tmp_path/'data/wav').glob('*.wav')))==1
    assert all('total_duration_limit' in str(r['input_errors']) for r in result['samples'][1:])


def test_duplicate_supplied_ids_still_export_all_blocked_observations(tmp_path):
    from asrlab.zip_dataset import import_zip
    from asrlab.benchmark import create_benchmark,run_benchmark,preset
    from asrlab.analysis_export import export_analysis
    z=archive(tmp_path,[('a.wav',wav_bytes()),('a.txt','hello'),('b.wav',wav_bytes()),('b.txt','hello'),
        ('metadata.csv','sample_id,audio_path,reference_path\nsame,a.wav,a.txt\nsame,b.wav,b.txt\n')])
    data=import_zip(z,tmp_path/'data','consent')
    assert len({r['sample_id'] for r in data['samples']})==2
    assert all(r['supplied_sample_id']=='same' for r in data['samples'])
    create_benchmark(tmp_path/'data/dataset.json',[preset('openai/whisper-small.en')],tmp_path/'bench')
    run_benchmark(tmp_path/'bench');export_analysis(tmp_path/'bench',tmp_path/'export')
    result=read_json(tmp_path/'export/results.json')
    assert len(result['samples'])==2 and len(result['failures'])==2


def test_configuration_identity_stable_across_repeat_and_export(tmp_path):
    from asrlab.benchmark import create_benchmark,run_benchmark,preset
    from asrlab.analysis_export import collect_results
    plan=create_benchmark(dataset(tmp_path),[preset('openai/whisper-small.en')],tmp_path/'bench',repeats=2)
    run_benchmark(tmp_path/'bench');rows=collect_results(tmp_path/'bench')['runs']
    assert len({r['model_config_id'] for r in rows})==1
    assert rows[0]['model_config_id']==plan['jobs'][0]['model_config_id']


def test_cancel_during_resume_does_not_restart_remaining_attempted_jobs(tmp_path,monkeypatch):
    from asrlab.benchmark import create_benchmark,run_benchmark,cancel_benchmark,preset
    import asrlab.runner as runner
    out=tmp_path/'bench';create_benchmark(dataset(tmp_path),[preset('openai/whisper-small.en')],out,repeats=2)
    run_benchmark(out)
    original=runner.run
    def cancel_after_first(config,**kwargs):
        state=original(config,**kwargs);cancel_benchmark(out);return state
    monkeypatch.setattr(runner,'run',cancel_after_first)
    result=run_benchmark(out,resume=True)
    assert [r['status'] for r in result['jobs']]==['blocked','cancelled']


def test_runner_pending_rows_are_cancelled_after_interruption(tmp_path,monkeypatch):
    import asrlab.runner as runner
    from asrlab.storage import read_jsonl
    source=dataset(tmp_path);data=read_json(source)
    class InterruptedWorker:
        resources=[]
        def __init__(self,*args):pass
        def request(self,*args,**kwargs):raise InterruptedError('cancelled')
        def close(self):pass
    monkeypatch.setattr(runner,'preflight',lambda c:{'reasons':[]})
    monkeypatch.setattr(runner,'WorkerClient',InterruptedWorker)
    state=runner.run({'model_id':'openai/whisper-small.en','out':str(tmp_path/'run'),
        'samples':data['samples'],'mode':'batch_file','dataset_split':'development'})
    assert state['status']=='cancelled'
    assert read_jsonl(tmp_path/'run/predictions.jsonl')[0]['status']=='cancelled'


@pytest.mark.skipif(os.environ.get('ASRLAB_TEST_UI')!='1',reason='Native desktop opt-in')
def test_wizard_switch_archive_invalidates_silence_and_preserves_reference_quality(tmp_path):
    import tkinter as tk
    from asrlab.ui import LabApp
    root=tk.Tk()
    try:
        app=LabApp(root);w=app.new_benchmark()
        z=archive(tmp_path,[('a.wav',wav_bytes()),('a.txt',''),('metadata.csv','sample_id,audio_path,reference_path,reference_quality\na,a.wav,a.txt,reviewed\n')])
        w.archive_path.set(str(z));w.inspect_archive();w.silence_ids.add('a')
        assert w.mapping[0]['reference_quality']=='reviewed'
        other=tmp_path/'other';other.mkdir();z2=archive(other,[('a.wav',wav_bytes(.2)),('a.txt','')])
        w.archive_path.set(str(z2));w.inspect_archive()
        assert not w.silence_ids
        w.close()
    finally:root.destroy()
