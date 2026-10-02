# Technical Review — session_002

Review date: October 1, 2026. Session started at 12:03:00 (UTC+07:00).

## Assessment

The session completed with readable feature data and video, increasing timestamps, and no reported errors. Processing continuity is consistent with the operator's report that the run felt as stable as session_001. This supports basic operation across two short sessions, not a general reliability or accuracy guarantee.

Both runs enabled video and disabled system audio, microphone, and transcription. The selected region changed from 1158 × 641 to 1146 × 649 pixels, including a position change. These are approximate repeat runs rather than an exactly controlled repeat. The lower mean processing time in session_002 is an observed difference, not evidence of a software improvement or its cause.

## Actual Configuration

| Item | Value |
| --- | --- |
| Status | closed |
| Duration | 62.403 s |
| Selected region | 1146 × 649 px; left=1542, top=559 |
| Video recording | Enabled, mp4v, 20 output FPS |
| System audio / microphone / transcript | Disabled / disabled / disabled |
| Python | 3.12.14 |
| MediaPipe / OpenCV contrib / MSS | 0.10.21 / 4.11.0.86 / 10.2.0 |
| NumPy / SciPy | 1.26.4 / 1.17.1 |
| Installed faster-whisper / CTranslate2 | 1.2.1 / 4.8.2; transcription was not used |
| Runtime versions versus session_001 | All versions recorded in session.json match |
| CPU, RAM, input identity, source commit | Not recorded in session metadata |

## Comparison with session_001

| Metric | session_001 | session_002 |
| --- | --- | --- |
| Session duration (s) | 64.308 | 62.403 |
| Feature rows | 1,243 | 1,322 |
| Mean processing time (ms) | 50.779 | 46.253 |
| Processing p50 (ms) | 51.615 | 45.238 |
| Processing p95 (ms) | 63.422 | 60.130 |
| Maximum processing time (ms) | 75.700 | 81.254 |
| Processing FPS over frame span | 19.383 | 21.250 |
| Mean frame gap (ms) | 51.593 | 47.060 |
| Frame-gap p95 (ms) | 65.000 | 62.000 |
| Maximum frame gap (ms) | 78.000 | 85.000 |
| Frame gaps above 100 ms | 0 | 0 |
| First tracking-mode timestamp (s) | 2.106 | 2.098 |
| Face-visible rows: mean processing time (ms) | 52.629 | 47.264 |
| Face-visible rows: processing p95 (ms) | 64.156 | 60.896 |

Mean and p95 processing time were lower in session_002, while the maximum was slightly higher. Both streams had no measured interval above 100 ms. These checks concern the recorded processing stream, not directly the UI render cadence. No numerical performance acceptance target was set.

Post-calibration statistics for session_002: 1,273 rows starting at 2.098 s; processing mean 46.458 ms, p50 45.443 ms, p95 60.710 ms; processing rate 21.145 FPS. The preceding 49 rows were calibration rows. Processing measurements cover screen capture through feature extraction, including synchronous video submission work, but not all subsequent action processing, file publication, or UI rendering. They are not end-to-end visual latency.

## Face Availability

There were 1,189 visible rows and 133 missing rows (89.939% visible). This is result availability, not accuracy, and includes the planned out-of-frame exercise.

| Missing interval | Rows | Next visible timestamp | Observed interval length |
| --- | --- | --- | --- |
| 47.661–47.725 s | 2 | 47.791 s | 0.130 s |
| 47.855–52.695 s | 131 | 52.732 s | 4.877 s |

The long interval is consistent with the planned departure from the frame, with a short detection interruption immediately beforehand. Exact physical departure/return timestamps were not provided, so these intervals cannot establish false-negative rates or reacquisition latency. No further missing rows occurred after 52.732 s. Exercise timestamps differ from session_001, which also limits direct phase-by-phase comparison.

## Integrity and Output Checks

| Check | Result |
| --- | --- |
| CSV timestamps | Strictly increasing from 0.087 to 62.253 s |
| Frame indices | Contiguous, 0–1,321 |
| frame_gap_ms | Matches all timestamp differences within 0.001 ms tolerance |
| Warnings / errors | Empty lists; none reported |
| Drops | Empty session drops object; no video queue drops reported |
| capture_drop_count | Zero in every row; not independent proof of zero capture loss |
| Video readability | All 1,246 declared frames decoded successfully |
| Video duration | 62.300 s at 20 FPS |
| Video dimensions | 1146 × 648 px, one pixel shorter than the selected region |
| Video writer failure | None reported |
| Video source frames skipped by fixed-rate resampling | 137 |
| Video fill/duplicate output frames | 61 |
| CSV video mappings | 1,185 populated indices; all within decoded frame bounds |

Video counters reconcile: 1,322 − 137 = 1,185 mapped source frames; 1,185 + 61 = 1,246 output frames. Fixed-rate resampling skips are distinct from queue drops. Fill/duplicate frames do not alone prove a visible freeze. The 20 FPS output setting must not be substituted for processing FPS.

The one-pixel video-height discrepancy recurs in both runs, each with an odd selected height. That pattern is consistent with an encoding-related size constraint, but the cause and affected image edge have not been verified. This remains an output issue to investigate, rather than a confirmed fix or diagnosis. The video duration is 0.103 s shorter than session duration, which includes finalization; this alone does not demonstrate data loss.

Audio and transcript outputs and their quality/latency metrics are N/A because those features were disabled.

## Next Run

Proceed to session_003 with video disabled and all audio/transcript options still disabled. Keep the current selection at 1146 × 649 pixels, its position, input, and procedure unchanged where possible. Retaining the selection avoids adding another region-size change to the video-on/off comparison. Use the same setup for session_004. The one-pixel encoding discrepancy can be tested separately later using an even-sized region.

No immediate performance change is justified by these two short runs alone. Basic data checks passed; action-label correctness and numerical landmark accuracy remain unassessed. The operator's qualitative feedback is recorded separately.

## Method and Evidence

Both sessions were recomputed from all CSV rows. FPS = (row count − 1) / (last timestamp − first timestamp). Percentiles use NumPy's default linear interpolation. The whole-run calculation includes calibration and missing-face rows. No intervals were removed; no pause-like gap was observed, but an explicit operator pause log is unavailable. Post-calibration calculations begin at the first tracking-mode row, not an assumed exercise stopwatch start.

Missing intervals run from the first missing row to the next visible row. Frame timestamps are session-relative. OpenCV decoded each complete video to check readability and dimensions; the video was not manually watched to assess visual correctness. Raw inputs were preserved. Run-time source commits, hardware load, and exact motion/input equivalence are unknown.

SHA-256 of reviewed session_002 inputs:

```text
features.csv  4d7c64fda4b9c46ce3ad308722d9c4d1627eced17ea40564aba6be7f47970226
session.json  b0d0076ab6ebfbdbf383f638326ea6c68e23757eaed83bcfd7188dcd660f3dbd
video.mp4     1434d1d3f37a1b6ccff7f6b46fccb95c8b7cade8b5b8d78260e3f52bb6eb3666
```
