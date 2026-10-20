> HISTORICAL ONLY ? selection withdrawn on 2026-10-20. Recommendations and
> approvals below are obsolete. No replacement model is selected by this change.
> Measurements are retained as historical evidence; continue evaluation in Vangia ASR Lab.

# English experiments 2 and 3

The web shortcuts have been removed. The CLI/backend implementation is retained
only to reproduce historical experiments with fixed models. These models are not
approved selections. Use ASR Lab for new selection work.

## Experiment 2: Qwen real-time replay

Uses the desktop application's Qwen decoder and TranscriptionWorker scheduler:
CPU float32, four threads, English, minimum window 1.2 s, forced split at 12 s,
endpoint pause 0.6 s, zero overlap. Audio arrives in 100 ms packets paced by a
monotonic clock. Inference runs concurrently with the producer. This is chunked
recognition, not native token streaming. Model loading finishes before playback.
The first sample after each load is flagged; there is no separate warm-up.

At EOF the worker drains remaining audio so the complete hypothesis can be scored.
This intentionally differs from the desktop Stop button's cancel-without-flush
behavior. Transcript delivery is measured at the application callback, not at
browser rendering or microphone capture.

- WER uses the complete concatenated live hypothesis and the existing normalization.
- `first_text_s`: first nonempty callback relative to file start.
- `first_text_from_vad_s`: first callback relative to estimated speech onset.
- `finalization_from_eof_s`: worker completion minus audio duration.
- `finalization_from_vad_s`: completion minus estimated final speech end.
- VAD estimates use threshold 0.35; they are not manually verified gold timestamps.
- `lag_s`: decoder result time minus chunk end; not stable-word latency.
- `queue_wait_s`: decoder start minus chunk end, including scheduler overhead.
- `queue_log`: queue duration sampled after decodes; `max_queue_s` is the maximum
  observed at those points, not a continuously sampled maximum.
- `wall_s` includes paced replay and draining; `elapsed_s`/RTF use decoder calls
  only. Endpoint checks and waiting are not decoder compute time.
- No word-level latency is claimed. Errors/drops fail the sample rather than
  silently scoring incomplete coverage. WER summaries cover successful samples.

## Experiment 3: Whisper offline latency

Uses the app's final Whisper decoder, large-v3 CPU INT8, four threads, beam 5,
English, VAD and its existing output filters. A normalized audio file is available
before timing starts. Timing includes file read, waveform conversion, decoding,
and transcript assembly until the complete result is available in memory.
Scoring and report persistence occur afterwards and are excluded. This is not
video upload latency or UI rendering latency. Model loading is separate.
The first sample after each load is flagged; later samples reuse the loaded model.

## Reports and preservation

JSON includes configuration, timing boundaries, chunks, queue logs and load sessions.
CSV includes per-file measurements and median/p95/max summaries. Different audio
durations affect offline completion times; examine duration and RTF together.
Old runs remain unchanged. Each pilot/full run has a new ID. Resuming checks the
original dataset, backs up the report and skips saved samples. Cancelled experiment
runs become interrupted and may be resumed; timing sessions are recorded separately.

For an unattended sequence of both three-sample pilots followed by both full runs:

```powershell
..\facial-cue-prototype\.venv\Scripts\python.exe .\run-experiments.py --dataset DATASET_ID --full-after-pilot
```

Do not start another server/process while this sequence is running. A newly started
server can classify another process's active reports as interrupted. An already
running server may be used for read-only report inspection; do not launch competing
runs. Pilots check execution and measurement integrity, not statistical validity.
