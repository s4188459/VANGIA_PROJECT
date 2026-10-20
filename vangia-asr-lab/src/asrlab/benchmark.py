"""Immutable multi-configuration campaigns over one paired imported dataset."""
import os
import random
import uuid
from pathlib import Path
from .common import ROOT,digest,model_record,read_json,sha256,utcnow,write_json
from .zip_dataset import verify_dataset


def preset(model_id):
    model=model_record(model_id)
    return {'model_id':model['canonical_model_id'],'backend':model['legacy_backend'],
            'language':'en','mode':'batch_file','device':'cpu','precision':model['legacy_compute_type'],
            'threads':4,'beam_size':model['legacy_beam_size'],'vad_filter':False,
            'condition_on_previous_text':False,'chunk_seconds':2.,'overlap_seconds':0.,
            'merge_policy':'prefix_dedupe','context_policy':'none','weights_path':'',
            'artifact_provenance':'','worker_python':'','diagnostic_retry':False}


def local_presets():
    """Reuse only explicit existing local configs; never resolve an alias or download."""
    from .common import registry
    result={m['canonical_model_id']:preset(m['canonical_model_id']) for m in registry()['models']}
    for p in sorted((ROOT/'runs').glob('*config.json')):
        try:
            c=read_json(p);model=c.get('model_id')
            if model in result and c.get('weights_path') and c.get('artifact_provenance'):
                for k in result[model]:
                    if k in c and k not in ('mode','diagnostic_retry'):result[model][k]=c[k]
        except (ValueError,OSError):continue
    return result


def create_benchmark(dataset,configs,out,repeats=1,seed=42):
    if not isinstance(repeats,int) or not 1<=repeats<=20:raise ValueError('Repeats must be 1..20')
    if not configs:raise ValueError('Select at least one model configuration')
    data=verify_dataset(dataset);jobs=[];ident=uuid.uuid4().hex;out=Path(out).resolve()
    seen=set()
    for config in configs:
        model=model_record(config['model_id'])
        if 'diagnostic_retry' in model['roles'] and not config.get('diagnostic_retry'):raise ValueError('Deferred model requires explicit opt-in')
        cfg={**preset(model['canonical_model_id']),**config}
        if cfg['mode'] not in ('batch_file','paced_replay'):raise ValueError('Benchmark supports batch_file or paced_replay')
        cfg={k:v for k,v in cfg.items() if k not in ('out','resume','samples','dataset_manifest','dataset_id','dataset_split','reference')}
        if cfg.get('temperature','cold_model_load')!='cold_model_load':raise ValueError('Warm worker reuse is not supported; repeats are cold model loads')
        from .runner import configuration_id
        identity=read_json(cfg['artifact_provenance']) if cfg.get('artifact_provenance') and Path(cfg['artifact_provenance']).exists() else {}
        cfgid=configuration_id(cfg,identity)
        if cfgid in seen:raise ValueError('Duplicate model configuration')
        seen.add(cfgid)
        for repeat in range(repeats):
            jobid=f'{cfgid[:12]}-r{repeat+1}'
            runid=uuid.uuid4().hex
            actual={**cfg,'out':str(out/'jobs'/jobid),'run_id':runid,'benchmark_id':ident,
                'repeat_id':repeat+1,'temperature':'cold_model_load','random_seed':seed,
                'dataset_id':data['dataset_id'],'dataset_split':data['split'],'samples':data['samples']}
            if data.get('dataset_manifest'):
                actual.pop('samples');actual['dataset_manifest']=data['dataset_manifest']
            jobs.append({'job_id':jobid,'run_id':runid,'run_path':'jobs/'+jobid,'repeat_id':repeat+1,
                         'model_config_id':cfgid,'temperature':'cold_model_load','config':actual,
                         'artifact_identity_sha256':digest(read_json(cfg['artifact_provenance'])) if cfg.get('artifact_provenance') and Path(cfg['artifact_provenance']).exists() else None})
    random.Random(seed).shuffle(jobs)
    plan={'schema_version':'1.0','benchmark_id':ident,'created_utc':utcnow(),
          'dataset_path':str(Path(dataset).resolve()),'dataset_hash':data['dataset_hash'],
          'dataset_id':data['dataset_id'],'split':data['split'],'samples':data['samples'],
          'input_status':data['status'],'input_errors':[{ 'sample_id':s['sample_id'],'errors':s['input_errors']} for s in data['samples'] if s['input_errors']],
          'seed':seed,'jobs':jobs,'repeat_policy':'fresh worker for each job; OS caches uncontrolled; no warm inference claim',
          'evidence_class':'E-LOCAL','source_archive_sha256':data['archive_sha256']}
    out.mkdir(parents=True,exist_ok=False)
    write_json(out/'benchmark.json',plan,exclusive=True)
    write_json(out/'benchmark.sha256.json',{'sha256':sha256(out/'benchmark.json')},exclusive=True)
    write_json(out/'state.json',{'status':'planned','jobs':[]})
    return plan


