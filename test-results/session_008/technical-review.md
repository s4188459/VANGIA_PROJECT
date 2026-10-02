# Session 008 — Technical review

## Findings

Action results are produced before overlay rendering. Across 834 frames, capture start to action/overlay readiness averaged **67.943 ms**, p95 **84.188 ms**. The action-rule execution plus overlay preparation interval itself averaged **0.545 ms**, p95 **0.885 ms**. Waiting for and drawing the overlay added **45.943 ms** on average across 829 rendered frames. Capture-to-render-return averaged **113.992 ms**, p95 **143.764 ms**. Rendering is therefore only part of the delay.

There is also intentional temporal decision delay. The detector smooths features with a trailing 250 ms median window, then requires most candidate actions to persist for 250 ms (300 ms for asymmetric brow/eye actions). Actual delay depends on samples and signal shape; the smoothing window does not imply a fixed 250 ms lag.

Offline replay through the current `ActionDetector` reproduced the ordered `active_action_ids` for all **834/834** feature rows. Internal state transitions showed 38 activations: 33 with positive confirmation duration and five nodding activations with zero additional state hold. For the 33 positive-duration activations, candidate-to-confirmation time was mean **285.485 ms**, median **285 ms**, p95 **318 ms**, maximum **324 ms**. This is reconstructed algorithmic confirmation time after smoothed thresholds are crossed, not motion-onset ground truth. Nodding still requires evidence of an oscillation; zero state hold does not mean instantaneous recognition. Blink decisions follow a separate closure/reopening path and are not included in these state counts.

The replay inspected transitions from inactive to active and used the state's candidate start and current feature timestamp. Replay matches the stored ranked snapshots, but ranked snapshots can suppress generic actions or limit output to four items. State activation and appearance of a ranked label are not interchangeable. Completed `observable_events` are emitted after release confirmation (or interruption); their backdated start/end fields are not real-time notification timestamps.

## Configuration and integrity

- Status: closed; duration 57.772 s. No warnings, errors or drops reported. This does not independently prove every sample was retained or that the UI returned to Ready.
- Region: 1405 x 800 at (1443, 291), slightly different from session 007.
- System audio enabled; video, microphone and transcript disabled.
- 834 feature rows and 834 timing rows, matching frame IDs in order; zero reported invalid timestamp orders and zero capacity omissions.
- Outcomes: 829 rendered, four replaced, one not rendered at close. Replacement describes the overlay slot, not capture loss.
- Face visible: 794/834 frames (95.204%). This measures availability, not accuracy. Modes: 765 tracking, 40 face missing, 29 calibrating.
- Processing FPS: **14.628**, calculated as `(rows - 1) / (last timestamp - first timestamp)`.
- `processing_ms`: mean 67.358, p50 66.740, p95 83.191, max 158.755 ms.
- Frame timestamp gaps: mean 68.361, p50 67.000, p95 85.400, max 111.000 ms. Sampling cadence also affects when a new gesture can first be observed.
- WAV: PCM16, stereo, 48 kHz, 2,769,694 frames, 57.701958 s; frame count agrees with audio metadata. Listening quality is the user's assessment (good). No source reference waveform was supplied for an audio-alignment/gap assessment.

## Stage measurements

Values are milliseconds. Percentiles use NumPy default linear interpolation. Each interval is calculated per row before aggregation; stage percentiles must not be summed. Capture/action intervals use 834 rows, rendered endpoints use 829.

| Interval | Mean | p50 | p95 | Max |
| --- | ---: | ---: | ---: | ---: |
| Capture | 25.453 | 25.429 | 32.437 | 86.686 |
| Conversion | 17.154 | 16.545 | 22.571 | 29.602 |
| Image preparation | 1.643 | 1.578 | 2.447 | 4.076 |
| MediaPipe inference | 21.958 | 21.992 | 27.640 | 49.876 |
| Features/status/point mapping | 1.189 | 1.136 | 1.946 | 2.983 |
| Actions and overlay preparation | 0.545 | 0.533 | 0.885 | 1.352 |
| Capture to action/overlay readiness | 67.943 | 67.341 | 84.188 | 158.979 |
| Publication handoff | 0.008 | 0.007 | 0.014 | 0.123 |
| UI wait | 7.793 | 6.769 | 20.394 | 46.207 |
| Bitmap creation | 15.010 | 14.408 | 20.870 | 34.167 |
| Tk image/canvas update | 23.133 | 22.528 | 30.599 | 41.827 |
| Action readiness to render return | 45.943 | 44.905 | 64.171 | 82.644 |
| Capture to render return | 113.992 | 111.502 | 143.764 | 223.414 |

The average total and average action-readiness values use different row populations, so subtracting their rounded means is not the reported post-action mean. Both threads can contend for resources; producing actions before rendering does not prove rendering has no indirect impact on capture/inference scheduling.

## Interpretation and next change

Detection has two sources of response delay: obtaining/processing a new sample and accumulating temporal evidence. The 68 ms frame path and reconstructed 285 ms confirmation interval describe different boundaries; neither alone is physical gesture-onset latency. Smoothing delay, sampling phase, model temporal behavior and action-specific evidence requirements must also be considered. No annotated video/onset reference was captured, so true gesture-onset-to-decision latency cannot be reported.

Capture/conversion are substantial before inference. A pixel-equivalent conversion optimization is justified to shorten the path to action decisions. Reducing confirmation or smoothing thresholds would change detection behavior and requires correctness/false-positive evaluation; no numerical threshold reduction is supported by this unannotated session alone. Details of the implemented conversion improvement and its validation are in `change-log.md`.

Session 007 had mean processing 56.877 ms, p95 64.437 ms, and 17.247 FPS. Session 008 is slower on these saved metrics, despite a similar region. Source timing/system load were not controlled and session 007 had no stage trace; instrumentation overhead alone cannot be inferred from this comparison.

## Preserved raw-file SHA-256

```text
audio.wav            baf880015d834585f0d6f6d769361b719d541cdfed982ee4d835e9b1058f9dc7
features.csv         3b32b3c42c3e8b61030d4c2e3aac01c441c6df75226506901c4281864c8a653b
landmark-timing.csv   77c9d181fc3ad73ee27745db793942a2a9204ff04f8056284b4cf2c9b94cec04
session.json         c9b1581c6d033e06bc8d17a2915b7fd0360257cb595140237c820789fad6b36a
```
