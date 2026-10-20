"""Read-only analysis views and versioned CSV/JSON bundles over auditable evidence."""
import csv
import io
import json
import math
import tempfile
import zipfile
from collections import Counter,defaultdict
from pathlib import Path
from statistics import mean

from .common import ROOT,canonical,digest,read_json,sha256,utcnow,write_json
from .storage import audit,read_jsonl,seal,write_jsonl
from .metrics import score,normalize,NORMALIZATION
from .timing import trace_summary,percentile

VERSION='1.0'
KEYS=['benchmark_id','run_id','model_config_id','repeat_id','dataset_hash']
MISSING_WORD_ENDPOINTS=('word_first_emit_lag_s','word_first_paint_proxy_lag_s',
                        'word_first_presented_lag_s','word_commit_lag_s')


def _contexts(source, sealed_job_id=None):
    source=Path(source)
    if (source/'benchmark.json').exists():
        from .benchmark import load_benchmark
        plan=load_benchmark(source)
        if sealed_job_id is None and (source/'ACTIVE').exists():raise ValueError('Benchmark is active; wait for completion or cancel before export')
        states={s['job_id']:s for s in read_json(source/'state.json')['jobs']}
        for job in plan['jobs']:
            if sealed_job_id is not None and job['job_id']!=sealed_job_id:continue
            path=source/job['run_path'];cfg=job['config']
            if sealed_job_id is not None:
                if not (path/'checksums.json').exists() or read_json(path/'state.json')['status'] not in ('completed','failed','blocked','cancelled'):
                    raise ValueError('Live results require a sealed terminal job')
            m={'run_id':job['run_id'],'model_config_id':job['model_config_id'],'model_id':cfg['model_id'],
               'dataset_id':plan['dataset_id'],'dataset_split':plan['split'],'input_mode':cfg['mode'],
               'config':cfg,'evidence_class':'E-LOCAL','dataset_hash':plan['dataset_hash']}
            yield _context(path,m,plan['samples'],states.get(job['job_id'],{'status':'not_run'}),
                           benchmark_id=plan['benchmark_id'],repeat_id=job['repeat_id'])
    else:
        check=audit(source)
        if not check['ok']:raise ValueError('Source integrity failed: '+str(check['errors']))
        manifest=read_json(source/'manifest.json')
        if manifest['input_mode']=='historical_whole_file':
            metrics=read_json(source/'metrics.json');refs=read_jsonl(source/'reference.jsonl')
            samples={s['id']:s for s in read_json(source/'samples.json')}
            refs=[{**r,'duration_s':samples[r['sample_id']].get('duration_s'),
                   'audio_sha256':samples[r['sample_id']].get('audio_sha256')} for r in refs]
            preds=read_jsonl(source/'predictions.jsonl')
            for archived in metrics['configurations']:
                m={**manifest,'model_config_id':archived['config_id'],'model_id':archived['model_id'],
                   'config':archived['config'],'dataset_hash':digest(refs),'archived_label':archived['label']}
                selected=[{**p,'text':p.get('hypothesis'),'service_s':p.get('elapsed_s')} for p in preds if p['config_id']==archived['config_id']]
                yield {'path':source,'manifest':m,'refs':refs,'preds':selected,'state':{'status':archived['status'],'reasons':[archived.get('error')]},
                       'metrics':{'load_s':archived['load_s'],'inference_service_s':archived.get('inference_s'),
                                  'rtf':archived.get('rtf'),'rtf_scope':'historical whole-file inference only'},
                       'benchmark_id':'historical-'+manifest['run_id'],'repeat_id':None,'source_hash':sha256(source/'checksums.json')}
        else:
            yield _context(source,manifest,[],{},benchmark_id=manifest.get('config',{}).get('benchmark_id',manifest['run_id']),
                           repeat_id=manifest.get('config',{}).get('repeat_id'))


