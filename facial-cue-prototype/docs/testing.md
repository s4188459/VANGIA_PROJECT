# Testing and Demonstration

## Current verification: 2026-10-06

After the LIVE boundary reconciliation and bounded endpoint IPC changes,
`python -B -m unittest discover -s tests` passed all **236 tests** in 10.896 s.
This includes the seven immediate-Stop tests. The earlier 2026-09-29 results
below are historical, not the current baseline.

The first full run found a timing-dependent Pause test failure. That test now
controls its clock and frame count rather than comparing a real sleep with
artificially increasing task timestamps; runtime Pause code was unchanged.

A real small.en replay of two previously transcribed session 014 windows
reproduced and then removed the boundary repetition while retaining new text.
Raw-file hashes stayed unchanged. This is not a WER evaluation or a live
hardware performance test. See
`../../test-results/live-transcript-improvement-2026-10-06/change-log.md`
and `replay-report.json` in that directory for commands, settings and limits.

## Recorded verification: 2026-09-29

The repository-preparation run used the existing Windows Python 3.12 environment:

| Check | Result |
| --- | --- |
| `python -m unittest discover -s tests` | 208 tests: 204 passed, 2 failures, 2 errors |
| `python -m pip check` | No broken requirements found |
| `python -m compileall -q src scripts tests` | Passed |
| Manual hardware checklist | Not performed during repository preparation |

The four outstanding tests are:

- `test_pause_drains_device_without_publishing_audio`: the paused capture worker
  waits without reading the stream; the test expects it to drain input while
  suppressing published audio.
- `test_bgra_conversion_preserves_pixels_and_skips_unused_video_copy`: the test
  imports `prepare_capture_frame`, which is absent from `src/frame_processing.py`.
- `test_decoder_uses_deterministic_single_pass_and_silence_guard`: the decoder
  call does not supply the expected `temperature` keyword.
- `test_uncertain_and_repetitive_segments_are_not_published_as_speech`: the
  decoder publishes uncertain/repetitive segments that the test expects filtered.

These are existing mismatches between code and tests, not a passing baseline.
Repository preparation changes documentation and Git packaging, not application
behavior. Earlier handbook statements about completed fixes must be read with
this current verification result in mind.

## Automated checks

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
```

The tests use fake frames/devices and do not activate the camera or microphone.
They verify software behavior, buffering, and timing, not recognition accuracy
for a particular speaker, accent, device, or lighting condition.

## Manual hardware checklist

Use yourself or a participant who has explicitly consented to the recording.

1. Run facial-only collection and confirm landmarks/FPS remain responsive.
2. Enable video and confirm the MP4 contains only the selected region and no app UI.
3. Record both audio sources and verify microphone/You on the left channel and
   loopback/Student on the right channel of `audio.wav`.
4. Speak English for ten seconds from each source and confirm delayed transcript
   entries appear beside the selected region.
5. Pause for five seconds, resume, and compare timestamps across outputs.
6. Disable one audio device and confirm remaining components continue.
7. Click **Generate Final Transcript** and compare final text with live text.
8. Confirm `session.json` ends with `closed` and inspect errors and drop reporting.

Do not claim hardware acceptance until these checks pass on the target computer.
For recognition evaluation, use the same consented English recording with a
written reference and compare live and final output. Record hardware, models,
settings, timing, and test conditions alongside any results.
