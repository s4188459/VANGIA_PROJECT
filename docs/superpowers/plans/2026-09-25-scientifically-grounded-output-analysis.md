# Scientifically Grounded Output And Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the rule-based observable-action collector with higher-quality session-reference calibration, more robust temporal rules, scientifically precise display labels, and objective session analysis/metadata outputs without training a model or changing legacy raw/event schemas.

**Architecture:** Extend the existing detector rather than replacing it. Calibration diagnostics stay in the temporal/domain layer, detector summaries cross the worker boundary as immutable data, and `RecordingSession` remains the single owner of persistence while expanding from two to four same-number files. Analysis is derived incrementally from action events, and replay uses the same production detector in read-only mode.

**Tech Stack:** Python 3.12, standard-library dataclasses/csv/json/statistics, OpenCV, MediaPipe Tasks, MSS, Tkinter, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-25-scientifically-grounded-output-analysis-design.md`

## Global Constraints

- Detection remains rule-based over MediaPipe numeric outputs; no model training or new inference dependency.
- `session_NNN.csv` keeps its exact current 29-column header.
- `session_NNN_events.csv` keeps its exact current six-column header and stable action IDs.
- Revised wording changes display labels only, never compatible event IDs.
- All thresholds are engineering heuristics and must be described as pending empirical validation.
- No confusion, attention, engagement, cognitive-load, emotion, fatigue, intention, agreement, understanding, or performance output.
- No participant identity, image, video, audio, screenshot, raw-landmark, cloud, or network output.
- All processing and persistence remain local.
- The project is not a Git repository. Use the plan ledger and test evidence; do not initialize Git or fabricate commits.

## Review Focus

- A MediaPipe build that omits one optional blendshape group must complete reference collection for available groups and disable only dependent actions; Task 1 tests this explicitly.
- Irregular low-FPS timestamps, equal timestamps, and gaps around 0.25 seconds must not divide by zero, inflate reference duration, or bridge events; Tasks 1 and 2 test these boundaries.
- Orphan `_analysis.csv` or `_metadata.json` files and a race on any of four paths must reserve the session number without deleting pre-existing files; Task 4 tests this.
- A process/storage failure during final analysis or metadata writing must preserve already populated raw/event files and attempt every close; Task 4 tests error aggregation and preservation.
- A stale worker summary callback after Stop must not modify a closed or newer session, while the final in-generation summary must arrive before close; Task 5 tests callback ordering and generation rejection.

---

### Task 1: Reference Quality Domain Model And Calibration Gate

**Files:**
- Modify: `src/action_types.py`
- Modify: `src/action_temporal.py`
- Modify: `src/action_detection.py`
- Modify: `tests/test_action_temporal.py`
- Modify: `tests/test_action_detection.py`

**Interfaces:**
- Produces `ReferenceQuality(str, Enum)` with `COLLECTING`, `UNSTABLE`, and `USABLE`.
- Adds config fields `reference_max_head_speed_deg_s: float = 20.0`, `reference_max_blink: float = 0.55`, and `minimum_turning_point_separation_s: float = 0.10`.
- Produces frozen `DetectorSessionSummary(final_timestamp_s, accepted_reference_frames, rejected_reference_frames, accepted_reference_duration_s, feature_sample_counts, unavailable_action_ids)`.
- Extends `ActionSnapshot` with `reference_quality: ReferenceQuality` and `unavailable_action_ids: tuple[str, ...]` using backward-compatible defaults.
- Produces `ReferenceFrameGate(config).evaluate(frame) -> tuple[bool, str | None]` and `reset_contiguous()`.
- Adds `BaselineModel.sample_counts() -> dict[str, int]` and `accepted_frame_count`.
- Adds `ActionDetector.session_summary() -> DetectorSessionSummary`.

- [ ] **Step 1: Write failing configuration and immutable-type tests**

Add tests asserting exact enum values, backward-compatible `ActionSnapshot(ActionMode.TRACKING)` construction, config defaults, rejection of negative gate values, and immutability of `DetectorSessionSummary`.

```python
snapshot = ActionSnapshot(ActionMode.TRACKING)
self.assertEqual(snapshot.reference_quality, ReferenceQuality.COLLECTING)
self.assertEqual(ActionDetectionConfig().reference_max_head_speed_deg_s, 20.0)
with self.assertRaises(ValueError):
    ActionDetectionConfig(reference_max_blink=-0.1)
