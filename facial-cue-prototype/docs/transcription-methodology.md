# Transcription Methodology and Report Notes

Updated: 2026-10-06. Scope: local English transcription in the dataset collector.

## Terminology and scientific basis

An utterance is a stretch of speech bounded here by a sufficiently long pause.
It is not necessarily a grammatical sentence. A speaker can hesitate within a
sentence or speak several sentences without pausing. This prototype uses an
acoustic endpoint rule, not a linguistic sentence-boundary classifier.

Voice activity detection (VAD) estimates which audio regions contain speech.
Silero supports a configurable minimum silence duration before separating
speech regions. This supplies the mechanism, not a universal recommended
duration for lessons. [Silero source and parameter documentation](https://github.com/snakers4/silero-vad/blob/master/src/silero_vad/utils_vad.py)

Endpointing research describes a trade-off between cutting speech off too early
and waiting too long. This motivates measuring both segmentation errors and
delay. It does not establish 0.8-1.2 seconds as an optimal range for every
speaker, language or task. [Two-pass Endpoint Detection for Speech Recognition](https://arxiv.org/abs/2401.08916)

The current LIVE endpoint uses **0.6 seconds**; word-gap grouping and decoder
VAD retain the **1.0 second** default. These are engineering settings, not
scientifically proven optima. No pause is interpreted as evidence of confusion,
difficulty, or cognitive load.

## Implemented pipeline

1. Capture microphone and system audio as separate technical sources.
2. Retain packets in a bounded live queue while inference is busy. A missing
   packet index breaks continuity rather than joining speech across missing audio.
3. Resample inference audio to 16 kHz and apply peak-limited gain.
4. Use Silero VAD on the most recent `pause_s + 1.0` seconds (1.6 seconds
   for LIVE) to check for trailing non-speech. Trim this context before process
   transport as well as inside VAD. The complete buffer remains available for ASR.
5. Send the buffered utterance to local faster-whisper when the pause is long
   enough, or when the maximum buffer duration is reached.
6. Request word timestamps. Join words across decoder segments while their
   estimated inter-word gap is less than 1 second. Split at gaps of at least
   1 second, independently for each source and transcription call.
7. Reconcile LIVE overlap using word text and estimated audio times, then
   publish the same transcript records to the panel and JSONL writer.

The final pass transcribes the saved audio and uses the same word-grouping rule.
It may produce different text, timestamps or grouping because its context is
longer. Existing saved sessions are not rewritten automatically.

faster-whisper provides word timestamps and Silero VAD integration. Word times
are model estimates rather than exact manual alignments. [Official faster-whisper documentation](https://github.com/SYSTRAN/faster-whisper#word-level-timestamps)

## Parameters in this revision

| Parameter | Value | Reason and limitation |
| --- | --- | --- |
| LIVE endpoint pause | 0.6 s | Existing setting retained in this revision |
| Word grouping / decoder VAD pause | 1.0 s | Independent of the LIVE endpoint pause |
| Earliest live endpoint check | 1.2 s of buffered audio | Allows short replies without the previous 3 s minimum |
| Endpoint check interval | 0.1 s of additional audio | Reduces check scheduling delay; adds VAD work |
| Endpoint analysis context | Last 1.6 s for LIVE; 2 s at the helper default | 1 s speech history plus pause; bounded VAD and IPC work |
| VAD speech threshold | 0.35 | Existing project setting, not newly optimized |
| Endpoint VAD padding | 0 ms | Avoids counting added padding as speech |
| Forced live split | 12 s | Bounds context and waiting during continuous speech |
| Overlap at forced split | 0.75 s | Retains acoustic context at a forced boundary |
| Live model | small.en, base.en fallback | Existing locally installed model selection |
| Decoding | beam size 5, CPU INT8, 4 threads | Existing accuracy/performance settings |
| Queue | 4096 packets | About 43 s for two 48 kHz sources with 1024-sample packets |

Constants `UTTERANCE_PAUSE_S`, `LIVE_ENDPOINT_PAUSE_S`, `LIVE_MAX_WINDOW_S`
and `ENDPOINT_CHECK_S` are in `src/transcription.py`; the orchestrator configures
the LIVE worker. Changing `LIVE_ENDPOINT_PAUSE_S` does not change word-gap
grouping. No threshold control is exposed in the UI.

## Timestamp semantics

For each grouped row:

```text
start_s = audio_chunk_session_start + first_word_relative_start
end_s   = audio_chunk_session_start + last_word_relative_end
```

Example: speech spans session time 12.2-15.4 s and the speaker then pauses.
The row remains `[12.2, 15.4]`; waiting for silence does not extend its end time
to 16.4. A later utterance receives its own row. Both sources share the session
clock but can overlap in time if both speakers speak simultaneously.

Endpoint waiting time, inference duration, queue delay and UI scheduling all
contribute to when the row appears. A 1 s pause threshold is not a guarantee of
1 s display latency. VAD decisions are frame-based and approximate. The panel's
existing transcript lag is measured from the end of the inference audio buffer,
which may include trailing silence; it is not total latency from the last word.

If word timestamps are unavailable, the code preserves the decoder segment
and its timestamps. That fallback does not guarantee pause-based grouping.

## Limits to report

- Silence boundaries and word-gap estimates can disagree, especially with noise,
  hesitation, unrecognized words or timestamp alignment errors.
- A forced 12 s live split, Stop, a capture gap, or the end of a final audio
  interval can produce a boundary without a 1 s pause.
- Forced overlaps can still produce repeated words; `timed_suffix_prefix_v2`
  reconciles exact timed suffix/prefix matches and a narrowly guarded clipped
  boundary-word variant. It is not general fuzzy transcript correction.
- A bounded queue absorbs temporary delays. Sustained overload can still drop
  live audio; a larger queue does not make inference faster.
- A short reply can take longer than the threshold because of the initial
  1.2 s buffer minimum and processing time.
- These changes do not train Whisper or establish accuracy for a given accent.

## Boundary reconciliation and process payload: 2026-10-06

Session 014 replay reproduced a forced boundary with "gonna read your" followed
by "to read your line". The new window began inside the estimated interval of
"gonna". Version 2 permits that first clipped word to differ only when at least
two subsequent suffix/prefix words match exactly at the same estimated audio
time. The mismatched intervals must overlap, the new first word must begin
within 50 ms of the window start, and the existing 350 ms midpoint tolerance
still applies. Changed negations are preserved. Other ambiguous mismatches,
later repetitions, separate sources and final transcription are not reconciled
by this new rule. Estimated timestamps can still be wrong; this is a heuristic.

The process proxy now sends only the context that endpoint VAD already uses.
For 12 s of mono float32 audio at 48 kHz and pause 0.6 s, audio payload size
falls from 2,304,000 to 307,200 bytes (86.7% less). This is a payload reduction,
not a claim of equivalent overall speedup. Model, decoding, action thresholds,
window/overlap settings and Stop policy are unchanged.

See `../../test-results/live-transcript-improvement-2026-10-06/change-log.md`
and its replay report for verification and limitations. Raw recordings and
saved transcripts are preserved; only future LIVE output uses the new rule.

## Latency regression investigation: 2026-09-27

The initial 100 ms endpoint-check implementation repeatedly resampled and
analyzed the complete growing utterance. The revised implementation analyzes
only the last `UTTERANCE_PAUSE_S + 1.0` seconds for endpointing. This bounds
the repeated VAD work while preserving the full utterance for ASR and the
1 s pause threshold. It uses a fresh VAD evaluation of recent context, not a
stateful streaming VAD. Real speech boundary accuracy still requires validation.

Local microbenchmarks, using synthetic noise rather than participant recordings:

| Work | Before | After |
| --- | --- | --- |
| Endpoint check on a 12 s, 48 kHz buffer | 45.48 ms | 7.80 ms |
| Endpoint check on a 6 s buffer | 22.67 ms | 7.80 ms |
| Endpoint check on a 2 s buffer | 7.76 ms | 8.51 ms |
| Feature CSV row serialization | 2.599 ms | 0.079 ms |

VAD timings are means of 5 warmed calls on seeded Gaussian noise (seed 42,
standard deviation 0.01). CSV timing is the mean of 200 writes to an in-memory
StringIO with 52 blendshape values; it excludes physical disk latency. These
small samples demonstrate bounded work and removed repeated computation, not
a controlled statistical comparison or end-to-end meeting performance result.

The CSV serializer now caches its fixed field-name mapping. The tracker
publishes each completed landmark overlay before synchronous feature recording.
Recording can still delay capture of the next frame. Audio-only sessions no
longer copy each screen frame for an unused video callback. The Tk callback
queue yields after at most 32 callbacks or about 4 ms between callbacks, then
reschedules pending work so overlay redraws can run. A single slow callback
cannot be interrupted by this budget.

The installed CTranslate2 runtime reported zero available CUDA devices during
this check. Whisper remains CPU-based with the same model, beam size and word
timestamp extraction. Four inference threads do not reserve or isolate CPU
cores. This revision does not claim near-zero ASR latency.

For dataset synchronization use capture/session timestamps, not when results
appear on the UI. Face tracking should remain current; deliberately delaying
the face overlay to wait for transcription would make it misalign with the
meeting image. The 1 s pause requirement necessarily adds endpoint waiting
before finalized text, plus inference and scheduling delay. Benchmark both
modalities together on real consented input before claiming hardware acceptance.

## Evaluation plan for the report

Use the same consented recordings and manual reference transcript for all runs.
Annotate utterance boundaries independently from ASR output. Include short
answers, long explanations, mid-sentence hesitations and alternating speakers.
Keep the model and remaining settings fixed while testing 0.8, 1.0 and 1.2 s.

Report word error rate, premature splits, missed boundaries, timestamp error,
end-of-speech-to-display latency (median and 95th percentile), and live dropped
packets. Record machine, dependency versions and settings with each experiment.
Compare live and final output separately. No comparative speech benchmark has
been completed for this revision.

Automated tests cover threshold edges, grouping across decoder segments,
absolute timestamps, final/live parity of the grouping rule, short-utterance
configuration, queue continuity and forced-window limits. They do not measure
recognition quality or linguistic sentence detection.

## Suggested methodology paragraph

The prototype segments speech using a pause-based utterance endpoint heuristic.
A Silero VAD stage detects speech activity, with a 1.0 s non-speech interval
selected as the default endpoint criterion. This value is a project parameter
chosen to balance premature segmentation and response delay, rather than a
universal linguistic boundary. Local Whisper recognition supplies word timing
estimates, which are grouped using the same pause threshold and mapped to the
session clock. Segment timestamps exclude the endpoint waiting interval.
Long continuous live input is bounded by a 12 s inference window. Threshold
suitability and recognition accuracy require evaluation against manually
annotated lesson recordings.
