from test_core import module
from asrlab.common import read_json
from asrlab.storage import audit


def test_diagnostic_missing_weights_preserves_synthetic_blocked_evidence(tmp_path):
    m=module('diagnostic')
    out=tmp_path/'diagnostic'
    result=m.smoke({'model_id':'openai/whisper-small.en','out':str(out)})
    assert result['status']=='blocked'
    assert read_json(out/'manifest.json')['evidence_class']=='SYNTHETIC'
    assert read_json(out/'metrics.json')['wer'] is None
    assert audit(out)['ok']
