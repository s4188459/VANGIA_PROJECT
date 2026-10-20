"""Run pilots, optionally followed by full English experiments. Old runs are untouched."""
import argparse
import json
from pathlib import Path
import time
from benchmark.runner import Runner, export_csv, export_summary_csv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset')
    parser.add_argument('--resume', help='Resume an interrupted run after verifying its previous process has stopped')
    parser.add_argument('--full-after-pilot', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / 'data'
    active = [p for p in (root/'runs').glob('*/run.json')
              if json.loads(p.read_text('utf-8'))['status'] in ('running','cancelling')]
    if active and (not args.resume or any(p.parent.name != args.resume for p in active)):
        raise SystemExit('A run is marked active. Finish or resolve it in the server before starting this script.')
    runner = Runner(root)
    if args.resume:
        run = runner.resume(args.resume)
        while runner.thread.is_alive():
            runner.thread.join(30)
            current = runner.get(run['id'])
            print(current['message'], current['completed_tasks'], '/', current['total_tasks'], flush=True)
        final = runner.get(run['id'])
        folder = root/'runs'/run['id']
        (folder/'summary.csv').write_bytes(export_summary_csv(final))
        (folder/'samples.csv').write_bytes(export_csv(final))
        print(final['status'], run['id'], flush=True)
        return
    if not args.dataset:
        parser.error('--dataset is required unless --resume is used')
    records = []
    for limit in ([3, 0] if args.full_after_pilot else [3]):
        for mode in ('experiment2', 'experiment3'):
            run = runner.start(args.dataset, [], dict(mode=mode, sample_limit=limit))
            print(json.dumps({'run_id':run['id'], 'mode':mode, 'sample_limit':limit}), flush=True)
            while runner.thread.is_alive():
                runner.thread.join(30)
                current = runner.get(run['id'])
                print(current['message'], current['completed_tasks'], '/', current['total_tasks'], flush=True)
            final = runner.get(run['id'])
            folder = root/'runs'/run['id']
            (folder/'summary.csv').write_bytes(export_summary_csv(final))
            (folder/'samples.csv').write_bytes(export_csv(final))
            records.append(dict(id=run['id'], mode=mode, limit=limit, status=final['status']))
            print(json.dumps(records[-1]), flush=True)
            if final['status'] != 'completed':
                raise SystemExit('Experiment did not complete successfully; subsequent runs were not started.')


if __name__ == '__main__':
    main()