```

- [ ] **Step 2: Write failing reference-frame gate tests**

Cover acceptance of the first complete stable frame, rejection for missing pose, non-finite pose, missing blink, blink `>=0.55`, combined angular speed above `20 deg/s`, and acceptance at exactly the configured boundary. Assert a non-increasing timestamp raises the existing readable timestamp error, while a gap above `0.25s` resets continuity and does not compute speed across the gap.

- [ ] **Step 3: Write failing calibration integration tests**

Feed visible but moving/closed-eye frames and assert progress/sample count do not advance, mode remains `CALIBRATING`, and quality is `UNSTABLE`. Then feed 30 accepted frames spanning two accepted seconds and assert `USABLE`, exact accepted/rejected counts, per-feature sample counts, and deterministic unavailable IDs for a deliberately absent mouth group.

- [ ] **Step 4: Run focused tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_action_temporal tests.test_action_detection -v
```

Expected: missing types/gate/summary interfaces and calibration assertions fail.

- [ ] **Step 5: Implement gate and diagnostics**

`ReferenceFrameGate` computes combined head speed as:

```python
speed = (
    abs(yaw - previous_yaw)
    + abs(pitch - previous_pitch)
    + abs(roll - previous_roll)
) / elapsed_s
```

It accepts only finite pose, available blink below the configured maximum, valid timing, and speed at or below the configured maximum. Rejected frames call `BaselineModel.break_contiguous()` and increment a detector rejection count without adding feature samples.

- [ ] **Step 6: Implement availability mapping**

Define one explicit mapping from action IDs to required baseline feature names in `action_detection.py`. `session_summary()` reports the detector's last processed timestamp and marks an action unavailable when any required feature has fewer than `baseline_min_samples` finite accepted values. Face lifecycle IDs never appear in `unavailable_action_ids`.

- [ ] **Step 7: Run focused and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_action_temporal tests.test_action_detection -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all existing detection behavior remains green except labels intentionally changed in Task 2.

---

### Task 2: Scientifically Precise Labels And Robust Detection Rules

**Files:**
- Modify: `src/action_detection.py`
- Modify: `tests/test_action_detection.py`

**Interfaces:**
- Keeps `ActionDetector.update(frame) -> tuple[ActionSnapshot, tuple[ActionEvent, ...]]` unchanged.
- Keeps every current action ID unchanged.
- Produces helper `select_gaze_direction(raw_deltas, thresholds, dominance_margin) -> tuple[str | None, float]`.
- Produces timestamped head-speed history and separated turning-point detection using `minimum_turning_point_separation_s`.

- [ ] **Step 1: Write failing label-compatibility tests**

Assert revised display labels and unchanged IDs for all nine revised entries from the spec. Pin one representative event:

```python
self.assertEqual(display.action_id, "eyes_looking_down")
self.assertEqual(display.label, "Eye-look estimate: down")
```

- [ ] **Step 2: Write failing raw-delta gaze tests**

Create baseline samples with different MAD values per direction. Assert winner selection uses raw deltas, the winner must pass its own adaptive threshold, the raw winner-to-runner-up difference must be at least `0.08`, and normalized ratios cannot cause a smaller raw direction to win. Retain the `0.46` brow-raise false-down and sustained `0.63` deliberate-down cases.

- [ ] **Step 3: Write failing reference-relative eye-asymmetry tests**

Calibrate with a persistent left/right blink difference of `0.20`. Assert the same difference after calibration does not activate `asymmetric_eye_closure`, while a relative increase above the configured `0.25` floor held for `0.30s` does.

- [ ] **Step 4: Write failing head-speed and turning-point tests**

Assert one large one-frame pose spike does not activate generic head movement when the median speed window remains below threshold. Assert sustained multi-frame motion does. For nod/shake, feed sign changes less than `0.10s` apart and assert rejection, then separated qualifying excursions and assert activation.

