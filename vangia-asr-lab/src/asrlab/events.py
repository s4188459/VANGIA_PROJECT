"""Single-writer append-only journal, with immutable corrupt-tail recovery."""
import json
import os
import threading
import time
import uuid
from pathlib import Path
from .common import canonical, utcnow
from .storage import validate


class EventLog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.events, self.ids, self.clocks, self.stages = [], set(), {}, {}
        self.lock = threading.RLock()
        self.recovery = {'valid_events': 0, 'corrupt_tail_preserved': False}
        self.active = self.path
        parts = [self.path] + sorted(self.path.parent.glob(self.path.name+'.part-*'))
        for part in parts:
            if not part.exists(): continue
            lines = part.read_bytes().splitlines(keepends=True)
            for i,line in enumerate(lines):
                try:
                    if not line.endswith(b'\n'): raise ValueError('unfinished record')
                    e = json.loads(line)
                    self._check(e); self._accept(e)
                except (ValueError, UnicodeError):
                    if i != len(lines)-1: raise ValueError('Corrupt journal interior; manual recovery required')
                    self.recovery['corrupt_tail_preserved'] = True
                    break
            self.active = part
        if self.recovery['corrupt_tail_preserved']:
            self.active = self.path.with_name(self.path.name+f'.part-{len(parts):04}')
        self.recovery['valid_events'] = len(self.events)

    def _check(self,e):
        validate(e,'event.schema.json')
        if e['event_id'] in self.ids: raise ValueError('duplicate event ID')
        if self.events and e['run_id'] != self.events[0]['run_id']: raise ValueError('run ID mismatch')
        if e['monotonic_ns'] < self.clocks.get(e['clock_id'],0): raise ValueError('Invalid monotonic order')
        synthetic = e['provenance_type']=='simulated_fixture'
        if (e['input_mode']=='synthetic_fixture' or e['source']=='synthetic_fixture') != synthetic:
            raise ValueError('synthetic provenance/input mismatch')
        start,end=e.get('audio_start_sample'),e.get('audio_end_sample')
        if start is not None and end is not None and end<start: raise ValueError('Invalid sample order')
        kind=e['event_type']; key=(e['session_id'],e.get('chunk_id'),e.get('attempt_id'))
        required={'inference_started':'inference_queued','inference_finished':'inference_started'}
        if kind in required and required[kind] not in self.stages.get(key,set()):
            raise ValueError(f'{kind} requires {required[kind]}')
        if kind=='caption_presentation_verified' and not (e['payload'].get('verification_method') and e['payload'].get('instrument_id')):
            raise ValueError('Physical presentation verification instrument required')
        if kind=='caption_paint_ack' and e.get('trace_quality')!='paint_proxy':
            raise ValueError('paint acknowledgment must be labeled paint_proxy')

    def _accept(self,e):
        self.events.append(e); self.ids.add(e['event_id']); self.clocks[e['clock_id']]=e['monotonic_ns']
        self.stages.setdefault((e['session_id'],e.get('chunk_id'),e.get('attempt_id')),set()).add(e['event_type'])

    def append(self,e):
        with self.lock:
            self._check(e)
            with self.active.open('a',encoding='utf-8') as f:
                f.write(canonical(e)+'\n'); f.flush(); os.fsync(f.fileno())
            self._accept(e)
        return e

    def emit(self,kind,run_id,session_id,input_mode,source='worker',payload=None,**kw):
        with self.lock:
            e=dict(run_id=run_id,session_id=session_id,event_id=uuid.uuid4().hex,event_type=kind,
                   utc_iso8601=utcnow(),monotonic_ns=time.monotonic_ns(),clock_id=f'host-{os.getpid()}',
                   source=source,payload=payload or {},provenance_type='simulated_fixture' if input_mode=='synthetic_fixture' else 'real_measurement',
                   input_mode=input_mode,**kw)
            return self.append(e)