def _context(path,manifest,refs,state,**extra):
    metrics={};preds=[];source_hash=None
    if (path/'manifest.json').exists():
        check=audit(path)
        if not check['ok']:raise ValueError('Source integrity failed: '+str(check['errors']))
        actual=read_json(path/'manifest.json')
        # A campaign has the full planned corpus, including jobs blocked before reference persistence.
        manifest={**actual,'dataset_hash':manifest.get('dataset_hash',actual.get('dataset_hash')),
                  'model_config_id':manifest.get('model_config_id',actual.get('model_config_id')),
                  'source_run_model_config_id':actual.get('model_config_id')}
        run_state=read_json(path/'state.json')
        if state.get('status')!='cancelled' or run_state['status']=='completed':state=run_state
        metrics=read_json(path/'metrics.json')
        refs=refs or read_jsonl(path/'reference.jsonl') or actual.get('config',{}).get('samples',[])
        if not refs and actual.get('config',{}).get('dataset_manifest'):
            raise ValueError('Blocked external-manifest run has no frozen references; export its benchmark campaign')
        preds=read_jsonl(path/'predictions.jsonl');source_hash=sha256(path/'checksums.json')
        if state.get('status')=='cancelled':preds=[p for p in preds if p.get('status')=='completed']
    return {'path':path,'manifest':manifest,'refs':refs,'preds':preds,'state':state,'metrics':metrics,'source_hash':source_hash,**extra}


def _aggregate(rows):
    total=len(rows);valid=[r for r in rows if r['scored']];out={}
    for prefix in ('raw','normalized'):
        denominator=sum(r[prefix+'_N'] for r in valid)
        numerator=sum(r[prefix+'_errors'] for r in valid)
        chars=sum(r[prefix+'_reference_characters'] for r in valid)
        ce=sum(r[prefix+'_character_errors'] for r in valid)
        conditional=numerator/denominator if denominator else None
        nonempty=[r[prefix+'_wer'] for r in valid if r[prefix+'_wer'] is not None]
        domains=defaultdict(list)
        for r in valid:domains[r['domain']].append(r)
        domain_rates=[sum(r[prefix+'_errors'] for r in rr)/sum(r[prefix+'_N'] for r in rr)
                      for rr in domains.values() if sum(r[prefix+'_N'] for r in rr)]
        out.update({prefix+'_wer_micro':conditional if len(valid)==total else None,
            'conditional_'+prefix+'_wer_micro':conditional,
            prefix+'_wer_macro_utterance':mean(nonempty) if nonempty and len(valid)==total else None,
            prefix+'_wer_macro_domain':mean(domain_rates) if domain_rates and len(valid)==total else None,
            prefix+'_cer':ce/chars if chars and len(valid)==total else None,
            prefix+'_numerator':numerator,prefix+'_denominator':denominator,
            prefix+'_character_errors':ce,prefix+'_reference_characters':chars,
            **{prefix+'_'+op:sum(r[prefix+'_'+op] for r in valid) for op in ('S','D','I')}})
    counts=Counter(r['status'] for r in rows)
    out.update(planned=total,completed=counts['completed'],failed=counts['failed'],blocked=counts['blocked'],
               cancelled=counts['cancelled'],not_run=counts['not_run'],scored=len(valid),
               completion_fraction=counts['completed']/total if total else 0,
               scoring_coverage=len(valid)/total if total else 0,
               missing_reason='incomplete_scored_corpus' if len(valid)!=total else None,
               count_scope='S/D/I and error denominators cover scored observations only; full-corpus rates null if incomplete')
    return out


