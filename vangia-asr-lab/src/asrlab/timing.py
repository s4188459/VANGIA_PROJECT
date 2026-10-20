"""Timing endpoints, censored omissions, queue growth and transcript revisions."""
from statistics import mean
from .metrics import align


def percentile(values,p):
    if not values:return None
    v=sorted(values); i=(len(v)-1)*p/100; low=int(i); high=min(low+1,len(v)-1)
    return v[low]+(v[high]-v[low])*(i-low)


def interval(start,end,calibrations=None):
    a,b=start['monotonic_ns'],end['monotonic_ns']; uncertainty=0
    if start['clock_id']!=end['clock_id']:
        calibrations=calibrations or {}
        for e,sign in ((start,-1),(end,1)):
            if e['clock_id']=='host':continue
            c=calibrations.get(e['clock_id'])
            if not c:return {'value':None,'missing_reason':'clock_unsynchronized','uncertainty_s':None}
            if c['uncertainty_ns']<0:raise ValueError('Invalid uncertainty')
            if sign<0:a+=c['offset_to_host_ns']
            else:b+=c['offset_to_host_ns']
            uncertainty+=c['uncertainty_ns']
    if b<a:raise ValueError('Negative time interval')
    return {'value':(b-a)/1e9,'missing_reason':None,'uncertainty_s':uncertainty/1e9}


def word_lag(references,events,event_type,calibrations=None):
    endpoints={'caption_paint_ack':'paint_proxy','caption_presentation_verified':'physical_presentation',
               'hypothesis_emitted':'model_emission','caption_committed':'commit'}
    if event_type not in endpoints:raise ValueError('UI request is not a measured endpoint')
    rows=[]
    for i,r in enumerate(references):
        row={'value':None,'missing_reason':'not_emitted_or_not_presented','uncertainty_s':None}
        if not r.get('reviewed') or r.get('end_ns') is None:
            row['missing_reason']='insufficient_alignment'
        else:
            matches=[e for e in events if e['event_type']==event_type and e.get('reference_word_index')==i]
            if event_type=='caption_presentation_verified':
                matches=[e for e in matches if e.get('payload',{}).get('verification_method') and e.get('payload',{}).get('instrument_id')]
            if matches:
                # Never subtract a segment timestamp as a word timestamp.
                results=[interval({'monotonic_ns':r['end_ns'],'clock_id':r['clock_id']},e,calibrations) for e in matches]
                valid=[v for v in results if v['value'] is not None]
                row=min(valid,key=lambda x:x['value']) if valid else results[0]
        rows.append(row)
    values=[r['value'] for r in rows if r['value'] is not None]
    return {'endpoint':endpoints[event_type],'observations':rows,'n_matched':len(values),'n_total':len(rows),
            'coverage':len(values)/len(rows) if rows else 0,'missing_fraction':1-len(values)/len(rows) if rows else None,
            **{f'p{p}':percentile(values,p) for p in (50,90,95,99)},'max':max(values) if values else None,
            'percentile_scope':'valid timed matches only; not a bound on omitted words'}


def backlog(rows):
    if len(rows)<2:return {'slope_s_per_min':None,'sustained_growth':None,'n':len(rows)}
    xs=[r['elapsed_s']/60 for r in rows];ys=[r['pending_audio_s'] for r in rows]
    if any(y<0 for y in ys) or any(b<=a for a,b in zip(xs,xs[1:])):raise ValueError('Invalid backlog times')
    xm,ym=mean(xs),mean(ys); slope=sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/sum((x-xm)**2 for x in xs)
    return {'slope_s_per_min':slope,'sustained_growth':slope>0,'n':len(rows),
            'max_pending_audio_s':max(ys),'max_oldest_pending_age_s':max(r['oldest_pending_age_s'] for r in rows)}


def stability(revisions,committed_prefix_lengths=None):
    committed_prefix_lengths=committed_prefix_lengths or [0]*len(revisions)
    changes=violations=0
    for i,(a,b) in enumerate(zip(revisions,revisions[1:])):
        changes+=sum(r['op']!='equal' for r in align(a.split(),b.split()))
        k=committed_prefix_lengths[i]
        violations+=a.split()[:k]!=b.split()[:k]
    n=len(revisions[-1].split()) if revisions else 0
    return {'changed_tokens':changes,'revisions_per_100_final_words':changes*100/n if n else None,
            'post_commit_modifications':violations,'first_final_mismatch':revisions[0]!=revisions[-1] if revisions else None}