- [ ] **Step 5: Run focused tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_action_detection -v
```

Expected: old labels, normalized-ratio gaze selection, absolute asymmetry, and two-frame speed behavior fail the new assertions.

- [ ] **Step 6: Implement the revised rules**

Select gaze using raw smoothed-minus-reference deltas before normalization. Store accepted reference asymmetry samples or derive paired reference samples in `BaselineModel`; do not subtract two independent medians as a substitute for median paired asymmetry. Maintain a deque of combined head speeds, evict by timestamp, and use its median. Turning points retain timestamps and reject candidates inside the configured separation.

- [ ] **Step 7: Run focused and full tests**

Use the Task 1 commands. Expected: all tests pass and event IDs/raw schemas remain unchanged.

---

### Task 3: Objective Event Analysis

**Files:**
- Create: `src/session_analysis.py`
- Create: `tests/test_session_analysis.py`

**Interfaces:**
- Produces `ANALYSIS_CSV_FIELDS` in the spec's exact order.
- Produces `SessionAnalysisRecorder(path, handle)`, `observe_event(event)`, `close(final_timestamp_s, remove_if_empty=False)`, `event_count`, and `closed`.
- Aggregates by stable action ID without retaining feature frames, images, or landmarks.

- [ ] **Step 1: Write failing aggregation tests**

Observe completed and interrupted events for two action IDs. Assert deterministic action-ID row ordering, exact counts, three-decimal times/durations, four-decimal max strength, and one final `session` row with the exact semantics from the spec.

Expected sample action row:

```text
action,eyes_looking_down,2,1,1,2.500,1.250,1.4200,4.000,8.200
```

- [ ] **Step 2: Write failing lifecycle/error tests**

Assert a valid header exists immediately after construction, `observe_event` rejects use after close, close is idempotent, final timestamp cannot precede observed event ends, and `remove_if_empty=True` removes only a session with no observed events.

- [ ] **Step 3: Run tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_session_analysis -v
```

Expected: `src.session_analysis` import fails.

- [ ] **Step 4: Implement streaming aggregation**

Use a small per-action dataclass containing counts, duration sum, peak maximum, first start, and last end. Write rows only during close. Do not read the event CSV back and do not retain individual events after aggregation.

- [ ] **Step 5: Run focused and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_session_analysis -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all pass.

---

### Task 4: Four-File Session Allocation And Metadata

**Files:**
- Create: `src/session_metadata.py`
- Modify: `src/recording_session.py`
- Modify: `src/session_recorder.py`
- Modify: `tests/test_action_event_recorder.py`
- Modify: `tests/test_session_recorder.py`
- Create: `tests/test_session_metadata.py`

**Interfaces:**
- Produces `SessionMetadataRecorder(path, handle, config, started_at)` with `update_summary(summary)` and idempotent `close(ended_at, status="closed")`.
- Extends `RecordingSession.create(directory, *, config=ActionDetectionConfig(), open_func=open, now_func=...)`.
- Adds `analysis_path`, `metadata_path`, and `update_detector_summary(summary)`.
- Allocates exact companion names `session_NNN_analysis.csv` and `session_NNN_metadata.json`.
- `RecordingSession.close(final_timestamp_s=0.0, remove_if_empty=False)` finalizes all four files and aggregates close errors.
- Changes `next_session_name()` to reserve raw, `_events.csv`, `_analysis.csv`, and `_metadata.json` names.

- [ ] **Step 1: Write failing metadata tests**

Assert valid JSON exists immediately with `status: recording`, schema/detector versions, filenames, complete serialized config, no participant/name field, and the interpretation boundary. After `update_summary` and close, assert `status: closed`, timestamps, accepted/rejected reference counts, feature counts, and unavailable IDs.

- [ ] **Step 2: Write failing allocation/race tests**

Cover an orphan file of each of the four suffixes, unrelated filenames, and an exclusive-open race independently on raw, event, analysis, and metadata paths. Assert a failed attempt removes only files created by that attempt and never deletes the pre-existing race winner.

- [ ] **Step 3: Write failing close-preservation tests**

Assert `write_event` updates both event CSV and in-memory analysis. Simulate analysis close failure followed by metadata close failure and assert raw/event close still occurs, populated raw/event files remain, and one `RecordingError` contains both messages. Assert header-only four-file startup cleanup removes all four files.