def _metric(name,value,run,numerator=None,denominator=None,unit=None,reason=None,scope=None,n_total=None,n_observed=None):
    if unit is None:
        unit='ratio' if any(s in name for s in ('wer','cer','fraction','coverage','rtf')) else 's' if name.endswith('_s') else 'bytes' if name.endswith('_bytes') else 'percent_one_core' if 'cpu_percent' in name else 'count'
    if n_total is None:n_total=run.get('planned',0)
    if n_observed is None:n_observed=run.get('scored',0) if any(s in name for s in ('wer','cer')) else (n_total if value is not None else 0)
    return {'metric_id':name,'value':value,'unit':unit,'definition_version':NORMALIZATION if name.startswith('normalized') else 'analysis-v1',
            'scope':scope or ('conditional_on_scored_samples' if name.startswith('conditional_') else 'one configuration and one repeat; never pooled across modes'),
            'numerator':numerator,'denominator':denominator,'n_total':n_total,'n_observed':n_observed,
            'coverage':n_observed/n_total if n_total else 0,'evidence_class':'I' if value is not None else 'G',
            'measurement_status':'available' if value is not None else 'missing',
            'missing_reason':None if value is not None else reason or run.get('missing_reason') or 'not_measured',
            'model_config_id':run['model_config_id'],'dataset_id':run.get('dataset_id'),'split_id':run.get('split'),
            'input_mode':run.get('mode'),'clock_basis':run.get('clock_id'),'uncertainty':None,
            'source_run_ids':[run['run_id']]}


