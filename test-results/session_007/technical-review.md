# Technical Review — session_007

Reviewed October 1, 2026. Run started at 22:00:10 (UTC+07:00).

## Finding

The operator still perceives landmark latency similar to session_006. Saved processing metrics improved after the region was reduced, but end-to-end overlay latency is not measured. Faster processing does not contradict the operator's observation: capture, inference, UI scheduling, and rendering are separate parts of perceived delay.

## Comparison

| Metric | session_006 | session_007 |
| --- | --- | --- |
| Selected region | 1850 × 1054 | 1403 × 807 |
| Duration (s) | 86.176 | 90.373 |
| Feature rows | 1,049 | 1,551 |
| Mean processing time (ms) | 79.952 | 56.877 |
| Processing p50 (ms) | 77.117 | 56.471 |
| Processing p95 (ms) | 101.193 | 64.437 |
| Maximum processing time (ms) | 164.277 | 88.234 |
| Processing FPS | 12.378 | 17.247 |
| Frame-gap p95 (ms) | 102.000 | 67.000 |
| Maximum frame gap (ms) | 125.000 | 93.000 |
| Gaps above 100 ms | 80 | 0 |
| Mean processing time for face-visible rows (ms) | 80.082 | 56.912 |

Region area decreased by approximately 42%, mean processing time by approximately 29%, and throughput increased by approximately 39%. These are descriptive changes, not proof of a causal relationship under fully controlled conditions. The region is still larger than the suggested approximate 1150 × 650 test size. Recorded runtime versions and options match session_006; source alignment, hardware load, and exact source commit are unknown.

Only meeting/system audio was enabled. Microphone, video, and transcript were disabled. Audio uses sample_count_with_pause_reanchor and the Realtek loopback device at a native 48 kHz, two channels.

## Integrity and Face Availability

- Session status is closed with a populated end timestamp. Warnings, errors, and drops are empty. This confirms metadata finalization, not an independently observed return of the UI to Ready.
- All 1,551 feature rows parsed. Frame indices are contiguous and timestamps strictly increase from 0.451 to 90.322 s.
- 1,519 rows contain a face result. Missing intervals are 0.451–1.225 s (14 missing rows) and 16.435–17.425 s (18 missing rows), where the endpoint is the next visible row. Without source ground truth, these are not classified as detection errors.
- WAV header: PCM16 stereo, 48 kHz, 4,335,308 frames, duration 90.319 s. This review checked the header, not full PCM quality or listening. The operator did not provide a new audio-quality assessment for this run.

## Interpretation and Next Step

The smaller region is associated with faster processing, but it did not resolve the perceived problem. Do not repeatedly shrink the region or claim that the lag is fixed based on FPS alone.

The next useful investigation is measurement of the visual pipeline: capture start/end, inference completion, overlay publication, UI consumption, and draw completion using a shared monotonic clock. Separate rendering time from queue wait and processing. Even draw completion is not physical display presentation; a synchronized visual reference would be needed for actual motion-to-screen latency.

Review the existing overlay's latest-frame handoff and rendering costs before selecting an optimization. This review changes documentation only; no new runtime instrumentation or optimization was implemented. Transcript testing remains deferred while the visible landmark delay is investigated.

## Method and Evidence

All rows were included, including startup and missing-face frames. FPS=(rows−1)/(last timestamp−first timestamp). Percentiles use NumPy default linear interpolation. processing_ms covers capture through feature extraction and excludes complete overlay presentation. No pauses were inferred or discarded. Raw inputs were preserved.

```text
features.csv  145b45bf599064d5cacbf4dd73e0b916116537c0a06b37645bcb6beea0a7f76e
session.json  263c9b6ce770110f061e0e32a5373a04ea8fb936119e61e2ba51c4cf3c2f264f
audio.wav     a47c48c107e65997626538b156485798059b44fd18f6cc8447cb822e6f90024d
```
