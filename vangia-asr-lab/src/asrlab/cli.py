"""Headless entry point; all model workers are optional."""
import argparse
import json
from pathlib import Path
from .common import registry, read_json, write_json


def main(argv=None):
    p = argparse.ArgumentParser(prog='asrlab')
    sub = p.add_subparsers(dest='command', required=True)
    i = sub.add_parser('import-legacy')
    i.add_argument('--json', required=True); i.add_argument('--csv', required=True); i.add_argument('--out', required=True)
    sub.add_parser('list-models')
    a = sub.add_parser('audit'); a.add_argument('run_dir')
    r = sub.add_parser('report'); r.add_argument('run_dir'); r.add_argument('--format', default='md,json,html')
    u = sub.add_parser('ui'); u.add_argument('--run-dir'); u.add_argument('--smoke', action='store_true')
    s = sub.add_parser('score'); s.add_argument('--reference',required=True);s.add_argument('--predictions',required=True);s.add_argument('--out')
    pl = sub.add_parser('plan');pl.add_argument('--matrix',required=True);pl.add_argument('--seed',type=int,default=42);pl.add_argument('--diagnostic-retry',action='store_true');pl.add_argument('--out')
    run = sub.add_parser('run');run.add_argument('--config',required=True);run.add_argument('--resume',action='store_true')
    pf = sub.add_parser('preflight');pf.add_argument('--config',required=True)
    da = sub.add_parser('dataset-add');da.add_argument('--registry',required=True);da.add_argument('--sample',required=True)
    dl = sub.add_parser('dataset-lock');dl.add_argument('--registry',required=True);dl.add_argument('--split',required=True)
    co = sub.add_parser('compare');co.add_argument('--a',required=True);co.add_argument('--b',required=True);co.add_argument('--seed',type=int,default=42)
    an = sub.add_parser('annotate');an.add_argument('run_dir');an.add_argument('--annotation',required=True)
    si = sub.add_parser('signoff');si.add_argument('run_dir');si.add_argument('--reviewer',required=True);si.add_argument('--notes',required=True)
    ca = sub.add_parser('capture');ca.add_argument('--out',required=True);ca.add_argument('--seconds',type=float,required=True);ca.add_argument('--consent-record-id',required=True);ca.add_argument('--device',type=int);ca.add_argument('--source',choices=['microphone','system_loopback'],default='microphone')
    ce = sub.add_parser('cancel');ce.add_argument('run_dir')
    sm = sub.add_parser('diagnostic-smoke');sm.add_argument('--config',required=True)
    red = sub.add_parser('export-redacted');red.add_argument('run_dir');red.add_argument('--out',required=True)
    delete = sub.add_parser('delete-run');delete.add_argument('run_dir');delete.add_argument('--confirm-run-id',required=True)
    bind = sub.add_parser('bind-legacy-audio');bind.add_argument('--archive',required=True);bind.add_argument('--json',required=True);bind.add_argument('--out',required=True);bind.add_argument('--consent-record-id',required=True)
    pr = sub.add_parser('preregister');pr.add_argument('--dataset',required=True);pr.add_argument('--configs',nargs='+',required=True);pr.add_argument('--outcomes',nargs='+',required=True);pr.add_argument('--owner',required=True);pr.add_argument('--out',required=True)
    study = sub.add_parser('study-add');study.add_argument('--study',required=True);study.add_argument('--response',required=True)
    summary = sub.add_parser('study-report');summary.add_argument('--study',required=True)
    arch = sub.add_parser('compare-architectures');arch.add_argument('--single',required=True);arch.add_argument('--dual',required=True)
    recovery = sub.add_parser('recover');recovery.add_argument('run_dir')
    trace = sub.add_parser('trace-summary');trace.add_argument('run_dir');trace.add_argument('--out')
    for command in ('preview-zip','import-zip'):
        zp=sub.add_parser(command);zp.add_argument('--archive',required=True);zp.add_argument('--metadata')
        if command=='import-zip':
            zp.add_argument('--out',required=True);zp.add_argument('--consent-record-id',required=True);zp.add_argument('--silence-id',action='append',default=[])
    bc=sub.add_parser('benchmark-create');bc.add_argument('--dataset',required=True);bc.add_argument('--configs',nargs='+',required=True);bc.add_argument('--out',required=True);bc.add_argument('--repeats',type=int,default=1);bc.add_argument('--seed',type=int,default=42)
    br=sub.add_parser('benchmark-run');br.add_argument('benchmark_dir');br.add_argument('--resume',action='store_true')
    bx=sub.add_parser('benchmark-cancel');bx.add_argument('benchmark_dir')
    ex=sub.add_parser('export-analysis');ex.add_argument('source');ex.add_argument('--out',required=True)
    ve=sub.add_parser('validate-export');ve.add_argument('source')
    cp=sub.add_parser('compare-analysis');cp.add_argument('--source-a',required=True);cp.add_argument('--run-a',required=True);cp.add_argument('--config-a',required=True);cp.add_argument('--source-b',required=True);cp.add_argument('--run-b',required=True);cp.add_argument('--config-b',required=True);cp.add_argument('--seed',type=int,default=42)
    args = p.parse_args(argv)
    try:
        if args.command == 'import-legacy':
            from .legacy import import_legacy
            result = import_legacy(args.json, args.csv, args.out)
            print(json.dumps({k:v for k,v in result.items() if k not in ('configurations','candidates')}, indent=2))
        elif args.command == 'list-models':
            print(json.dumps(registry(), indent=2))
        elif args.command == 'audit':
            from .storage import audit
            result = audit(args.run_dir); print(json.dumps(result, indent=2))
            return 0 if result['ok'] else 1
        elif args.command == 'report':
            from .reports import report
            print(report(args.run_dir, args.format.split(',')))
        elif args.command == 'ui':
            from .ui import launch
            launch(args.run_dir, args.smoke)
        else:
            if args.command in ('preview-zip','import-zip'):
                from .zip_dataset import preview_zip,import_zip
                result=preview_zip(args.archive,args.metadata) if args.command=='preview-zip' else import_zip(args.archive,args.out,args.consent_record_id,args.metadata,args.silence_id)
            elif args.command=='benchmark-create':
                from .benchmark import create_benchmark
                result=create_benchmark(args.dataset,[read_json(p) for p in args.configs],args.out,args.repeats,args.seed)
            elif args.command=='benchmark-run':
                from .benchmark import run_benchmark
                result=run_benchmark(args.benchmark_dir,args.resume)
            elif args.command=='benchmark-cancel':
                from .benchmark import cancel_benchmark
                result=cancel_benchmark(args.benchmark_dir)
            elif args.command=='export-analysis':
                from .analysis_export import export_analysis
                result=export_analysis(args.source,args.out)
            elif args.command=='validate-export':
                from .analysis_export import validate_bundle
                result=validate_bundle(args.source)
            elif args.command=='compare-analysis':
                from .analysis_export import compare_runs
                result=compare_runs(args.source_a,args.run_a,args.config_a,args.source_b,args.run_b,args.config_b,args.seed)
            elif args.command=='trace-summary':
                from .storage import audit
                from .events import EventLog
                from .timing import trace_summary
                integrity=audit(args.run_dir)
                if not integrity['ok']:raise ValueError('Trace evidence integrity failed: '+str(integrity['errors']))
                manifest=read_json(Path(args.run_dir)/'manifest.json')
                result={'source_run_id':manifest['run_id'],'evidence_class':manifest['evidence_class'],
                        **trace_summary(EventLog(Path(args.run_dir)/'events.jsonl').events)}
            elif args.command=='recover':
                from .storage import recover_run
                result=recover_run(args.run_dir)
            elif args.command=='preregister':
                from .governance import preregister
                result=preregister(args.out,read_json(args.dataset),[read_json(c) for c in args.configs],args.outcomes,args.owner)
            elif args.command=='study-add':
                from .study import add_response
                result=add_response(args.study,read_json(args.response))
            elif args.command=='study-report':
                from .study import summarize
                result=summarize(args.study)
            elif args.command=='compare-architectures':
                from .experiments import compare_architectures
                result=compare_architectures(read_json(args.single),read_json(args.dual))
            elif args.command=='bind-legacy-audio':
                from .legacy_audio import bind_archive
                result=bind_archive(args.archive,args.json,args.out,args.consent_record_id)
            elif args.command=='diagnostic-smoke':
                from .diagnostic import smoke
                result=smoke(read_json(args.config))
            elif args.command=='export-redacted':
                from .privacy import export_redacted
                result=export_redacted(args.run_dir,args.out)
            elif args.command=='delete-run':
                from .privacy import delete_run
                result=delete_run(args.run_dir,args.confirm_run_id)
            elif args.command=='score':
                from .storage import read_jsonl
                from .metrics import corpus_score
                result=corpus_score(read_jsonl(args.reference),read_jsonl(args.predictions))
            elif args.command=='plan':
                from .experiments import plan
                result=plan(args.matrix,args.seed,args.diagnostic_retry)
            elif args.command=='run':
                from .runner import run
                config=read_json(args.config)
                if args.resume:config['resume']=True
                result=run(config)
            elif args.command=='preflight':
                from .adapters import preflight
                result=preflight(read_json(args.config))
            elif args.command in ('dataset-add','dataset-lock'):
                from .datasets import DatasetRegistry
                manager=DatasetRegistry(args.registry)
                result=manager.add(read_json(args.sample)) if args.command=='dataset-add' else manager.lock(args.split)
            elif args.command=='compare':
                from .experiments import paired_bootstrap
                from .storage import read_jsonl
                result=paired_bootstrap(read_jsonl(args.a),read_jsonl(args.b),args.seed)
            elif args.command=='annotate':
                from .review import annotate
                result=annotate(args.run_dir,read_json(args.annotation))
            elif args.command=='signoff':
                from .review import sign_off
                result=sign_off(args.run_dir,args.reviewer,args.notes)
            elif args.command=='capture':
                from .audio import capture
                result=capture(args.out,args.seconds,args.consent_record_id,args.device,args.source)
                write_json(str(args.out)+'.capture.json',result)
            elif args.command=='cancel':
                read_json(Path(args.run_dir)/'manifest.json')
                (Path(args.run_dir)/'CANCEL').touch();result={'status':'cancel_requested'}
            if getattr(args,'out',None) and args.command in ('score','plan','trace-summary'):write_json(args.out,result)
            print(json.dumps(result,indent=2,ensure_ascii=False))
            if args.command in ('run','diagnostic-smoke','benchmark-run') and result['status']!='completed':return 3
            if args.command=='validate-export' and not result['ok']:return 1
        return 0
    except (ValueError, OSError, KeyError, ImportError) as exc:
        print(json.dumps({'status':'ERROR', 'reason':str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
