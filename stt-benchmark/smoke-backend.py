"""Technical inference smoke; never use its synthetic fixture to rank model quality."""
import argparse
from pathlib import Path
import json
import sys
import time
from benchmark.adapters import validate_config
from benchmark.worker_client import WorkerAdapter
from benchmark.datasets import write_json
from benchmark.catalog import backend_status

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend',required=True)
    parser.add_argument('--model',required=True)
    parser.add_argument('--language',choices=['en','vi'],default='en')
    parser.add_argument('--audio',type=Path,required=True)
    parser.add_argument('--download',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    python=Path(backend_status()[args.backend]['python_executable'] or sys.executable)
    config=validate_config(dict(label=args.model.split('/')[-1],backend=args.backend,model=args.model,
       python_executable=str(python) if python.is_file() else sys.executable,
       compute_type='int8' if args.backend=='faster-whisper' else 'float32',
       beam_size=1,vad_filter=False,allow_download=args.download,languages=[args.language]))
    adapter=WorkerAdapter(config)
    result={'config':config,'fixture':str(args.audio.resolve()),'kind':'technical-smoke-not-quality-benchmark'}
    try:
        start=time.perf_counter()
        result['runtime']=adapter.load()
        result['load_s']=time.perf_counter()-start
        start=time.perf_counter()
        result['prediction']=adapter.transcribe(args.audio,args.language)
        result['inference_s']=time.perf_counter()-start
        if not result['prediction']['text'].strip():raise ValueError('Empty output on speech fixture')
        result['status']='passed'
    except Exception as exc:
        result.update(status='failed',error=str(exc))
    finally:
        adapter.close()
    folder=root/'data'/'backend-smoke'
    write_json(folder/(args.backend+'-'+config['label'].replace(':','_')+'.json'),result)
    print(json.dumps(result,ensure_ascii=True),flush=True)
    return 0 if result['status']=='passed' else 1

if __name__=='__main__':sys.exit(main())