def collect_results(source, sealed_job_id=None):
    result={'schema_version':VERSION,'created_utc':utcnow(),'scientific_status':'INSUFFICIENT EVIDENCE',
            'warnings':['WER and latency gates remain provisional. WER is not comprehension.',
                        'Unknown speaker/session labels are one unknown group, not independent observations.',
                        'CSV strings beginning with formula markers are apostrophe-escaped; JSON preserves originals.'],
            'runs':[],'samples':[],'groups':[],'transcripts':[],'latency_observations':[],'resources':[],'failures':[],'provenance':[]}
    for context in _contexts(source, sealed_job_id):
        m=context['manifest'];cfg=m.get('config',{});state=context['state'];metrics=context['metrics'];path=context['path']
        base={'benchmark_id':context['benchmark_id'],'run_id':m['run_id'],'model_config_id':m.get('model_config_id') or 'unidentified',
              'repeat_id':context['repeat_id'],'dataset_hash':m.get('dataset_hash') or digest(context['refs'])}
        rowkeys=[p['sample_id'] for p in context['preds']]
        if len(set(rowkeys))!=len(rowkeys):raise ValueError('Duplicate prediction IDs in source')
        preds={p['sample_id']:p for p in context['preds']};rows=[]
        if len({r['sample_id'] for r in context['refs']})!=len(context['refs']):raise ValueError('Duplicate planned sample IDs')
        for ref in context['refs']:
            pred=preds.get(ref['sample_id']);status=pred.get('status','completed') if pred else state.get('status','not_run')
            status={'ok':'completed','error':'failed','planned':'not_run','running':'not_run','incomplete':'not_run'}.get(status,status)
            if pred is None and status=='completed':status='failed'
            hypothesis=pred.get('text',pred.get('hypothesis')) if pred and status=='completed' else None
            reason=None if status=='completed' else (pred or {}).get('error') or '; '.join(str(x) for x in state.get('reasons',[]) if x) or state.get('error') or status
            text=ref.get('text');scored=isinstance(text,str) and isinstance(hypothesis,str) and not ref.get('input_errors')
            if not scored and not reason:reason='reference_missing_or_invalid' if not isinstance(text,str) or ref.get('input_errors') else 'prediction_missing'
            row={**base,'sample_id':ref['sample_id'],'supplied_sample_id':ref.get('supplied_sample_id',ref['sample_id']),'speaker_id':ref.get('speaker_id') or 'unknown',
                 'session_id':ref.get('session_id') or 'unknown','domain':ref.get('domain') or 'unknown',
                 'reference_revision':ref.get('reference_revision'),'reference_quality':ref.get('reference_quality',ref.get('quality','unverified')),
                 'audio_sha256':ref.get('audio_sha256'),'pcm_sha256':ref.get('pcm_sha256'),
                 'original_audio_sha256':ref.get('original_audio_sha256'),'original_reference_sha256':ref.get('original_reference_sha256'),
                 'duration_s':ref.get('duration_s'),'status':status,'missing_reason':reason,'scored':scored,
                 'service_s':(pred or {}).get('service_s'),'evidence_class':m['evidence_class'],
                 'input_mode':m['input_mode'],'word_first_presented_lag_p95_s':None,'latency_missing_reason':'insufficient_alignment_or_presentation_not_measured'}
            transcript={**base,'sample_id':ref['sample_id'],'reference_revision':row['reference_revision'],
                        'reference':text,'hypothesis':hypothesis,'status':status,'missing_reason':reason,
                        'audio':ref.get('audio'),'raw_alignment':None,'normalized_alignment':None}
            for prefix,normalized in [('raw',False),('normalized',True)]:
                s=score(text,hypothesis,normalize=normalized) if scored else {}
                for key in ('wer','cer','S','D','I','N','errors','character_errors','reference_characters','hallucinated_words'):
                    row[prefix+'_'+key]=s.get(key)
                if not scored and isinstance(text,str):row[prefix+'_N']=len((normalize(text) if normalized else text).split())
                transcript[prefix+'_alignment']=s.get('alignment')
            rows.append(row);result['transcripts'].append(transcript)
            if status!='completed' or not scored:result['failures'].append({**base,'sample_id':ref['sample_id'],
                'status':status,'stage':'input_or_scoring' if ref.get('input_errors') else 'execution','reason':reason})
            for endpoint in MISSING_WORD_ENDPOINTS:
                result['latency_observations'].append({**base,'sample_id':ref['sample_id'],'session_id':row['session_id'],
                    'endpoint_type':endpoint,'observation_scope':'sample missing-word-timing summary',
                    'start_event_id':None,'end_event_id':None,'start_clock_id':None,'end_clock_id':None,
                    'value_s':None,'uncertainty_s':None,'measurement_status':'missing',
                    'n_total':row['normalized_N'],'n_observed':0,'coverage':0,
                    'missing_reason':'not_supported' if endpoint=='word_commit_lag_s' else row['latency_missing_reason']})
        if set(preds)-{r['sample_id'] for r in rows}:raise ValueError('Unplanned prediction sample IDs')
        run={**base,**_aggregate(rows),'model_id':m.get('model_id'),'archived_label':m.get('archived_label'),
             'backend':cfg.get('backend'),'checkpoint_revision':m.get('checkpoint_revision'),
             'precision':cfg.get('precision',cfg.get('compute_type')),'device':cfg.get('device'),
             'mode':m['input_mode'],'temperature':cfg.get('temperature','not_recorded'),
             'status':state.get('status','not_run'),'dataset_id':m.get('dataset_id'),'split':m.get('dataset_split'),
             'evidence_class':m['evidence_class'],'clock_id':m.get('clock_id'),
             'duration_s':sum(r['duration_s'] or 0 for r in rows),'duration_known_samples':sum(r['duration_s'] is not None for r in rows),
             'load_s':metrics.get('load_s'),'inference_service_s':metrics.get('inference_service_s'),
             'turnaround_s':metrics.get('offline_turnaround_s'),'rtf':metrics.get('rtf'),'rtfx':metrics.get('rtfx'),
             'rtf_scope':metrics.get('rtf_scope','not_recorded'),'peak_worker_rss_bytes':metrics.get('peak_worker_rss_bytes'),
             'resource_scope':metrics.get('resource_scope','not_recorded; old resource telemetry not verified'),
             'word_first_presented_lag_p95_s':None,'word_first_presented_coverage':0}
        resource_rows=[]
        if (path/'resources.csv').exists():
            with (path/'resources.csv').open(encoding='utf-8-sig',newline='') as f:
                for r in csv.DictReader(f):
                    converted={k:float(v) if k=='cpu_percent' and v else int(v) if k in ('monotonic_ns','pid','rss_bytes','read_bytes','write_bytes','process_count') and v else v for k,v in r.items()}
                    resource_rows.append({**base,**converted})
        run['cpu_percent_mean']=mean(r['cpu_percent'] for r in resource_rows) if resource_rows else None
        run['resource_samples']=len(resource_rows);result['resources']+=resource_rows
        resource_verified=metrics.get('resource_scope','').startswith('worker_process_tree')
        if not resource_verified:
            run['peak_worker_rss_bytes']=None;run['cpu_percent_mean']=None
            for rr in resource_rows:rr['measurement_quality']='resource_scope_unverified; retained archival observation, not model resource evidence'
        trace={}
        if (path/'events.jsonl').exists() and m['input_mode']!='historical_whole_file':
            from .events import EventLog
            events=EventLog(path/'events.jsonl').events;trace=trace_summary(events);byid={e['event_id']:e for e in events}
            for endpoint,summary in trace.items():
                if not isinstance(summary,dict) or 'observations' not in summary:continue
                for obs in summary['observations']:
                    start=byid.get(obs['start_event_id'],{});end=byid.get(obs['end_event_id'],{})
                    ref=next((r for r in rows if r['sample_id']==obs['session_id']),{})
                    result['latency_observations'].append({**base,'sample_id':ref.get('sample_id'),'session_id':ref.get('session_id',obs['session_id']),
                        'endpoint_type':endpoint,'observation_scope':'event interval','start_event_id':obs['start_event_id'],
                        'end_event_id':obs['end_event_id'],'start_clock_id':start.get('clock_id'),'end_clock_id':end.get('clock_id'),
                        'value_s':obs['value'],'uncertainty_s':obs['uncertainty_s'],
                        'measurement_status':'measured' if obs['value'] is not None else 'missing',
                        'missing_reason':obs['missing_reason'],'n_total':1,'n_observed':int(obs['value'] is not None),'coverage':int(obs['value'] is not None)})
                run[endpoint+'_p95']=summary['p95'];run[endpoint+'_coverage']=summary['coverage']
        run['metrics']={}
        for name,value in list(run.items()):
            if name in KEYS or isinstance(value,bool) or not (isinstance(value,(int,float)) or value is None):continue
            if name in ('model_id','archived_label','checkpoint_revision','clock_id','missing_reason'):continue
            prefix='normalized' if 'normalized' in name else 'raw'
            numerator=run.get(prefix+'_numerator') if 'wer_micro' in name else run.get(prefix+'_character_errors') if name.endswith('_cer') else None
            denominator=run.get(prefix+'_denominator') if 'wer_micro' in name else run.get(prefix+'_reference_characters') if name.endswith('_cer') else None
            run['metrics'][name]=_metric(name,value,run,numerator,denominator,
                reason='resource_scope_unverified' if name in ('peak_worker_rss_bytes','cpu_percent_mean') and not resource_verified else 'not_measured' if 'lag' in name else None)
        for endpoint,summary in trace.items():
            if not isinstance(summary,dict) or 'observations' not in summary:continue
            for p in ('p50','p90','p95','p99','max'):
                name=endpoint+'_'+p
                run['metrics'][name]=_metric(name,summary[p],run,unit='s',reason='no_valid_timed_observations',
                    scope=summary['percentile_scope'],n_total=summary['n_total'],n_observed=summary['n_matched'])
        for grouping in ('domain','speaker_id','session_id'):
            groups=defaultdict(list)
            for row in rows:groups[row[grouping]].append(row)
            for label,members in groups.items():
                group={**base,'group_by':grouping,'group_value':label,
                    'weighting':'micro=sum(errors)/sum(reference units); macro=unweighted nonempty utterances',**_aggregate(members)}
                group['metrics']={}
                for name,value in list(group.items()):
                    if name in KEYS or not (isinstance(value,(int,float)) or value is None):continue
                    prefix='normalized' if 'normalized' in name else 'raw'
                    group['metrics'][name]=_metric(name,value,{**run,**group},
                        numerator=group.get(prefix+'_numerator') if 'wer_micro' in name else group.get(prefix+'_character_errors') if name.endswith('_cer') else None,
                        denominator=group.get(prefix+'_denominator') if 'wer_micro' in name else group.get(prefix+'_reference_characters') if name.endswith('_cer') else None)
                result['groups'].append(group)
        for row in rows:
            row['metrics']={}
            for name,value in list(row.items()):
                if name in KEYS or isinstance(value,bool) or not (isinstance(value,(int,float)) or value is None):continue
                if name.endswith(('_sha256','_revision')):continue
                prefix='normalized' if name.startswith('normalized') else 'raw'
                row['metrics'][name]=_metric(name,value,{**run,'planned':1,'scored':int(row['scored']),'missing_reason':row['missing_reason']},
                    numerator=row.get(prefix+'_errors') if name.endswith('_wer') else row.get(prefix+'_character_errors') if name.endswith('_cer') else None,
                    denominator=row.get(prefix+'_N') if name.endswith('_wer') else row.get(prefix+'_reference_characters') if name.endswith('_cer') else None,
                    reason=row['latency_missing_reason'] if 'lag' in name else None,scope='one planned sample within one configuration/repeat')
        result['samples']+=rows;result['runs'].append(run)
        result['provenance'].append({**base,'source_path':str(path.resolve()),'source_checksums_sha256':context['source_hash'],
             'manifest':m,'worker_provenance':read_jsonl(path/'worker_provenance.jsonl'),'reference_quality_notice':'Scores are against provided references; unverified references remain unverified.'})
    return result


