# Session 008 — Reduce image conversion cost before action detection

## Problem & evidence

The user prioritizes facial action recognition response over landmark drawing. Session 008 conversion alone averages 17.154 ms (p95 22.571 ms), before the action result can be computed. Existing `MeetingTracker._run` makes a contiguous BGR copy from MSS BGRA and then another contiguous RGB copy even when video is disabled.

## Purpose and changes made

In `facial-cue-prototype/src/meeting_tracker.py`, `_run` now uses OpenCV's existing dependency to convert BGRA directly to RGB via `cv2.cvtColor(..., cv2.COLOR_BGRA2RGB)`. BGR is only created when the optional video callback exists, using `COLOR_BGRA2BGR`. The existing independent copy passed to the video callback is retained.

Previously both NumPy copies ran on every frame. Now the inference path performs a direct color conversion without constructing an unused BGR frame. Image dimensions and RGB pixel values are preserved, so this targets computational overhead before recognition without altering the evidence required by the action rules.

## Reasoning and trade-offs

Conversion was directly measured as a substantial cost. This is a bounded optimization of the existing capture path. There are no changes to the model, action thresholds, smoothing, audio, or rendering schedule. It cannot remove the intentional confirmation time; that remains a separate accuracy/responsiveness trade-off needing labeled gesture evaluation.

OpenCV scheduling and performance depend on runtime load. For video-enabled runs, BGR conversion now falls after `conversion_end_s`, inside the existing pre-inference preparation interval. `processing_ms` still includes it. Compare conversion plus preparation or capture-to-action readiness for cross-configuration analysis; the intended retest has video disabled.

## Before/after experiment and validation

A local isolated benchmark used one seeded (`default_rng(7)`) random uint8 BGRA image of shape 800 x 1405 x 4, five warm-up calls and 40 timed calls per implementation, measured with `perf_counter`:

| Conversion implementation | Mean | p95 |
| --- | ---: | ---: |
| Original two contiguous NumPy copies | 16.342 ms | 20.357 ms |
| Direct OpenCV BGRA-to-RGB | 0.953 ms | 1.187 ms |

Full RGB array equality was verified. This sequential microbenchmark establishes a promising computational improvement, not a live-session or perceptual improvement; CPU scheduling/cache state and active rendering/audio can affect results.

`tests/test_meeting_tracker.py::test_capture_conversion_preserves_all_rgb_and_video_bgr_pixels` exercises the real tracker with synthetic capture/landmarker dependencies, varied color/alpha values, and both video modes. It verifies complete RGB/BGR arrays and independent video storage. Existing tracker, action, audio and timing tests also ran in the full suite.

Full suite: **220 tests, 217 passed, 1 failure, 2 errors**. The three previously recorded issues remain:

- `test_bgra_conversion_preserves_pixels_and_skips_unused_video_copy`: missing `prepare_capture_frame` import in the separate `frame_processing` module; the tracker conversion change does not introduce that absent API.
- `test_decoder_uses_deterministic_single_pass_and_silence_guard`: missing `temperature` key.
- `test_uncertain_and_repetitive_segments_are_not_published_as_speech`: unexpected extra transcript segments.

## Pending live validation

Next session: 30–60 seconds, same source/region as 008 as closely as possible, system audio on, video/microphone/transcript off. Include clear sustained facial/head gestures. Compare capture-to-action-ready timings and sample spacing; the user assesses responsiveness of action labels and correctness as well as audio. On-screen labels also incur the measured UI/render delay, so their visible response must not be presented as a direct detector-only latency measurement.

All original session 008 data remain unchanged. No improvement in actual gesture-onset latency is claimed before retest.
