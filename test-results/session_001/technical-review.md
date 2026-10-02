# Technical Review — session_001

Review date: October 1, 2026. Run: October 1, 2026, 11:52:31–11:53:35 (UTC+07:00).

## Assessment

The recorded facial-processing pipeline completed successfully and produced readable feature data and video. This is a **face tracking + video recording** run, not the originally planned face-only baseline: session.json records video=true. Audio and transcription were disabled.

Basic collection and data-integrity checks passed. Performance is a measured baseline for this configuration, not a pass against an established latency target. The video has a one-pixel height discrepancy that remains unresolved. Landmark accuracy, action-label accuracy, and perceived overlay behavior are not established by these technical checks; see manual-review.md for the operator's observations.

## Actual Setup

| Item | Recorded value |
| --- | --- |
| Session status | closed |
| Session duration | 64.308 s |
| Selected region | 1158 × 641 px; left=1538, top=563 |
| Video | Enabled |
| System audio / microphone / transcript | Disabled / disabled / disabled |
| Python | 3.12.14 |
| MediaPipe / OpenCV contrib | 0.10.21 / 4.11.0.86 |
| MSS / NumPy | 10.2.0 / 1.26.4 |
| Installed faster-whisper / CTranslate2 / SciPy | 1.2.1 / 4.8.2 / 1.17.1; transcription was not used |
| CPU, RAM, exact input, run-time source commit | Not recorded in session metadata |

The prior CFG-001 documentation can provide context, but it is not proof that every parameter or source file was unchanged at capture time.

## Measured Performance

| Metric | Result |
| --- | --- |
| Feature rows | 1,243 |
| First / last frame timestamp | 0.095 / 64.173 s |
| Mean processing time, all rows | 50.779 ms |
| Processing p50 / p95, all rows | 51.615 / 63.422 ms |
| Maximum processing time | 75.700 ms |
| Processing FPS over recorded frame span | 19.383 |
| Mean / p95 frame gap | 51.593 / 65.000 ms |
| Maximum frame gap | 78.000 ms |
| Frame gaps above 100 ms | 0 of 1,242 intervals |
| First row in tracking mode | 2.106 s |
| Calibration rows | 43 |
| Post-calibration mean / p50 / p95 processing time | 50.934 / 51.782 / 63.695 ms |
| Post-calibration processing FPS | 19.318 |
| Face-visible rows: mean / p95 processing time | 52.629 / 64.156 ms |
| Face-missing rows: mean / p95 processing time | 35.472 / 47.771 ms |

Processing time measures the code interval from before screen capture through feature extraction. It includes synchronous video submission work when enabled, but excludes subsequent action processing, feature-file publication, and complete UI rendering. It is not speech latency or end-to-end visual latency.

The missing-face portion processes faster, so the overall mean understates the average cost while a face is detected. Keep the face-visible statistics when comparing later runs.

## Face Loss and Return

| Interval | Evidence |
| --- | --- |
| Main missing-face interval | 132 missing rows from 43.929 to 48.588 s; next visible row at 48.624 s |
| Observed main interval length | 4.695 s, from first missing row to next visible row |
| Brief missing result after return | One row at 48.695 s; visible again at 48.739 s |
| Second brief missing result after return | One row at 48.865 s; visible again at 48.910 s |

There were 1,109 visible rows and 134 missing rows: 89.220% of all processed rows contained a face result. This is availability, not detection accuracy; the intentional out-of-frame segment must not be treated as a failure. Outside the main missing interval, only two rows were missing (1,109/1,111 visible rows, approximately 99.82%). That filtered figure still has no independent ground-truth labels.

The main loss is consistent with the operator's report of leaving and re-entering the selected region. The two brief missing results occur immediately after return; the operator did not notice jitter or freezing. Exact physical re-entry time and UI display timestamps were not recorded, so reacquisition latency cannot be calculated in milliseconds.

The face_not_detected event spans 43.929–44.142 s: its 0.213 s duration reflects the missing-face confirmation interval in this recording, not the full period without a face. The face_detected_again event occurs at 48.624 s. CSV face_visible values were used for the complete interval analysis.

## Data and Video Integrity

| Check | Finding |
| --- | --- |
| CSV timestamp order | All 1,242 consecutive differences strictly positive |
| Frame indices | Contiguous, 0–1,242 |
| Stored frame_gap_ms | Matches timestamp differences within 0.001 ms tolerance |
| Session warnings / errors | Empty lists; none reported |
| Session drops / drop_details | Empty; no drops reported through these fields |
| capture_drop_count | Zero in every row; does not independently establish zero capture loss |
| Video decoding | All 1,285 declared frames decoded successfully |
| Video frame rate / duration | 20 FPS / 64.250 s |
| Video dimensions | 1158 × 640 px, versus the recorded region of 1158 × 641 px |
| Video writer | mp4v; no failure; 0 queue-dropped frames reported |
| Video resampling | 64 source frames skipped by fixed-rate resampling; 106 output fill/duplicate frames reported |
| CSV video mappings | 1,179 populated indices, all within decoded frame bounds |

The counters reconcile: 1,243 source frames − 64 resampled frames = 1,179 mapped source frames; 1,179 + 106 fill/duplicate frames = 1,285 output frames. The 64 skipped source frames are fixed-rate resampling, not video queue drops. Fill/duplicate frames include timeline filling and do not by themselves demonstrate a visible freeze.

The video is 0.058 s shorter than the full session duration, which also includes finalization; this difference alone is not evidence of lost recording time. Its one-pixel height difference is a confirmed output discrepancy. The encoding path is a possible explanation, but the cause and affected image edge were not verified in this review. Use an even-sized region in a subsequent controlled run if checking this separately.

Audio and transcript files are absent as expected. Transcript accuracy, LIVE lag, FINAL processing time, and audiovisual synchronization are N/A for this run.

## Interpretation and Next Test

- The frame stream is continuous at the measured scale: no observed inter-frame interval exceeded 78 ms. This supports processing continuity, but does not independently verify the UI never froze.
- Head-turn, blinking, jaw-opening, face-loss, and face-return events were recorded. Their presence verifies event output, not that every label is correct. No action ground truth was annotated.
- No comparison with an earlier run is possible: this is the first reviewed session.
- Retain this run as the baseline with video enabled. For the next comparison, repeat the same input, region, and procedure with video disabled and audio/transcript still disabled. This isolates video-recording overhead better than changing several options at once. Manual repetitions remain approximate unless the same prerecorded input is reused.

## Method and Evidence

All CSV rows were parsed; no frames or long gaps were removed from the whole-run statistics. No pause-like gap was observed, but an explicit operator pause log is unavailable. FPS = (number of rows − 1) / (last timestamp − first timestamp). Percentiles use NumPy's default linear interpolation. Post-calibration statistics start at the first tracking-mode row (2.106 s). This is a code-derived boundary, not an independently recorded start of the scripted exercise. Missing intervals run from the first missing row to the next visible row. All times are relative to the session clock, not an assumed stopwatch offset.

OpenCV decoded the entire video for readability and dimensions. The video was not manually watched or used to judge landmark accuracy. Current source files were inspected to interpret timing and resampling; the capture-time source commit is unknown. Raw inputs were preserved.

SHA-256 of reviewed inputs:

```text
features.csv  e17b7fee3bc380147524c5709c8a982b7221d5eb45bf52d81ba289166dab9006
session.json  eab9ea4c348c0a2c4f7cf7a7d3b73dbc43d9de7c92177d9a42012f0324284f26
video.mp4     ada9f342fa51539426dffe215efbe7e72a14f15f2396864a8e68c0173ffa031b
```
