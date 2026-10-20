"""Local worker protocol. JSON on stdout, library diagnostics on stderr; no network API."""
import contextlib
import json
import os
import sys
import time
import traceback


def main():
    from .adapters import Adapter
    adapter=None
    for line in sys.stdin:
        try:
            req=json.loads(line);start=time.monotonic_ns()
            with contextlib.redirect_stdout(sys.stderr):
                if req['op']=='load':adapter=Adapter(req['config']);value=adapter.load()
                elif req['op']=='transcribe':value=adapter.transcribe_file(req['audio'])
                elif req['op']=='unload':
                    if adapter:adapter.unload()
                    value={'unloaded':True}
                else:raise ValueError('Unknown worker operation')
            result={'id':req['id'],'ok':True,'result':value,'service_ns':time.monotonic_ns()-start,
                    'clock_id':f'worker-{os.getpid()}','worker_start_ns':start,'worker_end_ns':time.monotonic_ns()}
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            result={'id':req.get('id'),'ok':False,'error':f'{type(exc).__name__}: {exc}'}
        print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
