import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
import wave

import av
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.datasets import import_zip
from test_benchmark import make_zip


def encoded_fixture(container_format, codec, rate=48000):
    output = io.BytesIO()
    with av.open(output, mode='w', format=container_format) as container:
        stream = container.add_stream(codec, rate=rate)
        stream.layout = 'mono'
        samples = (.1*np.sin(2*np.pi*440*np.arange(rate//2)/rate)).astype(np.float32).reshape(1,-1)
        frame = av.AudioFrame.from_ndarray(samples,format='fltp',layout='mono')
        frame.sample_rate = rate
        converter = av.AudioResampler(format=stream.codec_context.codec.audio_formats[0].name,layout='mono',rate=rate)
        for converted in converter.resample(frame)+converter.resample(None):
            for packet in stream.encode(converted):
                container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    return output.getvalue()


class FormatTests(unittest.TestCase):
    def test_common_formats_become_same_canonical_format_and_keep_original(self):
        formats = [('mp3','mp3','libmp3lame'),('m4a','mp4','aac'),('flac','flac','flac'),
                   ('ogg','ogg','libopus'),('opus','opus','libopus'),('webm','webm','libopus'),
                   ('aac','adts','aac'),('wav','wav','pcm_s16le')]
        with tempfile.TemporaryDirectory() as directory:
            for extension,container,codec in formats:
                with self.subTest(extension=extension):
                    original = encoded_fixture(container,codec)
                    dataset = import_zip(make_zip({f'EN001.{extension}':original,'EN001.txt':'hello class'}),Path(directory),'fixture','en')
                    folder = Path(directory)/dataset['id']
                    metadata = dataset['samples'][0]
                    self.assertEqual((folder/'originals'/f'EN001.{extension}').read_bytes(),original)
                    with wave.open(str(folder/'audio/EN001.wav'),'rb') as wav:
                        self.assertEqual((wav.getframerate(),wav.getnchannels(),wav.getsampwidth()),(16000,1,2))
                        self.assertGreater(wav.getnframes(),0)
                        self.assertAlmostEqual(metadata['duration_s'],wav.getnframes()/16000)
                    self.assertEqual(metadata['original_sha256'],hashlib.sha256(original).hexdigest())
                    self.assertEqual(metadata['audio_sha256'],hashlib.sha256((folder/'audio/EN001.wav').read_bytes()).hexdigest())
                    self.assertEqual(dataset['audio_preprocessing']['sample_rate'],16000)

    def test_same_id_with_two_audio_extensions_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'Trùng'):
                import_zip(make_zip({'EN001.mp3':b'a','EN001.wav':b'b','EN001.txt':'hello'}),Path(directory),'duplicate','en')

    def test_invalid_compressed_audio_names_sample_and_leaves_no_import(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'EN001'):
                import_zip(make_zip({'EN001.mp3':b'not audio','EN001.txt':'hello'}),Path(directory),'broken','en')
            self.assertEqual(list(Path(directory).iterdir()),[])

if __name__=='__main__':
    unittest.main()
