"""Bind separately supplied original audio to legacy evidence using byte-level hashes."""
import hashlib
import io
import wave
import zipfile
from pathlib import Path
from .common import read_json,sha256,write_json
from .datasets import DatasetRegistry


def canonical_wav(data):
    import av
    pcm=bytearray()
    with av.open(io.BytesIO(data),mode='r') as container:
        if len(container.streams.audio)!=1 or container.streams.video:raise ValueError('One audio stream and no video required')
        resampler=av.AudioResampler(format='s16',layout='mono',rate=16000)
        def append(frames):
            for frame in frames:
                if len(pcm)+frame.samples*2>16000*600*2:raise ValueError('Legacy audio sample exceeds 600 seconds')
                pcm.extend(frame.to_ndarray().astype('<i2',copy=False).tobytes())
        for frame in container.decode(container.streams.audio[0]):
            frame.pts=None;append(resampler.resample(frame))
        append(resampler.resample(None))
    if not pcm:raise ValueError('Empty audio')
    output=io.BytesIO()
    with wave.open(output,'wb') as f:f.setparams((1,2,16000,0,'NONE','not compressed'));f.writeframes(pcm)
    return output.getvalue()


def bind_archive(archive,legacy_json,out,consent_record_id):
    if not consent_record_id:raise ValueError('Explicit local processing consent record required')
    original=read_json(legacy_json);samples=original['dataset']['samples']
    if len(samples)!=100 or len({s['id'] for s in samples})!=100:raise ValueError('Expected 100 unique legacy samples')
    references={s['id']:s['reference'] for m in original['models'] if m['status']=='completed' for s in m['samples']}
    path=Path(out)
    if path.exists():raise FileExistsError(path)
    # Validate every source before creating outputs; never extract arbitrary archive paths.
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate archive entry')
        for s in samples:
            for name,key in [(f"TEST/{s['original_filename']}",'original_sha256'),(f"TEST/{s['id']}.txt",'reference_source_sha256')]:
                info=z.getinfo(name)
                if info.file_size>128*1024*1024:raise ValueError('Oversized archive member')
                if hashlib.sha256(z.read(name)).hexdigest()!=s[key]:raise ValueError(f'Original source hash mismatch: {name}')
        path.mkdir(parents=True);(path/'wav').mkdir();manager=DatasetRegistry(path/'dataset')
        mismatches=[]
        for s in samples:
            wav=canonical_wav(z.read(f"TEST/{s['original_filename']}"));target=path/'wav'/f"{s['id']}.wav";target.write_bytes(wav)
            canonical_match=hashlib.sha256(wav).hexdigest()==s['audio_sha256']
            if not canonical_match:mismatches.append(s['id'])
            manager.add({'sample_id':s['id'],'audio':str(target.resolve()),'text':references[s['id']],
                'language':'en','speaker_id':'legacy-speaker-unknown','session_id':'legacy-session-unknown',
                'domain':'legacy-unknown','consent_record_id':consent_record_id,'provenance_type':'real_measurement',
                'reference_quality':'unverified','split':'legacy_development','original_audio_sha256':s['original_sha256'],
                'original_reference_sha256':s['reference_source_sha256'],'historic_audio_sha256':s['audio_sha256'],
                'historical_canonical_hash_match':canonical_match,'preprocessing':'pyav-mono-pcm16-16000-v1',
                'grouping_quality':'speaker/session not known; one conservative correlated cluster',
                'acquisition_quality':'original content source not independently verified'})
    locked=manager.lock('legacy_development')
    import av
    result={'verified_original_audio_count':100,'verified_reference_source_count':100,
            'verified_canonical_wav_count':100-len(mismatches),'canonical_mismatch_ids':mismatches,
            'dataset_split':'legacy_development','archive_sha256':sha256(archive),'legacy_json_sha256':sha256(legacy_json),
            'dataset_sha256':locked['sha256'],'decoder_version':av.__version__,
            'dataset_manifest':str((path/'dataset/split-legacy_development.json').resolve()),
            'notice':'Source hash parity proves identity, not consent provenance, speech timing or untouched validation. Decoder differences are explicit.'}
    write_json(path/'binding.json',result);return result