def load_benchmark(path):
    path=Path(path)
    if sha256(path/'benchmark.json')!=read_json(path/'benchmark.sha256.json')['sha256']:
        raise ValueError('Benchmark plan integrity failed')
    plan=read_json(path/'benchmark.json')
    for job in plan['jobs']:
        target=(path/job['run_path']).resolve()
        if not target.is_relative_to(path.resolve()):raise ValueError('Unsafe run path')
    return plan


def run_benchmark(path,resume=False,progress=None,presenter=None):
    from .runner import run
    path=Path(path);plan=load_benchmark(path);data=verify_dataset(plan['dataset_path'])
    if data['dataset_hash']!=plan['dataset_hash']:raise ValueError('Benchmark dataset changed')
    lock=path/'ACTIVE'
    # Exclusive writer lock is released after normal errors/cancel. A crashed process can be resumed.
    if lock.exists() and resume:
        import psutil
        try:
            owner=read_json(lock);p=psutil.Process(owner['pid'])
            alive=p.create_time()==owner['created']
        except (psutil.NoSuchProcess,ValueError,KeyError):alive=False
        if not alive:lock.unlink()
    import psutil
    write_json(lock,{'pid':os.getpid(),'created':psutil.Process().create_time()},exclusive=True)
    outcomes=[]
    try:
        if resume and (path/'CANCEL').exists():(path/'CANCEL').unlink()
        for index,job in enumerate(plan['jobs']):
            target=path/job['run_path'];cfg=dict(job['config']);cfg['out']=str(target.resolve())
            cancelled=(path/'CANCEL').exists()
            if cancelled:
                old=read_json(target/'state.json') if (target/'state.json').exists() else {}
                state=old if old.get('status')=='completed' else {'status':'cancelled','reasons':['benchmark_cancelled_before_start']}
            else:
                if progress:progress({'index':index,'total':len(plan['jobs']),'job':job,'status':'running'})
                try:
                    artifact=cfg.get('artifact_provenance')
                    if job['artifact_identity_sha256'] is not None and digest(read_json(artifact))!=job['artifact_identity_sha256']:
                        raise ValueError('Frozen artifact identity changed')
                    if target.exists() and not resume:
                        raise FileExistsError('Run already exists; use Resume')
                    cfg['resume']=resume
                    state=run(cfg,presenter=presenter,cancel_requested=lambda:(path/'CANCEL').exists())
                except Exception as exc:
                    state={'status':'failed','reasons':[f'{type(exc).__name__}: {exc}']}
            outcomes.append({'job_id':job['job_id'],'run_id':job['run_id'],**state})
            write_json(path/'state.json',{'status':'running','jobs':outcomes})
            if progress:progress({'index':index+1,'total':len(plan['jobs']),'job':job,**state})
        status='completed' if all(s['status']=='completed' for s in outcomes) else 'cancelled' if (path/'CANCEL').exists() else 'incomplete'
        result={'status':status,'jobs':outcomes};write_json(path/'state.json',result);return result
    finally:lock.unlink(missing_ok=True)


def cancel_benchmark(path):
    path=Path(path);plan=load_benchmark(path);(path/'CANCEL').touch()
    for job in plan['jobs']:
        target=path/job['run_path']
        if target.is_dir() and (target/'state.json').exists() and read_json(target/'state.json')['status']=='running':
            (target/'CANCEL').touch()
    return {'status':'cancel_requested'}