- [ ] **Step 4: Run focused tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_action_event_recorder tests.test_session_recorder tests.test_session_metadata -v
```

Expected: missing metadata interfaces, two-file-only allocation, and old naming pattern failures.

- [ ] **Step 5: Implement metadata and four-file ownership**

Create all members using exclusive mode. CSV handles use UTF-8, `newline=""`, and line buffering. JSON uses UTF-8 and is flushed after initial valid content. On finalization, seek to zero, truncate, write deterministic indented JSON, flush, then close.

- [ ] **Step 6: Implement collision cleanup and error aggregation**

Track ownership booleans per path. On any allocation failure, close and remove only files successfully created by the current attempt. During final close, attempt raw, event, analysis, and metadata finalization even after earlier failures; preserve populated data and report all errors together.

- [ ] **Step 7: Run focused and full tests**

Use the Task 4 focused command and full discovery. Expected: all pass and exact legacy headers remain unchanged.

---

### Task 5: Detector Summary Worker/Controller Integration

**Files:**
- Modify: `src/meeting_tracker.py`
- Modify: `src/app_controller.py`
- Modify: `tests/test_meeting_tracker.py`
- Modify: `tests/test_app_controller.py`

**Interfaces:**
- Extends `MeetingTracker` constructor with `session_summary_callback: Callable[[DetectorSessionSummary], None]` after `action_event_callback`.
- Worker invokes summary callback exactly once in `finally`, after final interrupted events and before `STOPPED`.
- Controller routes the callback to `RecordingSession.update_detector_summary` under the same generation token.
- Controller closes with the last processed timestamp supplied by the tracker summary.

- [ ] **Step 1: Write failing worker ordering tests**

Inject a detector whose `interrupt()` returns a final event and whose
`session_summary()` returns a known immutable summary. Assert callback order:

```text
raw feature -> regular events/overlay -> final interrupted event
-> detector summary -> ERROR if present -> STOPPED
```

Assert Pause does not publish the final summary and Stop publishes it once.

- [ ] **Step 2: Write failing controller generation tests**

Assert the final event and summary both reach the active `RecordingSession`
before generation increment and close. Invoke captured event/summary callbacks
after Stop and assert both are ignored. Start a second generation and assert a
stale first-generation summary cannot alter its metadata.

- [ ] **Step 3: Write failing startup/error cleanup tests**

Assert four files are allocated before overlay/worker creation, an overlay or
worker startup failure removes a wholly empty four-file set, and a runtime
summary/analysis failure preserves sessions with raw or event rows.

- [ ] **Step 4: Run integration tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_meeting_tracker tests.test_app_controller -v
```

Expected: constructor/callback/final-timestamp assertions fail.

- [ ] **Step 5: Implement callback and close ordering**

The worker obtains the final processed timestamp from
`DetectorSessionSummary.final_timestamp_s`. In `finally`, publish final events,
then summary, then terminal
tracker events. The controller joins the worker, then invalidates generation,
then closes the recording with the final timestamp.

- [ ] **Step 6: Run focused and full tests**

Use the Task 5 focused command and full discovery. Expected: all pass with no GUI opening.

---

### Task 6: Overlay Diagnostics And Read-Only Replay

**Files:**
- Modify: `src/overlay_renderer.py`
- Modify: `tests/test_overlay_renderer.py`
- Create: `scripts/analyze_session.py`
- Create: `tests/test_analyze_session.py`

**Interfaces:**
- Renderer consumes `ActionSnapshot.reference_quality` without changing `render_overlay_rgb` signature.
- Produces `scripts.analyze_session.load_feature_rows(path)` and `analyze(path, output_stream) -> int`.
- Replay writes only to the supplied text stream; it never modifies source data or creates session files.

- [ ] **Step 1: Write failing overlay copy tests**

Assert exact text `Calibrating reference... 64%` for collecting quality and
`Hold still for reference` for unstable quality. Assert existing tracking,
face-missing, reacquired, pause, FPS, four-row, bounds, and dither tests remain
unchanged.

- [ ] **Step 2: Write failing replay parser tests**

Use temporary raw CSV fixtures with the exact 29-column header. Assert blank
optional values become `None`, booleans parse strictly, malformed headers and
non-monotonic timestamps produce readable errors, and input bytes remain
unchanged after analysis.

- [ ] **Step 3: Write failing replay report tests**

