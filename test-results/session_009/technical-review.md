# Session 009 — Conversion optimization retest

## Findings

Capture-to-action/overlay readiness decreased from **67.943 to 51.316 ms** on average (24.47%); p95 decreased from **84.188 to 62.788 ms**. Conversion decreased from **17.154 to 1.763 ms**, supporting the intended benefit of direct BGRA-to-RGB conversion. Processing cadence increased from **14.628 to 19.280 FPS**. These are per-frame computation measurements, not physical gesture-onset-to-decision latency.

The user reports that action detection seems fairly close to real time while landmarks feel extremely delayed. Software timings support improved computation before action output but do not establish the entire perceived delay. Capture-to-render-return improved only slightly, **113.992 to 108.990 ms** on average. Post-action UI wait/render increased from **45.943 to 57.225 ms**. The latest-frame slot replaced **87/713 frames (12.202%)** before consumption, compared with 4/834 in session 008. Replaced overlays are not missing detector evaluations: every feature frame still has its matching timing row.

## Configuration and integrity

- Duration: 37.680 s; status closed; no reported warnings/errors/drops. Closed metadata does not independently confirm the UI returned to Ready.
- Region: 1403 x 803 at (1444, 287), versus 1405 x 800 at (1443, 291) in 008. Source sequence and system load were not controlled; this is not a rigorously controlled A/B experiment.
- System audio on; video, microphone and transcript off.
- 713 feature and timing rows, matching ordered frame IDs; 713 unique timing IDs. Timing metadata reports zero omitted frames and zero invalid orders.
- Outcomes: 625 rendered, 87 replaced, one not rendered at close. All have valid reported ordering.
- Face visible: 664/713 (93.128%), an availability measure rather than accuracy. Modes: 623 tracking, 49 face missing, 41 calibrating.
- 24 completed/interrupted observable event records. Event start/end timestamps are not notification-emission timestamps.
- Audio: PCM16 stereo, 48 kHz, 1,804,288 frames (37.589333 s); count matches session metadata. No listening assessment was supplied for 009, and no reference waveform was used.

## Timings

Milliseconds, using NumPy default linear percentiles. Per-frame stage differences precede aggregation. All-frame intervals use 713 samples; rendered endpoints use 625. Missing render endpoints are not treated as zeros.

| Interval | 008 mean | 009 mean | 009 p50 | 009 p95 | 009 max |
| --- | ---: | ---: | ---: | ---: | ---: |
| Capture | 25.453 | 25.109 | 24.633 | 35.305 | 54.245 |
| Conversion | 17.154 | 1.763 | 1.632 | 2.368 | 21.928 |
| Image preparation | 1.643 | 1.471 | 1.412 | 1.965 | 5.486 |
| Inference | 21.958 | 21.251 | 21.408 | 26.657 | 34.671 |
| Features/status/point mapping | 1.189 | 1.110 | 1.059 | 1.864 | 2.992 |
| Actions and overlay preparation | 0.545 | 0.611 | 0.620 | 1.036 | 1.522 |
| Capture to action readiness | 67.943 | 51.316 | 51.549 | 62.788 | 87.145 |
| UI wait | 7.793 | 19.905 | 19.181 | 44.888 | 62.107 |
| Bitmap construction | 15.010 | 15.003 | 14.577 | 20.107 | 30.063 |
| Tk image/canvas update | 23.133 | 22.309 | 21.629 | 29.009 | 45.922 |
| Action readiness to render return | 45.943 | 57.225 | 55.664 | 83.898 | 123.092 |
| Capture to render return | 113.992 | 108.990 | 107.414 | 138.271 | 176.037 |

Mean `processing_ms`: 50.666; p50 50.870; p95 62.038; maximum 86.961. Feature timestamp spacing: mean 51.867 ms, p50 53.000, p95 65.000, maximum 85.000. Processing FPS is `(713 - 1) / (last feature timestamp - first feature timestamp)`.

Measured render-return cadence: **16.936 updates/s**, spacing mean **59.045 ms**, p50 **57.787 ms**, p95 **71.254 ms**, maximum **127.367 ms**. This is software canvas-update cadence, not physical display refresh rate.

## Why overlay responsiveness did not follow detector throughput

Current `ControlPanel._draw_overlay` calls `draw_pending()` synchronously, then schedules its next callback using `root.after(16, ...)`. Thus 16 ms is a requested delay after drawing finishes, not a 16 ms complete drawing period. Bitmap plus Tk work averages 37.312 ms in this session, before that requested delay and other UI scheduling. The observed approximately 59 ms rendering cadence is consistent with this cost. Faster production now outpaces observed rendering cadence; latest-frame replacement prevents unlimited backlog but cannot make rendering instantaneous.

This is evidence of a UI throughput limitation, not proof that it fully explains the user's extreme perceived lag. The final timing marker precedes Windows composition/physical presentation and cannot isolate model-internal temporal lag. Action labels drawn in the same overlay also pay the UI/render cost; a subjective distinction between label response and mesh alignment is not a detector-only stopwatch measurement.

## Temporal action verification

Replaying saved features through the current `ActionDetector` reproduced the ordered active action IDs for **713/713 rows**, with no mismatches. Internal inactive-to-active transitions totaled 20, of which 17 required positive persistence duration. Candidate-to-confirmation duration for those 17 was mean **277.118 ms**, p50 **270 ms**, p95 **316.8 ms**, max **328 ms**. Session 008's corresponding mean was 285.485 ms; different gestures and samples prevent attributing that small change solely to optimization.

The 250 ms trailing median window and 250/300 ms persistence rules remain in effect. Confirmation duration begins after the smoothed threshold becomes a candidate; it excludes the unknown physical motion onset and is not a fixed smoothing-lag measurement. Zero-persistence state transitions still depend on the relevant temporal pattern. Blink detection is a separate closure/reopening path. Snapshot ranking/suppression can delay or omit an active label's appearance. No ground-truth action accuracy or onset latency is established by replay consistency.

## Decision

The conversion optimization has a measured live-session benefit before action detection. Keep this result as the current detection baseline. There is no evidence here requiring a change to action thresholds or the landmark model. Any subsequent visual-latency work should target the measured render/scheduling costs and validate the visual result separately. Avoid requesting an identical repeat merely to collect more of the same evidence.

No application code changed during this review. The three previously reported failing tests are still unresolved; this session is not validation of those unrelated contracts. Original data were preserved; only review documents were added.

## Raw-file SHA-256

```text
audio.wav            302d9d3e3716a5c7510455e5b4e6b896265531a2536d946ea11f5c6d7155d321
features.csv         b75cdccc9ef1dbabe5bd259d296fe08f87b9a7908bf1062b9b2e0e870e727cbc
landmark-timing.csv   1824489ea13fba71a48d558f28ac934115bfe534450a7831d007227afee69245
session.json         ab39f366b9d82ac75eb23b8a4c75197a997f1f0fd70ebca3c12841c035e227f0
```