def present_caption(request,log,presenter,timeout=5):
    """Wait for GUI redraw-cycle acknowledgment, never for unobservable physical display."""
    import threading
    done=threading.Event();gate=threading.Lock();active=True
    def ack():
        nonlocal active
        with gate:
            if not active:return
            active=False
            log.emit('caption_paint_ack',request['run_id'],request['session_id'],request['input_mode'],source='ui',
                caption_text=request.get('caption_text'),hypothesis_version=request.get('hypothesis_version'),
                chunk_id=request.get('chunk_id'),trace_quality='paint_proxy',
                payload={'request_event_id':request['event_id'],'proxy_method':'GUI redraw-cycle completion',
                         'physical_presentation_verified':False})
            done.set()
    presenter(request.get('caption_text',''),ack)
    done.wait(timeout)
    with gate:active=False
    return {'acknowledged':done.is_set(),'endpoint':'paint_proxy','physical_presentation_verified':False}


def pending_audio_seconds(chunks,rate):
    end=0;count=0
    for c in sorted(chunks,key=lambda c:c['start_sample']):
        count+=max(0,c['end_sample']-max(end,c['start_sample']));end=max(end,c['end_sample'])
    return count/rate


def session_trace_metrics(backlog_rows,revisions):
    from collections import defaultdict
    queues=defaultdict(list);texts=defaultdict(list)
    for row in backlog_rows:queues[row['session_id']].append(row)
    for row in revisions:texts[row['session_id']].append(row['text'])
    results={}
    for session,rows in queues.items():
        active=[r for r in rows if r.get('capture_active',True)]
        # Duplicate clock ticks are coalesced; never mix sessions or final queue draining.
        active=list({r['elapsed_s']:r for r in active}.values());active.sort(key=lambda r:r['elapsed_s'])
        results[session]={**backlog(active),'observed_max_oldest_pending_age_s':max(r['oldest_pending_age_s'] for r in rows),
                          'scope':'during source acquisition; post-source drain excluded from slope'}
    return {'backlog':{'sessions':results,'sustained_growth':any(r.get('sustained_growth') for r in results.values())},
            'stability':{'sessions':{sid:stability(values) for sid,values in texts.items()}}}


def trace_summary(events):
    """Host-observed stage durations. No segment measurement is labeled word latency."""
    def summarize(rows):
        values=[r['value'] for r in rows if r['value'] is not None]
        return {'unit':'s','definition_version':'host-stage-v1','observations':rows,
                'n_matched':len(values),'n_total':len(rows),
                'coverage':len(values)/len(rows) if rows else 0,
                **{f'p{p}':percentile(values,p) for p in (50,90,95,99)},
                'max':max(values) if values else None,
                'percentile_scope':'timed matches only; missing endpoints excluded and counted'}
    def observation(start,end):
        value=interval(start,end) if end else {'value':None,'missing_reason':'endpoint_not_recorded','uncertainty_s':None}
        return {**value,'start_event_id':start['event_id'],'end_event_id':end['event_id'] if end else None,
                'session_id':start['session_id']}
    def paired(start_kind,end_kind):
        key=lambda e:(e['session_id'],e.get('chunk_id'),e.get('attempt_id'))
        ends={key(e):e for e in events if e['event_type']==end_kind}
        return summarize([observation(e,ends.get(key(e))) for e in events if e['event_type']==start_kind])
    acks={e['payload'].get('request_event_id'):e for e in events
          if e['event_type']=='caption_paint_ack' and e.get('trace_quality')=='paint_proxy'}
    proxy=summarize([observation(e,acks.get(e['event_id'])) for e in events if e['event_type']=='caption_update_requested'])
    origins={};first={}
    for e in events:
        sid=e['session_id']
        if e['event_type']=='audio_frame_captured' and sid not in origins:
            origins[sid]={**e,'monotonic_ns':e['payload'].get('capture_origin_ns',e['monotonic_ns'])}
        if e['event_type']=='hypothesis_emitted' and e.get('caption_text','').strip() and sid not in first:first[sid]=e
    return {'queue_dwell_s':paired('inference_queued','inference_started'),
            'host_inference_roundtrip_s':paired('inference_started','inference_finished'),
            'ui_request_to_paint_proxy_s':proxy,
            'source_start_to_first_nonempty_emission_s':summarize([observation(e,first.get(sid)) for sid,e in origins.items()]),
            'word_first_presented_lag_p95_s':None,'physical_presentation_verified':False,
            'word_latency_missing_reason':'reviewed word-to-caption alignment and presentation endpoints required'}
