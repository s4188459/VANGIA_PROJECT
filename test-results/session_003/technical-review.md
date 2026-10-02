# Technical Review — session_003

Reviewed October 1, 2026. Run: 12:54:15–12:55:16 (UTC+07:00).

## Assessment

This face-only run completed with readable, temporally ordered feature data and no reported errors. The operator noticed no difference from the preceding experience. The measured performance difference from session_002 is small: processing FPS increased from 21.250 to 21.531, while mean processing time decreased from 46.253 to 45.683 ms. This single comparison does not establish the causal overhead of video recording or prove that its effect is zero.

Video was disabled as intended. The capture region, its position, and all recorded runtime versions match session_002. Unrecorded differences in input motion, background load, or source code cannot be ruled out. The out-of-frame interval also differs in duration.

## Recorded Setup

| Item | Value |
| --- | --- |
| Session status | closed |
| Duration | 61.693 s |
| Region | 1146 × 649 px; left=1542, top=559 |
| Video / system audio / microphone / transcript | All disabled |
| Python | 3.12.14 |
| MediaPipe / OpenCV contrib / MSS | 0.10.21 / 4.11.0.86 / 10.2.0 |
| NumPy / SciPy | 1.26.4 / 1.17.1 |
| Installed faster-whisper / CTranslate2 | 1.2.1 / 4.8.2; not used for transcription |
| Source commit, CPU, RAM, exact input identity | Not recorded in session metadata |

## Comparison

| Metric | session_002: video on | session_003: video off |
| --- | --- | --- |
| Duration (s) | 62.403 | 61.693 |
| Feature rows | 1,322 | 1,326 |
| Mean processing time (ms) | 46.253 | 45.683 |
| Processing p50 (ms) | 45.238 | 44.953 |
| Processing p95 (ms) | 60.130 | 58.108 |
| Maximum processing time (ms) | 81.254 | 78.443 |
| Processing FPS | 21.250 | 21.531 |
| Mean frame gap (ms) | 47.060 | 46.445 |
| Frame-gap p95 (ms) | 62.000 | 60.000 |
| Maximum frame gap (ms) | 85.000 | 78.000 |
| Frame gaps above 100 ms | 0 | 0 |
| Face-visible processing mean (ms) | 47.264 | 46.725 |
| Face-visible processing p95 (ms) | 60.896 | 58.876 |

The whole-run mean decreased by approximately 0.570 ms (1.23%), and FPS increased by approximately 0.281 (1.32%). These are descriptive differences, not statistically established improvements. Comparing face-visible rows also yields only a small mean difference, approximately 0.539 ms.

Calibration occupied 45 rows; the first tracking-mode row is at 2.109 s. The 1,281 post-calibration rows have mean processing time 45.725 ms, p50 45.005 ms, p95 58.274 ms, and processing FPS 21.499.

Processing time covers capture through feature extraction, not the complete interval to an overlay redraw. Processing FPS describes the recorded frame stream. Neither directly proves UI rendering smoothness; that assessment comes from the operator.

## Face Availability

1,182 of 1,326 rows contained a face result (89.140%). The 144 missing rows include the intended out-of-frame exercise, so this percentage is not detection accuracy.

| Missing interval | Rows | Next visible timestamp | Observed interval length |
| --- | --- | --- | --- |
| 46.897–52.194 s | 143 | 52.249 s | 5.352 s |
| 52.305 s | 1 | 52.362 s | 0.057 s |

The main interval is consistent with the planned departure. A single additional missing result occurred just after the first return detection. No later missing rows were recorded. Actual physical return time was not independently logged, so the 57 ms brief missing interval must not be presented as physical re-entry-to-detection latency.

## Integrity Checks

| Check | Result |
| --- | --- |
| CSV parsing | All 1,326 rows parsed |
| Frame indices | Contiguous, 0–1,325 |
| Timestamps | Strictly increasing, 0.108–61.648 s |
| frame_gap_ms | Matches every timestamp difference within 0.001 ms tolerance |
| Warnings / errors | Empty lists; none reported |
| Drops / media_stats | Empty objects, consistent with optional media being disabled |
| capture_drop_count | Zero throughout; not independent proof of zero capture loss |
| Video mappings | All blank, as expected with video disabled |
| Video, audio, transcript files | Absent as expected |

No recorded frame gap exceeded 78 ms. This supports continuity of processing over the recorded span, rather than a guarantee about all aspects of the application. No performance threshold was defined in advance. The previous video-height discrepancy cannot be retested in this run because no video was recorded.

## Conclusion and Next Run

Basic collection and data-integrity checks passed. The result is consistent with the operator noticing no change when video was disabled. It is premature to prioritize video recording as a major bottleneck based on this pair alone.

Run session_004 as a repeat of session_003: keep the same region and procedure, and leave video, audio, and transcription disabled. This provides the second face-only measurement before progressing to audio and transcription. Do not change source code or models between these baseline runs if avoidable. Action-label correctness and numerical landmark accuracy remain unassessed.

## Method and Evidence

All feature rows from sessions 002 and 003 were recomputed. FPS = (row count − 1) / (last timestamp − first timestamp). Percentiles use NumPy's default linear interpolation. Whole-run statistics include calibration and missing-face rows; post-calibration statistics begin at the first tracking-mode row. No intervals were excluded. No pause-like gap was observed, but explicit operator pause timestamps are unavailable. Missing intervals extend from the first missing row to the next visible row. Times refer to the session clock, not an assumed exercise stopwatch offset.

No video-based visual assessment was possible for this run. Raw inputs were preserved. Checks concern saved data, not a new live application run or a rerun of the unit-test suite.

SHA-256 of reviewed inputs:

```text
features.csv  5a17b78b56315447be71807d83084921bed4a8abb0893a50be7d5a042607f32f
session.json  4305e2b5a3c09969809d2e1e5d68e63a0bbc8209cf5eb046436da987ad33e8aa
```