TABLES={'run_summary.csv':'runs','sample_metrics.csv':'samples','group_metrics.csv':'groups',
        'latency_observations.csv':'latency_observations','resources.csv':'resources','failures.csv':'failures'}
GRAINS={'runs':'one run/configuration/repeat','samples':'one planned sample/run/configuration/repeat',
        'groups':'one metadata group/run/configuration/repeat','latency_observations':'one event interval or explicitly missing sample-word summary',
        'resources':'one sampled worker process-tree observation','failures':'one unsuccessful or unscored planned sample'}


def csv_value(value):
    if value is None:return ''
    if isinstance(value,bool):return 'true' if value else 'false'
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r','\n')):return "'"+value
    return value


def _columns(rows,kind):
    cols=list(KEYS)
    defaults={'samples':['sample_id','status','missing_reason','normalized_wer'],
              'latency_observations':['sample_id','endpoint_type','value_s','missing_reason'],
              'resources':['monotonic_ns','pid','cpu_percent','rss_bytes'],
              'failures':['sample_id','status','stage','reason']}
    for key in defaults.get(kind,[]):
        if key not in cols:cols.append(key)
    for row in rows:
        for k,v in row.items():
            if not isinstance(v,(dict,list)) and k not in cols:cols.append(k)
    return cols


