"""Bounded, non-executing ZIP input with explicit pairing and immutable provenance."""
import csv
import hashlib
import io
import stat
import wave
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

from .common import digest,read_json,sha256,utcnow,write_json
from .datasets import DatasetRegistry
from .storage import seal

AUDIO={'.wav','.m4a','.mp3','.flac'}
DEFAULT_LIMITS={'max_files':10000,'max_total_bytes':1024**3,'max_file_bytes':128*1024**2,
                'max_duration_s':600,'max_total_duration_s':36000,'max_text_bytes':2*1024**2}


def safe_name(name):
    p=PurePosixPath(name)
    if not name or '\\' in name or ':' in name or p.is_absolute() or any(
        x in ('','..','.') or x.endswith((' ','.')) or any(ord(c)<32 for c in x)
        for x in name.rstrip('/').split('/')):
        raise ValueError('Unsafe ZIP/member path: '+name)
    return p.as_posix()


def _members(z,limits):
    members={};seen=set();total=0
    if len(z.infolist())>limits['max_files']:raise ValueError('ZIP file count limit exceeded')
    for item in z.infolist():
        name=safe_name(item.orig_filename)
        if name.casefold() in seen:raise ValueError('Duplicate ZIP path (case-insensitive): '+name)
        seen.add(name.casefold())
        if stat.S_ISLNK(item.external_attr>>16):raise ValueError('Symlink archive member forbidden')
        if item.flag_bits&1:raise ValueError('Encrypted ZIP members unsupported')
        if item.is_dir():continue
        total+=item.file_size
        if item.file_size>limits['max_file_bytes'] or total>limits['max_total_bytes']:
            raise ValueError('ZIP size limit exceeded')
        suffix=PurePosixPath(name).suffix.lower()
        if suffix not in AUDIO|{'.txt','.csv'} or (suffix=='.csv' and PurePosixPath(name).name!='metadata.csv'):
            raise ValueError('Unsupported archive member (audio/TXT/metadata.csv only): '+name)
        if suffix in ('.txt','.csv') and item.file_size>limits['max_text_bytes']:raise ValueError('Text size limit exceeded')
        members[name]=item
    return members


def _metadata(z,members,metadata):
    if isinstance(metadata,list):return metadata
    if metadata:return list(csv.DictReader(Path(metadata).read_text(encoding='utf-8-sig').splitlines()))
    names=[n for n in members if PurePosixPath(n).name=='metadata.csv']
    if len(names)>1:raise ValueError('Multiple metadata.csv files; select an explicit metadata file')
    return list(csv.DictReader(io.StringIO(z.read(names[0]).decode('utf-8-sig')))) if names else []


def preview_zip(archive,metadata=None,limits=None):
    limits={**DEFAULT_LIMITS,**(limits or {})}
    with zipfile.ZipFile(archive) as z:
        members=_members(z,limits);mapping=_metadata(z,members,metadata)
        explicit={};used_refs=set()
        for item in mapping:
            name=safe_name(item.get('audio_path',''))
            if name not in members or PurePosixPath(name).suffix.lower() not in AUDIO:
                raise ValueError('Metadata audio not in archive: '+name)
            if name in explicit:raise ValueError('Duplicate metadata audio mapping: '+name)
            explicit[name]=item
        audio=[n for n in members if PurePosixPath(n).suffix.lower() in AUDIO]
        stems=Counter(str(PurePosixPath(n).with_suffix('')).casefold() for n in audio)
        texts={str(PurePosixPath(n).with_suffix('')).casefold():n for n in members if n.lower().endswith('.txt')}
        rows=[]
        for name in audio:
            stem=str(PurePosixPath(name).with_suffix(''));meta=explicit.get(name,{})
            ref=meta.get('reference_path') if name in explicit else texts.get(stem.casefold())
            errors=[]
            if stems[stem.casefold()]>1 and name not in explicit:errors.append('ambiguous_pair')
            if ref:
                ref=safe_name(ref)
                if ref not in members or not ref.lower().endswith('.txt'):errors.append('missing_reference')
                if ref in used_refs:errors.append('reference_reused_by_multiple_audio')
                used_refs.add(ref)
            else:errors.append('missing_reference')
            row={'sample_id':meta.get('sample_id') or (stem if stems[stem.casefold()]==1 else name),
                 'audio_path':name,'reference_path':ref,'language':meta.get('language') or 'en',
                 'domain':meta.get('domain') or 'unknown','speaker_id':meta.get('speaker_id') or 'unknown',
                 'session_id':meta.get('session_id') or 'unknown','split':meta.get('split') or 'development',
                 'reference_quality':meta.get('reference_quality') or 'unverified',
                 'input_errors':errors,'warnings':[],'duration_s':None}
            if row['language']!='en':errors.append('english_only')
            if row['split'] not in ('development','holdout','legacy_development','public_benchmark'):errors.append('invalid_split')
            if 'unknown' in (row['speaker_id'],row['session_id']):row['warnings'].append('unknown grouping; not independent sessions')
            rows.append(row)
        if not rows:raise ValueError('No supported audio in ZIP')
        ids=Counter(r['sample_id'] for r in rows)
        for row in rows:
            row['supplied_sample_id']=row['sample_id']
            if ids[row['sample_id']]>1:
                row['input_errors'].append('duplicate_sample_id')
                row['sample_id']='invalid-duplicate-'+digest({'id':row['sample_id'],'audio':row['audio_path']})
        return {'schema_version':'1.0','archive_sha256':sha256(archive),'samples':rows,'limits':limits,
                'unpaired_transcripts':[n for n in texts.values() if n not in used_refs]}


