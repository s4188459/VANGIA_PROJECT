# Observable Action Detection And Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert existing raw facial features into calibrated, temporally stable observable-action labels, show at most four labels inside the selected region, and save paired action-event CSV files without changing the raw CSV schema.

**Architecture:** A per-worker `ActionDetector` calibrates median/MAD baselines, smooths valid features, and drives reusable timed action states plus specialized blink and repeated-head-motion histories. The worker fans one `FeatureFrame` into the unchanged raw recorder and detector, then publishes immutable snapshots to the overlay and completed events to a controller-owned paired recording session.

**Tech Stack:** Python 3.12, MediaPipe 0.10.21, NumPy, OpenCV 4.11, MSS 10.2, Tkinter, standard-library `csv`, `statistics`, `collections.deque`, `pathlib`, and `unittest`

**Spec:** `docs/superpowers/specs/2026-09-24-observable-action-detection-design.md`

## Global Constraints

- Do not implement confusion, emotion, attention, engagement, cognitive-load, understanding, intent, or performance classification.
- Preserve the exact 29-column `session_XXX.csv` schema and all existing raw-field meanings.
- Store derived events only in `session_XXX_events.csv`.
- Never overwrite or delete an existing user file.
- Do not save video, images, screenshots, audio, raw frames, or raw landmark arrays.
- Runtime processing remains local and performs no network access.
- Tk objects remain main-thread-only; worker callbacks publish immutable data or write CSV.
- Reset baseline and temporal state on every Start; retain baseline across Pause/Resume and temporary face loss.
- All engineering defaults live in one frozen configuration structure and are documented as unvalidated defaults.
- The workspace is not a Git repository. Do not initialize Git or invent commits. Create `.superpowers/sdd/2026-09-24-observable-action-detection/progress.md` and record every RED/GREEN command, review finding, and implementation ruling there.

## Review Focus

- A user moves during calibration or some features remain blank: unrelated baselines still complete, missing-dependent actions stay disabled, and no NaN enters state.
- A timestamp repeats, jumps backward, or jumps forward across Pause: backward/non-monotonic input fails readably; large forward gaps interrupt events without counting gap time.
- An event filename exists without its raw partner, or appears during allocation: allocation advances and never overwrites either path.
- One frame simultaneously satisfies many generic and specific rules: suppression and ranking remain deterministic and the overlay never exceeds four rows.
- Stop races with worker callbacks: final interrupted events are written before generation invalidation and both recorders close exactly once.

---

### Task 1: Action Domain Model, Configuration, Baseline, And Smoothing

**Files:**
- Create: `src/action_types.py`
- Create: `src/action_temporal.py`
- Create: `tests/test_action_temporal.py`
- Create: `.superpowers/sdd/2026-09-24-observable-action-detection/progress.md`

**Interfaces:**
- Produces: frozen `ActionDetectionConfig` with every default from the accepted spec and `validated() -> ActionDetectionConfig`.
- Produces: `ActionMode` enum values `CALIBRATING`, `TRACKING`, `FACE_MISSING`, `PAUSED`.
- Produces: frozen `ActionDisplay`, `ActionEvent`, and `ActionSnapshot` dataclasses.
- Produces: `BaselineModel.add(frame, delta_s)`, `ready`, `progress`, `median(name)`, and `mad(name)`.
- Produces: `RollingFeatureWindow.add(frame)`, `smoothed(name)`, and `clear()`.

- [ ] **Step 1: Create the execution ledger**

First line:

```text
# SDD ledger - plan: docs/superpowers/plans/2026-09-24-observable-action-detection.md
```

Record that Git/worktree/commit operations are unavailable because the workspace has no `.git` directory.

- [ ] **Step 2: Write failing domain and validation tests**

Pin immutable records and invalid configuration:

```python
config = ActionDetectionConfig()
self.assertEqual(config.baseline_duration_s, 2.0)
self.assertEqual(config.maximum_overlay_actions, 4)
self.assertIs(config.validated(), config)
with self.assertRaisesRegex(ValueError, "sensitivity"):
    replace(config, sensitivity=0.0).validated()
```

Also reject non-positive durations, fewer than two baseline samples, release floors greater than activation floors, and `maximum_overlay_actions < 1`.

- [ ] **Step 3: Write failing baseline tests**

Use non-zero synthetic neutral frames and assert:

```python
baseline.add(frame_at(0.00, yaw=9.0, brow=0.35), 0.0)
baseline.add(frame_at(0.04, yaw=11.0, brow=None), 0.04)
self.assertAlmostEqual(baseline.median("head_yaw_deg"), 10.0)
self.assertIsNone(baseline.median("brow_raise"))  # not enough brow samples
```

