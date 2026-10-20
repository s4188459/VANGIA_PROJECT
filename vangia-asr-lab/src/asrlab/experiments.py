"""Progressive planning and matched, session-clustered comparisons."""
import random
from collections import defaultdict
from .common import read_json,digest,model_record
from .timing import percentile


def plan(matrix,seed=42,diagnostic_retry=False):
    matrix=read_json(matrix);jobs=[];pending=[]
    if matrix['language']!='en':raise ValueError('English only')
    for e in matrix['experiments']:
        keys=e.get('model_keys')
        if e.get('default_enabled') is False and not diagnostic_retry:continue
        if not isinstance(keys,list):
            pending.append({'experiment':e['id'],'reason':'historical import' if e['id']=='T0-historic' else 'Requires development finalist selection / pre-registration'})
            continue
        for key in keys:
            model_record(key)
            for repeat in range(e.get('replicates_cold_warm',1)):
                j={'experiment':e['id'],'model_key':key,'dataset':e['dataset'],'mode':e['mode'],
                   'repeat':repeat,'temperature':'cold' if repeat==0 else 'warm','seed':seed,
                   'status':'NOT MEASURED','chunk_seconds':2 if 'chunk_seconds' in e else None,
                   'overlap_seconds':0 if 'overlap_seconds' in e else None}
                j['job_id']=digest(j);jobs.append(j)
    random.Random(seed).shuffle(jobs)
    return {'seed':seed,'matrix_sha256':digest(matrix),'jobs':jobs,'pending':pending,
            'policy':'Progressive baseline first; explicit one-factor ablations, no Cartesian expansion'}


def paired_bootstrap(a,b,seed=42,replicates=2000):
    if replicates<2000:raise ValueError('At least 2000 bootstrap replicates required')
    def index(rows):
        r={x['sample_id']:x for x in rows}
        if len(r)!=len(rows):raise ValueError('duplicate sample ID')
        return r
    aa,bb=index(a),index(b)
    if not aa or aa.keys()!=bb.keys():raise ValueError('Comparison must be paired')
    groups=defaultdict(list)
    for key,x in aa.items():
        y=bb[key]
        for field in ('pcm_sha256','reference_revision','session_id','N'):
            if not x.get(field) or x[field]!=y.get(field):raise ValueError(f'Unpaired input/reference/session: {field}')
        if x.get('errors') is None or y.get('errors') is None:raise ValueError('Incomplete paired corpus: do not exclude failures')
        groups[x['session_id']].append(key)
    def diff(keys):
        denom=sum(aa[k]['N'] for k in keys)
        return (sum(bb[k]['errors'] for k in keys)-sum(aa[k]['errors'] for k in keys))/denom
    rng=random.Random(seed);clusters=list(groups);draws=[]
    for _ in range(replicates):
        keys=[key for group in rng.choices(clusters,k=len(clusters)) for key in groups[group]]
        draws.append(diff(keys))
    return {'difference_b_minus_a':diff(list(aa)),'ci95':[percentile(draws,2.5),percentile(draws,97.5)],
            'seed':seed,'replicates':replicates,'clusters':len(clusters),'unstable':len(clusters)<10,
            'method':'paired session cluster bootstrap of micro-WER difference','evidence_class':'I'}


def pareto(rows,dimensions):
    if len({(r['mode'],r['dataset_hash']) for r in rows})>1:raise ValueError('Pareto requires matched mode and dataset')
    valid=[r for r in rows if all(r.get(k) is not None for k in dimensions)]
    frontier=[]
    for r in valid:
        if not any(all(other[k]<=r[k] for k in dimensions) and any(other[k]<r[k] for k in dimensions) for other in valid):frontier.append(r['id'])
    return {'frontier':frontier,'missing':[r['id'] for r in rows if r not in valid],'dimensions_minimized':dimensions}


def compare_architectures(single,dual):
    for key in ('dataset_hash','session_ids'):
        if not single.get(key) or single[key]!=dual.get(key):raise ValueError('Architectures require matched data/sessions')
    fields=('live_wer','offline_wer','total_turnaround_s','measured_combined_peak_rss_bytes','critical_errors')
    if any(r.get('evidence_class')!='E-LOCAL' for r in (single,dual)):raise ValueError('Actual local measurements required')
    missing=[f'{name}/{field}' for name,r in [('single',single),('dual',dual)] for field in fields if r.get(field) is None]
    if missing:return {'status':'INSUFFICIENT EVIDENCE','missing':missing,'decision':'HUMAN REVIEW REQUIRED'}
    return {'offline_wer_difference_dual_minus_single':dual['offline_wer']-single['offline_wer'],
            'live_wer_difference_dual_minus_single':dual['live_wer']-single['live_wer'],
            'turnaround_difference_s':dual['total_turnaround_s']-single['total_turnaround_s'],
            'combined_peak_rss_difference_bytes':dual['measured_combined_peak_rss_bytes']-single['measured_combined_peak_rss_bytes'],
            'critical_error_difference':dual['critical_errors']-single['critical_errors'],
            'decision':'HUMAN REVIEW REQUIRED','evidence_class':'I',
            'resource_rule':'Uses measured architecture totals; separate worker peaks are not summed into a simultaneous peak'}
