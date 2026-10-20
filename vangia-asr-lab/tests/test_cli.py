import json
import pytest
from asrlab.cli import main


def test_required_cli_score_plan_and_run(tmp_path,capsys):
    ref=tmp_path/'ref.jsonl';pred=tmp_path/'pred.jsonl'
    ref.write_text('{"sample_id":"s","text":"hello world"}\n')
    pred.write_text('{"sample_id":"s","text":"hello"}\n')
    assert main(['score','--reference',str(ref),'--predictions',str(pred)])==0
    assert json.loads(capsys.readouterr().out)['normalized']['wer_micro']==.5
    assert main(['plan','--matrix','config/experiment_matrix.json'])==0
    assert json.loads(capsys.readouterr().out)['jobs']
    cfg=tmp_path/'config.json';cfg.write_text(json.dumps({'mode':'synthetic_fixture','out':str(tmp_path/'run')}))
    assert main(['run','--config',str(cfg)])==0
    assert main(['audit',str(tmp_path/'run')])==0


def test_dataset_cli_and_review_export(tmp_path,capsys):
    from test_core import wav
    audio=tmp_path/'a.wav';wav(audio)
    item={'sample_id':'a','audio':str(audio),'text':'test','language':'en','speaker_id':'p','session_id':'s',
          'domain':'test','consent_record_id':'c','provenance_type':'real_measurement','reference_quality':'reviewed','split':'development'}
    spec=tmp_path/'sample.json';spec.write_text(json.dumps(item))
    assert main(['dataset-add','--registry',str(tmp_path/'data'),'--sample',str(spec)])==0
    assert main(['dataset-lock','--registry',str(tmp_path/'data'),'--split','development'])==0


def test_bad_configuration_returns_actionable_error(tmp_path,capsys):
    cfg=tmp_path/'bad.json';cfg.write_text('{"mode":"batch_file","out":"unused"}')
    assert main(['run','--config',str(cfg)])==2
    assert 'reason' in json.loads(capsys.readouterr().out)
