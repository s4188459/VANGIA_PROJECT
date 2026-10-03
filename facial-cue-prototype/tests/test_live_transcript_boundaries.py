import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
from src.transcription import LocalEnglishTranscriber, speech_has_ended
from src.audio_recorder import AudioChunk, AudioSource

class BoundaryTests(unittest.TestCase):
    def chunk(self, start, source=AudioSource.SYSTEM_AUDIO):
        return AudioChunk(source, 0, start, start+6, 16000, 1, np.zeros(96000,np.float32))

    def model(self, batches):
        batches=iter(batches)
        class Model:
            def transcribe(self, audio, **kwargs):
                return [NS(words=[NS(start=s,end=e,word=w) for s,e,w in next(batches)])],None
        return Model()

    def test_overlap_phrase_with_timestamp_jitter_removed_but_new_words_kept(self):
        t=LocalEnglishTranscriber('unused',model=self.model([
            [(5.1,5.4,' mutual'),(5.4,5.8,' friend')],
            [(0,.4,' Mutual'),(.4,.7,' friend,'),(.7,1.2,' introduced'),(1.2,1.6,' them.')]]))
        t.transcribe(self.chunk(0))
        rows=t.transcribe(self.chunk(5.25))
        self.assertEqual([r.text for r in rows],['introduced them.'])
        self.assertAlmostEqual(rows[0].start_s,5.95)

    def test_real_repetition_after_overlap_is_kept(self):
        t=LocalEnglishTranscriber('unused',model=self.model([
            [(5,5.3,' yes')],[(.4,.7,' yes'),(.8,1.1,' yes')]]))
        t.transcribe(self.chunk(0))
        self.assertEqual(t.transcribe(self.chunk(5.25))[0].text,'yes yes')

    def test_different_source_and_final_are_not_deduplicated(self):
        for phase in ('live','final'):
            t=LocalEnglishTranscriber('unused',phase=phase,model=self.model([
                [(5,5.8,' hello')],[(0,.5,' hello')]]))
            t.transcribe(self.chunk(0))
            source=AudioSource.MICROPHONE if phase=='live' else AudioSource.SYSTEM_AUDIO
            self.assertEqual(t.transcribe(self.chunk(5.25,source))[0].text,'hello')

    def test_live_endpoint_can_use_shorter_pause_without_changing_default(self):
        audio=np.zeros(32000,np.float32)
        with patch('faster_whisper.vad.get_speech_timestamps',side_effect=lambda audio, options: [{'start':0,'end':len(audio)-9600}]):
            self.assertTrue(speech_has_ended(audio,16000,pause_s=.6))
            self.assertFalse(speech_has_ended(audio,16000))

    def test_complete_duplicate_returns_no_empty_segment(self):
        t=LocalEnglishTranscriber('unused',model=self.model([
            [(5.3,5.8,' hello')],[(.1,.55,' hello')]]))
        t.transcribe(self.chunk(0))
        self.assertEqual(t.transcribe(self.chunk(5.25)),())

    def test_nonoverlapping_chunk_keeps_same_phrase(self):
        t=LocalEnglishTranscriber('unused',model=self.model([
            [(5.3,5.8,' hello')],[(0,.5,' hello')]]))
        t.transcribe(self.chunk(0))
        self.assertEqual(t.transcribe(self.chunk(6))[0].text,'hello')