def _csv(path,rows,columns):
    with Path(path).open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,columns,extrasaction='ignore');writer.writeheader()
        writer.writerows({k:csv_value(row.get(k)) for k in columns} for row in rows)


def _definition(column):
    if 'wer' in column:return 'ratio','(S+D+I)/N; micro uses pooled counts; macro uses equal utterance/domain weights; may exceed 1; 0.15=15%'
    if 'cer' in column:return 'ratio','character edit errors/reference characters; normalized excludes whitespace; raw preserves it'
    if column in ('rtf','rtfx'):return 'ratio','worker inference service/audio duration (RTF), reciprocal (RTFx); see rtf_scope'
    if 'coverage' in column or 'fraction' in column:return 'ratio','observed eligible units/planned units; see related counts and missing_reason'
    if column.endswith('_s') or any(column.endswith('_s_'+p) for p in ('p50','p90','p95','p99','max')):return 's','elapsed duration at named endpoints; see clock, endpoint_type and scope'
    if column.endswith('_bytes'):return 'bytes','recorded bytes; RSS summed across sampled worker process tree, see resource_scope'
    if column=='cpu_percent' or column=='cpu_percent_mean':return 'percent_one_core','one logical core=100%; process-tree sum; initial process observation lacks prior interval'
    if column.endswith(('_S','_D','_I','_N','_errors','_numerator','_denominator','_characters','_words')):return 'count','S=substitution D=deletion I=insertion N=reference tokens; aggregates count scored subset only'
    if column in ('planned','completed','failed','blocked','cancelled','not_run','scored','n_total','n_observed','resource_samples','duration_known_samples','process_count'):return 'count','number of named observations; disjoint status counts sum to planned'
    if column=='monotonic_ns':return 'ns','host monotonic sampling timestamp; never subtract uncalibrated clocks'
    if 'sha256' in column or column.endswith('_hash'):return 'SHA256','content identity; does not establish consent or reference correctness'
    if column in KEYS or column.endswith('_id') or column=='reference_revision':return 'identifier','stable join identity; repeat_id does not imply an independent speaker/session'
    if column in ('reason','missing_reason','latency_missing_reason'):return 'text','why measurement or execution is unavailable; blank only when available/not applicable'
    return 'text','literal '+column.replace('_',' ')+' from recorded evidence; unknown or not_recorded is explicit'


