# Session 012 cause investigation

Date: 2026-10-03. Investigation only; no application source changes.

## Confirmed Stop behavior

In src/transcription.py, TranscriptionWorker.stop appends a sentinel behind pending audio and joins the worker for 10 seconds. The worker processes pending packets serially, then flushes the partial buffer. If it is still alive, stop sets cancellation and raises the timeout error. Cancellation suppresses subsequent segment publication; it does not interrupt an already executing native Whisper inference call.

Session 012 records exactly this timeout. The recording interval ended at 84.077 s and the timeout error was logged at 94.100 s, consistent with the configured grace period. This proves failure to finish within the deadline, but not whether the thread was then in inference, endpoint detection or another worker operation; no historical stack was recorded.

SessionOrchestrator.stop records stats only when an operation returns successfully. Because worker.stop raises first, last_metrics is never persisted on this path. This is a confirmed diagnostic gap: the session cannot reveal historical decode RTF or remaining queue duration. Empty drops does not establish complete transcription; cancellation of pending work is not recorded as a per-interval drop here.

The controller performs Stop synchronously on the UI thread, which can make the interface wait during shutdown. However, worker UI callbacks use TkCallbackQueue / SimpleQueue, so inspection does not support the specific hypothesis of workers waiting for a direct cross-thread Tk after call.

## Offline replay of the actual WAV

Used current LocalEnglishTranscriber and TranscriptionWorker, the system-audio/right channel, 48 kHz PCM, 1024-sample packets matching the capture implementation, small.en CPU int8 / 4 threads / beam 5, endpoint 0.6 s, maximum window 12 s and overlap 0.75 s. Fed the complete recording without real-time pacing. Allowed 180 s for this diagnostic drain; production timeout was not changed. No UI, MediaPipe or live capture ran as part of this replay. Model initialization is excluded from elapsed time.

- WAV duration: 83.473 s.
- Total worker replay: 26.468 s.
- Endpoint checks: 658; cumulative 2.921 s (approximately 4.44 ms/check).
- Eight silence decodes plus eight decodes returning text; spoken-window decode durations: 2.802, 2.262, 3.270, 3.061, 3.443, 2.991, 2.863 and 2.029 s.
- Eight transcript segments returned; zero worker failures, dropped chunks or rejected model segments.
- The final two windows (70.067-82.067 and 81.317-83.473 s on the WAV timeline) also return text. A separate decode of these tail windows produced:

> And we know that it's a little bit unnerving and might be awkward and sometimes you might not know what to say, especially if you need to say this in English. So this dialogue might give you some ideas.

> Let's proceed. I'm saying

These are model outputs, not a human-verified reference. They provide evidence of additional speech beyond the saved LIVE JSON and the user's supplied reference. The earlier 6.25% WER therefore describes only the supplied excerpt and must not be used as a whole-recording completeness score. WAV-relative replay timestamps have a different origin from session-relative timestamps.

Replay demonstrates that this audio and current model can finish independently under the current conditions. It does not reproduce the original concurrent workload or establish its CPU utilization. Endpoint overhead is measurable but was not the dominant replay cost.

## Frame-stage evidence

Means in milliseconds, computed directly from matching stage timestamps:

| Stage | Session 011 | Session 012 |
|---|---:|---:|
| Screen capture | 24.31 | 38.56 |
| BGRA conversion | 1.74 | 3.38 |
| MediaPipe inference | 19.17 | 45.58 |
| Feature extraction after inference | 1.19 | 2.93 |
| Published frame waiting for UI consumption | 20.02 | 37.26 |
| Overlay bitmap generation | 13.84 | 36.22 |
| Tk image creation/update | 22.54 | 55.84 |

UI-stage means include only rendered frames. Acquisition/processing means include all recorded frames; do not sum the two populations to reconstruct total latency. MediaPipe slowdown is present throughout 012, including the early capture interval, not just at Stop.

The slowdown affects detection and rendering. Capture-to-features is 47.72 -> 93.72 ms; features_end_s is marked BEFORE detector.update. Capture-to-overlay_callback (after action update and overlay preparation) is approximately 48.25 -> 94.90 ms. Neither measures real gesture onset or temporal smoothing/persistence delay. Rendered capture-to-render is 105.29 -> 224.54 ms; this ends at Tk call return, not physical presentation.

Current rendering still creates a full-size background and PhotoImage each frame; the UI schedules another draw 16 ms after drawing finishes. These are confirmed ongoing costs, but their presence alone does not explain the difference between runs. Capture regions differ by only about 0.45% in pixel count.

## Findings and remaining uncertainty

Confirmed: the 10-second shutdown budget was exceeded; cancellation prevents saving subsequent results; error-path transcription metrics are lost; the WAV contains model-decodable tail content absent from LIVE JSON; both inference and rendering were slower.

Leading hypothesis: reduced available compute / competing workload during session 012 caused slower frame stages and delayed transcription, leaving work past the shutdown deadline. Not proven: exact CPU contention source, thermal/power state, background processes, or whether a particular decode stalled. Session 012 has no recorded evidence to distinguish these. Current offline replay cannot retrospectively prove the trigger.

Next diagnostic change should persist per-decode duration, endpoint cost, queue duration, current worker phase and unprocessed audio intervals on both normal and timeout exits. Measure a controlled concurrent workload before choosing thread/resource changes. Preserve bounded Stop and report unfinished work explicitly rather than merely extending its timeout.

Validation: all 21 existing tests in tests.test_transcription passed, including timeout suppression and partial-window flush coverage. No application source, raw session data or model settings were modified.
