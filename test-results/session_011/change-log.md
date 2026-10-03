# LIVE transcript boundary and latency changes ? 2026-10-03

## Problem & evidence

Session 011 contains repeated boundary phrases (Well, other one, will be yours, mutual friend) with adjacent segment overlap of 0.56?0.65 s. The worker retains 0.75 s of audio on forced splits but only checks whole-segment end timestamps when publishing, allowing repeated words in a boundary-crossing segment. The user also reports text appearing slowly after pauses; current LIVE endpoint waiting is 1 s and maximum buffering 12 s.

## Purpose and changes

All paths are relative to the authoritative `AI Course/VANGIA_PROJECT/facial-cue-prototype` checkout.

- `src/transcription.py::LocalEnglishTranscriber._deduplicate_overlap`: before grouping words into output segments, compares previously decoded suffix words with new prefix words for the same audio source, only when chunks overlap. Matching ignores punctuation/case and requires word midpoint alignment within 0.35 s and overlap-time eligibility. Removes the longest matching prefix; retains original timestamps of remaining words. History is bounded to 64 words per source. It applies only to LIVE; FINAL is unchanged by this deduplication path. Missing word timestamps cause conservative pass-through and history reset. This addresses matching boundary repetition, not every possible decoder rewrite or hallucination.
- `speech_has_ended`: accepts a separate pause parameter. Default and word-grouping pause remain 1 s. `LIVE_ENDPOINT_PAUSE_S=0.6` triggers LIVE endpoint checking earlier; endpoint checks still occur every 0.1 s of new audio. VAD context is bounded to pause plus 1 s.
- `src/session_orchestrator.py`: uses a partially bound 0.6 s LIVE endpoint and `LIVE_MAX_WINDOW_S=12.0` (retained after rejecting shorter trials); minimum window 1.2 s and overlap 0.75 s remain. Records endpoint and maximum-buffer values in new-session metadata.
- Restores the three previously agreed fixes absent from this checkout: explicit decoder settings (`temperature=0`, no previous-text conditioning, hallucination-silence threshold 1 s); segment quality filtering below -1 average log probability or above 2.4 compression ratio (including nonfinite values); and `src/frame_processing.py::prepare_capture_frame` used by the tracker for direct BGRA conversion with optional video BGR. These are targeted edits, not a wholesale copy of the other project. Quality filtering affects LIVE and FINAL. Options are recorded in transcriber configuration; rejected count is cumulative in memory.
- `tests/test_live_transcript_boundaries.py`: tests time-jittered repeated phrase removal, preservation of later real repetition, separate audio sources, FINAL isolation and independent endpoint pause. `tests/test_session_orchestrator.py` checks the new LIVE wiring.

## Reasoning and trade-offs

Shorter endpoint waiting reduces post-pause buffering by up to about 0.4 s before decoding. The 12 s continuous-speech buffer is retained for context quality. Decoding is still batched; neither change guarantees instantaneous text. More frequent decodes increase repeated context/CPU overhead and may shorten linguistic context. Beam size/model/threads remain unchanged. Audio recording and landmark rendering were not modified; their performance still needs to be checked under new decoding frequency.

Time-constrained suffix/prefix matching is safer than deleting every repeated word: legitimate repetition later in the audio should remain. Nevertheless, timestamp jitter beyond 0.35 s, changed tokenization/wording or partial-word recognition can escape matching. Very close legitimate repetition can be ambiguous. The regression tests establish specified cases, not universal deduplication correctness. The older whole-segment cutoff remains a fallback in the worker.

Quality heuristics can reject difficult but valid speech; lower latency and fewer repeated words must be evaluated together with omissions. FINAL retains its 30 s buffering and grouping behavior, but receives the restored shared decoder quality controls.

## Validation

- New tests were run before implementation: the repeated boundary phrase was retained and the optional endpoint parameter was absent. A synthetic endpoint fixture was corrected to account for the bounded VAD context; the jitter fixture explicitly uses 0.2 s midpoint drift, within the intended matching tolerance.
- Final full suite on this checkout: **226 tests passed**. The three older regressions are resolved here, rather than citing tests from the other workspace.
- Real-model offline replay results are recorded below when complete. Offline replay does not reproduce UI scheduling or measure live speech-to-visible-text latency.

