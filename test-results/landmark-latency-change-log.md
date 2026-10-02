# Landmark latency instrumentation

Date: 2026-10-01 (Asia/Bangkok)

## Problem & evidence

The session 006/007 reviews report visible landmark delay even after reducing the region from 1850 x 1054 to 1403 x 807. Recorded mean processing decreased from 79.952 ms to 56.877 ms, p95 from 101.193 ms to 64.437 ms, and processing FPS increased from 12.378 to 17.247. These are historical review values, not a new benchmark of this change. The user still perceived similar delay.

Existing `processing_ms` ends before action detection, overlay publication, and UI rendering. It cannot locate the complete visible-path delay. Code inspection confirms a latest-frame slot, not an unbounded overlay FIFO. Its configured 16 ms draw timer is not a measured wait time.

## Purpose

Measure stages of the existing pipeline using the session's monotonic clock and the same `frame_index` as `features.csv`. This change adds diagnostics; it does not claim to improve latency. Architecture, model settings, image dimensions, action thresholds, audio capture, transcription settings, and UI timer intervals are preserved.

## Measurement principle and interpretation

Each captured image is treated as one traceable unit. Its `frame_index` identifies the corresponding feature row, and its timing token follows the same image's landmark result into the overlay. Reading the clock at each boundary gives timestamps for that specific frame; subtracting two timestamps gives elapsed time between those boundaries. Never subtract a capture timestamp from frame A from a render timestamp belonging to frame B.

All stages read the same session clock, backed by `time.perf_counter`. This monotonic clock measures elapsed time without depending on changes to the calendar clock. Worker and UI timestamps therefore share one origin and unit. The clock continues through Pause; pause-only redraws carry no new capture timing token.

Conceptual path:

```text
Capture -> convert/prepare image -> infer landmarks -> features/actions
        -> publish latest overlay -> wait for UI -> build bitmap -> update Tk canvas
```

For a rendered frame, the principal diagnostic interval is:

```text
capture-to-render-return_ms = (render_end_s - capture_start_s) * 1000
```

The intermediate differences locate where this elapsed time accumulated. They include both work and scheduling/waiting during each interval; an inference interval is the elapsed duration of the inference call, not a pure CPU-time measurement.

Illustrative example only, not a measurement from this project:

| Boundary for one frame | Session timestamp | Elapsed from capture start |
| --- | --- | --- |
| Capture begins | 10.000 s | 0 ms |
| Inference begins after capture/image preparation | 10.012 s | 12 ms |
| Inference returns | 10.050 s | 50 ms |
| Overlay is published after feature/action work | 10.055 s | 55 ms |
| UI takes the overlay | 10.075 s | 75 ms |
| Tk canvas update returns | 10.090 s | 90 ms |

This frame took 90 ms from capture start to the canvas-update return: 12 ms before inference, 38 ms in inference, 5 ms until publication, 20 ms waiting for the UI, and 15 ms for bitmap/Tk work. The actual CSV has finer boundaries to split these groups further. Such a result would warrant investigating inference and UI wait; it would not establish a root cause from a single frame.

FPS answers how frequently frames are processed; latency answers how old a particular result is when it reaches a later boundary. For example, 20 FPS implies an average frame interval near 50 ms, but does not establish 50 ms capture-to-render latency. Existing `processing_ms` measures only an earlier portion of this path. Faster processing can coexist with a long UI/render delay, so neither FPS nor `processing_ms` alone disproves the user's observation.

The overlay retains only its latest pending frame. If B replaces A before the UI takes A, record A as `replaced` with blank UI/render timestamps and measure B independently. Do not assign zero latency to A or pretend it was displayed. Report both the timing distribution of rendered frames and the number of frames not rendered. Otherwise, good timings for a small rendered subset could conceal poor update continuity.

Across the diagnostic session, mean describes the average, p50 the median, p95 the value at or below which approximately 95% of measured values fall, and max the largest observed value. Compute total latency directly per frame before taking percentiles: the sum of stage p95 values is not the total p95 because each stage's slowest cases may belong to different frames. Analyze only valid, complete endpoint pairs and disclose omitted/invalid records.

The final stamp is taken when the Tk canvas update call returns. Windows composition and display refresh can occur later. This measurement also starts after the camera/network/video source has already produced the image being captured. It cannot quantify all motion-to-visible-overlay delay or isolate temporal lag inside the landmark model. User observation remains necessary; if software timings do not explain the visible delay, a separate visual measurement may be needed. Instrumentation provides evidence for choosing an optimization; it is not itself a latency fix.

