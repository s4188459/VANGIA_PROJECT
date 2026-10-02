# Technical Review — session_004

Reviewed October 1, 2026. Session started at 13:06:54 (UTC+07:00).

## Assessment

The face-only session closed successfully with readable feature data, continuous frame indices, increasing timestamps, and no reported errors. The operator reported no unusual behavior. Basic collection and data-integrity checks passed; no numerical performance or accuracy target was established.

The operator changed accounts and reselected the capture region before this run. The region changed from 1146 × 649 px at (1542,559) in session_003 to 1151 × 643 px at (1541,558). Performance comparisons are therefore descriptive, not a strictly controlled repeat or evidence of a software improvement.

## Configuration and Results

Video, system audio, microphone, and transcription were all disabled. Recorded Python/package versions match session_003: Python 3.12.14, MediaPipe 0.10.21, OpenCV contrib 4.11.0.86, MSS 10.2.0, NumPy 1.26.4, SciPy 1.17.1, faster-whisper 1.2.1, and CTranslate2 4.8.2. Transcription packages were installed but transcription was not used. CPU, RAM, exact input identity, and capture-time source commit are not recorded.

| Metric | session_003 | session_004 |
| --- | --- | --- |
| Duration (s) | 61.693 | 61.452 |
| Feature rows | 1,326 | 1,348 |
| Mean processing time (ms) | 45.683 | 44.702 |
| Processing p50 (ms) | 44.953 | 43.309 |
| Processing p95 (ms) | 58.108 | 61.264 |
| Maximum processing time (ms) | 78.443 | 83.781 |
| Processing FPS | 21.531 | 21.997 |
| Mean frame gap (ms) | 46.445 | 45.461 |
| Frame-gap p95 (ms) | 60.000 | 63.000 |
| Maximum frame gap (ms) | 78.000 | 88.000 |
| Gaps above 100 ms | 0 | 0 |
| Face-visible processing mean (ms) | 46.725 | 45.579 |
| Face-visible processing p95 (ms) | 58.876 | 61.831 |

The mean was slightly lower and FPS slightly higher, while p95 and the maximum were higher. This is not an across-the-board improvement. No recorded inter-frame gap exceeded 88 ms, supporting continuity of the saved processing stream. UI rendering cadence is not directly measured.

Calibration occupied 48 rows; the first tracking-mode row was at 2.185 s. For the 1,300 rows from that point onward, processing mean was 44.796 ms, p50 43.459 ms, and p95 61.313 ms. Processing time covers capture through feature extraction, not the full delay to an overlay redraw.

## Face Availability

1,214 of 1,348 rows contained a face result (90.059%); 134 rows were missing. This is availability rather than detection accuracy and includes the intentional departure exercise.

| Missing interval | Rows | Next visible timestamp | Observed length |
| --- | --- | --- | --- |
| 46.694 s | 1 | 46.750 s | 0.056 s |
| 46.816–51.626 s | 132 | 51.662 s | 4.846 s |
| 51.832 s | 1 | 51.880 s | 0.048 s |

The main interval is consistent with leaving the region, with one brief missing result before it and one shortly after return. No subsequent missing rows were recorded. Exact physical departure/return times were not independently logged, so these intervals do not quantify reacquisition latency or false-negative accuracy.

## Integrity

- All 1,348 rows parsed; frame indices are contiguous from 0 to 1,347.
- Timestamps increase strictly from 0.171 to 61.407 s. Stored frame_gap_ms agrees with all timestamp differences within 0.001 ms tolerance.
- Session status is closed. Warnings/errors are empty lists; drops and media_stats are empty objects.
- capture_drop_count is zero throughout, which is not independent proof of zero capture loss.
- Video mappings are blank. Video/audio/transcript outputs are absent as expected with those features disabled.
- Audio quality, transcript accuracy, LIVE lag, and video dimensions are N/A. The video-height issue seen in sessions 001–002 is not retested here.

## Baseline Assessment and Next Test

The first four sessions support basic operation over short runs. They do not establish long-session reliability or action/landmark accuracy. The two face-only sessions achieved approximately 21.5–22.0 FPS. Region and input differences mean the small video-on/off differences should not be interpreted as isolated causal effects. No immediate performance change is warranted from these results alone.

Proceed to session_005: face tracking plus meeting/system audio only. Keep video, microphone, and transcript disabled. Use a repeatable 60–90 second English video with a visible face and known speech, and retain it for sessions 006–007. Record filename/link and playback start/end positions. Maintain region and volume across those audio runs. The new input establishes a new comparison group; do not treat its difference from session_004 as purely audio overhead.

After Stop, inspect audio.wav and report whether the speech is audible and whether there are obvious interruptions or distortion. System audio is expected on the right channel, with the disabled microphone channel silent on the left. Technical analysis can check format, levels, channel activity, intervals, and reported errors; correctness against the original sound still needs reference audio or manual review.

## Method and Evidence

All rows were included in whole-run statistics, including calibration and missing-face periods. FPS = (row count − 1) / (last timestamp − first timestamp). NumPy default linear interpolation was used for percentiles. Post-calibration statistics begin at the first tracking-mode row. Missing intervals extend from the first missing row to the next visible row. No intervals were discarded; no pause-like gap was observed, although an explicit pause log is unavailable. Times use the session clock, not an assumed exercise stopwatch offset.

Both sessions 003 and 004 were recomputed for comparison. Raw inputs were preserved. No live application test or unit-test suite was run as part of this review. No video was available for visual inspection.

SHA-256 of session_004 inputs:

```text
features.csv  69661ffb335860a2935346717e06268884604d582f236f99362d2bce3b24d593
session.json  b227ccda2568e21a31e45a3270ecbc7df06c202a404095311adaa94a7ac132fe
```
