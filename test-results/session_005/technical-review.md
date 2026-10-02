# Technical Review — session_005

Reviewed October 1, 2026. Session started at 13:15:35 (UTC+07:00).

## Assessment

Follow-up: the operator confirmed an unexpected application exit when pressing Stop. Post-run implementation changes and verification are recorded in [change-log.md](change-log.md). Hardware confirmation of the changes is still pending; the original findings below describe the preserved session_005 evidence.

Audio capture produced a readable WAV, but this run should not be accepted as a clean audio baseline. The operator reports severe crackling/distortion despite intelligible content. The waveform contains many short exact-zero intervals that warrant investigation. Session finalization is also unresolved: metadata still says recording although the audio components say stopped.

Do not advance to transcript quality comparisons until recording quality and finalization have been investigated. Raw data and the unfinished event journal have been preserved; neither metadata nor audio was repaired during this review.

## Input and Configuration

- Operator-reported source: **Improve your Speaking and Conversational skills with me / English Speaking Practice**, playback **0:00–1:33** (93 seconds).
- Follow-up: the operator confirmed that original playback sounds very clean and only audio.wav sounds distorted. The source contains natural speech pauses; the operator did not Pause the application. The original media/link was not supplied for independent waveform comparison.
- System/meeting audio enabled; microphone, video recording, and transcript disabled.
- Capture region: 1745 × 993 px at (1099,293), substantially different from session_004's 1151 × 643 region. Input also changed. Processing differences cannot be attributed solely to audio recording.
- Recorded environment: Python 3.12.14; MediaPipe 0.10.21; OpenCV contrib 4.11.0.86; MSS 10.2.0; NumPy 1.26.4; SciPy 1.17.1; faster-whisper 1.2.1; CTranslate2 4.8.2. Hardware, actual capture-device format, and capture-time commit are not recorded here.

## Audio Measurements

| Check | Result |
| --- | --- |
| WAV format | PCM16, stereo, 48,000 Hz |
| Frames declared and read | 4,511,544; full declared payload readable |
| WAV duration | 93.9905 s |
| Metadata audio interval | Session 0.000–94.008631 s; WAV frames 0–4,511,544 |
| Left channel | Entirely zero, expected with microphone disabled |
| Right channel peak absolute sample | 27,363 of 32,768 scale, approximately 0.835 full scale |
| Right channel RMS | 3,246.85 PCM units across the full recording, including silence |
| Right channel samples at or above absolute 32,760 | 0 |
| Right channel exact-zero samples | 27.333% |
| Internal exact-zero runs lasting 1–20 ms | 1,562 |
| Total duration of those short zero runs | 15.0548 s |
| Longest exact-zero run | 3.7523 s |

The saved waveform does not show saturation at the PCM limits. This does not rule out distortion upstream or clipping subsequently attenuated before saving. The measured zero runs cannot distinguish natural source silence from introduced gaps. Natural speech pauses are confirmed by the operator and must not be classified as capture failures. No clean reference waveform was available, and this analysis did not independently listen to the recording. The operator's clean-original/distorted-recording comparison establishes a reported recording-quality problem, but does not identify the exact faulty component.

The nearly 94-second recording versus the reported 93-second source segment can include setup/start/stop padding; this is not by itself evidence of synchronization failure. The 18.131 ms difference between the mapped interval endpoint and WAV duration is recorded as a timing discrepancy, not proven drift.

## Code-Based Hypothesis — Not Yet Confirmed

Current src/audio_recorder.py timestamps each AudioCaptureWorker packet using session-clock readings immediately before and after a blocking stream.read. In src/stereo_audio.py, StereoAudioWriter places the packet at round((chunk.start_s - session_start) * sample_rate). Buffers are zero-padded, and overlapping writes replace previous samples.

Consequently, variation in CPU scheduling/read timing can create gaps or overlaps even if captured packets contain contiguous audio samples. This is a plausible mechanism for crackling, not a confirmed explanation of this waveform or its zero runs. It has not been reproduced in a controlled experiment, and the actual packet timestamps/native source rate are not retained in this session. Clean source playback is now confirmed by the operator; device/driver behavior, resampling boundaries, packet placement, and recorded-file playback conditions still need investigation. Overflow exceptions are suppressed in stream.read, so empty error counters do not establish that all captured samples were retained.

## Finalization Issue

At inspection, session.json contains:

- status=recording, ended_at_local=null, duration_s=0.0.
- system_audio and audio component states both stopped.
- A populated audio interval and media_stats.audio with 4,511,544 written frames.
- Empty observable_events, while events.tmp.jsonl still contains 76 lines.
- Empty warnings/errors, drops, and drop_details.

This is not a successfully finalized session record. It may reflect interrupted, pending, or failed finalization; the exact cause is unknown. Empty errors must not be interpreted as a clean run. The event journal should be retained for diagnosis, not deleted or silently merged. The real capture span is available from feature/audio timestamps, despite duration_s remaining zero.

## Facial Processing

| Metric | Result |
| --- | --- |
| Feature rows | 1,400 |
| First / last timestamp | 0.887 / 93.976 s |
| Mean / p50 processing time | 65.936 / 65.628 ms |
| Processing p95 / maximum | 75.957 / 112.080 ms |
| Processing FPS | 15.029 |
| Frame-gap p95 / maximum | 76.100 / 118.000 ms |
| Gaps above 100 ms | 2 |
| Timestamp order | Strictly increasing |
| Frame indices | Contiguous, 0–1,399 |

Processing time is capture through feature extraction, not end-to-end UI latency. The larger region and changed source prevent an isolated audio-overhead comparison with session_004.

## Next Steps

1. The operator confirmed that Stop caused an unexpected application exit. Original playback was clean. Preserve this session as evidence and use the new diagnostics during the retest.
2. Diagnose packet timing and session finalization before proceeding to sessions 006–007. A controlled capture should compare sample-contiguous recording against timestamp-positioned output, retaining packet timing and source-rate information.
3. After a verified fix, repeat the same 0:00–1:33 segment with the same region/device/volume. Compare waveform continuity and operator listening results, and require finalized metadata before accepting the audio baseline.

## Method and Evidence

All CSV rows were parsed. FPS=(rows−1)/(last timestamp−first timestamp); percentiles use NumPy default linear interpolation. All PCM frames were read with Python wave and analyzed numerically. Zero runs are consecutive samples exactly equal to zero; short-run counts exclude leading/trailing silence and include lengths 48–960 samples at 48 kHz. They are not automatically classified as dropped audio.

SHA-256 of inspected raw inputs:

```text
session.json      e77562a2852da33b4ece38de544641bb490e4f544be8ae9235f5fd5ced3b4a9a
features.csv      174716261c923cd7ac54047c1d88cb18817a9070443a9b688fc49f0927af4eff
audio.wav         b89641ac24085258e989674773687895f391670a924f400008ead85b8b2a12bb
events.tmp.jsonl  ef7079bfe99133847c0eafae81f0e7df53308cbbeb2fcb839215e8518b86ab01
```
