import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import wave
import zipfile
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.adapters import validate_config, FasterWhisperAdapter
from benchmark.datasets import import_zip
from benchmark.runner import Runner, aggregate, export_csv
from benchmark.scoring import normalize, score
from server import make_server


def wav_bytes():
    data = io.BytesIO()
    with wave.open(data, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b'\0\0' * 16000)
    return data.getvalue()


def make_zip(entries=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as bundle:
        for name, data in (entries or {'audio/EN001.wav': wav_bytes(), 'transcripts/EN001.txt': 'hello class'}).items():
            bundle.writestr(name, data)
    output.seek(0)
    return output


def config(label='test model'):
    return validate_config({'label': label, 'model': 'fake-local-path'})


class FakeAdapter:
    def __init__(self, config):
        self.config = config
    def load(self):
        if self.config['label'] == 'cannot load':
            raise RuntimeError('test load failure')
    def transcribe(self, audio_path, language):
        if self.config['label'] == 'partial' and audio_path.stem == 'EN002':
            raise RuntimeError('test decode failure')
        return {'text': 'hello class'}
    def close(self):
        pass


class ScoringTests(unittest.TestCase):
    def test_renamed_english_model_cannot_silently_transcribe_vietnamese(self):
        adapter = FasterWhisperAdapter(config())
        adapter.model = SimpleNamespace(model=SimpleNamespace(is_multilingual=False),
                                        transcribe=lambda *args, **kwargs: (iter(()), SimpleNamespace(language='en')))
        with self.assertRaisesRegex(ValueError, 'đa ngôn ngữ'):
            adapter.transcribe(Path('unused.wav'), 'vi')
    def test_configuration_rejects_fractional_boolean_and_null_values(self):
        for changes in ({'beam_size':1.5}, {'cpu_threads':True}, {'model':None}, {'label':None}, {'vad_filter':'false'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_config({'label':'test','model':'local', **changes})
    def test_normalization_and_unicode(self):
        self.assertEqual(normalize('  Hello, CLASS! '), 'hello class')
        self.assertEqual(normalize('TÔI học tiếng Việt.'), 'tôi học tiếng việt')
        self.assertEqual(normalize('Don’t'), "don't")

    def test_edit_counts(self):
        cases = [('a b c', 'a b c', (0, 0, 0)), ('a b c', 'a x c', (1, 0, 0)),
                 ('a b c', 'a c', (0, 1, 0)), ('a b', 'a x b', (0, 0, 1)),
                 ('a b', '', (0, 2, 0))]
        for ref, hyp, expected in cases:
            result = score(ref, hyp)
            self.assertEqual(tuple(result[k] for k in ('substitutions','deletions','insertions')), expected)
        self.assertGreater(score('a', 'a b c')['wer'], 1)

    def test_empty_reference_rejected(self):
        with self.assertRaises(ValueError):
            score('...', 'hello')

    def test_corpus_weighting(self):
        rows = [dict(status='ok', reference_words=1, errors=1, elapsed_s=1, duration_s=2),
                dict(status='ok', reference_words=9, errors=0, elapsed_s=1, duration_s=2),
                dict(status='error')]
        result = aggregate(rows)
        self.assertAlmostEqual(result['wer'], .1)
        self.assertEqual(result['failed'], 1)
        self.assertEqual(result['rtf'], .5)


class DatasetTests(unittest.TestCase):
    def test_truncated_wav_and_invalid_utf8_rejected(self):
        for entries in ({'EN001.wav':wav_bytes()[:-10], 'EN001.txt':'hello'},
                        {'EN001.wav':wav_bytes(), 'EN001.txt':b'\xff\xfe\x00'}):
            with self.assertRaises(ValueError):
                import_zip(make_zip(entries),self.root,'invalid','en')
        self.assertEqual(list(self.root.iterdir()),[])
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    def test_valid_zip_preserves_audio_and_utf8(self):
        reference = 'Xin chào lớp học.'
        dataset = import_zip(make_zip({'a/VI001.wav':wav_bytes(), 't/VI001.txt':reference}), self.root, 'Vietnamese', 'vi')
        self.assertEqual(dataset['samples'][0]['duration_s'], 1)
        self.assertEqual((self.root/dataset['id']/'transcripts/VI001.txt').read_text(encoding='utf-8'), reference)
        self.assertEqual((self.root/dataset['id']/'audio/VI001.wav').read_bytes(), wav_bytes())
    def test_unpaired_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Thiếu TXT'):
            import_zip(make_zip({'EN001.wav':wav_bytes()}), self.root, 'missing', 'en')
    def test_duplicates_and_traversal_rejected(self):
        for entries in ({'x/EN001.wav':wav_bytes(), 'y/en001.wav':wav_bytes()},
                        {'../EN001.wav':wav_bytes()}, {'C:/EN001.wav':wav_bytes()}):
            with self.assertRaises(ValueError):
                import_zip(make_zip(entries), self.root, 'bad', 'en')
    def test_invalid_audio_and_empty_reference_leave_no_dataset(self):
        for entries in ({'EN001.wav':b'bad audio', 'EN001.txt':'hello'},
                        {'EN001.wav':wav_bytes(), 'EN001.txt':'...'}):
            with self.assertRaises(ValueError):
                import_zip(make_zip(entries), self.root, 'bad', 'en')
        self.assertEqual(list(self.root.iterdir()), [])


class RunnerTests(unittest.TestCase):
    def test_hundred_pairs_two_models_are_persisted_and_exported(self):
        entries = {f'{sample:03}.{ext}':data for sample in range(100)
                   for ext,data in [('wav',wav_bytes()),('txt','hello class')]}
        dataset = import_zip(make_zip(entries), self.root/'datasets','100 fixture pairs','en')
        run = self.runner.start(dataset['id'],[config('first'),config('second')])
        self.runner.thread.join(30)
        self.assertFalse(self.runner.thread.is_alive())
        result = self.runner.get(run['id'])
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['completed_tasks'],200)
        self.assertEqual(result['common_sample_count'],100)
        self.assertEqual(len(list(csv.DictReader(io.StringIO(export_csv(result).decode('utf-8-sig'))))),200)
    def test_restarted_runner_marks_unfinished_run_interrupted(self):
        from benchmark.datasets import write_json
        run = self.execute([config()])
        run['status']='running'
        run['models'][0]['status']='running'
        write_json(self.root/'runs'/run['id']/'run.json',run)
        recovered = Runner(self.root).get(run['id'])
        self.assertEqual(recovered['status'],'interrupted')
        self.assertEqual(recovered['models'][0]['status'],'interrupted')
        self.assertEqual(len(recovered['models'][0]['samples']),2)
    def test_windows_multiline_transcript_hash_is_stable(self):
        dataset = import_zip(make_zip({'EN001.wav':wav_bytes(), 'EN001.txt':b'hello\r\nclass\r\n'}),
                             self.root/'datasets','windows','en')
        run = self.runner.start(dataset['id'], [config()])
        self.runner.thread.join(10)
        result = self.runner.get(run['id'])
        self.assertEqual(result['models'][0]['summary']['failed'],0)
        self.assertEqual(result['models'][0]['summary']['wer'],0)
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        entries = {f'{sample}.{ext}':data for sample in ('EN001','EN002')
                   for ext,data in [('wav',wav_bytes()),('txt','hello class')]}
        self.dataset = import_zip(make_zip(entries), self.root/'datasets', 'pilot', 'en')
        self.runner = Runner(self.root, {'faster-whisper':FakeAdapter})
    def tearDown(self):
        if self.runner.thread:
            self.runner.thread.join(10)
        self.temp.cleanup()
    def execute(self, configs):
        run = self.runner.start(self.dataset['id'], configs)
        self.runner.thread.join(10)
        self.assertFalse(self.runner.thread.is_alive())
        return self.runner.get(run['id'])
    def test_comparison_uses_intersection_and_preserves_errors(self):
        run = self.execute([config('complete'),config('partial')])
        self.assertEqual(run['status'], 'completed_with_errors')
        self.assertEqual(run['common_sample_count'], 1)
        self.assertEqual(run['models'][0]['summary']['completed'], 2)
        self.assertEqual(run['models'][1]['summary']['failed'], 1)
        self.assertEqual(run['completed_tasks'], 4)
        self.assertEqual(run['models'][0]['common_summary']['completed'], 1)
        fresh = Runner(self.root).get(run['id'])
        self.assertEqual(fresh, run)
        csv_rows = list(csv.DictReader(io.StringIO(export_csv(run).decode('utf-8-sig'))))
        self.assertEqual(len(csv_rows), 4)
    def test_model_load_failure_is_counted(self):
        run = self.execute([config('cannot load'),config('complete')])
        self.assertEqual(run['models'][0]['summary']['failed'], 2)
        self.assertEqual(run['common_sample_count'], 0)
        self.assertIsNone(run['models'][0]['summary']['wer'])
    def test_modified_reference_is_rejected(self):
        (self.root/'datasets'/self.dataset['id']/'transcripts/EN001.txt').write_text('changed',encoding='utf-8')
        run = self.execute([config()])
        self.assertEqual(run['models'][0]['summary']['failed'], 1)
    def test_vietnamese_rejects_english_only_model(self):
        dataset = import_zip(make_zip(),self.root/'datasets','vi','vi')
        with self.assertRaisesRegex(ValueError,'đa ngôn ngữ'):
            self.runner.start(dataset['id'],[validate_config({'label':'en','model':'small.en'})])
    def test_cancellation_between_samples(self):
        entered, release = threading.Event(), threading.Event()
        class SlowAdapter(FakeAdapter):
            def transcribe(self, path, language):
                entered.set()
                release.wait(5)
                return {'text':'hello class'}
        self.runner.adapters = {'faster-whisper':SlowAdapter}
        run = self.runner.start(self.dataset['id'],[config()])
        self.assertTrue(entered.wait(5))
        with self.assertRaises(ValueError):
            self.runner.start(self.dataset['id'],[config()])
        self.runner.cancel(run['id'])
        release.set()
        self.runner.thread.join(10)
        final = self.runner.get(run['id'])
        self.assertEqual(final['status'],'cancelled')
        self.assertEqual(final['completed_tasks'],1)
    def test_csv_formula_is_escaped(self):
        run = self.execute([config('=danger')])
        rows = list(csv.DictReader(io.StringIO(export_csv(run).decode('utf-8-sig'))))
        self.assertEqual(rows[0]['model'], "'=danger")


class HttpTests(unittest.TestCase):
    def test_upload_preview_run_download_and_origin_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = make_server(tmp, 0)
            server.runner.adapters = {'faster-whisper':FakeAdapter}
            thread = threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            def request(path, body=None, content='application/json', origin=None):
                headers = {'Content-Type':content}
                if origin: headers['Origin'] = origin
                return urllib.request.urlopen(urllib.request.Request(base+path,data=body,headers=headers), timeout=10)
            try:
                with request('/') as response:
                    self.assertIn('STT Bench',response.read().decode())
                with request('/api/datasets?name=pilot&language=en',make_zip().getvalue(),'application/zip') as response:
                    dataset = json.load(response)
                with request(f"/api/datasets/{dataset['id']}/EN001/audio") as response:
                    self.assertEqual(response.read(),wav_bytes())
                with request('/api/runs',json.dumps({'dataset_id':dataset['id'],'models':[config()], 'references_reviewed':True}).encode()) as response:
                    run = json.load(response)
                server.runner.thread.join(10)
                with request(f"/api/runs/{run['id']}/csv") as response:
                    self.assertIn('hello class',response.read().decode('utf-8-sig'))
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request('/api/models',json.dumps(config()).encode(),origin='http://other.test')
                self.assertEqual(error.exception.code,400)
                with request('/api/state') as response:
                    self.assertEqual(len(json.load(response)['runs']),1)
            finally:
                server.shutdown(); server.server_close(); thread.join(5)


if __name__ == '__main__':
    unittest.main()
