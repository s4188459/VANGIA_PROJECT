"""Rerun the two failed historical configurations without changing the old run."""
import hashlib
import json
import os
import shutil
from pathlib import Path

from benchmark.runner import Runner, export_summary_csv


def main():
    root = Path(__file__).resolve().parent
    data = root / 'data'
    original_id = 'e634c257ef69434383d580442820821e'
    original = json.loads((data / 'runs' / original_id / 'run.json').read_text('utf-8'))
    dataset = original['dataset']
    folder = data / 'datasets' / dataset['id']
    manifest = json.loads((folder / 'manifest.json').read_text('utf-8'))
    if manifest != original.get('source_dataset', dataset):
        raise RuntimeError('Historical dataset manifest changed.')
    for sample in dataset['samples']:
        audio = folder / 'audio' / (sample['id'] + '.wav')
        reference = (folder / 'transcripts' / (sample['id'] + '.txt')).read_text('utf-8')
        if (hashlib.sha256(audio.read_bytes()).hexdigest() != sample['audio_sha256']
                or hashlib.sha256(reference.encode()).hexdigest() != sample['reference_sha256']):
            raise RuntimeError(f"Historical input changed: {sample['id']}")
    configs = []
    for repo, backend in [('Qwen/Qwen3-ASR-1.7B', 'qwen-asr'),
                          ('facebook/mms-1b-all', 'transformers-ctc')]:
        source = next(m['config'] for m in original['models'] if m['config']['model'] == repo)
        model = data / 'model-cache' / (repo.replace('/', '--') + '-repaired')
        python = root / '.backends' / backend / 'Scripts' / 'python.exe'
        if not (model / 'config.json').is_file() or not python.is_file():
            raise RuntimeError(f'Repaired model/environment missing: {repo}')
        configs.append({**source, 'label': source['label'] + ' [recovery]',
                        'model': str(model), 'python_executable': str(python),
                        'allow_download': False})
    # Isolate recovery bookkeeping from the web server and its historical runs.
    recovery = data / 'recovery'
    target = recovery / 'datasets' / dataset['id']
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(folder, target, copy_function=os.link)
    for path in (recovery / 'runs').glob('*/run.json'):
        record = json.loads(path.read_text('utf-8'))
        if record['status'] in ('running', 'cancelling'):
            raise RuntimeError(f"Recovery already active: {record['id']}")
    runner = Runner(recovery)
    run = runner.start(dataset['id'], configs, {'mode': 'final', 'sample_limit': 0})
    pointer = {'run_id': run['id'], 'source_run_id': original_id,
               'purpose': 'recovery of failed preliminary configurations; not focused validation'}
    (data / 'recovery-run.json').write_text(json.dumps(pointer, indent=2), encoding='utf-8')
    print(json.dumps(pointer), flush=True)
    while runner.thread.is_alive():
        runner.thread.join(30)
        current = runner.get(run['id'])
        print(json.dumps({k: current[k] for k in ('id', 'status', 'completed_tasks', 'total_tasks', 'message')}), flush=True)
    result = runner.get(run['id'])
    (recovery / 'runs' / run['id'] / 'summary.csv').write_bytes(export_summary_csv(result))
    print('Saved recovery summary; original results unchanged.', flush=True)
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
