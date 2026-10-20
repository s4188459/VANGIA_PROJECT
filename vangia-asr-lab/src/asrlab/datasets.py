"""Consented audio manifests with immutable split locks and reference revisions."""
from pathlib import Path
import sqlite3
import json
import wave
from .common import canonical,digest,sha256,write_json,utcnow


class DatasetRegistry:
    def __init__(self,path):
        self.path=Path(path); self.path.mkdir(parents=True,exist_ok=True)
        self.db_path=self.path/'datasets.sqlite'
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS samples(id TEXT PRIMARY KEY, body TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS locks(split TEXT PRIMARY KEY, body TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS references_log(revision TEXT PRIMARY KEY, body TEXT NOT NULL)')

    def _db(self):return sqlite3.connect(self.db_path)

    def samples(self):
        with self._db() as db:return [json.loads(r[0]) for r in db.execute('SELECT body FROM samples ORDER BY id')]

    def add(self,item):
        item=dict(item); audio=Path(item['audio'])
        if audio.suffix.lower()!='.wav':raise ValueError('Only PCM WAV audio is accepted; video is excluded')
        if item.get('language')!='en':raise ValueError('English only')
        if not item.get('consent_record_id'):raise ValueError('Explicit consent record required')
        for key in ('sample_id','speaker_id','session_id','domain','split','reference_quality','provenance_type','text'):
            if key not in item or (key!='text' and not item[key]):raise ValueError(f'Missing {key}')
        if item['split'] not in ('development','holdout','legacy_development','public_benchmark','synthetic_fixture'):raise ValueError('Invalid split')
        if item['provenance_type'] not in ('real_measurement','simulated_fixture'):raise ValueError('Invalid provenance')
        if (item['split']=='synthetic_fixture')!=(item['provenance_type']=='simulated_fixture'):raise ValueError('synthetic split mismatch')
        with wave.open(str(audio),'rb') as f:
            if (f.getnchannels(),f.getsampwidth(),f.getframerate())!=(1,2,16000):raise ValueError('Require mono PCM16 16000 Hz WAV; declare resampling externally')
            pcm=f.readframes(f.getnframes()); duration=f.getnframes()/f.getframerate()
        import hashlib
        item.update(audio=str(audio.resolve()),audio_sha256=sha256(audio),pcm_sha256=hashlib.sha256(pcm).hexdigest(),
                    duration_s=duration,reference_revision=digest(item['text']),word_alignment=item.get('word_alignment'))
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM samples WHERE id=?',(item['sample_id'],)).fetchone():raise ValueError('duplicate sample ID')
            if db.execute('SELECT 1 FROM locks WHERE split=?',(item['split'],)).fetchone():raise ValueError('split locked')
            for r, in db.execute('SELECT body FROM samples'):
                old=json.loads(r)
                if old['split']!=item['split'] and (old['speaker_id']==item['speaker_id'] or old['session_id']==item['session_id'] or old['pcm_sha256']==item['pcm_sha256'] or old['sample_id']==item.get('parent_sample_id') or old.get('parent_sample_id')==item['sample_id']):
                    raise ValueError('split contamination: speaker/session/audio/parent overlap')
            db.execute('INSERT INTO samples VALUES (?,?)',(item['sample_id'],canonical(item)))
        return item

    def lock(self,split):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            rows=[json.loads(r[0]) for r in db.execute('SELECT body FROM samples ORDER BY id')]
            rows=[r for r in rows if r['split']==split]
            if not rows:raise ValueError('Cannot lock empty split')
            manifest={'split':split,'samples':rows,'sha256':digest(rows),'locked_utc':utcnow()}
            db.execute('INSERT INTO locks VALUES (?,?)',(split,canonical(manifest)))
            write_json(self.path/f'split-{split}.json',manifest,exclusive=True)
        return manifest

    def correct_reference(self,sample_id,text,reviewer_id):
        if not reviewer_id:raise ValueError('Reviewer required')
        original=next((r for r in self.samples() if r['sample_id']==sample_id),None)
        if not original:raise ValueError('Unknown sample')
        revision={'sample_id':sample_id,'text':text,'reviewer_id':reviewer_id,'parent_revision':original['reference_revision'],
                  'reference_revision':digest({'text':text,'parent':original['reference_revision'],'reviewer':reviewer_id}),
                  'created_utc':utcnow(),'applies_to_locked_manifest':False}
        with self._db() as db:db.execute('INSERT INTO references_log VALUES (?,?)',(revision['reference_revision'],canonical(revision)))
        return revision
