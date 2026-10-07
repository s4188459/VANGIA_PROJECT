import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
from src.transcription import LocalEnglishTranscriber, speech_has_ended
from src.audio_recorder import AudioChunk, AudioSource
from src.live_inference_process import ProcessEnglishTranscriber

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

    def test_clipped_boundary_word_with_two_timed_anchors_is_removed(self):
        # Word offsets reproduced by replaying session 014's adjacent windows.
        t=LocalEnglishTranscriber('unused',model=self.model([
            [(11.24,11.36,' gonna'),(11.36,11.60,' read'),(11.60,11.88,' your.')],
            [(0,.14,' to'),(.14,.34,' read'),(.34,.62,' your'),(.62,1.02,' line')]]))
        first=self.chunk(0)
        first=AudioChunk(first.source,0,0,12,16000,1,np.zeros(192000,np.float32))
        t.transcribe(first)
        rows=t.transcribe(self.chunk(11.25))
        self.assertEqual([r.text for r in rows],['line'])
        self.assertAlmostEqual(rows[0].start_s,11.87)

    def test_uncertain_boundary_edits_are_preserved(self):
        cases = [
            # The differing word is not cut by the new window.
            ([(5.3,5.4,' gonna'),(5.4,5.6,' read'),(5.6,5.9,' your')],
             [(0,.14,' to'),(.14,.34,' read'),(.34,.62,' your')]),
            # One anchor is insufficient.
            ([(5.2,5.4,' gonna'),(5.4,5.8,' read')],
             [(0,.14,' to'),(.14,.54,' read')]),
            # A later repetition is not the same audio.
            ([(5.2,5.4,' gonna'),(5.4,5.6,' read'),(5.6,5.9,' your')],
             [(1,1.14,' to'),(1.14,1.34,' read'),(1.34,1.62,' your')]),
            # Do not silently erase a changed negation.
            ([(5.2,5.4,' gonna'),(5.4,5.6,' read'),(5.6,5.9,' your')],
             [(0,.14,' not'),(.14,.34,' read'),(.34,.62,' your')]),
            ([(5.2,5.4," can't"),(5.4,5.6,' read'),(5.6,5.9,' your')],
             [(0,.14,' to'),(.14,.34,' read'),(.34,.62,' your')]),
        ]
        for previous,current in cases:
            with self.subTest(current=current,previous=previous):
                t=LocalEnglishTranscriber('unused',model=self.model([previous,current]))
                t.transcribe(self.chunk(0))
                self.assertEqual(t.transcribe(self.chunk(5.25))[0].text,
                                 ''.join(w[2] for w in current).strip())

    def test_process_endpoint_preserves_vad_input_with_bounded_payload(self):
        proxy=object.__new__(ProcessEnglishTranscriber)
        for rate in (16000,48000):
            for duration in (.5,12):
                for pause in (.6,1.):
                    with self.subTest(rate=rate,duration=duration,pause=pause):
                        samples=np.linspace(-.1,.1,round(rate*duration),dtype=np.float32)
                        captured=[]
                        def request(operation,payload):
                            self.assertEqual(operation,'boundary')
                            audio,sample_rate,pause_s=payload
                            captured.append(audio)
                            return speech_has_ended(audio,sample_rate,pause_s=pause_s)
                        proxy._request=request
                        seen=[]
                        def vad(audio,options):
                            seen.append(audio.copy())
                            return []
                        with patch('faster_whisper.vad.get_speech_timestamps',side_effect=vad):
                            direct=speech_has_ended(samples,rate,pause_s=pause)
                            remote=proxy.speech_boundary(samples,rate,pause_s=pause)
                        self.assertEqual(direct,remote)
                        np.testing.assert_array_equal(seen[0],seen[1])
                        self.assertLessEqual(len(captured[0]),round(rate*(pause+1)))
