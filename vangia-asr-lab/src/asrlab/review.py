"""Versioned human review and a conservative, explicit acceptance rubric."""
from pathlib import Path
from .common import canonical,read_json,ROOT,utcnow,write_json,digest
from .storage import read_jsonl,validate,audit,seal


def annotate(path,annotation):
    validate(annotation,'reviewer_annotation.schema.json')
    if annotation['review_status']=='adjudicated' and not annotation.get('adjudicator_id'):raise ValueError('adjudicator required')
    if annotation.get('end_sample') is not None and annotation.get('start_sample') is not None and annotation['end_sample']<annotation['start_sample']:raise ValueError('Invalid audio span')
    path=Path(path);path.mkdir(parents=True,exist_ok=True);target=path/'annotations.jsonl'
    for key in ('reviewer_id','sample_id','reference_revision','annotation_id'):
        if not annotation[key].strip():raise ValueError(f'{key} cannot be blank')
    sealed=(path/'checksums.json').exists()
    if sealed:
        if not audit(path)['ok']:raise ValueError('Existing evidence integrity failed')
        manifest=read_json(path/'manifest.json')
        refs={r['sample_id']:r for r in read_jsonl(path/'reference.jsonl')}
        if annotation['sample_id'] not in refs:raise ValueError('Unknown sample')
        ref=refs[annotation['sample_id']]
        if annotation['run_id']!=manifest['run_id'] or annotation['reference_revision']!=ref.get('reference_revision',digest(ref['text'])):
            raise ValueError('Annotation run/reference revision mismatch')
    if any(r['annotation_id']==annotation['annotation_id'] for r in read_jsonl(target)):raise ValueError('duplicate annotation ID')
    with target.open('a',encoding='utf-8') as f:f.write(canonical(annotation)+'\n')
    if sealed:seal(path)
    return annotation


def decision(manifest,metrics,signoff=None):
    gates=read_json(ROOT/'config/provisional_gates.json');missing=[]
    if manifest.get('dataset_split')!='holdout':missing.append('untouched held-out sessions')
    if manifest.get('input_mode') in ('historical_whole_file','synthetic_fixture'):missing.append('actual current live/offline evidence')
    for key in gates['decision_policy']['required_validation_dimensions']:
        if not metrics.get('validation_evidence',{}).get(key):missing.append(key)
    if not gates['owner'] or not gates['approval_date']:missing.append('owner-approved use-case-specific acceptance policy')
    if not signoff or not signoff.get('reviewer'):missing.append('human sign-off')
    return {'status':'INSUFFICIENT EVIDENCE' if missing else 'ELIGIBLE','validated':False,
            'project_status':'NOT PROVEN' if missing else 'MEETS EXPLORATORY GATES',
            'missing':missing,'gate_version':gates['version'],'evidence_class':'P'}


def sign_off(path,reviewer,notes):
    if not reviewer.strip() or not notes.strip():raise ValueError('Reviewer and rationale required')
    path=Path(path);manifest=read_json(path/'manifest.json');metrics=read_json(path/'metrics.json')
    if not audit(path)['ok']:raise ValueError('Existing evidence integrity failed')
    entry={'reviewer':reviewer,'notes':notes,'created_utc':utcnow(),
           'decision':decision(manifest,metrics,{'reviewer':reviewer})}
    with (path/'signoffs.jsonl').open('a',encoding='utf-8') as f:f.write(canonical(entry)+'\n')
    seal(path)
    return entry


def candidate_status(execution,metrics):
    """Exploratory triage only: explicit physical/human evidence is needed for eligibility."""
    status=execution.get('status','planned')
    reason='Current evidence does not establish usability'
    if status=='blocked':result='BLOCKED';reason='Required environment or input unavailable'
    elif status in ('failed','cancelled'):result='FAILED';reason='Execution incomplete; preserve failure rate'
    elif metrics.get('wer') is None:result='NOT MEASURED'
    elif metrics['wer']>.15:
        result='BORDERLINE';reason='Above provisional 15% WER hypothesis; not a scientific rejection threshold'
    elif metrics.get('p95_presented_s') is None or metrics.get('coverage') is None:
        result='INSUFFICIENT EVIDENCE';reason='True presentation timing / coverage missing; paint proxy cannot qualify'
    elif metrics.get('owner_approved') and metrics.get('human_approved') and metrics.get('heldout') and metrics.get('all_required_dimensions'):
        result='ELIGIBLE';reason='Eligible for scoped final human decision; no automatic validation'
    else:result='INSUFFICIENT EVIDENCE'
    return {'status':result,'reason':reason,'validated':False,'evidence_class':'P'}