def _write_bundle(source,out,data):
    out.mkdir(parents=True,exist_ok=False);dictionary=[]
    for filename,kind in TABLES.items():
        cols=_columns(data[kind],kind);_csv(out/filename,data[kind],cols)
        for col in cols:
            unit,definition=_definition(col)
            dictionary.append({'file':filename,'row_unit':GRAINS[kind],'column':col,'unit':unit,'definition':definition,
                'missing_policy':'blank CSV / null JSON; see status and missing_reason; never zero-imputed',
                'csv_encoding':'UTF-8 BOM; formula-like text escaped with leading apostrophe'})
    _csv(out/'data_dictionary.csv',dictionary,list(dictionary[0]))
    write_jsonl(out/'transcripts.jsonl',data['transcripts']);write_json(out/'results.json',data)
    # Ship a local schema alongside results, independent of the installed package paths.
    schema=read_json(Path(__file__).parent/'resources/schemas/analysis_results.schema.json')
    write_json(out/'analysis_results.schema.json',schema)
    manifest={'schema_version':VERSION,'created_utc':utcnow(),'source':str(Path(source).resolve()),
              'row_counts':{filename:len(data[kind]) for filename,kind in TABLES.items()},
              'transcript_count':len(data['transcripts']),'audio_included':False,'transcripts_included':True,
              'privacy':'Contains transcripts and metadata; keep private. No recording files bundled.',
              'source_identity':data['provenance'],'csv_formula_policy':'escape formula-like text with apostrophe; JSON is lossless'}
    write_json(out/'export_manifest.json',manifest)
    lines=['# Vangia benchmark analysis','',f"Configurations/repeats: {len(data['runs'])}. Planned sample observations: {len(data['samples'])}.",
           '', '[E] Local execution evidence. [I] Derived scores. [P] 15% WER / 3 s P95 are provisional. [G] Missing measurements stay null.',
           'No automatic VALIDATED decision. RTF is not visible caption latency. Repeats are not independent sessions.',
           'Errors, denominators and reference quality must be inspected before comparing models.',
           '', '| Model/config | Mode | Status | Completed/planned | Normalized micro WER | RTF |', '|---|---|---|---:|---:|---:|']
    for r in data['runs']:
        lines.append(f"| {str(r['model_id'] or r.get('archived_label') or 'fixture').replace('|','/')} / {r['model_config_id'][:12]} | {r['mode']} | {r['status']} | {r['completed']}/{r['planned']} | {r['normalized_wer_micro']} | {r['rtf']} |")
    lines+=['','Full-corpus rates are null for incomplete scoring. Conditional values describe scored successes only.',
            'Read data_dictionary.csv for units and denominators; inspect failures.csv and latency coverage.',
            'Source manifests and artifact identities are included in results.json. Original run evidence is unchanged.']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');seal(out)


