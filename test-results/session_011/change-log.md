# LIVE transcript boundary and latency changes ? 2026-10-03

## Problem & evidence

Session 011 contains repeated boundary phrases (Well, other one, will be yours, mutual friend) with adjacent segment overlap of 0.56?0.65 s. The worker retains 0.75 s of audio on forced splits but only checks whole-segment end timestamps when publishing, allowing repeated words in a boundary-crossing segment. The user also reports text appearing slowly after pauses; current LIVE endpoint waiting is 1 s and maximum buffering 12 s.

## Purpose and changes

All paths are relative to the authoritative `AI Course/VANGIA_PROJECT/facial-cue-prototype` checkout.

- `src/transcription.py::LocalEnglishTranscriber._deduplicate_overlap`: before grouping words into output segments, compares previously decoded suffix words with new prefix words for the same audio source, only when chunks overlap. Matching ignores punctuation/case and requires word midpoint alignment within 0.35 s and overlap-time eligibility. Removes the longest matching prefix; retains original timestamps of remaining words. History is bounded to 64 words per source. It applies only to LIVE; FINAL is unchanged by this deduplication path. Missing word timestamps cause conservative pass-through and history reset. This addresses matching boundary repetition, not every possible decoder rewrite or hallucination.
- `speech_has_ended`: accepts a separate pause parameter. Default and word-grouping pause remain 1 s. `LIVE_ENDPOINT_PAUSE_S=0.6` triggers LIVE endpoint checking earlier; endpoint checks still occur every 0.1 s of new audio. VAD context is bounded to pause plus 1 s.
- `src/session_orchestrator.py`: uses a partially bound 0.6 s LIVE endpoint and `LIVE_MAX_WINDOW_S=6.0` instead of 12 s; minimum window 1.2 s and overlap 0.75 s remain. Records endpoint and maximum-buffer values in new-session metadata.
- Restores the three previously agreed fixes absent from this checkout: explicit decoder settings (`temperature=0`, no previous-text conditioning, hallucination-silence threshold 1 s); segment quality filtering below -1 average log probability or above 2.4 compression ratio (including nonfinite values); and `src/frame_processing.py::prepare_capture_frame` used by the tracker for direct BGRA conversion with optional video BGR. These are targeted edits, not a wholesale copy of the other project. Quality filtering affects LIVE and FINAL. Options are recorded in transcriber configuration; rejected count is cumulative in memory.
- `tests/test_live_transcript_boundaries.py`: tests time-jittered repeated phrase removal, preservation of later real repetition, separate audio sources, FINAL isolation and independent endpoint pause. `tests/test_session_orchestrator.py` checks the new LIVE wiring.

## Reasoning and trade-offs

A shorter maximum buffer limits buffering during continuous speech, and shorter endpoint waiting reduces post-pause waiting. Decoding is still batched; neither change guarantees instantaneous text. More frequent decodes increase repeated context/CPU overhead and may shorten linguistic context. Beam size/model/threads remain unchanged. Audio recording and landmark rendering were not modified; their performance still needs to be checked under new decoding frequency.

Time-constrained suffix/prefix matching is safer than deleting every repeated word: legitimate repetition later in the audio should remain. Nevertheless, timestamp jitter beyond 0.35 s, changed tokenization/wording or partial-word recognition can escape matching. Very close legitimate repetition can be ambiguous. The regression tests establish specified cases, not universal deduplication correctness. The older whole-segment cutoff remains a fallback in the worker.

Quality heuristics can reject difficult but valid speech; lower latency and fewer repeated words must be evaluated together with omissions. FINAL retains its 30 s buffering and grouping behavior, but receives the restored shared decoder quality controls.

## Validation

- New tests were run before implementation: the repeated boundary phrase was retained and the optional endpoint parameter was absent. A synthetic endpoint fixture was corrected to account for the bounded VAD context; the jitter fixture explicitly uses 0.2 s midpoint drift, within the intended matching tolerance.
- Full suite on this checkout: **224 tests passed**. The three older regressions are resolved here, rather than citing tests from the other workspace.
- Real-model offline replay results are recorded below when complete. Offline replay does not reproduce UI scheduling or measure live speech-to-visible-text latency.

## Adjustment map

- Endpoint wait: `LIVE_ENDPOINT_PAUSE_S` (0.6 s), separate from `UTTERANCE_PAUSE_S` (1 s grouping/default).
- Continuous-speech buffer limit: `LIVE_MAX_WINDOW_S` (6 s).
- Dedup time tolerance: 0.35 s in `_deduplicate_overlap`; do not increase without testing real repeated speech.
- Keep recorded configuration and actual quality-filter values synchronized when adjusting.

## Manual retest

Session 012: same English passage, system audio and LIVE transcript on, video/microphone off. Report text delay, duplicated/omitted words, landmark responsiveness and audio/Stop. Compare actual output to the same reference; do not overwrite session 011.
