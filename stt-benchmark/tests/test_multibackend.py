import io
import csv
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.scoring import character_distance, score
from benchmark.replay import replay, validate_options
from benchmark.catalog import catalog, supported_languages
from benchmark.adapters import validate_config
from benchmark.runner import Runner, aggregate, export_summary_csv
from benchmark.datasets import import_zip
from test_benchmark import make_zip, FakeAdapter, config


class MultiBackendTests(unittest.TestCase):
    def test_batch_more_than_eight_models_and_summary_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            ds=import_zip(make_zip(),root/'datasets','batch','en')
            runner=Runner(root,adapters={'faster-whisper':FakeAdapter})
            configs=[config('model '+str(i)) for i in range(10)]+[config('cannot load')]
            run=runner.start(ds['id'],configs)
            runner.thread.join(20)
            result=runner.get(run['id'])
            self.assertEqual(result['status'],'completed_with_errors')
            self.assertEqual(result['completed_tasks'],11)
            rows=list(csv.DictReader(io.StringIO(export_summary_csv(result).decode('utf-8-sig'))))
            self.assertEqual(len(rows),11)
            self.assertEqual(rows[0]['wer'],'0.0')
            self.assertEqual(rows[-1]['status'],'error')
            self.assertEqual(rows[-1]['failed'],'1')
            with self.assertRaises(ValueError):runner.start(ds['id'],[config(str(i)) for i in range(51)])

    def test_cer_independent_oracle(self):
        def oracle(a, b):
            row = list(range(len(b) + 1))
            for i, x in enumerate(a, 1):
                current = [i]
                for j, y in enumerate(b, 1):
                    current.append(min(row[j]+1,current[-1]+1,row[j-1]+(x!=y)))
                row = current
            return row[-1]
        words = [''.join(p) for n in range(5) for p in itertools.product('aộ', repeat=n)]
        for a in words:
            for b in words:
                self.assertEqual(character_distance(a,b), oracle(a,b), (a,b))
        self.assertEqual(score('Tôi học', 'tôi học')['cer'], 0)
        self.assertGreater(score('tôi', 'toi')['cer'], 0)
        self.assertEqual(score('data set', 'dataset')['cer'], 0)

    def test_every_preset_validates_and_language_is_enforced(self):
        for row in catalog():
            cfg = validate_config({**row, 'compute_type':'int8' if row['backend']=='faster-whisper' else 'float32',
                                   'vad_filter':row['backend']=='faster-whisper','beam_size':1})
            self.assertEqual(set(supported_languages(cfg)),set(row['languages']))
        self.assertEqual(supported_languages(validate_config({'label':'x','model':'distil-large-v3'})), ['en'])

    def test_invalid_options_and_unsupported_knobs(self):
        for value in ({'chunk_seconds':True},{'chunk_seconds':float('nan')},{'mode':'magic'},{'allow_cloud':'yes'}):
            with self.assertRaises(ValueError):validate_options(value)
        with self.assertRaises(ValueError):
            validate_config({'label':'x','model':'x','backend':'vosk'})

    def test_replay_causal_queue_and_last_short_chunk(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'a.wav'
            with wave.open(str(path),'wb') as f:
                f.setparams((1,2,16000,0,'NONE','not compressed'))
                f.writeframes(b'\0\0'*80000)
            class Adapter:
                def transcribe(self, path, language):
                    with wave.open(str(path),'rb') as f:
                        self.asserted_duration=f.getnframes()/f.getframerate()
                    return {'text':'hello'}
            ticks=iter([0,3,3,6,6,7])
            result=replay(Adapter(),path,'en',2,clock=lambda:next(ticks))
            self.assertEqual([r['end_s'] for r in result['chunks']],[2,4,5])
            self.assertEqual([r['emitted_at_s'] for r in result['chunks']],[5,8,9])
            self.assertEqual(result['replay_metrics']['first_text_s'],5)
            self.assertEqual(result['replay_metrics']['deadline_misses'],2)
            self.assertEqual(result['text'],'hello hello hello')
            with self.assertRaises(InterruptedError):
                replay(Adapter(),path,'en',2,cancelled=lambda:True)

    def test_runner_new_metrics_and_cloud_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            ds=import_zip(make_zip(),root/'datasets','test','en')
            runner=Runner(root, adapters={'faster-whisper':FakeAdapter})
            run=runner.start(ds['id'],[config()],{'mode':'live_replay','chunk_seconds':1})
            runner.thread.join(10)
            run=runner.get(run['id'])
            self.assertEqual(run['status'],'completed')
            self.assertEqual(run['models'][0]['summary']['cer'],0)
            self.assertIsNotNone(run['models'][0]['summary']['chunk_p95_s'])
            cloud=validate_config({'label':'cloud','model':'scribe_v2','backend':'elevenlabs',
                                  'compute_type':'float32','vad_filter':False,'beam_size':1})
            with self.assertRaisesRegex(ValueError,'cloud'):
                runner.start(ds['id'],[cloud])


if __name__=='__main__':unittest.main()