def _decode(data,limit):
    import av
    pcm=bytearray()
    with av.open(io.BytesIO(data)) as container:
        if container.streams.video or len(container.streams.audio)!=1:raise ValueError('audio_only_single_stream_required')
        resampler=av.AudioResampler(format='s16',layout='mono',rate=16000)
        def add(frames):
            for f in frames:
                if len(pcm)+f.samples*2>limit*32000:raise ValueError('duration_limit')
                pcm.extend(f.to_ndarray().astype('<i2',copy=False).tobytes())
        for frame in container.decode(container.streams.audio[0]):
            frame.pts=None;add(resampler.resample(frame))
        add(resampler.resample(None))
    if not pcm:raise ValueError('empty_audio')
    output=io.BytesIO()
    with wave.open(output,'wb') as f:
        f.setparams((1,2,16000,0,'NONE','not compressed'));f.writeframes(pcm)
    return output.getvalue(),bytes(pcm)


def import_zip(archive,out,consent_record_id,metadata=None,silence_ids=(),limits=None):
    if not str(consent_record_id).strip():raise ValueError('Explicit consent record required')
    preview=preview_zip(archive,metadata,limits);limits=preview['limits'];out=Path(out)
    out.mkdir(parents=True,exist_ok=False);(out/'originals').mkdir();(out/'wav').mkdir()
    silence=set(silence_ids);total_duration=0;budget_exhausted=False
    with zipfile.ZipFile(archive) as z:
        for i,row in enumerate(preview['samples']):
            key=f'{i:06d}';data=z.read(row['audio_path']);original=out/'originals'/(key+PurePosixPath(row['audio_path']).suffix.lower())
            original.write_bytes(data)
            row.update(original_audio_sha256=sha256(original),original_audio=str(original.resolve()),
                       consent_record_id=consent_record_id,provenance_type='real_measurement',text=None,
                       reference_revision=None,audio=str((out/'wav'/(key+'.wav')).resolve()),
                       audio_sha256=None,pcm_sha256=None,silence_confirmed=row['sample_id'] in silence,
                       preprocessing='pyav-mono-pcm16-16000-v1',word_alignment=None)
            try:
                remaining=limits['max_total_duration_s']-total_duration
                if budget_exhausted or remaining<=0:raise ValueError('total_duration_limit')
                allowed=min(limits['max_duration_s'],remaining)
                try:wav,pcm=_decode(data,allowed)
                except ValueError as exc:
                    if 'duration_limit' in str(exc) and allowed<limits['max_duration_s']:
                        budget_exhausted=True;raise ValueError('total_duration_limit') from exc
                    raise
                Path(row['audio']).write_bytes(wav)
                row.update(audio_sha256=sha256(row['audio']),pcm_sha256=hashlib.sha256(pcm).hexdigest(),duration_s=len(pcm)/32000)
                total_duration+=row['duration_s']
            except Exception as exc:row['input_errors'].append('invalid_audio: '+str(exc))
            if row['reference_path'] and 'missing_reference' not in row['input_errors']:
                data=z.read(row['reference_path']);ref=out/'originals'/(key+'.txt');ref.write_bytes(data)
                row['original_reference_sha256']=sha256(ref);row['original_reference']=str(ref.resolve())
                try:
                    row['text']=data.decode('utf-8-sig');row['reference_revision']=digest(row['text'])
                    if not row['text'].strip() and not row['silence_confirmed']:row['input_errors'].append('unconfirmed_empty_reference')
                except UnicodeError:row['input_errors'].append('reference_not_utf8')
    # Check contamination across all rows, even if another input error would prevent registration.
    rows=preview['samples']
    for i,a in enumerate(rows):
        for b in rows[:i]:
            if a['split']!=b['split'] and any(a.get(k) and a[k]==b.get(k) for k in ('speaker_id','session_id','pcm_sha256')):
                a['input_errors'].append('split_contamination');b['input_errors'].append('split_contamination')
    if len({r['split'] for r in rows})>1:
        for row in rows:row['input_errors'].append('mixed_splits; import one benchmark split at a time')
    ready=all(not r['input_errors'] for r in rows)
    if ready:
        manager=DatasetRegistry(out/'registry')
        for row in rows:manager.add(row)
        locked=manager.lock(rows[0]['split'])
        preview['dataset_manifest']=str((out/'registry'/f"split-{locked['split']}.json").resolve())
    import importlib.metadata
    preview.update(dataset_id=digest({'archive':preview['archive_sha256'],'rows':rows}),
        dataset_hash=digest(rows),created_utc=utcnow(),status='READY' if ready else 'NEEDS_ATTENTION',
        consent_record_id=consent_record_id,decoder_version=importlib.metadata.version('av'),
        split=rows[0]['split'],metadata_mapping=metadata if isinstance(metadata,list) else None)
    write_json(out/'dataset.json',preview,exclusive=True);seal(out)
    return preview


def verify_dataset(path):
    path=Path(path);dataset=read_json(path)
    if digest(dataset['samples'])!=dataset['dataset_hash']:raise ValueError('Dataset content hash changed')
    hashes=read_json(path.parent/'checksums.json')
    for name,expected in hashes.items():
        p=(path.parent/name).resolve()
        if not p.is_relative_to(path.parent.resolve()) or not p.is_file() or sha256(p)!=expected:
            raise ValueError('Imported dataset integrity failed: '+name)
    return dataset