Cover visible-only collection, independent missing values, finite-value filtering, minimum samples plus accumulated contiguous valid time, gap time exclusion, median/MAD correctness, and progress clamped to `[0, 1]`.

- [ ] **Step 4: Write failing rolling-window tests**

Assert a spike is rejected by timestamped median smoothing, old values expire by `smoothing_window_s`, missing values do not become zero, and `clear()` removes every sample.

- [ ] **Step 5: Run tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_action_temporal -v
```

Expected: import failures because `action_types` and `action_temporal` do not exist.

- [ ] **Step 6: Implement the domain model and temporal primitives**

Use explicit dataclass fields rather than an untyped threshold dictionary. `BaselineModel` iterates only the numeric optional fields in `FeatureFrame`, stores finite floats per field, and tracks valid observation time separately from wall/session time. Use median absolute deviation:

```python
center = statistics.median(values)
mad = statistics.median(abs(value - center) for value in values)
```

`RollingFeatureWindow` owns one deque per field and evicts entries older than `timestamp_s - smoothing_window_s`.

- [ ] **Step 7: Run focused and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_action_temporal -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass and raw CSV tests remain unchanged.

---

### Task 2: Reusable Timed Action State Machine

**Files:**
- Modify: `src/action_temporal.py`
- Modify: `tests/test_action_temporal.py`

**Interfaces:**
- Consumes: `ActionEvent` and validated timing values from Task 1.
- Produces: `TimedActionState(action_id, label, minimum_duration_s, release_duration_s, cooldown_s)`.
- Produces: `update(timestamp_s, strength, activation_threshold, release_threshold) -> tuple[ActionDisplay | None, ActionEvent | None]`.
- Produces: `interrupt(timestamp_s) -> ActionEvent | None` and `reset()`.

- [ ] **Step 1: Write failing activation and hysteresis tests**

Feed a deterministic timeline:

```python
state.update(1.00, 0.70, 0.60, 0.35)  # pending
display, event = state.update(1.30, 0.72, 0.60, 0.35)  # active
self.assertAlmostEqual(display.duration_s, 0.30)
self.assertIsNone(event)
state.update(1.40, 0.40, 0.60, 0.35)  # remains active by hysteresis
```

Assert no single-frame activation, candidate start is retained, peak strength updates, and release must stay below its threshold for `release_duration_s`.

- [ ] **Step 2: Write failing cooldown, interruption, and timestamp tests**

Assert normal release produces one `completed` event, Pause-style interruption produces one `interrupted` event, pending interruption produces no event, repeated interrupt is idempotent, cooldown blocks immediate reactivation, and a non-increasing timestamp raises `ValueError("Action timestamps must increase")`.

- [ ] **Step 3: Run tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_action_temporal -v
```

Expected: missing `TimedActionState` failures.

- [ ] **Step 4: Implement the state transitions**

Keep candidate start, release-candidate start, active start, peak, last timestamp, and cooldown end explicit. End a completed event at the first below-release timestamp, not the later confirmation timestamp, so release confirmation does not inflate duration.

- [ ] **Step 5: Run focused and full tests and record evidence**

Use the Task 1 commands. Expected: all pass.

---

### Task 3: Calibrated Static Action Families And Face Lifecycle

**Files:**
- Create: `src/action_detection.py`
- Create: `tests/test_action_detection.py`

**Interfaces:**
- Consumes: `FeatureFrame`, `ActionDetectionConfig`, `BaselineModel`, `RollingFeatureWindow`, and `TimedActionState`.
- Produces: `ActionDetector(config=ActionDetectionConfig())`.
- Produces: `update(frame: FeatureFrame) -> tuple[ActionSnapshot, tuple[ActionEvent, ...]]`.
- Produces: `interrupt(timestamp_s: float, mode: ActionMode) -> tuple[ActionSnapshot, tuple[ActionEvent, ...]]`.

- [ ] **Step 1: Write failing calibration and face-state tests**

Generate 30+ visible non-zero neutral frames. Assert `CALIBRATING` and zero actions before both duration/sample conditions, exact median-relative completion afterward, immediate `FACE_MISSING` display, confirmed `face_not_detected` event after 0.20 seconds, one `face_detected_again` event on return, baseline retention, and fresh smoothing after return.

Include Review Focus coverage: moving/blank calibration inputs must leave only dependent actions unavailable; finite unrelated features still calibrate.

- [ ] **Step 2: Write failing orientation and gaze tests**

