"""Consented human task responses and paired reviewer agreement; no WER-to-utility conversion."""
from collections import Counter
from statistics import mean
from pathlib import Path
from .common import canonical,utcnow
from .storage import read_jsonl


def add_response(path,response):
    required=('response_id','participant_id','consent_record_id','task_id','stimulus_run_id','stimulus_sha256','group')
    for field in required:
        if not response.get(field):raise ValueError(f'Missing {field}')
    if not 0<=response['task_score']<=1:raise ValueError('task_score must be in [0,1]')
    for field in ('readability_rating','lag_annoyance_rating'):
        if response[field] not in (1,2,3,4,5):raise ValueError(f'{field} must be a 1..5 response')
    path=Path(path);path.mkdir(parents=True,exist_ok=True);target=path/'study_responses.jsonl'
    if any(r['response_id']==response['response_id'] for r in read_jsonl(target)):raise ValueError('duplicate response ID')
    record={**response,'recorded_utc':utcnow()}
    with target.open('a',encoding='utf-8') as f:f.write(canonical(record)+'\n')
    return record


def summarize(path):
    rows=read_jsonl(Path(path)/'study_responses.jsonl')
    return {'responses':len(rows),'participants':len({r['participant_id'] for r in rows}),
            'stimuli':len({r['stimulus_sha256'] for r in rows}),
            'task_score_mean':mean(r['task_score'] for r in rows) if rows else None,
            'readability_mean':mean(r['readability_rating'] for r in rows) if rows else None,
            'lag_annoyance_mean':mean(r['lag_annoyance_rating'] for r in rows) if rows else None,
            'validated':False,'evidence_class':'I','weighting':'response-weighted descriptive means; participant clustering needed for inference'}


def agreement(a,b):
    if not a or a.keys()!=b.keys():raise ValueError('Reviewer labels must be paired on identical units')
    n=len(a);observed=sum(a[k]==b[k] for k in a)/n;ca,cb=Counter(a.values()),Counter(b.values())
    expected=sum(ca[k]*cb[k] for k in set(ca)|set(cb))/n**2
    return {'n':n,'observed_agreement':observed,'cohens_kappa':(observed-expected)/(1-expected) if expected<1 else None,
            'missing_reason':'constant_labels' if expected==1 else None,'method':'unweighted Cohen kappa'}
