import unittest
import threading
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np

from src.audio_recorder import AudioChunk, AudioSource
from src.transcription import LocalEnglishTranscriber, TranscriptionWorker, TranscriptSegment, speech_has_ended


class Segment:
    def __init__(self, start, end, text): self.start=start; self.end=end; self.text=text


class FakeModel:
    def transcribe(self, audio, **kwargs):
        self.audio = audio
        self.kwargs = kwargs
        return [Segment(.25, 1.5, " hello ")], object()


class TranscriptionTests(unittest.TestCase):
    def test_decoder_uses_deterministic_single_pass_and_silence_guard(self):
        model = FakeModel()
        transcriber = LocalEnglishTranscriber("unused", model=model)
        transcriber.transcribe(AudioChunk(AudioSource.MICROPHONE, 0, 0, 2, 16000, 1, np.ones(32000, np.float32)))
        self.assertEqual(model.kwargs["temperature"], 0.0)
        self.assertFalse(model.kwargs["condition_on_previous_text"])
        self.assertEqual(model.kwargs["hallucination_silence_threshold"], 1.0)
        self.assertEqual(model.kwargs["beam_size"], 5)

    def test_uncertain_and_repetitive_segments_are_not_published_as_speech(self):
        class Model:
            def transcribe(self, audio, **kwargs):
                return [
                    SimpleNamespace(start=0., end=.5, text="invented", avg_logprob=-1.5, compression_ratio=1., no_speech_prob=.1),
                    SimpleNamespace(start=.5, end=1., text="loop loop loop", avg_logprob=-.1, compression_ratio=4., no_speech_prob=.1),
                    SimpleNamespace(start=1., end=1.5, text="clear speech", avg_logprob=-.2, compression_ratio=1., no_speech_prob=.1),
                ], None
        transcriber = LocalEnglishTranscriber("unused", model=Model())
        rows = transcriber.transcribe(AudioChunk(AudioSource.MICROPHONE, 0, 0, 2, 16000, 1, np.ones(32000, np.float32)))
        self.assertEqual([r.text for r in rows], ["clear speech"])
        self.assertEqual(transcriber.rejected_segments, 2)

    def test_vad_failure_is_reported_and_disables_worker(self):
        reported = []
        failed = threading.Event()
        def broken(*_): raise RuntimeError("VAD failed")
        def report(value): reported.append(value); failed.set()
        worker = TranscriptionWorker(FakeModel(), lambda _: None, window_s=1., max_window_s=2.,
                                     speech_boundary=broken, error_callback=report)
        worker.start()
        worker.submit(AudioChunk(AudioSource.MICROPHONE, 0, 0., 1., 4, 1, np.ones(4, np.float32)))
        self.assertTrue(failed.wait(1))
        worker.stop()
        self.assertIn("VAD failed", reported[0]["message"])
        self.assertFalse(worker.submit(AudioChunk(AudioSource.MICROPHONE, 1, 1., 2., 4, 1, np.ones(4))))

    def test_decode_failure_reports_source_and_time_not_only_drop_count(self):
        class Broken:
            def transcribe(self, _): raise RuntimeError("model failed")
        reported = []
        worker = TranscriptionWorker(Broken(), lambda _: None, window_s=1., error_callback=reported.append)
        worker.start()
        worker.submit(AudioChunk(AudioSource.MICROPHONE, 0, 4., 5., 4, 1, np.ones(4, np.float32)))
        worker.stop()
        self.assertEqual(reported[0]["source"], "microphone")
        self.assertEqual(reported[0]["start_s"], 4.)
        self.assertIn("model failed", reported[0]["message"])

    def test_metrics_include_per_source_queue_duration_and_rtf(self):
        metrics = []
        class Decoder:
            def transcribe(self, _): return ()
        worker = TranscriptionWorker(Decoder(), lambda _: None, window_s=1., metrics_callback=metrics.append)
        worker.start()
        worker.submit(AudioChunk(AudioSource.SYSTEM_AUDIO, 0, 0., 1., 4, 1, np.ones(4, np.float32)))
        worker.stop()
        self.assertGreaterEqual(metrics[-1].rtf, 0.)
        self.assertEqual(metrics[-1].source, "system_audio")
        self.assertEqual(metrics[-1].queued_duration_s, {"microphone": 0., "system_audio": 0.})

    def test_speech_end_requires_one_second_after_last_speech(self):
        audio = np.zeros(32000, np.float32)
        with patch("faster_whisper.vad.get_speech_timestamps") as vad:
            for pause, expected in ((.6, False), (.8, False), (.999, False), (1.0, True), (1.2, True)):
                vad.return_value = [{"start": 0, "end": len(audio) - round(pause * 16000)}]
                self.assertEqual(speech_has_ended(audio, 16000), expected)
            vad.return_value = []
            self.assertTrue(speech_has_ended(audio, 16000))

    def test_endpoint_work_is_bounded_for_long_utterances(self):
        audio = np.zeros(12 * 48000, np.float32)
        with patch("faster_whisper.vad.get_speech_timestamps", return_value=[]) as vad:
            self.assertTrue(speech_has_ended(audio, 48000))
        self.assertEqual(len(vad.call_args.args[0]), 2 * 16000)
        self.assertEqual(len(audio), 12 * 48000)

    def test_pause_groups_words_across_decoder_segments_in_live_and_final(self):
        class WordModel:
            def transcribe(self, audio, **kwargs):
                self.options = kwargs
                return iter([
                    SimpleNamespace(words=[SimpleNamespace(start=.2, end=.5, word=" Yes,")]),
                    SimpleNamespace(words=[SimpleNamespace(start=1.3, end=1.6, word=" understood.")]),
                    SimpleNamespace(words=[SimpleNamespace(start=2.6, end=3., word=" Next.")]),
                ]), None

        for phase in ("live", "final"):
            model = WordModel()
            transcriber = LocalEnglishTranscriber("unused", model=model, phase=phase)
            chunk = AudioChunk(AudioSource.MICROPHONE, 0, 10, 15, 16000, 1, np.zeros(80000, np.float32))
            rows = transcriber.transcribe(chunk)
            self.assertEqual([r.text for r in rows], ["Yes, understood.", "Next."])
            self.assertEqual([(r.start_s, r.end_s) for r in rows], [(10.2, 11.6), (12.6, 13.)])
            self.assertTrue(model.options["word_timestamps"])
            self.assertEqual(model.options["vad_parameters"]["min_silence_duration_ms"], 1000)

    def test_timed_out_stop_prevents_late_transcript_writes(self):
        entered = threading.Event()
        release = threading.Event()
        published = []

        class SlowTranscriber:
            def transcribe(self, chunk):
                entered.set()
                release.wait(2)
                return (TranscriptSegment(1, 0, 1, AudioSource.MICROPHONE, "You", "late"),)

        worker = TranscriptionWorker(SlowTranscriber(), published.append, window_s=1)
        worker.start()
        try:
            worker.submit(AudioChunk(AudioSource.MICROPHONE, 0, 0, 1, 4, 1, np.ones(4, np.float32)))
            self.assertTrue(entered.wait(1))
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                worker.stop(grace_s=.01)
        finally:
            release.set()
            worker._thread.join(2)
        self.assertEqual(published, [])

    def test_two_audio_sources_survive_a_busy_decoder(self):
        entered = threading.Event()
        release = threading.Event()
        accepted = []

        class SlowTranscriber:
            def transcribe(self, chunk):
                accepted.append(chunk)
                entered.set()
                release.wait(3)
                return ()

        worker = TranscriptionWorker(SlowTranscriber(), lambda _: None, window_s=1)
        worker.start()
        try:
            worker.submit(AudioChunk(AudioSource.MICROPHONE, 0, 0, 1, 48000, 1,
                                     np.zeros(48000, np.float32)))
            self.assertTrue(entered.wait(2))
            # Three seconds of 1024-sample packets from both real capture sources.
            for index in range(140):
                for source in AudioSource:
                    start = 1 + index * 1024 / 48000
                    worker.submit(AudioChunk(source, index + 1, start, start + 1024 / 48000,
                                             48000, 1, np.zeros(1024, np.float32)))
            self.assertEqual(worker.dropped_chunks, 0)
        finally:
            release.set()
            worker.stop()

    def test_short_missing_packet_is_not_concatenated_as_contiguous_speech(self):
        accepted = []
        class Transcriber:
            def transcribe(self, chunk):
                accepted.append(chunk)
                return ()
        worker = TranscriptionWorker(Transcriber(), lambda _: None)
        worker.start()
        worker.submit(AudioChunk(AudioSource.MICROPHONE, 0, 0, .1, 100, 1, np.ones(10, np.float32)))
        worker.submit(AudioChunk(AudioSource.MICROPHONE, 2, .2, .3, 100, 1, np.ones(10, np.float32)))
        worker.stop()
        self.assertEqual([len(c.samples) for c in accepted], [10, 10])

    def test_speech_boundary_keeps_long_phrase_together(self):
        accepted = []
        class Transcriber:
            def transcribe(self, chunk):
                accepted.append(chunk)
                return ()
        worker = TranscriptionWorker(
            Transcriber(), lambda _: None, window_s=3, max_window_s=12,
            speech_boundary=lambda audio, rate: len(audio) >= 600,
        )
        worker.start()
        for index in range(6):
            worker.submit(AudioChunk(AudioSource.MICROPHONE, index, index, index + 1,
                                     100, 1, np.ones(100, np.float32)))
        worker.stop()
        self.assertEqual([len(c.samples) for c in accepted], [600])

    def test_continuous_speech_has_bounded_window(self):
        accepted = []
        class Transcriber:
            def transcribe(self, chunk):
                accepted.append(chunk)
                return ()
        worker = TranscriptionWorker(
            Transcriber(), lambda _: None, window_s=3, max_window_s=12,
            speech_boundary=lambda audio, rate: False,
        )
        worker.start()
        worker.submit(AudioChunk(AudioSource.MICROPHONE, 0, 0, 14, 100, 1, np.ones(1400, np.float32)))
        worker.stop()
        self.assertEqual(len(accepted[0].samples), 1200)
        self.assertAlmostEqual(accepted[-1].end_s, 14)

    def test_cpu_model_reserves_capacity_for_face_tracking(self):
        created = []

        def model_factory(*args, **kwargs):
            created.append((args, kwargs))
            return FakeModel()

        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            LocalEnglishTranscriber(Path(directory), model_factory=model_factory)

        self.assertEqual(created[0][1]["cpu_threads"], 4)
        self.assertEqual(created[0][1]["num_workers"], 1)

    def test_maps_chunk_time_and_source(self):
        model = FakeModel()
        transcriber = LocalEnglishTranscriber("unused", model=model)
        chunk = AudioChunk(AudioSource.SYSTEM_AUDIO, 0, 12.0, 16.0, 16000, 1, np.zeros(16000, np.float32))
        segment = transcriber.transcribe(chunk)[0]
        self.assertEqual((segment.start_s, segment.end_s, segment.speaker, segment.text), (12.25, 13.5, "Student", "hello"))
        self.assertEqual(model.kwargs["language"], "en")
        self.assertEqual(model.kwargs["beam_size"], 5)
        self.assertEqual(model.kwargs["vad_parameters"]["threshold"], 0.35)

    def test_native_48khz_audio_is_resampled_to_16khz(self):
        model = FakeModel()
        transcriber = LocalEnglishTranscriber("unused", model=model)
        chunk = AudioChunk(AudioSource.SYSTEM_AUDIO, 0, 0.0, 0.1, 48000, 1, np.ones(4800, np.float32))
        transcriber.transcribe(chunk)
        self.assertEqual(len(model.audio), 1600)

    def test_worker_aggregates_short_chunks_before_transcribing(self):
        accepted = []
        class FakeTranscriber:
            def transcribe(self, chunk):
                accepted.append(chunk)
                return ()
        worker = TranscriptionWorker(FakeTranscriber(), lambda segment: None, window_s=1.0)
        worker.start()
        worker.submit(AudioChunk(AudioSource.MICROPHONE, 0, 0.0, 0.5, 4, 1, np.ones(2, np.float32)))
        worker.submit(AudioChunk(AudioSource.MICROPHONE, 1, 0.5, 1.0, 4, 1, np.ones(2, np.float32)))
        worker.stop()
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(accepted[0].samples), 4)

    def test_worker_flushes_partial_window_on_stop(self):
        accepted = []
        class FakeTranscriber:
            def transcribe(self, chunk): accepted.append(chunk); return ()
        worker = TranscriptionWorker(FakeTranscriber(), lambda segment: None, window_s=4.0)
        worker.start()
        worker.submit(AudioChunk(AudioSource.MICROPHONE, 0, 2.0, 2.5, 4, 1, np.ones(2, np.float32)))
        worker.stop()
        self.assertEqual(len(accepted), 1)

    def test_worker_reuses_only_configured_overlap(self):
        accepted = []
        class FakeTranscriber:
            def transcribe(self, chunk): accepted.append(chunk); return ()
        worker = TranscriptionWorker(FakeTranscriber(), lambda segment: None, window_s=1.0, overlap_s=0.25)
        worker.start()
        worker.submit(AudioChunk(AudioSource.MICROPHONE, 0, 0.0, 1.0, 4, 1, np.arange(4, dtype=np.float32)))
        worker.submit(AudioChunk(AudioSource.MICROPHONE, 1, 1.0, 1.75, 4, 1, np.arange(3, dtype=np.float32)))
        worker.stop()
        self.assertEqual([len(chunk.samples) for chunk in accepted], [4, 4])
        self.assertEqual(accepted[1].start_s, 0.75)

    def test_full_queue_discards_oldest_chunk_and_accepts_newest(self):
        worker = TranscriptionWorker(FakeModel(), lambda segment: None, queue_size=2)
        worker._accepting = True
        chunks = [
            AudioChunk(AudioSource.MICROPHONE, index, float(index), float(index + 1),
                       1, 1, np.ones(1, np.float32))
            for index in range(3)
        ]

        self.assertTrue(worker.submit(chunks[0]))
        self.assertTrue(worker.submit(chunks[1]))
        self.assertTrue(worker.submit(chunks[2]))

        queued = [worker._queue.get_nowait(), worker._queue.get_nowait()]
        self.assertEqual([chunk.segment_index for chunk in queued], [1, 2])
        self.assertEqual(worker.dropped_chunks, 1)

    def test_metrics_report_post_inference_lag(self):
        metrics = []
        times = iter((4.0, 6.0))

        class FakeTranscriber:
            def transcribe(self, chunk):
                next(times)
                return ()

        worker = TranscriptionWorker(
            FakeTranscriber(), lambda segment: None,
            window_s=1.0,
            clock=lambda: next(times),
            metrics_callback=metrics.append,
        )
        worker.start()
        worker.submit(AudioChunk(
            AudioSource.MICROPHONE, 0, 2.0, 3.0, 1, 1,
            np.ones(1, np.float32),
        ))
        worker.stop()

        self.assertEqual(metrics[-1].lag_s, 3.0)
        self.assertEqual(metrics[-1].dropped_chunks, 0)


if __name__ == "__main__": unittest.main()