After calibration, hold synthetic signals long enough to assert all six head-orientation labels. For gaze, reproduce the supplied distinction:

```python
false_down = baseline_frame(gaze_down=0.46, brow_raise=0.81)
true_down = baseline_frame(gaze_down=0.63, brow_raise=0.34)
```

Assert the first does not activate `eyes_looking_down`, the second does after smoothing/hold, only the strongest direction activates, the 0.08 dominance margin is enforced, and eye direction remains independent from pitch/head labels.

- [ ] **Step 3: Write failing brow and mouth tests**

Assert inner raise, generic raise, lower, asymmetry, jaw open, smile, pucker, funnel, and generic mouth movement against non-zero baselines. Pin session-006-like `mouth_pucker=0.75` as neutral so it produces no event. Assert specific labels suppress redundant generic labels.

- [ ] **Step 4: Write failing gap and invalid timestamp tests**

Assert a `>0.25` second gap interrupts active events at the previous timestamp, clears windows/pending state, preserves baseline, and resumes with no stale label. Equal/backward frame timestamps must raise a readable error.

- [ ] **Step 5: Run tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_action_detection -v
```

Expected: missing `ActionDetector`.

- [ ] **Step 6: Implement threshold helpers and static families**

Central helpers compute:

```python
activation = max(floor, baseline_mad * config.adaptive_mad_multiplier)
activation /= config.sensitivity
release = max(release_floor, activation * 0.60)
relative = smoothed - baseline_median
```

Create state objects once in `ActionDetector.__init__`; never recreate them per frame. Missing required values reset only the dependent pending state. Use stable snake-case IDs and the exact neutral labels from the spec.

- [ ] **Step 7: Implement face lifecycle and interruption**

Face state is a special temporal path rather than an ordinary numeric rule. `interrupt()` flushes ordinary active states, clears temporal buffers, preserves baseline, and returns a PAUSED or TRACKING snapshot without stale actions.

- [ ] **Step 8: Run focused and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_action_detection -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all pass.

---

### Task 4: Blink, Repeated Head Motion, Stillness, And Arbitration

**Files:**
- Modify: `src/action_detection.py`
- Modify: `tests/test_action_detection.py`

**Interfaces:**
- Extends `ActionDetector.update()` without changing its signature.
- Produces deterministic `blinking`, `long_eye_closure`, `frequent_blinking`, `asymmetric_eye_closure`, `nodding`, `shaking_head`, `head_movement_detected`, and `head_mostly_still` behavior.

- [ ] **Step 1: Write failing blink timeline tests**

Use 30 FPS timestamps. Assert a two-frame/0.05-second closure followed by release creates one completed blink and a 0.35-second display, a 0.80-second closure becomes long closure and suppresses blinking, four completed blinks in eight seconds activate frequent blinking, old blinks expire, and sustained left/right difference activates asymmetry.

- [ ] **Step 2: Write failing nod/shake/stillness tests**

Feed smoothed angle timelines with known turning points. Assert one static pitch angle is only orientation, alternating pitch excursions create nodding, alternating yaw creates shaking, insufficient excursion creates neither, generic angular speed creates head movement, and all three axes below the range floor for 1.50 seconds create head mostly still.

- [ ] **Step 3: Write failing ranking and suppression tests**

Create six simultaneous candidates. Assert no more than four survive; long closure, nodding/shaking, specific brow, and specific mouth labels suppress their generic alternatives; duration then strength then ID produces deterministic order across repeated frames.

- [ ] **Step 4: Run tests and verify RED**

Use `tests.test_action_detection`; expected failures name the absent temporal labels.

- [ ] **Step 5: Implement specialized histories**

Use timestamped deques. Turning points require velocity-sign changes after a small deadband; count only alternating excursions that meet the configured amplitude within 1.5 seconds. Blink completion timestamps feed an eight-second deque. Do not infer speaking.

- [ ] **Step 6: Implement arbitration as a pure helper**

`rank_actions(displays, maximum) -> tuple[ActionDisplay, ...]` performs suppression and stable sorting without mutating state, making Review Focus overflow behavior directly testable.

- [ ] **Step 7: Run focused and full tests and record evidence**

Expected: all pass.

---

### Task 5: Action Event Recorder And Collision-Safe Paired Session Allocation

**Files:**
- Create: `src/action_event_recorder.py`
- Create: `src/recording_session.py`
- Create: `tests/test_action_event_recorder.py`
- Modify: `src/session_recorder.py`
- Modify: `tests/test_session_recorder.py`

**Interfaces:**
- Produces: `EVENT_CSV_FIELDS` in accepted order.
- Produces: `ActionEventRecorder(path, handle)`, `write(event)`, and idempotent `close()`.
- Produces: `RecordingSession.create(directory, open_func=open)`, `write_feature(frame)`, `write_event(event)`, `close(remove_if_empty=False)`.
- Produces properties: `raw_path`, `event_path`, `raw_row_count`, `event_row_count`, `closed`.
- Changes `next_session_name()` to reserve numbers found in either raw or `_events` filenames while retaining its raw filename return value.

- [ ] **Step 1: Write failing event formatting tests**

Assert exact header and this serialized row:

```text
12.400,14.100,eyes_looking_down,1.700,0.7200,completed
```

Reject unknown statuses, negative duration, end before start, and write after close. Double close remains harmless.

- [ ] **Step 2: Write failing paired-allocation tests**

Cover empty directory, orphan raw file, orphan event file, unrelated names, a raw-path race, an event-path race after this process created raw, and initialization failure. Assert only files created by the failed attempt are removed; pre-existing files and populated partial sessions survive.

- [ ] **Step 3: Run tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_action_event_recorder tests.test_session_recorder -v
```

