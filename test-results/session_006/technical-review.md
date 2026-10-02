# Technical Review — session_006

Reviewed October 1, 2026. This is the audio-fix retest, not a transcript test.

## Assessment

Audio quality is now reported as very good by the operator. The session finalized with status=closed and a populated end timestamp; this confirms successful file finalization for this run, but does not independently confirm the UI returned to Ready. No errors or drops are reported. A new manual concern is visibly delayed landmarks. The recorded facial processing is slower than session_005 and merits a separate controlled check before further changes.

## Configuration and Comparability

Only system/meeting audio was enabled; video, microphone, and transcript were disabled. Metadata confirms sample_count_with_pause_reanchor timing, and a Realtek loopback device at 48 kHz with two native channels.

The region changed from 1745 × 993 to 1850 × 1054 pixels, at (999,289). This is approximately 12.5% more pixels than session_005 and about 2.64 times the pixel area of session_004. Capture and overlay workloads may be affected, but causation has not been measured. Hardware load, input equivalence, and runtime source commit are not established. The new recording is about 86 seconds, so exact repetition of the prior 0:00–1:33 segment is not confirmed.

## Facial Processing

| Metric | session_005 | session_006 |
| --- | --- | --- |
| Feature rows | 1,400 | 1,049 |
| Mean processing time (ms) | 65.936 | 79.952 |
| Processing p50 (ms) | 65.628 | 77.117 |
| Processing p95 (ms) | 75.957 | 101.193 |
| Maximum processing time (ms) | 112.080 | 164.277 |
| Processing FPS | 15.029 | 12.378 |
| Frame-gap p95 (ms) | 76.100 | 102.000 |
| Maximum frame gap (ms) | 118.000 | 125.000 |
| Inter-frame gaps above 100 ms | 2 | 80 |

All 1,049 rows parsed, indices are contiguous, and timestamps strictly increase from 1.464 to 86.130 s. No frame interval exceeded 250 ms. The data show slower processing, not necessarily long freezes, consistent with the operator's distinction of visible delay.

processing_ms covers capture through feature extraction; complete overlay rendering and presentation are not included. Current code schedules overlay updates using a 16 ms UI timer, which is not a measured or guaranteed display interval. End-to-end landmark latency is therefore **not measured**. The 79.952 ms mean must not be presented as the entire perceived delay. Enlarged capture area, UI rendering, and runtime workload are potential contributors; the audio correction cannot be singled out from this comparison.

## Audio and Finalization

| Check | Finding |
| --- | --- |
| Session duration | 86.176 s |
| WAV format | PCM16 stereo, 48 kHz |
| Declared / decoded frames | 4,136,369 / 4,136,369 |
| WAV duration | 86.174 s |
| Left channel | Entirely silent, expected with microphone disabled |
| Right channel peak | 28,422 PCM units, below full scale |
| Samples with absolute amplitude >= 32,760 | 0 |
| Right-channel exact-zero fraction | 3.049% |
| Internal zero runs of 1–20 ms | 45, totaling 0.07923 s |
| Status / errors / drops | closed / none reported / none reported |

Session_005 contained 1,562 short zero runs totaling 15.05479 s; this run contains far fewer. Together with the operator's listening assessment, this supports improved recording quality. Different recording durations/source alignment prevent a precise same-input distortion comparison, and natural source pauses must not be classified as dropped audio. No independent AI listening assessment was performed. The waveform does not show PCM-limit clipping, which does not rule out every form of distortion.

## Next Step

Keep the current code and audio settings. Repeat a fixed source segment with a smaller displayed video and a correspondingly smaller selected face region (approximately 1150 × 650 px), retaining comparable face framing. Record the actual source segment and any changed device/volume settings. Compare saved processing metrics and perceived landmark delay. This is a capture-size check, not proof that cropping alone solves all delay.

If visible lag persists, instrument capture-to-overlay timing before choosing an optimization. Transcript testing remains deferred while landmark responsiveness is investigated. The audio-fix retest is positive for recorded sound and metadata finalization; UI Stop behavior still needs explicit operator confirmation.

## Method and Evidence

Whole-run metrics include all frames. FPS=(rows−1)/(last timestamp−first timestamp), with NumPy default linear percentile interpolation. PCM data were fully read. Short zero runs exclude leading/trailing silence and contain 48–960 consecutive zero samples. Raw inputs were preserved.

```text
session.json  5a7e72b4d4c2540f292b0fe346a7daf25a377962ce94fbe4eb3f611a6e6a073f
features.csv  0e3ecf5458aaf8a4b78d92becb95114aa825647df99f2a90b03afe054ed230c0
audio.wav     5af015117a677906f81b7895c31edb8e2073edf85cee91e958b187c1837ee46b
```
