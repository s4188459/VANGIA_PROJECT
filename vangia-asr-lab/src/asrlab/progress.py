"""Read-only live progress. Never audits or scores unfinished evidence."""
import json
import time
from datetime import datetime
from pathlib import Path
import psutil

TERMINAL = {'completed', 'failed', 'blocked', 'cancelled', 'incomplete'}

def _json(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def _lines(path):
    if not path.exists(): return []
    lines = path.read_text(encoding='utf-8').splitlines()
    rows = []
    for index, line in enumerate(lines):
        try: rows.append(json.loads(line))
        except json.JSONDecodeError:
            if index != len(lines)-1: raise
    return rows

def snapshot(source, now=None):
    source = Path(source); now = time.time() if now is None else now
    plan = _json(source/'benchmark.json', {})
    state = _json(source/'state.json', {})
    owner = _json(source/'ACTIVE', {})
    alive = False; workers = []; rss = 0
    if owner:
        try:
            process = psutil.Process(owner['pid'])
            alive = process.create_time() == owner['created']
            if alive:
                for p in process.children(recursive=True):
                    try:
                        if 'asrlab.worker' in p.cmdline():
                            workers.append(p.pid); rss += p.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied): pass
        except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError): pass
    outcomes = {j['job_id']: j for j in state.get('jobs', [])}
    rows = []; latest = None
    for index, job in enumerate(plan.get('jobs', [])):
        folder = source/job['run_path']; outcome = outcomes.get(job['job_id'], {})
        local = _json(folder/'state.json', {})
        status = local.get('status', outcome.get('status', 'waiting'))
        events = _lines(folder/'events.jsonl'); event = events[-1] if events else {}
        event_time = datetime.fromisoformat(event['utc_iso8601']).timestamp() if event.get('utc_iso8601') else None
        if event_time is not None: latest = max(latest or event_time, event_time)
        started = next((e for e in reversed(events) if e.get('event_type')=='run_started'), None)
        start_time = datetime.fromisoformat(started['utc_iso8601']).timestamp() if started and started.get('utc_iso8601') else None
        elapsed = max(0,(event_time if status in TERMINAL and event_time else now)-start_time) if start_time else None
        predictions = {r['sample_id']: r for r in _lines(folder/'predictions.jsonl')}
        # Append-only attempts remain available during prediction-file replacement.
        attempts = {r['sample_id']: r for r in _lines(folder/'prediction_attempts.jsonl')}
        for sid, row in attempts.items():
            if sid not in predictions: predictions[sid] = row
        total = len(plan.get('samples', []))
        counts = {s: sum(r.get('status') == s for r in predictions.values()) for s in ('completed','failed','cancelled')}
        pending = max(0, total-sum(counts.values()))
        if status == 'cancelled': counts['cancelled'] += pending; pending = 0
        errors = [r.get('error') for r in predictions.values() if r.get('error')]
        error = errors[-1] if errors else local.get('error') or '; '.join(local.get('reasons', outcome.get('reasons', [])))
        phase = {'run_started':'Checking inputs', 'model_load_started':'Loading model',
                 'model_loaded':'Model loaded', 'inference_started':'Transcribing',
                 'inference_queued':'Queued audio', 'inference_finished':'Saving prediction',
                 'inference_error':'Inference error', 'run_finished':'Finished'}.get(event.get('event_type'), event.get('event_type', 'Waiting / checking prerequisites'))
        if status in TERMINAL: phase = status.capitalize()
        if status == 'running' and not alive: phase = 'Interrupted: owner process is not running'
        rows.append({'job_id':job['job_id'], 'model':job['config']['model_id'], 'index':index+1,
                     'repeat':job['repeat_id'], 'status':status, 'phase':phase, 'total':total,
                     **counts, 'pending':pending, 'sample':event.get('chunk_id') or '',
                     'event_age_s':max(0, now-event_time) if event_time is not None else None,
                     'elapsed_s':elapsed,
                     'error':error or '', 'run_path':str(folder)})
    active = next((r for r in rows if r['status']=='running'), None)
    status = 'stopping' if alive and (source/'CANCEL').exists() else 'running' if alive else state.get('status','planned')
    if status == 'running' and not alive: status = 'interrupted'
    return {'status':status, 'alive':alive, 'workers':workers, 'worker_rss_mib':rss/1048576,
            'rows':rows, 'active':active, 'last_event_age_s':max(0,now-latest) if latest else None,
            'total':sum(r['total'] for r in rows),
            **{k:sum(r[k] for r in rows) for k in ('completed','failed','cancelled','pending')}}
