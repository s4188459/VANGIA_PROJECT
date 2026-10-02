# Audio capture correction following session_005

Date: October 1, 2026.

The operator reported clean source playback but a severely distorted audio.wav, and application exit when pressing Stop. The saved session remained marked recording. Session_005 is preserved as evidence.

## Changes

- AudioCaptureWorker now timestamps consecutive PCM packets by sample count after an initial session-clock anchor. CPU scheduling variation no longer directly inserts gaps or overlapping packet positions. Pause/Resume re-anchors the timeline, and paused capture drains the device without publishing audio.
- The capture worker owns stream shutdown. Stop signals cancellation and joins; it no longer closes/terminates PortAudio concurrently with a blocking read. Native streams are polled for available samples before reading, so idle devices can stop without a blocking read. A timeout is reported instead of forcibly closing an in-use stream.
- Input overflow is reported rather than suppressed. An overflow ends that capture worker with an error rather than silently stitching uncertain data together.
- Session audio metadata records device names/native rates/channel counts and the packet-timing strategy.
- Application startup enables logs/application.log for UI/worker exceptions and logs/native-fault.log for native faults supported by Python faulthandler. Logs are best-effort diagnostics, not guaranteed to capture every process termination.

## Verification

Regression tests exercise scheduling jitter through the WAV writer, stream ownership during a blocked read, and Stop on an idle native-style stream. The jitter/Stop regressions fail against the original committed worker and pass with the corrected implementation. Existing audio pause/drain coverage now passes as well.

The full suite currently contains 211 tests: 208 pass, with three previously documented outstanding checks (missing prepare_capture_frame, decoder temperature expectation, uncertain/repetitive transcript filtering). These unrelated areas were not changed.

## Limits and Hardware Retest

The tests reproduce code-level defects, not the user's exact native crash. Actual clean audio and reliable Stop still require a hardware retest. Initial capture alignment is estimated from the first read; long-term device clock drift and per-packet resampling are not resolved by this change.

Restart the application so it loads the changed code. Repeat the same source video from 0:00 to 1:33 with only Meeting audio enabled. Keep microphone, video recording, and transcript disabled. Save as a new session in test-results; do not overwrite session_005. This is an audio-fix retest, not the planned transcript test even if its folder is session_006.

Check that audio is clean, Stop returns to Ready without closing the application, and session.json ends with status closed and a non-null end time. If it still closes, preserve the new session and both files under logs for diagnosis. Do not continue to transcript quality evaluation until the recording is usable.