def export_analysis(source,out):
    source=Path(source).resolve();out=Path(out).resolve()
    if out==source or out.is_relative_to(source):raise ValueError('Export must be outside source evidence directory')
    for parent in out.parents:
        if (parent/'manifest.json').exists() or (parent/'benchmark.json').exists() or (parent/'dataset.json').exists():
            raise ValueError('Export cannot write inside existing evidence or dataset directories')
    if out.exists():raise FileExistsError(out)
    data=collect_results(source)
    if not data['runs']:raise ValueError('No run configurations to export')
    if out.suffix.lower()=='.zip':
        out.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='asrlab-export-',dir=out.parent) as temp:
            stage=Path(temp)/'bundle';_write_bundle(source,stage,data)
            checked=validate_bundle(stage)
            if not checked['ok']:raise ValueError('Bundle validation failed: '+str(checked['errors']))
            with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED) as z:
                for p in sorted(stage.iterdir()):z.write(p,p.name)
    else:
        _write_bundle(source,out,data);checked=validate_bundle(out)
        if not checked['ok']:raise ValueError('Bundle validation failed: '+str(checked['errors']))
    return {'status':'exported','path':str(out),'runs':len(data['runs']),'sample_observations':len(data['samples']),
            'validated':True,'validation_scope':'schema/parity/integrity, not scientific model validation'}


def validate_bundle(path):
    from jsonschema import Draft202012Validator
    path=Path(path);errors=[]
    try:
        hashes=read_json(path/'checksums.json')
        for name,expected in hashes.items():
            target=(path/name).resolve()
            if not target.is_relative_to(path.resolve()) or not target.is_file() or sha256(target)!=expected:errors.append('Checksum mismatch: '+name)
        data=read_json(path/'results.json');canonical(data)  # rejects nonfinite JSON numbers
        schema=read_json(path/'analysis_results.schema.json')
        errors.extend(e.message for e in Draft202012Validator(schema).iter_errors(data))
        manifest=read_json(path/'export_manifest.json')
        for filename,kind in TABLES.items():
            with (path/filename).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            if len(rows)!=len(data[kind]) or len(rows)!=manifest['row_counts'][filename]:errors.append('Row count mismatch: '+filename);continue
            for row,expected in zip(rows,data[kind]):
                if any(row[k]!=str(csv_value(expected.get(k))) for k in row):errors.append('CSV/JSON mismatch: '+filename);break
        if read_jsonl(path/'transcripts.jsonl')!=data['transcripts']:errors.append('Transcript parity mismatch')
        for run in data['runs']:
            rows=[r for r in data['samples'] if all(r[k]==run[k] for k in KEYS)]
            if len(rows)!=run['planned']:errors.append('Planned sample count mismatch')
            if sum(run[k] for k in ('completed','failed','blocked','cancelled','not_run'))!=run['planned']:errors.append('Status denominator mismatch')
            agg=_aggregate(rows)
            if any(run.get(k)!=v for k,v in agg.items()):errors.append('Aggregate mismatch')
    except (ValueError,OSError,KeyError,TypeError) as exc:errors.append(str(exc))
    return {'ok':not errors,'errors':errors,'scope':'bundle schema, integrity, row/score parity; not model validation'}


def compare_runs(source_a,run_a,config_a,source_b,run_b,config_b,seed=42):
    from .experiments import paired_bootstrap
    a=collect_results(source_a);b=collect_results(source_b)
    def selected(data,run_id,config):
        runs=[r for r in data['runs'] if r['run_id']==run_id and r['model_config_id']==config]
        if len(runs)!=1:raise ValueError('Select one exact run/configuration/repeat')
        rows=[r for r in data['samples'] if r['run_id']==run_id and r['model_config_id']==config]
        return runs[0],rows
    ar,aa=selected(a,run_a,config_a);br,bb=selected(b,run_b,config_b)
    for field in ('mode','temperature','dataset_hash','split'):
        if ar[field]!=br[field]:raise ValueError('Comparison requires matched '+field)
    def paired(rows):
        return [{'sample_id':r['sample_id'],'session_id':r['session_id'] or 'unknown',
                 'pcm_sha256':r['pcm_sha256'],'reference_revision':r['reference_revision'],
                 'N':r['normalized_N'],'errors':r['normalized_errors']} for r in rows]
    result=paired_bootstrap(paired(aa),paired(bb),seed)
    result['unknown_session_warning']=any(r['session_id']=='unknown' for r in aa+bb)
    result['scope']='one selected repeat per configuration; not independent repeat clusters'
    return result
