"""Auditable batch and real-time-paced independent chunk jobs with resumable state."""
import csv
import json
import os
import platform
import queue
import random
import threading
import time
import uuid
from pathlib import Path

from .common import canonical,digest,model_record,read_json,sha256,utcnow,write_json
from .storage import create_run,read_jsonl,seal,write_jsonl,audit
from .events import EventLog
from .metrics import corpus_score,paired_score_rows,NORMALIZATION
from .audio import read_pcm,write_pcm,paced_chunks,merge,live_chunks
from .adapters import preflight
from .worker_client import WorkerClient
from .timing import backlog,stability,session_trace_metrics,pending_audio_seconds


def _append(path,row):
    path=Path(path)
    if path.name=='prediction_attempts.jsonl' and (path.parent/'recovery.json').exists():path=path.with_name('prediction_attempts.resumed.jsonl')
    with Path(path).open('a',encoding='utf-8') as f:f.write(canonical(row)+'\n');f.flush();os.fsync(f.fileno())


def _metric(value,metric_id,manifest,unit,numerator=None,denominator=None,reason=None):
    return {'metric_id':metric_id,'definition_version':'1.0','model_config_id':manifest.get('model_config_id'),
            'dataset_id':manifest['dataset_id'],'split_id':manifest['dataset_split'],'input_mode':manifest['input_mode'],
            'unit':unit,'numerator':numerator,'denominator':denominator,'value':value,'missing_reason':reason,
            'coverage':None,'uncertainty':None,'clock_basis':manifest.get('clock_id'),
            'source_run_ids':[manifest['run_id']],'evidence_class':manifest['evidence_class']}


def decoder_config(config):
    fields=('model_id','backend','weights_path','artifact_provenance','device','precision','threads',
            'beam_size','vad_filter','condition_on_previous_text','max_new_tokens','language','diagnostic_retry')
    return {k:config[k] for k in fields if k in config}


def configuration_id(config,identity):
    """Deployment configuration identity excludes job, repetition and corpus identity."""
    defaults={'mode':'batch_file','chunk_seconds':2,'overlap_seconds':0,'merge_policy':'prefix_dedupe',
              'context_policy':'none','vad':None,'language':'en','precision':'int8','device':'cpu',
              'threads':4,'beam_size':5,'vad_filter':False,'condition_on_previous_text':False}
    dimensions={**defaults,**decoder_config(config)}
    dimensions.update({k:config.get(k,v) for k,v in defaults.items()})
    dimensions['worker_python']=config.get('worker_python') or ''
    dimensions['normalization']=NORMALIZATION
    return digest({'deployment':dimensions,'artifact':identity})


