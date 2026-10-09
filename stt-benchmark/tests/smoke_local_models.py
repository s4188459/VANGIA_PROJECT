"""Opt-in real-model smoke check. Audio is a synthetic fixture, never a research result.

Usage: python tests/smoke_local_models.py --audio data/smoke/SMOKE001.wav
Expects speech: Please open your textbook to page twenty. Read the first question and explain your answer.
"""
import argparse
import io
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.datasets import import_zip
from benchmark.runner import Runner
from server import ROOT, default_models


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    args = parser.parse_args()
    root = ROOT / 'data' / 'smoke' / 'state'
    zip_data = io.BytesIO()
    with zipfile.ZipFile(zip_data, 'w') as bundle:
        bundle.writestr('audio/SMOKE001.wav', args.audio.read_bytes())
        bundle.writestr('transcripts/SMOKE001.txt',
                        'Please open your textbook to page twenty. Read the first question and explain your answer.')
    zip_data.seek(0)
    dataset = import_zip(zip_data, root/'datasets', 'Synthetic smoke fixture — not research data', 'en')
    runner = Runner(root)
    configs = default_models()
    if not configs:
        raise RuntimeError('No local model paths found for this opt-in check.')
    run = runner.start(dataset['id'], configs)
    print('Started real-model smoke run: '+run['id'], flush=True)
    runner.thread.join()
    result = runner.get(run['id'])
    print(json.dumps({'status':result['status'], 'report':str(root/'runs'/run['id']/'run.json'),
                      'models':[{'label':m['config']['label'], 'status':m['status'],
                                 'summary':m['summary'], 'samples':m['samples']} for m in result['models']]},
                     ensure_ascii=True, indent=2), flush=True)
    if result['status'] != 'completed' or any(not m['samples'][0].get('hypothesis','').strip() for m in result['models']):
        raise RuntimeError('Real-model smoke did not complete with speech output.')


if __name__ == '__main__':
    main()