## Changes made: before / after

Paths in this section are relative to `facial-cue-prototype`.

| File / function | Before | After and purpose |
| --- | --- | --- |
| `src/landmark_timing.py`: `FrameTiming`, `LandmarkTimingRecorder` (new) | No per-frame visual-path timing record | Stores stage timestamps in memory, keeps one terminal outcome per frame, flags timestamp order violations, counts records omitted at capacity, writes CSV at close. |
| `src/dataset_session.py`: `DatasetSession.__init__`, `close` | Finalized existing dataset files | Owns the timing recorder; closes it with the dataset and writes `landmark_timing` metadata. Diagnostic storage failure is surfaced through the existing incomplete-session/error path while feature storage still closes. |
| `src/app_controller.py`: `_start_worker` | Supplied clock and optional video callback | Also passes the dataset's timing recorder to the tracker. Existing tracker-stop-before-dataset-close ordering is retained. |
| `src/meeting_tracker.py`: `__init__`, `_run` | Only `processing_ms` and frame spacing available | Adds a timing token to each captured frame and stamps capture, conversion, inference, feature and overlay-callback boundaries. Capture/inference/worker exceptions can produce `tracker_error`. Pause status publications carry no capture token. |
| `src/overlay_data.py`: `OverlayFrame`, `LatestOverlayFrame.publish/take/clear` | Latest frame retained without diagnostic identity | Carries timing token; stamps publication and consumption inside the slot lock; marks displaced frames `replaced` and cleared pending frames `cleared`. Latest-frame behavior stays the same. |
| `src/overlay_window.py`: `draw_pending`, `set_paused` | Rendered PPM and updated Tk canvas | Stamps PPM completion and canvas-update return; records `rendered` or `render_error`. Pause redraws do not reuse the previous capture's timing token. |
| `tests/test_landmark_timing.py` (new), `tests/test_meeting_tracker.py`, `tests/test_overlay_window.py`, `tests/test_app_controller.py` | No timing coverage | Adds eight tests covering frame association, timing order, missing render, replacement, capacity, late callbacks, renderer errors, pause redraw, storage errors and controller Stop finalization. |

No changes were made to `control_panel.py` or `overlay_renderer.py`: their existing calls are measured at the handoff and renderer boundaries. Pre-existing uncommitted audio fixes remain in place. Existing session data and reports are untouched.

## Diagnostic outputs

New captured sessions create `landmark-timing.csv` at Stop. Each row joins to `features.csv` by `frame_index`. A capture that fails before feature publication may have a diagnostic row without a feature row. An empty session creates no timing CSV.

All `*_s` fields are seconds since the same `SessionClock` origin. They are neither wall-clock times nor rounded MediaPipe timestamps. Blank fields mean the stage was not reached/observed, not zero duration.

| Field | Exact boundary |
| --- | --- |
| `capture_start_s` | Diagnostic record begins, immediately before the existing processing timer and MSS grab. Includes small instrumentation overhead before grab. |
| `capture_end_s` | MSS `grab` returns. |
| `conversion_end_s` | BGRA array validation, BGR and RGB contiguous conversion complete. |
| `inference_start_s` | Immediately before `detect_for_video`, after timestamp preparation, optional video callback, and MediaPipe image construction. |
| `inference_end_s` | `detect_for_video` returns. |
| `features_end_s` | Face status/point mapping, feature extraction and existing processing-field assignment complete; before action detection. |
| `overlay_callback_s` | Action detection, action field construction and overlay creation complete; immediately before overlay callback. |
| `overlay_published_s` | Inside the latest-frame slot lock, immediately before assigning the pending frame. |
| `ui_consumed_s` | Inside that lock, as the UI takes and clears the pending frame. |
| `bitmap_end_s` | `render_overlay_ppm` returns. |
| `render_end_s` | `PhotoImage` creation and canvas `itemconfigure` return. This is not physical display presentation. |

For valid rows, subtract endpoints and multiply by 1000 for milliseconds:

- Capture: `capture_end_s - capture_start_s`.
- Conversion: `conversion_end_s - capture_end_s`.
- Image/video preparation: `inference_start_s - conversion_end_s`.
- Inference: `inference_end_s - inference_start_s`.
- Feature processing: `features_end_s - inference_end_s`.
- Action/overlay preparation: `overlay_callback_s - features_end_s`.
- Callback handoff: `overlay_published_s - overlay_callback_s`.
- UI wait: `ui_consumed_s - overlay_published_s`.
- Bitmap construction: `bitmap_end_s - ui_consumed_s`.
- Tk image/canvas update: `render_end_s - bitmap_end_s`.
- Capture-to-render-return: `render_end_s - capture_start_s` (rendered rows only).

