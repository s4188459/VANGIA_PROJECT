# Session 013 review

Date: 2026-10-06. Review only; no application changes.

Session closed successfully, with no recorded errors, warnings or drops. Duration: 48.9489485 seconds. System audio enabled; microphone, video and LIVE transcription disabled. There is no transcript.jsonl, as expected with transcript=false. This run cannot validate Whisper process cancellation, transcript Stop behavior, transcript repetition, or simultaneous transcription/frame-processing performance.

The WAV opens as 48 kHz, stereo, 16-bit PCM with 2,347,770 frames (48.911875 s), matching the manifest frame count. This is structural validation, not a subjective listening test or proof that no input samples were lost.

Timing records: 1,081; rendered 927, replaced 153, stopped 1; no omitted or invalid-order records. Final feature timestamp: 48.892 s, before the frozen session Stop boundary.

| Metric | Session 012 (transcript ON) | Session 013 (transcript OFF) |
|---|---:|---:|
| Feature FPS | 10.43 | 22.29 |
| Capture-to-post-action callback mean / p95 ms | 94.90 / 123.86 | 44.14 / 52.99 |
| Capture-to-render mean / p95 ms | 224.54 / 306.96 | 93.98 / 116.17 |

FPS = (feature row count - 1) / feature timestamp span. Post-action latency = overlay_callback_s - capture_start_s, for rows with that marker. Render latency = render_end_s - capture_start_s for rendered frames. Values converted to milliseconds; p95 uses linear interpolation. Post-action timing measures computation, not real gesture-onset delay (smoothing/persistence remains separate). Render timing ends at Tk call return, not physical display presentation.

Performance is better in 013, but transcription configuration and capture region differ, so this is not a controlled proof that the recent implementation improved concurrent performance. UI responsiveness and absence of visible updates after Stop require manual observations; neither is established solely by closed status.

Remaining targeted test: system audio + LIVE transcription enabled, microphone/video recording disabled, 45-60 seconds, then Stop during speech. Inspect process execution metadata, cancellation statistics, saved transcript and manual Stop responsiveness. Untranscribed tail audio is expected under cancel-without-flush policy, not automatically an error.

## Raw SHA-256

- audio.wav: 3e45a7906f53e5f5145badf9b37cfc4def56a1b6d56d1d7dcc7a71cb9fdc2c72
- features.csv: 005df58113825d5ee794640a357f4bfc30c8d3680a14f91f316f8d9016e44951
- landmark-timing.csv: 3269846dc25f50e27275b9799b54976c19eff2d9bbc50fa08e14bbaee03eb9ad
- session.json: 2edaf16b52e8287b2b0a1472bfe26c311e95b15b99f691eb2089b13ebbfe99c9
