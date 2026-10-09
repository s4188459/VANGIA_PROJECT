"""Opt-in real HTTP/model smoke, using a synthetic audio fixture, not study data."""
import argparse
import csv
import io
import json
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import hashlib
import wave
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import ROOT, default_models, make_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    args = parser.parse_args()
    data_root = ROOT/'data'/'smoke'/('http-'+uuid.uuid4().hex)
    audio = args.audio.read_bytes()
    reference = 'Please open your textbook to page twenty.\r\nRead the first question and explain your answer.\r\n'
    archive = io.BytesIO()
    with zipfile.ZipFile(archive,'w') as bundle:
        bundle.writestr('audio/SMOKE001'+args.audio.suffix.lower(),audio)
        bundle.writestr('transcripts/SMOKE001.txt',reference)
    server = make_server(data_root,0)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    def request(route, body=None, content='application/json'):
        req = urllib.request.Request(base+route,data=body,headers={'Content-Type':content})
        with urllib.request.urlopen(req,timeout=30) as response:
            return response.read()
    try:
        for route in ('/','/app.js','/style.css'):
            assert request(route), f'Empty static file: {route}'
        try:
            request('/api/datasets?language=en',b'not a zip','application/zip')
            raise AssertionError('Invalid upload accepted')
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
        dataset = json.loads(request('/api/datasets?name=Synthetic%20HTTP%20QA&language=en',archive.getvalue(),'application/zip'))
        preview_audio = request(f"/api/datasets/{dataset['id']}/SMOKE001/audio")
        with wave.open(io.BytesIO(preview_audio),'rb') as wav:
            assert (wav.getframerate(),wav.getnchannels(),wav.getsampwidth()) == (16000,1,2)
        assert hashlib.sha256(preview_audio).hexdigest() == dataset['samples'][0]['audio_sha256']
        assert (data_root/'datasets'/dataset['id']/'originals'/('SMOKE001'+args.audio.suffix.lower())).read_bytes() == audio
        preview = json.loads(request(f"/api/datasets/{dataset['id']}/SMOKE001/reference"))['text']
        assert preview == reference.replace('\r\n','\n').strip()
        models = default_models()
        assert len(models)==2,'Expected installed base.en and small.en'
        payload = {'dataset_id':dataset['id'],'models':models,'references_reviewed':True}
        run = json.loads(request('/api/runs',json.dumps(payload).encode()))
        print('HTTP real-model run: '+run['id'],flush=True)
        deadline = time.monotonic()+180
        while run['status'] in ('running','cancelling'):
            if time.monotonic()>deadline:
                raise TimeoutError('HTTP smoke exceeded 180 seconds')
            time.sleep(.2)
            run = json.loads(request('/api/runs/'+run['id']))
        assert run['status']=='completed',run
        assert run['completed_tasks']==2 and run['common_sample_count']==1
        assert all(m['samples'][0]['hypothesis'].strip() for m in run['models'])
        csv_data = request('/api/runs/'+run['id']+'/csv')
        csv_rows = list(csv.DictReader(io.StringIO(csv_data.decode('utf-8-sig'))))
        report = json.loads(request('/api/runs/'+run['id']+'/json'))
        assert report==run and len(csv_rows)==2
        for row,model in zip(csv_rows,run['models']):
            sample=model['samples'][0]
            assert row['sample_id']=='SMOKE001' and row['hypothesis']==sample['hypothesis']
            assert float(row['wer'])==sample['wer']
            assert int(row['substitutions'])+int(row['deletions'])+int(row['insertions'])==sample['errors']
        print(json.dumps({'status':'passed','scope':'HTTP upload, preview, real inference, scoring, CSV/JSON parity',
                          'models':[m['config']['label'] for m in run['models']],
                          'run_id':run['id'],'report':str(data_root/'runs'/run['id']/'run.json')},indent=2),flush=True)
    finally:
        if server.runner.thread and server.runner.thread.is_alive():
            server.runner.cancel_event.set()
            server.runner.thread.join(30)
        server.shutdown();server.server_close();thread.join(5)


if __name__=='__main__':
    main()
