"""Schema validation, immutable evidence and integrity auditing."""
from pathlib import Path
import json
import sqlite3

from jsonschema import Draft202012Validator, FormatChecker
from .common import ROOT, canonical, read_json, sha256, write_json


def validate(value, schema):
    errors = sorted(Draft202012Validator(read_json(ROOT/'schemas'/schema),
                    format_checker=FormatChecker()).iter_errors(value), key=lambda e: str(e.path))
    if errors:
        raise ValueError('; '.join(f'{list(e.path)}: {e.message}' for e in errors))


def create_run(path, manifest):
    validate(manifest, 'run_manifest.schema.json')
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    write_json(path/'manifest.json', manifest, exclusive=True)
    write_json(path/'manifest.sha256.json',{'sha256':sha256(path/'manifest.json')},exclusive=True)
    for name in ('events', 'predictions', 'reference', 'annotations'):
        (path/f'{name}.jsonl').touch()
    return path


def write_jsonl(path, rows):
    with Path(path).open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(canonical(row) + '\n')


def read_jsonl(path):
    if not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def index_evidence(path, configurations, samples):
    with sqlite3.connect(Path(path)/'evidence.sqlite') as db:
        db.execute('CREATE TABLE configurations (config_id TEXT PRIMARY KEY, label TEXT, evidence TEXT NOT NULL)')
        db.execute('CREATE TABLE samples (sample_id TEXT PRIMARY KEY, evidence TEXT NOT NULL)')
        db.executemany('INSERT INTO configurations VALUES (?,?,?)',
                      [(r['config_id'], r['label'], canonical(r)) for r in configurations])
        db.executemany('INSERT INTO samples VALUES (?,?)', [(r['id'], canonical(r)) for r in samples])


def seal(path):
    path = Path(path)
    files = {p.relative_to(path).as_posix(): sha256(p) for p in sorted(path.rglob('*'))
             if p.is_file() and p.name not in ('checksums.json', 'CANCEL')}
    write_json(path/'checksums.json', files)


def audit(path):
    path = Path(path)
    errors = []
    try:
        validate(read_json(path/'manifest.json'), 'run_manifest.schema.json')
        hashes = read_json(path/'checksums.json')
        for name, expected in hashes.items():
            target = (path/name).resolve()
            if not target.is_relative_to(path.resolve()):
                errors.append(f'unsafe checksum path: {name}')
            elif not target.is_file() or sha256(target) != expected:
                errors.append(f'checksum mismatch: {name}')
        from .events import EventLog
        events=EventLog(path/'events.jsonl')
        manifest=read_json(path/'manifest.json')
        if events.recovery['corrupt_tail_preserved']:
            recovery=read_json(path/'recovery.json') if (path/'recovery.json').exists() else {}
            preserved=recovery.get('preserved_journal_hashes',{})
            if not preserved:errors.append('corrupt journal tail preserved; recovery required')
            for name,expected in preserved.items():
                if Path(name).name!=name or not (path/name).is_file() or sha256(path/name)!=expected:errors.append('preserved journal changed')
        if any(e['run_id']!=manifest['run_id'] or e['input_mode']!=manifest['input_mode'] for e in events.events):
            errors.append('event/manifest identity mismatch')
        for a in read_jsonl(path/'annotations.jsonl'):validate(a,'reviewer_annotation.schema.json')
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    return {'ok': not errors, 'errors': errors, 'scope': 'integrity, not scientific validation'}


def recover_run(path):
    """Explicit crash recovery; preserve damaged originals and rebuild only derived snapshots."""
    import shutil
    from .events import EventLog
    path=Path(path);witness=read_json(path/'manifest.sha256.json')
    if sha256(path/'manifest.json')!=witness['sha256']:raise ValueError('immutable manifest changed; recovery refused')
    manifest=read_json(path/'manifest.json');validate(manifest,'run_manifest.schema.json')
    if manifest['input_mode'] in ('live_microphone','live_loopback'):raise ValueError('Cannot resume interrupted live capture; replay saved audio in a new run')
    if (path/'reference.sha256.json').exists() and sha256(path/'reference.jsonl')!=read_json(path/'reference.sha256.json')['sha256']:
        raise ValueError('immutable reference changed; recovery refused')
    if (path/'checksums.json').exists():raise ValueError('Run already sealed; use normal resume or inspect integrity errors')
    event_log=EventLog(path/'events.jsonl')
    if any(e['run_id']!=manifest['run_id'] for e in event_log.events):raise ValueError('Event run identity changed')
    recovery_dir=path/'recovery';recovery_dir.mkdir(exist_ok=False)
    for name in ('predictions.jsonl','state.json'):
        if (path/name).exists():shutil.copyfile(path/name,recovery_dir/(name+'.original'))
    rows=[]
    for attempts in (path/'prediction_attempts.jsonl',path/'prediction_attempts.resumed.jsonl'):
        if not attempts.exists():continue
        lines=attempts.read_bytes().splitlines(keepends=True)
        for i,line in enumerate(lines):
            try:
                if not line.endswith(b'\n'):raise ValueError('partial tail')
                rows.append(json.loads(line))
            except ValueError:
                if i!=len(lines)-1:raise ValueError('Corrupt attempt journal interior')
                break
        shutil.copyfile(attempts,recovery_dir/(attempts.name+'.original'))
    latest={r['sample_id']:r for r in rows};write_jsonl(path/'predictions.jsonl',latest.values())
    preserved={p.name:sha256(p) for p in [path/'events.jsonl']+sorted(path.glob('events.jsonl.part-*')) if p.exists()}
    result={'status':'failed','reason':'interrupted; recovered durable attempts, resume explicitly',
            'recovered_samples':len(latest),'preserved_journal_hashes':preserved}
    write_json(path/'recovery.json',result,exclusive=True);write_json(path/'state.json',result)
    write_json(path/'metrics.json',{'status':'INSUFFICIENT EVIDENCE','reason':'interrupted run recovered; metrics require resume'})
    from .reports import report
    report(path);seal(path);return result
