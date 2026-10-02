# Change Log — Audio Recording and Stop

Date: October 1, 2026.

Status: code changes implemented and automated checks performed; hardware acceptance pending. This record describes changes made after session_005. Its original recordings and metadata have not been modified.

## Why Changes Were Made

1. The operator confirmed that original video playback was very clean, but the recorded audio.wav was severely distorted despite intelligible speech.
2. The operator confirmed that clicking Stop caused the application to exit unexpectedly instead of returning to Ready.
3. Saved metadata remained status=recording, ended_at_local=null, duration_s=0, with an unfinished event journal, even though audio components were marked stopped.

Natural pauses in the source speech were confirmed. They are not treated as capture failures. The exact cause of the original audible distortion and native process exit is not yet proven; the changes address independently reproducible code-level timing and stream-lifecycle defects.

## What Changed

| File in facial-cue-prototype | Previous behavior | Updated behavior / purpose |
| --- | --- | --- |
| src/audio_recorder.py | Each packet position depended on wall-clock readings around a blocking read, allowing scheduling jitter to produce gaps or overlaps in the saved timeline. | Consecutive packet timestamps are derived from sample counts after an initial clock anchor. Pause/Resume re-anchors the timeline. |
| src/audio_recorder.py | Stop could stop/close the native stream while the capture thread was still reading it. | Stop signals cancellation and waits; the capture worker owns stream cleanup. A timeout is reported without forcibly closing an in-use stream. |
| src/audio_devices.py | The stream wrapper did not expose available input sample counts. | Exposes get_read_available so the worker can poll before reading and respond to Stop while the device is idle. |
| src/audio_recorder.py | Pause stopped draining device input; input overflow errors were suppressed. | Paused capture drains input without publishing packets. Overflow now reports an error and stops that worker. |
| src/session_orchestrator.py | Device format and packet-timing strategy were not stored. | Records selected device names, native sample rates/channel counts, and the sample-count timing strategy in session audio metadata. |
| src/main.py | No persistent startup-configured diagnostics for these failures. | Adds application.log for UI/worker exceptions and native-fault.log via faulthandler under facial-cue-prototype/logs. Diagnostic capture is best effort. |
| tests/test_audio_capture_regressions.py | No tests covering this jitter/Stop combination. | Adds synthetic PCM-to-WAV continuity, blocked-read shutdown ownership, and idle-stream Stop regression tests. |

The original WAV was not denoised or rewritten. Transcript models and recognition settings were not changed. Metadata finalization on actual hardware still needs confirmation; a native crash has not been reproduced in the test environment.

## Verification Results

| Check | Result |
| --- | --- |
| Audio-focused tests | 13 passed |
| Jitter and Stop regressions against original committed worker | Both failed as expected, demonstrating the old timing/lifecycle defects |
| Same regressions against modified worker | Passed |
| Full suite at verification | 211 tests: 208 passed, 1 failure, 2 errors |
| Remaining full-suite problems | Previously documented missing prepare_capture_frame, missing decoder temperature expectation, and uncertain/repetitive transcript filtering; outside this audio change |
| Python compilation | All source/script/test files compiled in memory successfully |
| compileall bytecode writing | Blocked by permissions on existing __pycache__ paths; replaced with in-memory compilation for syntax verification |
| git diff --check | No whitespace errors |
| session_005 raw input hashes | Confirmed unchanged after implementation |

Automated checks do not establish that the user's hardware recording now sounds clean or that the original crash is resolved. Initial audio alignment remains estimated from the first read; long-term device-clock drift and per-packet resampling are not solved here.

## Retest Procedure

1. Restart the application to load the changed code.
2. Use the same video, **Improve your Speaking and Conversational skills with me / English Speaking Practice**, from **0:00 to 1:33**.
3. Enable only Meeting audio; leave Video, Microphone, and Transcript off. Keep source volume/device/region as close to session_005 as possible and record differences.
4. Save a new session under test-results. If it is session_006, label it **Audio fix retest**, not the previously planned transcript test.
5. Click Stop and check that the app returns to Ready without exiting.
6. Listen to the saved WAV and report whether distortion remains.
7. Technical review must verify status=closed, a populated end timestamp, readable audio, and errors/intervals. If the app exits, retain the session and application/native-fault logs.

Acceptance remains pending until both the manual listening check and session-finalization check succeed. Resume transcript testing only after audio recording is usable.