Expected: missing modules/interfaces.

- [ ] **Step 4: Implement event serialization and paired allocation**

Use exclusive mode `"x"`, UTF-8, `newline=""`, and line buffering. Pair names derive from one number. If event exclusive-open loses a race, close and remove only the just-created header-only raw path, then retry using the newly observed maximum number.

- [ ] **Step 5: Implement paired close error aggregation**

Attempt to close both recorders even when the first close raises. Return one `RecordingError` containing both messages where needed. `remove_if_empty=True` removes both only when neither recorder contains a data row.

- [ ] **Step 6: Run focused and full tests**

Expected: all pass and the old raw-recorder API/tests remain valid.

---

### Task 6: Worker And Controller Integration

**Files:**
- Modify: `src/meeting_tracker.py`
- Modify: `src/app_controller.py`
- Modify: `src/overlay_data.py`
- Modify: `tests/test_meeting_tracker.py`
- Modify: `tests/test_app_controller.py`
- Modify: `tests/test_overlay_data.py`

**Interfaces:**
- Changes worker constructor to `MeetingTracker(region, event_callback, overlay_callback, feature_callback, action_event_callback, *, detector_factory=ActionDetector, ...)`.
- Changes controller `recorder_factory` default to `RecordingSession.create`.
- Raw feature callback writes through `RecordingSession.write_feature`; action-event callback uses `write_event`.
- Replaces frame-local `actions: tuple[str, ...]` with `action_snapshot: ActionSnapshot | None` on `OverlayFrame`.

- [ ] **Step 1: Write failing worker fan-out and lifecycle tests**

Inject a fake detector. Assert each processed feature is sent to the raw callback before detector output is published, completed events reach `action_event_callback`, snapshot and landmarks share one `OverlayFrame`, and no image data enters detector/events.

Construct `OverlayFrame(..., action_snapshot=snapshot)` directly and assert the frozen snapshot is retained while legacy frame-local action strings are no longer part of the dataclass.

Assert Pause invokes detector interruption once, Resume clears the paused overlay without rebuilding baseline, Stop flushes final interrupted events before STOPPED, and missing-face frames continue raw recording.

- [ ] **Step 2: Write failing controller paired-recorder tests**

Assert Start creates the pair before overlay/worker, displays the raw filename, writes raw and event callbacks to the same session, and Stop order is:

```text
tracker.stop/join -> final event write -> generation increment -> paired close
```

Cover Review Focus stale callbacks after close, event write failure, empty startup cleanup, partial preservation, idempotent Quit, Reselect, and ERROR followed by STOPPED retaining the first error.

