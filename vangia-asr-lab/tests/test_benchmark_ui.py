import os
import time
import pytest
from test_zip_dataset import archive,wav_bytes


@pytest.mark.skipif(os.environ.get('ASRLAB_TEST_UI')!='1',reason='Native desktop opt-in')
def test_wizard_zip_configure_run_export_without_editing_json(tmp_path):
    import tkinter as tk
    from asrlab.ui import LabApp
    from asrlab.analysis_export import validate_bundle
    root=tk.Tk()
    try:
        app=LabApp(root);root.update()
        assert hasattr(app,'new_benchmark')
        wizard=app.new_benchmark();root.update()
        z=archive(tmp_path,[('a.wav',wav_bytes()),('a.txt','hello world')])
        wizard.archive_path.set(str(z));wizard.consent.set('test-consent')
        wizard.dataset_path.set(str(tmp_path/'data'))
        wizard.inspect_archive();root.update()
        assert len(wizard.preview_tree.get_children())==1
        wizard.import_data();root.update()
        assert wizard.dataset is not None
        wizard.select_models(['openai/whisper-small.en'])
        # No dependency/weights in the preset: a real blocked run, never mocked inference.
        wizard.presets['openai/whisper-small.en']['weights_path']='missing-test-weights'
        wizard.benchmark_path.set(str(tmp_path/'benchmark'))
        wizard.start_benchmark()
        deadline=time.monotonic()+20
        while wizard.busy and time.monotonic()<deadline:
            root.update();time.sleep(.02)
        assert not wizard.busy
        wizard.refresh_results();root.update()
        deadline=time.monotonic()+15
        while not wizard.result_tree.get_children() and time.monotonic()<deadline:
            root.update();time.sleep(.02)
        assert len(wizard.result_tree.get_children())==1
        assert 'blocked' in str(wizard.result_tree.item(wizard.result_tree.get_children()[0])['values']).lower()
        wizard.export_bundle(tmp_path/'analysis')
        assert validate_bundle(tmp_path/'analysis')['ok']
        wizard.window.destroy()
    finally:root.destroy()


@pytest.mark.skipif(os.environ.get('ASRLAB_TEST_UI')!='1',reason='Native desktop opt-in')
def test_live_tracking_visible_while_busy_and_cancel(tmp_path):
    import tkinter as tk
    from asrlab.ui import LabApp
    from test_progress import fixture
    d=fixture(tmp_path)
    (d/'prediction_attempts.jsonl').write_text('{"sample_id":"1","status":"completed"}\n')
    (d/'events.jsonl').write_text('{"event_type":"model_load_started","utc_iso8601":"2026-10-18T00:00:00+00:00"}\n')
    root=tk.Tk()
    try:
        wizard=LabApp(root).new_benchmark();wizard.source=tmp_path;wizard.begin_tracking();wizard.busy=True
        deadline=time.monotonic()+8
        while not wizard.monitor_data and time.monotonic()<deadline:root.update();time.sleep(.02)
        assert wizard.monitor_data is not None
        assert 'Loading model' in wizard.live_title.get()
        assert 'Succeeded 1/6' in wizard.live_detail.get()
        assert len(wizard.tracking_tree.get_children())==2
        assert str(wizard.run_buttons[0]['state'])=='disabled'
        assert str(wizard.stop_button['state'])=='normal'
        (tmp_path/'CANCEL').touch();wizard.monitor_next=0
        deadline=time.monotonic()+8
        while 'STOPPING' not in wizard.live_title.get() and time.monotonic()<deadline:root.update();time.sleep(.02)
        assert 'STOPPING' in wizard.live_title.get()
        wizard.busy=False;wizard.close()
    finally:root.destroy()


def test_workflow_cli_preview_import_run_and_export(tmp_path,capsys):
    from asrlab.cli import main
    from asrlab.common import write_json
    z=archive(tmp_path,[('a.wav',wav_bytes()),('a.txt','hi')])
    assert main(['preview-zip','--archive',str(z)])==0
    assert main(['import-zip','--archive',str(z),'--out',str(tmp_path/'data'),'--consent-record-id','c'])==0
    config=tmp_path/'config.json';write_json(config,{'model_id':'openai/whisper-small.en'})
    assert main(['benchmark-create','--dataset',str(tmp_path/'data/dataset.json'),'--configs',str(config),'--out',str(tmp_path/'bench')])==0
    assert main(['benchmark-run',str(tmp_path/'bench')])==3
    assert main(['export-analysis',str(tmp_path/'bench'),'--out',str(tmp_path/'export')])==0
    assert main(['validate-export',str(tmp_path/'export')])==0