Assert stdout includes reference completion time, accepted/rejected counts,
unavailable action IDs, event counts, maximum simultaneous actions, and the
objective per-action analysis table. Assert no confusion/emotion/attention
score appears.

- [ ] **Step 4: Run tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_overlay_renderer tests.test_analyze_session -v
```

Expected: old calibration text and missing replay module fail.

- [ ] **Step 5: Implement renderer and replay CLI**

CLI usage is exact:

```powershell
.\.venv\Scripts\python.exe .\scripts\analyze_session.py "C:\path\session_001.csv"
```

The script imports production `FeatureFrame`, `ActionDetector`, and analysis
aggregation helpers. It emits a text report only. It does not instantiate MSS,
MediaPipe landmarker, Tkinter, or any recorder.

- [ ] **Step 6: Run focused and full tests**

Use the Task 6 focused command and full discovery. Expected: all pass.

---

### Task 7: Documentation, Replay Evidence, And Privacy Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/system-outputs-and-observable-actions.md`
- Modify: `.superpowers/sdd/2026-09-25-scientifically-grounded-output-analysis/progress.md`

**Interfaces:**
- Documents four-file output, session-reference terminology, revised labels,
  analysis/metadata schemas, replay command, threshold provenance, and future
  separate manual labels.

- [ ] **Step 1: Update user documentation**

Document the `Hold still for reference` behavior, revised labels with stable
IDs, exact four filenames, analysis columns, metadata fields, and read-only
replay command. State that no accuracy percentage or psychological inference is
available without independent labels.

- [ ] **Step 2: Update the full output catalog**

For every threshold table, add provenance `Engineering heuristic; pending
empirical validation`. Replace neutral-baseline terminology, explain median
absolute deviation in full, and add known confounds: lighting, blur, face
resolution, distance, occlusion, glasses, mirror orientation, head pose,
person-specific morphology, jitter, FPS, and frame gaps.

- [ ] **Step 3: Replay the supplied session read-only**

```powershell
.\.venv\Scripts\python.exe .\scripts\analyze_session.py ".\data\session_006.csv"
```

Record reference completion time, accepted/rejected counts, unavailable IDs,
event counts, and maximum displayed actions in the ledger. Hash the file before
and after and assert hashes match.

- [ ] **Step 4: Run final automated verification**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import ast,pathlib; files=list(pathlib.Path('src').glob('*.py'))+list(pathlib.Path('tests').glob('*.py'))+list(pathlib.Path('scripts').glob('*.py')); [ast.parse(path.read_text(encoding='utf-8')) for path in files]; print(f'syntax ok: {len(files)} files')"
```

Expected: every test passes, requirements are consistent, and every Python file parses.

- [ ] **Step 5: Run storage/scope scans**

```powershell
rg -n "VideoWriter|imwrite|\.shot\(|\.save\(|requests\.|socket\.|urlopen" src
rg -n "confus|emotion|engagement|cognitive|attention|fatigue|agreement|understanding" src
rg -n "participant|student_name|raw_landmark" src
```

Expected: no runtime media/network writer, no prohibited inferred output, and no identity/raw-landmark persistence. Documentation strings that prohibit these concepts are allowed outside `src`.

- [ ] **Step 6: Run four-file smoke test**

In a temporary directory, create `RecordingSession`, write one missing-face raw
frame and one completed synthetic event, update a synthetic detector summary,
close, parse all four outputs, and assert same session number, exact legacy
headers, valid analysis rows, and valid closed metadata. Ensure all readers are
closed before temporary cleanup on Windows.

- [ ] **Step 7: Leave real-world accuracy claims to future labeled validation**

Manual acceptance verifies only observable movements, stable calibration, file
creation, and timestamp alignment. Do not report precision, recall, F1, or an
accuracy percentage until independently labeled consented data exists.

## Completion Definition

- All seven tasks have focused RED-to-GREEN evidence and a final green suite.
- Raw/event schemas and IDs are backward compatible.
- Reference-quality gating and robust detector changes are active in the live worker.
- Every session owns raw, event, analysis, and metadata files with collision-safe numbering.
- Replay is read-only and uses production detection code.
- Documentation distinguishes coefficients, observable events, and unsupported psychological inference.
- No manual webcam/meeting claim is made until the user performs consented acceptance testing.