## Adjustment map

- Endpoint wait: `LIVE_ENDPOINT_PAUSE_S` (0.6 s), separate from `UTTERANCE_PAUSE_S` (1 s grouping/default).
- Continuous-speech buffer limit: `LIVE_MAX_WINDOW_S` (12 s; 6/8 s trials were not retained).
- Dedup time tolerance: 0.35 s in `_deduplicate_overlap`; do not increase without testing real repeated speech.
- Keep recorded configuration and actual quality-filter values synchronized when adjusting.

## Manual retest

Session 012: same English passage, system audio and LIVE transcript on, video/microphone off. Report text delay, duplicated/omitted words, landmark responsiveness and audio/Stop. Compare actual output to the same reference; do not overwrite session 011.


## Final real-model replay and selected configuration

The final selected configuration is **0.6 s endpoint pause, 12 s maximum window**, minimum 1.2 s and overlap 0.75 s. The 6 s and 8 s configurations mentioned during implementation were experiments and have been reverted. Both produced additional fragment/repetition errors in real-model replay.

Replayed the original WAV's right/system-audio channel through the actual small.en model and TranscriptionWorker, feeding 0.1 s audio packets as fast as possible, including Stop flush. This tests segmentation/decoder behavior offline, not real-time CPU contention or UI publication latency. No source files were overwritten. Source WAV interval timing versus capture packetization may differ from the original live run, so this is not a controlled isolation of each code change.

| Maximum window | Replay wall time (excluding model construction) | Decoder calls | Result |
| --- | ---: | ---: | --- |
| 6 s | 59.287 s | 18 | More fragment/recognition errors; rejected |
| 8 s | 52.143 s | 16 | Additional repeated boundary phrases; rejected |
| 12 s | 48.523 s | 13 | Best of these trials; retained |

All three offline runs reported no worker failure, dropped packets, or quality-filter rejections. These decoder call counts include silence/empty output and are not transcript segment counts. Runtime is batch replay runtime, not speech-to-text latency.

Final normalized WER: **11/198 = 5.56%**, versus **18/198 = 9.09%** for the original session transcript. Normalization lowercases, removes punctuation and retains internal apostrophes. It counts gonna/going-to and contractions as differences. All settings changed together, so this improvement cannot be assigned entirely to deduplication.

Remaining errors include `second line` instead of `second mine`, `lines in ... lines`, and repeated `and we know that`. The conservative matcher does not remove every rephrased or poorly aligned overlap. This is an improvement on the reference-based aggregate score, not a complete solution to recognition errors or duplicates. Increasing matching tolerance blindly could remove real repeated speech.

Final replay text (punctuation retained from output):

> Hey everybody, today we're making another video where we're gonna be practicing your speaking and conversational skills by having a conversation, you and me. Well, because you asked... for it and I'm very glad that you love this format. So let's go over what it's going to look like. I have prepared a dialogue. One line is for me and the other one is for you. You will see them on the screen. I'm going to say my line and you are going to read your... line out loud on the screen and that's going to be your response. And then vice versa. The first line will be yours and the second line. This exercise will give you already ready lines in... lines and answers to use in real life with other people and get you prepared to have conversations. In addition, you might pick up a phrase or two. And for this video, I thought it'd be useful to go through a dialogue of two people meeting each other for the first time, and let's say a mutual friend introduced them. I believe that we've all been in such a situation and we know that... and we know that it's a little bit

One full-suite run while real-model replay was consuming CPU failed the existing wall-clock-dependent `test_pause_produces_no_rows_and_resume_keeps_elapsed_gap` (25 ms observed versus 30 ms expected). It was not suppressed or altered. After replay finished, the final full suite passed all 226 tests. This indicates a timing-sensitive test under concurrent load; it is recorded rather than presented as uninterrupted passing verification.

No live text-publication timing series was added. The endpoint change reduces a configured wait, but actual end-to-visible-text improvement remains to be validated in session 012. Long continuous speech can still wait until the 12 s maximum window.
