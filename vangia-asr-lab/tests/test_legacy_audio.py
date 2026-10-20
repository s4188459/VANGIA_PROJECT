import importlib.util
from pathlib import Path
import pytest
from test_core import module
from test_legacy import PACKAGE,JSON
from asrlab.common import read_json


def test_audio_binding_requires_explicit_local_processing_consent(tmp_path):
    m=module('legacy_audio')
    with pytest.raises(ValueError,match='consent'):
        m.bind_archive(PACKAGE/'TEST (3).zip',JSON,tmp_path/'bound','')


@pytest.mark.skipif(importlib.util.find_spec('av') is None,reason='Optional PyAV archive conversion dependency')
def test_supplied_archive_matches_every_historical_audio_and_reference(tmp_path):
    m=module('legacy_audio')
    result=m.bind_archive(PACKAGE/'TEST (3).zip',JSON,tmp_path/'bound','user-authorized-local-processing')
    assert result['verified_original_audio_count']==100
    assert result['verified_reference_source_count']==100
    assert result['verified_canonical_wav_count']==100
    assert result['dataset_split']=='legacy_development'
    split=read_json(tmp_path/'bound/dataset/split-legacy_development.json')
    assert len(split['samples'])==100
    assert all(s['reference_quality']=='unverified' for s in split['samples'])