- [ ] **Step 3: Run integration tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_meeting_tracker tests.test_app_controller -v
```

Expected: constructor and recorder-interface failures.

- [ ] **Step 4: Integrate the detector in the worker**

Create one detector inside `_run`. Keep `last_processed_timestamp_s`. On the first paused loop, call `detector.interrupt(last_timestamp, ActionMode.PAUSED)`, publish returned events, and publish a paused snapshot. In `finally`, interrupt at the last observed timestamp before emitting STOPPED.

- [ ] **Step 5: Integrate paired ownership in the controller**

Do not invalidate generation before `tracker.stop()` joins; recorders must remain valid for final event callbacks. Immediately after join, increment generation, close the pair, hide overlay, and clear feature display. Generation checks still reject any callback arriving after join/close.

- [ ] **Step 6: Run focused and full tests**

Expected: all pass; no GUI opens.

---

### Task 7: Stable Observable-Action Overlay

**Files:**
- Modify: `src/overlay_renderer.py`
- Modify: `tests/test_overlay_renderer.py`
- Modify: `tests/test_overlay_window.py`
- Modify: `src/feature_data.py`
- Modify: `tests/test_feature_data.py`

**Interfaces:**
- Consumes: `OverlayFrame.action_snapshot` produced by Task 6.
- Removes obsolete `movement_actions()` and its single-frame tests after temporal integration is green.
- Renderer consumes snapshot modes and action durations.

- [ ] **Step 1: Write failing renderer-state tests**

Patch `cv2.putText` and assert exact text for calibration percentage, face missing, reacquisition, no action, paused, and four active rows with one-decimal durations. Supply five actions and assert the fifth is never drawn.

- [ ] **Step 2: Write failing layout and background tests**

Render 160x90, 320x180, and 1920x1080 outputs. Assert exact output dimensions, every modified pixel remains in bounds, heading/action baselines use fixed row positions, and the backing region contains both transparent-key and dark pixels in a stable checkerboard pattern.

- [ ] **Step 3: Run tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_overlay_renderer tests.test_overlay_window -v
```

Expected: missing snapshot rendering behavior.

- [ ] **Step 4: Implement snapshot rendering**

Reserve heading plus four row slots regardless of active count. Use neutral colors and no red warning styling for observations. Clamp panel dimensions and omit rows that cannot fit. Keep FPS in a stable heading position.

- [ ] **Step 5: Remove frame-local action heuristic**

Delete `movement_actions()` only after worker tests consume `ActionDetector`. Retain `gaze_label()` for the raw coefficient panel; do not change raw values or CSV fields.

- [ ] **Step 6: Run focused and full tests and visually inspect synthetic renders**

Render all special modes and a four-action 640x360 frame to temporary PNG files, inspect them with `view_image`, then delete only those verified temporary paths. Expected: readable text, no overlap, stable panel, and visible dither transparency.

---

### Task 8: Documentation, Replay Verification, And Privacy Audit

**Files:**
- Modify: `README.md`
- Modify: `.superpowers/sdd/2026-09-24-observable-action-detection/progress.md`

**Interfaces:**
- Documents neutral interpretation, calibration posture, paired files, event schema, defaults, Pause semantics, and manual acceptance.

- [ ] **Step 1: Update exact usage documentation**

Document that the user holds a neutral pose while `Calibrating...` is visible, action labels are engineering observations rather than mental-state inference, raw/event CSVs are paired, and Pause/Stop can produce `interrupted` events.

- [ ] **Step 2: Add a read-only session replay check**

Run `session_006.csv` through `ActionDetector` without screen capture. Report calibration completion time, action IDs/counts, maximum simultaneous displayed actions, and confirm the supplied brow-raise-like `gaze_down=0.46` case does not become `eyes_looking_down` while deliberate `0.63` synthetic input does. Do not modify the supplied CSV.

- [ ] **Step 3: Run final automated verification**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import ast,pathlib; files=list(pathlib.Path('src').glob('*.py'))+list(pathlib.Path('tests').glob('*.py'))+list(pathlib.Path('scripts').glob('*.py')); [ast.parse(path.read_text(encoding='utf-8')) for path in files]; print(f'syntax ok: {len(files)} files')"
```

Expected: every test passes, no broken requirements, and all Python files parse.

- [ ] **Step 4: Run storage and scope scans**

```powershell
rg -n "VideoWriter|imwrite|\.shot\(|\.save\(|requests\.|socket\.|urlopen" src
rg -n "confus|emotion|engagement|cognitive|attention|Speaking" src
rg -n "landmark" src/action_event_recorder.py src/recording_session.py
```

Expected: no runtime media/network writers, no prohibited classifier labels, and no raw-landmark event serialization. The setup downloader remains the only permitted `urlopen`, under `scripts/`.

- [ ] **Step 5: Run paired-recorder smoke test**

In a temporary directory, create `RecordingSession`, write one synthetic raw missing-face frame and one completed synthetic action event, close, parse both with `csv.DictReader`, and assert matching session numbers plus exact headers. No screen capture or personal data is used.

- [ ] **Step 6: Leave real-data visual acceptance to the user**

The user performs the twelve manual steps in the accepted spec with consented input. Record exact filenames and any false-positive sequence they report; never request video or biometric CSV upload unless they explicitly choose to share it.