`outcome` is one of `rendered`, `replaced`, `cleared`, `render_error`, `tracker_error`, or `not_rendered_at_close`. The last outcome includes the pending frame that cannot be drawn while the UI thread runs Stop. Replacement is an overlay presentation skip, not a capture/video queue drop. A rendered/replaced frame retains its terminal outcome if a later callback fails; the tracker error remains available through the existing error path.

`order_valid` checks nondecreasing order of present stage timestamps. It does not imply all stages exist. Analyze rendered rows with complete endpoints and valid order; report outcome counts separately to avoid hiding unrendered frames.

`session.json.landmark_timing` records filename, clock domain, capacity, recorded/omitted frame counts, outcome counts, invalid-order count and finalization state. A write failure sets `finalized: false` and reports the error. Existing metadata schema remains 3.0 with this additive field; existing `features.csv` columns and `processing_ms` boundaries are unchanged.

## Reasoning and trade-offs

The existing latest-frame handoff is preserved. Stamping inside its lock avoids attributing a replaced frame's timing to its successor. UI and worker share a small timing token rather than matching timestamps heuristically.

Recording is bounded to the first 20,000 attempted capture frames per session. Further attempts are counted as omitted and tracking continues. This easily covers the planned 30–60 second diagnostic run; long-session distributions must disclose truncation. Memory grows only to this cap. No asynchronous disk writer or extra worker is introduced.

Capture/render perform clock reads, small dictionary updates and short lock operations. Their cost is included in observed durations; runtime overhead on the user's hardware has not been benchmarked. CSV serialization and disk I/O happen at Stop on the closing thread, which can lengthen Stop for a large diagnostic buffer. An abnormal process exit before Stop loses in-memory timing data; persistent crash diagnostics from the earlier audio fix remain available.

These measurements include OS/Python scheduling delays. They do not isolate CPU execution time, camera/source-video age, MediaPipe's internal tracking/filtering lag, desktop composition, display refresh, or the physical moment pixels become visible. Feature CSV publication occurs after overlay publication and can overlap rendering; it is not a separate stage in this visual-path record, although its cost can affect subsequent capture spacing. No bottleneck is confirmed yet.

## Validation

- New session ownership/finalization tests were first observed failing because instrumentation was absent; tracker and rendering tests likewise failed before their hooks were added.
- Full suite after implementation: **219 tests; 216 passed, 1 failure, 2 errors**. All eight added tests passed.
- In-memory syntax compilation passed for all ten new/modified source and test files in this change. `git diff --check` found no whitespace errors (Git reported only existing LF/CRLF conversion warnings). This is not a claim that `compileall` passed.
- Existing issues remain unchanged and outside this scope:
  - `test_bgra_conversion_preserves_pixels_and_skips_unused_video_copy`: missing `prepare_capture_frame` import.
  - `test_decoder_uses_deterministic_single_pass_and_silence_guard`: missing `temperature` key.
  - `test_uncertain_and_repetitive_segments_are_not_published_as_speech`: extra `invented` and `loop loop loop` segments.
- Stop integration exercises a real dataset/controller/orchestrator with synthetic tracker input, both without audio and with audio selected but no hardware devices. It does not establish hardware capture quality or actual UI responsiveness.
- Renderer tests substitute Tk/native windows. Real Windows rendering and perceived latency remain to be tested.

## Next manual session and analysis

Restart the app to load this code. Record one new 30–60 second session into `test-results` using the session 007 region/source as closely as possible (1403 x 807 at 1443, 286 if still appropriate), with visible head movement. Enable meeting/system audio; disable video, microphone and transcript. Do not change other settings. The app allocates the next available session number; do not overwrite session 007.

Press Stop and note whether the app stays open and returns to Ready. Supply only the manual observations: visible delay/jitter/freezes and audio quality. Technical metrics will be computed from the new output files; no manual transcription of metrics is required.

The next technical review will join timing and feature rows, check ordering and completeness, report outcomes/omissions, and calculate mean/p50/p95/max per stage using NumPy's default linear interpolation. Compare existing processing metrics to session 007 with input/configuration caveats. There is no pre-instrumentation capture-to-render baseline, so no before/after end-to-end improvement can yet be claimed. Select an optimization only after these data identify a plausible bottleneck; validate perceived improvement with the user afterwards.
