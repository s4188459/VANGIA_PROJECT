import csv
import io
import stat
import wave
import zipfile
import pytest
from asrlab.common import read_json,sha256


def wav_bytes(seconds=.1):
    output=io.BytesIO()
    with wave.open(output,'wb') as f:
        f.setparams((1,2,16000,0,'NONE','not compressed'))
        f.writeframes(b'\x01\x00'*int(16000*seconds))
    return output.getvalue()


def archive(tmp_path, entries):
    path=tmp_path/'input.zip'
    with zipfile.ZipFile(path,'w') as z:
        for name,data in entries:
            if isinstance(name,str):
                info=zipfile.ZipInfo();info.filename=name
            else:info=name
            z.writestr(info,data)
    return path


def api():
    import asrlab.zip_dataset as mod
    return mod


def test_nested_pairing_and_original_hashes(tmp_path):
    z=archive(tmp_path,[('lesson/a.wav',wav_bytes()),('lesson/a.txt','hello world')])
    m=api();preview=m.preview_zip(z)
    assert len(preview['samples'])==1
    assert preview['samples'][0]['audio_path']=='lesson/a.wav'
    assert preview['samples'][0]['reference_path']=='lesson/a.txt'
    before=sha256(z)
    result=m.import_zip(z,tmp_path/'dataset','explicit-consent')
    row=result['samples'][0]
    assert row['text']=='hello world' and row['duration_s']==pytest.approx(.1)
    assert row['speaker_id']==row['session_id']=='unknown'
    assert not row['input_errors'] and row['pcm_sha256']
    assert sha256(z)==before and read_json(tmp_path/'dataset/dataset.json')==result
    assert len(list((tmp_path/'dataset/originals').iterdir()))==2
    with pytest.raises(FileExistsError):m.import_zip(z,tmp_path/'dataset','explicit-consent')


def test_metadata_mapping_and_missing_reference_preserved(tmp_path):
    z=archive(tmp_path,[('a.wav',wav_bytes()),('b.wav',wav_bytes()),('scripts/other.txt','hello'),
        ('metadata.csv','sample_id,audio_path,reference_path,domain,speaker_id,session_id,split\ncustom,a.wav,scripts/other.txt,classroom,p1,s1,development\n')])
    result=api().import_zip(z,tmp_path/'data','consent')
    rows={r['sample_id']:r for r in result['samples']}
    assert rows['custom']['text']=='hello' and rows['custom']['domain']=='classroom'
    assert len(rows)==2
    missing=next(r for r in rows.values() if r['audio_path']=='b.wav')
    assert missing['text'] is None and 'missing_reference' in missing['input_errors']
    assert result['status']=='NEEDS_ATTENTION'


def test_empty_reference_requires_explicit_silence_confirmation(tmp_path):
    z=archive(tmp_path,[('a.wav',wav_bytes()),('a.txt','')]);m=api()
    result=m.import_zip(z,tmp_path/'one','consent')
    assert 'unconfirmed_empty_reference' in result['samples'][0]['input_errors']
    result=m.import_zip(z,tmp_path/'two','consent',silence_ids=['a'])
    assert result['samples'][0]['text']=='' and not result['samples'][0]['input_errors']
    assert result['samples'][0]['silence_confirmed']


@pytest.mark.parametrize('name',['../a.wav','/a.wav','C:/a.wav','dir\\a.wav','a:stream.wav','x/../../a.wav'])
def test_reject_unsafe_paths_before_creating_output(tmp_path,name):
    z=archive(tmp_path,[(name,wav_bytes())])
    with pytest.raises(ValueError,match='[Uu]nsafe'):api().import_zip(z,tmp_path/'data','consent')
    assert not (tmp_path/'data').exists()


def test_reject_symlink_case_collision_and_size_limit(tmp_path):
    link=zipfile.ZipInfo('a.wav');link.create_system=3;link.external_attr=(stat.S_IFLNK|0o777)<<16
    z=archive(tmp_path,[(link,b'target')])
    with pytest.raises(ValueError,match='[Ss]ymlink'):api().preview_zip(z)
    z=archive(tmp_path,[('A.wav',wav_bytes()),('a.wav',wav_bytes())])
    with pytest.raises(ValueError,match='[Dd]uplicate'):api().preview_zip(z)
    z=archive(tmp_path,[('a.wav',wav_bytes())])
    with pytest.raises(ValueError,match='limit'):api().preview_zip(z,limits={'max_total_bytes':1})


def test_bad_audio_video_unknown_extensions_and_duration_are_explicit(tmp_path):
    m=api();z=archive(tmp_path,[('a.wav',b'invalid'),('a.txt','hi')])
    assert any('invalid_audio' in e for e in m.import_zip(z,tmp_path/'bad','consent')['samples'][0]['input_errors'])
    z=archive(tmp_path,[('a.mp4',b'video')])
    with pytest.raises(ValueError,match='Unsupported'):m.preview_zip(z)
    z=archive(tmp_path,[('run.py','print(1)')])
    with pytest.raises(ValueError,match='Unsupported'):m.preview_zip(z)
    z=archive(tmp_path,[('a.wav',wav_bytes(.2)),('a.txt','hi')])
    r=m.import_zip(z,tmp_path/'long','consent',limits={'max_duration_s':.1})
    assert 'duration_limit' in str(r['samples'][0]['input_errors'])


def test_ambiguous_stems_and_split_overlap_are_not_guessed(tmp_path):
    z=archive(tmp_path,[('a.wav',wav_bytes()),('a.flac',b'invalid'),('a.txt','hello')])
    assert all('ambiguous_pair' in r['input_errors'] for r in api().preview_zip(z)['samples'])
    z=archive(tmp_path,[('a.wav',wav_bytes()),('a.txt','hi'),('b.wav',wav_bytes()),('b.txt','hello'),
        ('metadata.csv','sample_id,audio_path,reference_path,speaker_id,session_id,split\na,a.wav,a.txt,p,s,development\nb,b.wav,b.txt,p,s,holdout\n')])
    r=api().import_zip(z,tmp_path/'data','consent')
    assert any('split_contamination' in str(x['input_errors']) for x in r['samples'])