def run(config,presenter=None,cancel_requested=None):
    config=dict(config);out=Path(config['out']);mode=config.get('mode','batch_file')
    effective={k:v for k,v in config.items() if k not in ('out','resume')}
    synthetic=mode=='synthetic_fixture'; run_id=config.get('run_id') or uuid.uuid4().hex
    live=mode in ('live_microphone','live_loopback')
    if live and config.get('resume'):raise ValueError('Cannot resume live capture; create a new consented session or replay the saved audio')
    if mode in ('paced_replay','live_microphone','live_loopback'):
        chunk=config.get('chunk_seconds',2);overlap=config.get('overlap_seconds',0)
        import math
        if not isinstance(chunk,(int,float)) or not math.isfinite(chunk) or chunk<=0 or not 0<=overlap<chunk:raise ValueError('Invalid chunk/overlap seconds')
        if config.get('vad') and overlap:raise ValueError('VAD adaptive chunks require overlap=0')
    reasons=[];model=None;ready=None
    if not synthetic:
        model=model_record(config['model_id']);ready=preflight(config);reasons+=ready['reasons']
    samples=config.get('samples',[])
    if live:
        samples=[{'sample_id':'capture','session_id':config.get('session_id',run_id),'speaker_id':config.get('speaker_id','unknown'),
                  'audio':str((out/'captured.wav').resolve()),'text':config.get('reference',''),'language':'en',
                  'consent_record_id':config.get('capture_consent_record_id'),'duration_s':config.get('capture_duration_s',0),
                  'domain':config.get('domain','unverified'),'reference_quality':'unverified'}]
    if config.get('dataset_manifest'):
        split=read_json(config['dataset_manifest'])
        if digest(split['samples'])!=split['sha256']:raise ValueError('Dataset split hash mismatch')
        samples=split['samples']
        if config.get('dataset_split',split['split'])!=split['split']:raise ValueError('Split mismatch')
        config['dataset_split']=split['split']
    if not synthetic:
        if not samples:reasons.append('missing_audio: no dataset samples')
        ids=set()
        for s in samples:
            if s.get('input_errors'):reasons.append(f"input_errors: {s['sample_id']}: {s['input_errors']}")
            if s.get('split') and s['split']!=config.get('dataset_split','development'):
                raise ValueError('Sample split differs from effective run split; holdout data cannot be relabeled')
            if s['sample_id'] in ids:raise ValueError('duplicate job/sample ID')
            ids.add(s['sample_id'])
            if not s.get('consent_record_id'):reasons.append(f"consent required: {s['sample_id']}")
            if s.get('language','en')!='en':raise ValueError('English only')
            if s.get('provenance_type')=='simulated_fixture':reasons.append('synthetic input cannot be labeled real; use synthetic_fixture workflow')
            try:
                if live:continue
                pcm,rate=read_pcm(s['audio'])
                import hashlib
                if s.get('pcm_sha256')!=hashlib.sha256(pcm).hexdigest():reasons.append(f"PCM hash absent/mismatch: {s['sample_id']}")
                actual_duration=len(pcm)/2/rate
                if not isinstance(s.get('duration_s'),(int,float)) or abs(s['duration_s']-actual_duration)>1/rate:reasons.append(f"audio duration absent/mismatch: {s['sample_id']}")
                if s.get('reference_revision')!=digest(s.get('text','')):reasons.append(f"reference revision absent/mismatch: {s['sample_id']}")
                if not s.get('audio_sha256') or sha256(s['audio'])!=s['audio_sha256']:reasons.append(f"audio hash absent/mismatch: {s['sample_id']}")
            except (ValueError,OSError) as exc:reasons.append(f"missing_audio / invalid audio: {s['sample_id']}: {exc}")
        if config.get('dataset_split')=='holdout' and not (config.get('dataset_manifest') and config.get('preregistration')):
            reasons.append('Held-out run requires locked dataset_manifest and preregistration')
        elif config.get('dataset_split')=='holdout':
            from .governance import check_registration
            check_registration(read_json(config['preregistration']),split,effective)
    identity=read_json(config['artifact_provenance']) if not synthetic and config.get('artifact_provenance') and Path(config['artifact_provenance']).is_file() else {}
    manifest={'run_id':run_id,'schema_version':'1.0','language':'en','dataset_id':config.get('dataset_id','fixture' if synthetic else 'local'),
              'dataset_split':'synthetic_fixture' if synthetic else config.get('dataset_split','development'),
              'input_mode':mode,'created_utc':utcnow(),'evidence_class':'SYNTHETIC' if synthetic else 'E-LOCAL',
              'status':'planned','model_id':model['canonical_model_id'] if model else None,
              'checkpoint_revision':identity.get('revision'),'weights_sha256':digest(identity['files']) if identity.get('files') else None,
              'artifact_identity':identity,
              'model_config_id':configuration_id(config,identity),
              'config':effective,'dataset_hash':digest(samples),'normalization_version':NORMALIZATION,
              'hardware':{'platform':platform.platform(),'cpu':platform.processor(),'logical_cores':os.cpu_count()},
              'random_seed':config.get('random_seed',42),'clock_id':f'host-{os.getpid()}',
              'clock_calibration':None,'source_urls':[model['model_card_url']] if model else [],
              'missing_reasons':['physical_presentation_not_measured','reference_word_alignment_not_measured']}
    if out.exists():
        if not config.get('resume'):raise FileExistsError(out)
        old=read_json(out/'manifest.json')
        if old['model_config_id'] not in (manifest['model_config_id'],digest({'config':effective,'artifact':identity})):raise ValueError('Resume artifact/config identity changed')
        if old['config']!=effective or old['dataset_hash']!=digest(samples):raise ValueError('Resume config/dataset must match immutable manifest')
        result=audit(out)
        if not result['ok']:raise ValueError('Cannot resume modified evidence: '+str(result['errors']))
        state=read_json(out/'state.json')
        if state['status']=='completed':return state
        manifest=old;run_id=old['run_id']
        if (out/'CANCEL').exists(): (out/'CANCEL').unlink()
    else:create_run(out,manifest)
    run_id=manifest['run_id'];log=EventLog(out/'events.jsonl')
    def emit(kind,session='run',**kw):
        e=log.emit(kind,run_id,session,mode,**kw)
        if kind=='caption_update_requested' and presenter:
            from .timing import present_caption
            present_caption(e,log,presenter,config.get('ui_ack_timeout_s',5))
        return e
    def cancelled():return (out/'CANCEL').exists() or bool(cancel_requested and cancel_requested())
    state={'status':'blocked' if reasons else 'running','reasons':reasons,'evidence_class':manifest['evidence_class']}
    write_json(out/'state.json',state)
    if reasons or cancelled():
        if cancelled():state={'status':'cancelled','reasons':['cancelled_before_model_load'],'evidence_class':manifest['evidence_class']}
        emit('run_finished',payload=state)
        write_json(out/'metrics.json',{'status':state['status'].upper(),'reasons':state['reasons'],'wer':None,'live_lag_p95_s':None})
        from .reports import report
        report(out);seal(out);return state
    emit('run_started',payload={'resume':config.get('resume',False)})
    if synthetic:
        # No decoder is impersonated: fixed fixtures exercise plumbing only.
        refs=[{'sample_id':'fixture-1','text':'the sample is synthetic','domain':'fixture','reference_revision':digest('the sample is synthetic')}]
        preds=[{'sample_id':'fixture-1','text':'the sample is synthetic','status':'completed','provenance_type':'simulated_fixture'}]
        emit('inference_queued',chunk_id='fixture-1',payload={'fixture':True})
        emit('inference_started',chunk_id='fixture-1',payload={'fixture':True})
        emit('inference_finished',chunk_id='fixture-1',payload={'fixture':True})
        emit('hypothesis_emitted',chunk_id='fixture-1',hypothesis_version=1,caption_text=preds[0]['text'],model_id=None,payload={'fixture':True})
        emit('caption_update_requested',caption_text=preds[0]['text'],payload={'fixture':True})
        write_jsonl(out/'reference.jsonl',refs);write_jsonl(out/'predictions.jsonl',preds)
        metrics={**corpus_score(refs,preds),'evidence_class':'SYNTHETIC','notice':'SIMULATED TEST FIXTURE; no ASR inference or usability evidence',
                 'live_lag_p95_s':None,'presentation_missing_reason':'not_measured'}
        state={'status':'completed','evidence_class':'SYNTHETIC'}
    else:
        worker=None;start=time.monotonic();service_s=0;load_s=None;resources=[];backlog_rows=[];revisions=[]
        predictions={r['sample_id']:r for r in read_jsonl(out/'predictions.jsonl')}
        service_s=sum(r.get('service_s',0) for r in predictions.values() if r.get('status')=='completed')
        refs=[{**s,'text':s.get('text','')} for s in samples]
        if not (out/'reference.jsonl').stat().st_size:
            write_jsonl(out/'reference.jsonl',refs)
            write_json(out/'reference.sha256.json',{'sha256':sha256(out/'reference.jsonl')},exclusive=True)
        ordered=list(samples);random.Random(config.get('random_seed',42)).shuffle(ordered)
        if not (out/'job_order.json').exists():write_json(out/'job_order.json',[s['sample_id'] for s in ordered],exclusive=True)
        try:
            if cancelled():raise InterruptedError('cancelled')
            worker=WorkerClient(config.get('worker_python'),out,cancelled)
            emit('model_load_started')
            loaded=worker.request('load',timeout=config.get('load_timeout_s',1800),config=decoder_config(config))
            load_s=loaded['service_ns']/1e9
            _append(out/'worker_provenance.jsonl',loaded['result'])
            emit('model_loaded',payload={'load_s':load_s,**loaded['result']})
            for sample in ordered:
                sid=sample['sample_id']
                if predictions.get(sid,{}).get('status')=='completed':continue
                if cancelled():raise InterruptedError('cancelled')
                attempt=uuid.uuid4().hex
                try:
                    if mode=='batch_file':
                        emit('inference_queued',sid,chunk_id=sid,attempt_id=attempt)
                        emit('inference_started',sid,chunk_id=sid,attempt_id=attempt)
                        result=worker.request('transcribe',timeout=config.get('inference_timeout_s',600),audio=sample['audio'])
                        elapsed=result['service_ns']/1e9;service_s+=elapsed
                        emit('inference_finished',sid,chunk_id=sid,attempt_id=attempt,payload={'worker_service_s':elapsed,'worker_clock_id':result['clock_id'],'cross_clock_offset':None})
                        prediction={**result['result'],'service_s':elapsed}
                    else:
                        prediction,elapsed=_run_paced(sample,config,out,worker,emit,cancelled,backlog_rows,revisions)
                        service_s+=elapsed
                    row={'sample_id':sid,'session_id':sample.get('session_id',sid),'pcm_sha256':sample.get('pcm_sha256'),
                         'reference_revision':sample.get('reference_revision'),'attempt_id':attempt,'status':'completed',
                         'provenance_type':'real_measurement',**prediction}
                except (RuntimeError,TimeoutError,ValueError) as exc:
                    row={'sample_id':sid,'attempt_id':attempt,'status':'failed','error':str(exc),'text':None}
                    emit('inference_error',sid,chunk_id=sid,attempt_id=attempt,payload={'reason':str(exc)})
                _append(out/'prediction_attempts.jsonl',row);predictions[sid]=row
                write_jsonl(out/'predictions.jsonl',predictions.values())
                if worker.process.poll() is not None:break
            state={'status':'completed' if len(predictions)==len(samples) and all(r['status']=='completed' for r in predictions.values()) else 'failed',
                   'evidence_class':'E-LOCAL'}
        except InterruptedError:
            state={'status':'cancelled','evidence_class':'E-LOCAL'}
        except (RuntimeError,TimeoutError,OSError,ValueError) as exc:
            state={'status':'failed','error':str(exc),'evidence_class':'E-LOCAL'}
        finally:
            if worker:resources=worker.resources;worker.close()
        for sample in samples:
            if sample['sample_id'] not in predictions:predictions[sample['sample_id']]={'sample_id':sample['sample_id'],'status':'cancelled' if state['status']=='cancelled' else 'failed','error':state.get('error',state['status'])}
        write_jsonl(out/'predictions.jsonl',predictions.values())
        if live and (out/'captured.wav').exists():
            write_json(out/'captured_audio.json',{'audio_sha256':sha256(out/'captured.wav'),'reference_quality':'unverified',
                        'input_mode':mode,'source_audio':str(out/'captured.wav')})
        with (out/'resources.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=['monotonic_ns','pid','cpu_percent','rss_bytes','read_bytes','write_bytes','process_count','resource_scope','partial']);writer.writeheader();writer.writerows(resources)
        duration=sum(s.get('duration_s',0) for s in samples)
        scoring=corpus_score(refs,list(predictions.values()))
        if live and not config.get('reference'):
            scoring={'status':'reference_unreviewed','completion_fraction':1 if state['status']=='completed' else 0,
                     'normalized':{'wer_micro':None,'missing_reason':'reference_unreviewed'}}
        metrics={**scoring,'load_s':load_s,'inference_service_s':service_s,'offline_turnaround_s':time.monotonic()-start,
            'rtf':service_s/duration if duration and state['status']=='completed' else None,
            'rtfx':duration/service_s if duration and service_s and state['status']=='completed' else None,
            'rtf_scope':'inference service only; excludes load, queue and rendering','live_lag_p95_s':None,
            'presentation_missing_reason':'not_measured',**session_trace_metrics(backlog_rows,revisions),
            'resource_samples':len(resources),'peak_worker_rss_bytes':max((r['rss_bytes'] for r in resources),default=None),
            'resource_scope':'worker_process_tree; summed RSS may count shared pages more than once; excludes GUI; CPU uses one-core=100%; new-process first sample has no CPU interval',
            'error_count':sum(p['status']!='completed' for p in predictions.values())}
        metrics['metric_records']=[_metric(metrics['rtf'],'rtf',manifest,'s/s',service_s,duration,
                    None if metrics['rtf'] is not None else 'incomplete_corpus'),
                    _metric(None,'word_first_presented_lag_p95_s',manifest,'s',reason='not_measured')]
    from .timing import trace_summary
    metrics['trace_summary']=trace_summary(log.events)
    write_jsonl(out/'paired_scores.jsonl',paired_score_rows(refs,preds if synthetic else list(predictions.values())))
    write_json(out/'metrics.json',metrics);write_json(out/'state.json',state)
    emit('run_finished',payload=state)
    from .reports import report
    report(out);seal(out)
    return state


def _run_paced(sample,config,out,worker,emit,cancelled,backlog_rows,revisions):
    chunks=queue.Queue(maxsize=10000);stop=threading.Event();origin=time.monotonic();sid=sample['sample_id']
    def producer():
        try:
            cancel=lambda:stop.is_set() or cancelled()
            if config['mode']=='live_microphone':
                source=live_chunks(sample['audio'],config['capture_duration_s'],config['capture_consent_record_id'],config['capture_device'],config.get('chunk_seconds',2),config.get('overlap_seconds',0),cancel)
            else:source=paced_chunks(sample['audio'],config.get('chunk_seconds',2),config.get('overlap_seconds',0),cancel,config.get('vad'))
            for chunk in source:
                if stop.is_set():break
                chunk['chunk_id']=uuid.uuid4().hex
                chunk['attempt_id']=uuid.uuid4().hex
                emit('audio_frame_captured',sid,source='microphone' if config['mode']=='live_microphone' else 'paced_replay',audio_start_sample=chunk['start_sample'],audio_end_sample=chunk['end_sample'],sample_rate_hz=chunk['sample_rate_hz'],
                     payload={'source_capture_ns':chunk['captured_ns'],'capture_origin_ns':chunk['capture_origin_ns']})
                emit('chunk_created',sid,chunk_id=chunk['chunk_id'],audio_start_sample=chunk['start_sample'],audio_end_sample=chunk['end_sample'],sample_rate_hz=chunk['sample_rate_hz'],
                     payload={'segmentation_policy':chunk.get('segmentation_policy','fixed_window'),'adapted_independent_inference':True})
                queued=emit('inference_queued',sid,chunk_id=chunk['chunk_id'],attempt_id=chunk['attempt_id'],payload={'queued_at_capture_ns':chunk['captured_ns']})
                chunk['enqueued_ns']=queued['monotonic_ns']
                chunks.put(chunk,timeout=1)
        except Exception as exc:chunks.put(exc)
        finally:chunks.put(None)
    thread=threading.Thread(target=producer,daemon=True);thread.start()
    text='';elapsed=0;version=0
    try:
        while True:
            if cancelled():raise InterruptedError('cancelled')
            try:c=chunks.get(timeout=.1)
            except queue.Empty:continue
            if c is None:break
            if isinstance(c,Exception):raise c
            cid=c['chunk_id'];attempt=c['attempt_id'];rate=c['sample_rate_hz']
            queue_age=(time.monotonic_ns()-c['captured_ns'])/1e9
            with chunks.mutex:pending=[x for x in chunks.queue if isinstance(x,dict)]
            pending_s=pending_audio_seconds([c]+pending,rate)
            elapsed_source=time.monotonic()-origin
            backlog_rows.append({'session_id':sid,'elapsed_s':elapsed_source,'pending_audio_s':pending_s,
                'oldest_pending_age_s':queue_age,'capture_active':elapsed_source<=sample.get('duration_s',float('inf'))})
            emit('resource_sample',sid,payload=backlog_rows[-1])
            chunkfile=out/'current_chunk.wav';write_pcm(chunkfile,c['pcm'])
            emit('inference_started',sid,chunk_id=cid,attempt_id=attempt,payload={'queue_dwell_s':(time.monotonic_ns()-c['enqueued_ns'])/1e9,'capture_end_to_service_s':queue_age})
            result=worker.request('transcribe',timeout=config.get('inference_timeout_s',600),audio=str(chunkfile.resolve()))
            elapsed+=result['service_ns']/1e9
            emit('inference_finished',sid,chunk_id=cid,attempt_id=attempt,payload={'worker_service_s':result['service_ns']/1e9})
            version+=1
            emit('hypothesis_emitted',sid,chunk_id=cid,hypothesis_version=version,caption_text=result['result']['text'],model_id=config['model_id'])
            merged=merge(text,result['result']['text'],config.get('overlap_seconds',0)>0 and config.get('merge_policy','prefix_dedupe')!='plain_concat')
            text=merged['text'];revisions.append({'session_id':sid,'text':text})
            emit('merge_revision',sid,chunk_id=cid,hypothesis_version=version,caption_text=text,payload=merged)
            emit('caption_update_requested',sid,chunk_id=cid,hypothesis_version=version,caption_text=text,
                 payload={'presentation':'not_measured; UI must acknowledge separately'})
    finally:
        stop.set();thread.join(timeout=2)
    return {'text':text,'service_s':elapsed,'segments':None,'word_timestamps_quality':'insufficient_alignment'},elapsed
