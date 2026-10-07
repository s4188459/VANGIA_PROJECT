# LIVE transcript improvement change log

## 2026-10-06 - Boundary repetition and bounded endpoint transport

### Problem and evidence

Session 014's third LIVE segment ends with "you are gonna read your"; its fourth
starts with "to read your line". Before changing the code, an offline small.en
replay of windows [17.361913333333035, 29.361913333333035] and
[28.611913333333035, 40.611913333333035] reproduced both saved texts.

The replay placed "gonna" at 28.6019133-28.7219133 s and the next window's
"to" at 28.6119133-28.7519133 s. Subsequent "read your" word times matched
closely. The exact-only suffix/prefix matcher could not reconcile the clipped
first word. These are model-estimated word times, not manual alignments.

Source inspection also showed endpoint RPCs serializing the full growing audio
buffer even though the child VAD immediately kept only `pause_s + 1.0` seconds.

### Changes

- `src/transcription.py`: upgraded metadata to `timed_suffix_prefix_v2`.
  Existing exact timed suffix/prefix matching remains. A first-word mismatch
  can be removed only if the preceding estimate straddles the new window start,
  the new word begins within 50 ms of that start, their intervals overlap,
  and at least two following words match exactly at the same estimated times.
  The existing 350 ms midpoint tolerance still applies. Changed negations are
  preserved. Later repetitions, insufficient anchors and other ambiguous edits
  remain intact. No general fuzzy text rewriting was added.
- `src/transcription.py`, `src/live_inference_process.py`: share
  `endpoint_audio_context()` and trim before endpoint IPC. The child's VAD
  receives the same context as before; Whisper still receives full decode windows.
- `tests/test_live_transcript_boundaries.py`: added three tests, including
  subcases for timestamp/negation safety and identical VAD input with bounded
  payload at 16/48 kHz, 0.5/12 s buffers and 0.6/1.0 s pause settings.
- `tests/test_meeting_tracker.py`: made an existing Pause test deterministic
  using a controlled clock and bounded frame count, with cleanup in `finally`.
  The first full-suite run failed its old real-time gap assertion (28 ms versus
  a 30 ms minimum). Fast fake frames can push strictly increasing task timestamps
  ahead of wall time; the revised test checks an exact 5 s elapsed gap and no
  rows/captures while paused. Runtime Pause behavior was not modified.
- Added `scripts/probe_session_014_boundaries.py` for reproducible offline replay
  and a serialization microbenchmark. It refuses output inside session 014 or
  overwriting an existing report. It does not decode the unprocessed tail,
  launch the app, activate capture devices or generate a final transcript.
- Updated `docs/transcription-methodology.md` and `docs/testing.md` to describe
  current behavior and distinguish current checks from historical results.

### Verification

All Python commands used the existing interpreter at
`D:\@_Binh's document\VANGIAPROJECT\facial-cue-prototype\.venv\Scripts\python.exe`
with working directory
`D:\@_Binh's document\AI Course\VANGIA_PROJECT\facial-cue-prototype`.
Only the interpreter was reused; no files in the other project were synchronized.

| Check | Result |
|---|---|
| `python -B -m unittest tests.test_live_transcript_boundaries tests.test_transcription tests.test_immediate_stop -v` | 37 passed, 10.886 s |
| Initial `python -B -m unittest discover -s tests` | 236 run; one pre-existing timing-dependent Pause test failed, as described above |
| Final `python -B -m unittest discover -s tests` | 236 passed, 10.896 s |
| Real small.en boundary replay after the fix | Segment 3 unchanged; segment 4 starts with "line out loud...", removing only "to read your " |
| Raw artifact integrity | SHA-256 of all five session 014 raw files unchanged |
| `git diff --check` | Passed |

Replay command:

```powershell
python -B scripts\probe_session_014_boundaries.py --output ..\test-results\live-transcript-improvement-2026-10-06\replay-report.json
```

Use a new output filename when repeating; the saved report is intentionally
protected from overwrite. Detailed configuration, replay outputs, hashes and
benchmark results are in `replay-report.json`.

For a 12 s mono float32 buffer at 48 kHz, endpoint audio payload decreased from
2,304,000 to 307,200 bytes (86.7%); serialized messages measured 2,304,189 and
307,389 bytes. After 10 warmups, 200 serialization iterations measured:

| Serialization only | Mean | p95 |
|---|---:|---:|
| Full buffer | 1.9839 ms | 2.4518 ms |
| Bounded context | 0.0427 ms | 0.0655 ms |

These are indicative local microbenchmarks; automated tests were also running
during the probe. They exclude transport wait, VAD, model decoding, Tk rendering
and concurrent face tracking. Payload reduction is deterministic; timing gains
are not an end-to-end latency or FPS claim.

### Scope and remaining limitations

Model, CPU threads, beam size, endpoint pause, window length, overlap,
smoothing/action thresholds, architecture and cancel-without-flush Stop policy
were preserved. Previously saved transcripts and raw audio were not rewritten.
Dataset pilot files were not changed or expanded.

This fixes the reproduced session 014 boundary case; it does not establish that
all repetition is eliminated. Estimated word times and clipped-word matching
remain heuristic and can be wrong. No verified full reference is available, so
WER and overall transcription accuracy were not claimed. Long-session
concurrent hardware performance remains unmeasured in this pass. No duplicate
manual run was requested from the user.
