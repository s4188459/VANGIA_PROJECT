# Facial Feature Recording Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic, local CSV recording and real-time control-panel display of MediaPipe facial features whenever meeting-region tracking starts.

**Architecture:** Replace legacy Face Mesh inference with one MediaPipe Tasks Face Landmarker in VIDEO mode, then convert each result into an immutable `FeatureFrame`. The worker publishes that frame to a thread-safe UI latest-value slot and a CSV recorder while continuing to publish pixel landmarks to the existing transparent overlay. The controller owns recording lifecycle so Stop, Reselect, errors, and Quit deterministically close the file.

**Tech Stack:** Python 3.12, MediaPipe 0.10.21 Tasks API, MSS 10.2.0, OpenCV 4.11.0.86, NumPy, Tkinter, Python `csv`, `pathlib`, and `unittest`

**Spec:** `docs/superpowers/specs/2026-09-24-facial-feature-recording-design.md`

## Global Constraints

- Windows 10 2004+ or Windows 11 remains required for capture-excluded windows.
- Use one local `models/face_landmarker.task`; runtime code performs no network access.
- Track at most one face and keep `num_faces=1` so MediaPipe smoothing remains enabled.
- `confidence` is always blank; never invent or label an estimated score as detection confidence.
- Do not save video, images, screenshots, audio, raw frames, or raw landmark arrays.
- Do not implement confusion, emotion, attention, cognitive-load classification, lecturer alerts, cloud services, or model training.
- Start begins tracking and recording together; Pause writes no rows; Resume preserves the original elapsed-time clock.
- Existing files must never be overwritten.
- Tk objects are created, updated, and destroyed only on the main thread.
- The workspace is not a Git repository; do not initialize Git or create commits. Record execution evidence in `.superpowers/sdd/2026-09-24-facial-feature-recording/progress.md` instead.

## Review Focus

- If another `session_XXX.csv` appears between filename preview and Start, exclusive creation must choose another number without overwriting it; Task 2 tests this race.
- Multiple frames within one clock millisecond and a long Pause must still produce strictly increasing MediaPipe timestamps while CSV elapsed time keeps the pause gap; Task 4 tests both.
- Missing blendshapes, no transformation matrix, or a malformed matrix must leave only affected fields blank and keep the session alive; Task 1 tests these cases.
- Model startup failure must remove a newly created header-only CSV, while a later capture/write failure must preserve all rows already written; Task 5 tests both cleanup paths.
- A stale worker callback after Stop or Reselect must not write to a closed/new recorder or update the current panel; Task 5 tests generation-token rejection.

Before Task 1, create `.superpowers/sdd/2026-09-24-facial-feature-recording/progress.md`. Its first line must identify this plan path; append each RED/GREEN command result, review finding, native-model check, and any implementation ruling as work proceeds.

---

### Task 1: Immutable Facial Feature Model And Extraction

**Files:**
- Create: `src/feature_data.py`
- Create: `tests/test_feature_data.py`

**Interfaces:**
- Produces: frozen `FeatureFrame` with the CSV fields from the accepted spec.
- Produces: `extract_feature_frame(result, timestamp_s: float, frame_index: int) -> FeatureFrame`.
- Produces: `matrix_to_euler_degrees(matrix) -> tuple[float, float, float] | None` returning `(yaw, pitch, roll)`.
- Produces: `gaze_label(frame: FeatureFrame, threshold: float = 0.2) -> str`.
- Produces: `LatestFeatureFrame.publish(frame)`, `take()`, and `clear()`.

- [ ] **Step 1: Write failing tests for visible and missing faces**

Create fake results whose landmarks expose `x`, `y`, and `z`; categories expose `category_name` and `score`; matrices are NumPy arrays. Pin the complete expected record:

```python
frame = extract_feature_frame(result, timestamp_s=12.4, frame_index=8)
self.assertTrue(frame.face_visible)
self.assertIsNone(frame.confidence)
self.assertAlmostEqual(frame.blink, 0.2)
self.assertAlmostEqual(frame.brow_raise, 0.7)
self.assertAlmostEqual(frame.mouth_activity, 0.8)

missing = extract_feature_frame(empty_result, 13.0, 9)
self.assertFalse(missing.face_visible)
self.assertIsNone(missing.head_yaw_deg)
self.assertIsNone(missing.blink)
```

- [ ] **Step 2: Write failing mapping and robustness tests**

Assert gaze mapping by name rather than category order:

```python
self.assertAlmostEqual(frame.gaze_left, (eye_look_out_left + eye_look_in_right) / 2)
self.assertAlmostEqual(frame.gaze_right, (eye_look_in_left + eye_look_out_right) / 2)
```

Also assert:

- an identity matrix returns `(0, 0, 0)`;
- known X/Y/Z rotations return expected pitch/yaw/roll within `0.01` degrees;
- the gimbal-lock branch returns finite values;
- malformed or absent matrices produce `None` orientation fields without raising;
- a missing expected blendshape leaves that direct field and dependent aggregate blank;
- `gaze_label` returns `Center` below `0.2` and the strongest direction above it;
- publishing A then B returns B once from `LatestFeatureFrame`.

- [ ] **Step 3: Run the focused tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_feature_data -v
```

Expected: import failure because `src.feature_data` does not exist.

- [ ] **Step 4: Implement the data model and extraction**

Define all numeric feature fields as `float | None`. Build a `{category_name: score}` dictionary, calculate named direct scores, then calculate aggregates only when every required operand is present. For head center/depth, average all returned landmarks. Use the rotation convention accepted in the spec: pitch around X, yaw around Y, and roll around Z, including an explicit near-singular branch.

The immutable shape must contain exactly:

```python
@dataclass(frozen=True)
class FeatureFrame:
    timestamp_s: float
    frame_index: int
    face_visible: bool
    confidence: float | None
    head_center_x: float | None
    head_center_y: float | None
    head_depth: float | None
    head_yaw_deg: float | None
    head_pitch_deg: float | None
    head_roll_deg: float | None
    gaze_left: float | None
    gaze_right: float | None
    gaze_up: float | None
    gaze_down: float | None
    blink_left: float | None
    blink_right: float | None
    blink: float | None
    brow_inner_up: float | None
    brow_outer_up_left: float | None
    brow_outer_up_right: float | None
    brow_down_left: float | None
    brow_down_right: float | None
    brow_raise: float | None
    jaw_open: float | None
    mouth_smile_left: float | None
    mouth_smile_right: float | None
    mouth_pucker: float | None
    mouth_funnel: float | None
    mouth_activity: float | None
```

- [ ] **Step 5: Run focused and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_feature_data -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass and no GUI opens.

---

### Task 2: Collision-Safe CSV Session Recorder

**Files:**
- Create: `src/session_recorder.py`
- Create: `tests/test_session_recorder.py`

**Interfaces:**
- Consumes: `FeatureFrame` from Task 1.
- Produces: `CSV_FIELDS: tuple[str, ...]` in accepted schema order.
- Produces: `next_session_name(directory: Path) -> str` for UI preview.
- Produces: `CsvSessionRecorder.create(directory: Path, *, open_func=open) -> CsvSessionRecorder` using exclusive mode `"x"`.
- Produces properties: `path: Path`, `row_count: int`, `closed: bool`.
- Produces methods: `write(frame)`, `close(*, remove_if_empty: bool = False)`.

- [ ] **Step 1: Write failing allocation and no-overwrite tests**

Using `tempfile.TemporaryDirectory`, assert:

```python
self.assertEqual(next_session_name(folder), "session_001.csv")
(folder / "session_001.csv").touch()
(folder / "session_003.csv").touch()
self.assertEqual(next_session_name(folder), "session_004.csv")
```

Simulate a race by making the first exclusive `open` raise `FileExistsError`; assert `create()` retries the next number. Assert unrelated names do not affect numbering and nonexistent/unwritable directories raise readable `RecordingError` values.

- [ ] **Step 2: Write failing CSV formatting and cleanup tests**

Write one visible and one missing-face `FeatureFrame`, close, and read with `csv.DictReader`. Assert:

- exact header order;
- `true`/`false` lowercase;
- timestamp has three decimal places;
- feature values have fixed decimal formatting;
- `confidence` and missing-face features are empty strings;
- `row_count == 2`;
- double close is harmless;
- write after close raises `RecordingError`;
- `close(remove_if_empty=True)` removes header-only output but never removes a file with one row.

- [ ] **Step 3: Run tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_session_recorder -v
```

Expected: import failure because `src.session_recorder` does not exist.

- [ ] **Step 4: Implement exclusive allocation and CSV writing**

Use a strict regular expression `^session_(\d+)\.csv$`, maximum existing number plus one, then an exclusive-open retry loop. Open with `encoding="utf-8"`, `newline=""`, and line buffering. Use `csv.DictWriter` and an explicit serializer:

```python
def _format_value(name, value):
    if value is None:
        return ""
    if name == "face_visible":
        return "true" if value else "false"
    if name == "timestamp_s":
        return f"{value:.3f}"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)
```

Wrap create, write, flush, close, and optional deletion failures in `RecordingError` while preserving the original message.

- [ ] **Step 5: Run focused and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_session_recorder -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass.

---

### Task 3: MediaPipe Tasks Adapter And Model Setup

**Files:**
- Create: `src/face_landmarker.py`
- Create: `scripts/download_face_landmarker_model.py`
- Create: `tests/test_face_landmarker.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `DEFAULT_MODEL_PATH = <project>/models/face_landmarker.task`.
- Produces: `FaceLandmarkerConfigurationError`.
- Produces: `create_face_landmarker(model_path=DEFAULT_MODEL_PATH, *, tasks=mp.tasks) -> context manager`.
- Produces: download script using the official model URL `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task`.

- [ ] **Step 1: Write failing adapter configuration tests**

Inject a fake Tasks API and assert `create_face_landmarker()` passes:

```python
running_mode=RunningMode.VIDEO
num_faces=1
output_face_blendshapes=True
output_facial_transformation_matrixes=True
min_face_detection_confidence=0.5
min_face_presence_confidence=0.5
min_tracking_confidence=0.5
```

Assert a missing path raises `FaceLandmarkerConfigurationError` containing both `face_landmarker.task` and the documented download command. Assert an exception from `create_from_options` is wrapped with a readable invalid-model message.

- [ ] **Step 2: Run tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_face_landmarker -v
```

Expected: import failure because `src.face_landmarker` does not exist.

- [ ] **Step 3: Implement the factory and atomic downloader**

The adapter validates the local path before constructing `BaseOptions` and `FaceLandmarkerOptions`. The downloader uses only standard-library `urllib.request`, writes to `face_landmarker.task.part`, rejects an empty or implausibly small response, then atomically replaces the final path. It refuses to overwrite an existing valid model unless invoked with `--force`.

Add these ignore rules while preserving existing entries:

```gitignore
models/*.task
models/*.part
```

- [ ] **Step 4: Run focused and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_face_landmarker -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass without downloading a model.

- [ ] **Step 5: Download and validate the official model**

Request network approval, then run:

```powershell
.\.venv\Scripts\python.exe .\scripts\download_face_landmarker_model.py
.\.venv\Scripts\python.exe -c "from src.face_landmarker import create_face_landmarker; landmarker=create_face_landmarker(); landmarker.close(); print('Face Landmarker model: OK')"
```

Expected: a nonempty local `models/face_landmarker.task` and successful task construction. Do not run tracking or upload data during this check.

---

### Task 4: Migrate The Tracking Worker To Face Landmarker

**Files:**
- Modify: `src/meeting_tracker.py`
- Replace: `tests/test_meeting_tracker.py`

**Interfaces:**
- Consumes: `create_face_landmarker`, `extract_feature_frame`, `OverlayFrame`, and `landmarks_to_pixels`.
- Changes constructor to `MeetingTracker(region, event_callback, overlay_callback, feature_callback, *, mss_factory=MSS, landmarker_factory=create_face_landmarker, clock=time.perf_counter, sleep_func=time.sleep)`.
- Publishes one `FeatureFrame` and one `OverlayFrame` per processed result.

- [ ] **Step 1: Rewrite worker tests for the Tasks API**

Use fake MSS and fake landmarker boundaries. The fake landmarker exposes `detect_for_video(mp_image, timestamp_ms)` and records timestamps. Tests must assert:

- RGB input reaches a MediaPipe-image factory boundary;
- one visible result publishes matching overlay points and one feature frame;
- one empty result publishes `face_visible=false`, empty overlay points, and does not stop;
- two rapid frames receive strictly increasing integer timestamps even when the fake clock repeats;
- a Pause performs zero new grabs/detections/feature callbacks;
- after advancing the fake clock during Pause, Resume's next feature timestamp contains the time gap;
- capture, task, or feature-callback errors emit ERROR then STOPPED;
- no result callback contains captured NumPy image data.

- [ ] **Step 2: Run worker tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_meeting_tracker -v
```

Expected: constructor and fake-method failures against the old Face Mesh worker.

- [ ] **Step 3: Implement synchronous VIDEO-mode inference**

Keep inference on the existing worker thread. Convert contiguous RGB data to `mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)`, call `detect_for_video`, derive `FeatureFrame`, and fan it out. Generate task timestamps with:

```python
candidate_ms = int((clock() - session_start) * 1000)
timestamp_ms = max(candidate_ms, previous_timestamp_ms + 1)
```

Use `timestamp_ms / 1000.0` for the CSV feature timestamp, so the task input and recorded row share the same timebase. Increment `frame_index` only after a processed result. Retain current PAUSED, RESUMED, FACE_STATUS, ERROR, and STOPPED events.

- [ ] **Step 4: Run worker and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_meeting_tracker -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass; Pause produces no rows and missing faces continue.

---

### Task 5: Controller-Owned Recording Lifecycle

**Files:**
- Modify: `src/app_controller.py`
- Replace: `tests/test_app_controller.py`

**Interfaces:**
- Consumes: `CsvSessionRecorder.create`, `next_session_name`, and worker feature callbacks.
- Adds: `AppController.choose_save_folder()`, `stop()`, `_publish_feature(frame, generation)`, and `_close_recorder(remove_if_empty=False)`.
- View additions: `ask_save_folder() -> str`, `show_save_folder(path, next_name)`, `publish_features(frame, row_count, filename)`, and `clear_features()`.
- Preserves the existing `AppState` values; `stop()` transitions directly from RUNNING/PAUSED to READY after joining and cleanup.

- [ ] **Step 1: Write failing folder and Start gating tests**

Extend `FakeView` with folder and feature methods. Assert:

- Start with a region but no folder creates neither recorder nor tracker;
- canceling folder selection preserves the previous folder;
- choosing a folder updates the preview filename;
- Start creates recorder before worker, passes a feature callback, and displays the active filename;
- a recorder creation error creates no overlay or worker and leaves READY with the exact error.

- [ ] **Step 2: Write failing lifecycle and stale-callback tests**

Assert:

- `stop()` stops/joins the worker, closes recorder once, hides overlay, clears feature display, and returns READY;
- Pause/Resume does not close or recreate the recorder;
- Reselect performs Stop semantics before opening selection;
- Quit closes once and is idempotent;
- ERROR with zero rows closes using `remove_if_empty=True`;
- ERROR after one row preserves the partial file;
- STOPPED after ERROR does not overwrite the retained error status;
- a feature callback carrying an old generation token writes nothing and updates no panel;
- a write exception propagates back into the worker callback path and results in session cleanup.

- [ ] **Step 3: Run controller tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_app_controller -v
```

Expected: failures because the controller lacks recorder ownership, folder selection, and Stop.

- [ ] **Step 4: Implement lifecycle in one ownership boundary**

Store `_save_folder`, `_recorder`, and `_recording_generation` on the controller. The worker's feature callback must call recorder `write()` before `view.publish_features()` so the displayed row count always describes durable in-process CSV state. `_stop_worker()` joins first, then closes the recorder, preventing writes after close. Generation checks must happen before accessing the recorder.

Do not call Tk from the worker: `view.publish_features()` may only publish into the panel's lock-protected latest-value slot.

- [ ] **Step 5: Run controller and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_app_controller -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass.

---

### Task 6: Recording Controls And Real-Time Coefficient Panel

**Files:**
- Modify: `src/control_panel.py`
- Modify: `src/main.py`
- Modify: `tests/test_control_panel_keys.py`
- Create: `tests/test_feature_display.py`

**Interfaces:**
- Consumes: `LatestFeatureFrame`, `FeatureFrame`, `gaze_label`, and controller view additions from Task 5.
- Produces: `format_feature_display(frame, row_count, filename) -> dict[str, str]`.
- Produces view methods: `ask_save_folder`, `show_save_folder`, `publish_features`, and `clear_features`.
- Changes `bind_actions` to include `on_choose_folder` and `on_stop`.

- [ ] **Step 1: Write failing pure display-format tests**

Assert a visible feature renders concise strings:

```python
self.assertEqual(display["face"], "Visible")
self.assertEqual(display["head"], "Yaw 8.20 | Pitch -2.10 | Roll 1.40")
self.assertEqual(display["gaze"], "Up 0.71")
self.assertEqual(display["rows"], "248")
```

Assert a missing face renders `Not detected` and `--` feature values. Long filenames and paths must be shortened for display without changing the actual stored path.

- [ ] **Step 2: Extend fake-widget control tests and verify RED**

Assert:

- Choose Save Folder calls `tkinter.filedialog.askdirectory`;
- Start stays disabled in READY until both controller region state and panel folder state are present;
- folder selection is disabled while RUNNING/PAUSED;
- Stop is enabled only while RUNNING/PAUSED;
- Stop invokes the controller callback once and remains disabled outside RUNNING/PAUSED;
- publishing many feature frames before one draw renders only the newest frame;
- capture-exclusion failure still disables Select/Folder/Start/Pause/Stop while leaving Quit enabled.

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_feature_display tests.test_control_panel_keys -v
```

Expected: missing functions, methods, and controls.

- [ ] **Step 3: Implement the compact operational panel**

Add a folder row, Start/Pause/Stop controls with stable grid dimensions, and a compact coefficient grid for Recording, Elapsed, Face, Head, Gaze, Blink, Brow, Mouth, and Rows. Avoid nested cards and keep headings sized for a tool panel. Poll `LatestFeatureFrame` at 100 ms from Tk's main thread while the existing landmark overlay poll remains independent.

Keep shortcuts:

- `S`: Pause/Resume.
- `R`: stop current session then Reselect.
- `Q` or Escape: Quit.

Buttons remain authoritative; no global keyboard hook is introduced.

- [ ] **Step 4: Wire `main.py` actions and run tests**

Update `panel.bind_actions(...)` with `controller.choose_save_folder` and `controller.stop`, then run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_feature_display tests.test_control_panel_keys -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass and import tests create no Tk window.

---

### Task 7: Documentation, Privacy Audit, And End-To-End Verification

**Files:**
- Modify: `README.md`
- Modify: `.superpowers/sdd/2026-09-24-facial-feature-recording/progress.md`

**Interfaces:**
- Documents model setup, output schema, controls, privacy, interpretation limits, and manual acceptance.

- [ ] **Step 1: Update exact setup and run commands**

Document:

```powershell
cd .\facial-cue-prototype
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\scripts\download_face_landmarker_model.py
.\.venv\Scripts\python.exe .\src\main.py
```

Explain `confidence` is intentionally blank, angles are model-relative rather than medical measurements, scores are coefficients rather than emotion/confusion labels, and facial coefficients require appropriate consent.

- [ ] **Step 2: Document CSV and manual video-alignment workflow**

Include the exact column header and this sequence:

1. Start an external test video with a visible timer.
2. Choose region and save folder, then press Start near video zero.
3. Perform blink, gaze, brow, mouth, and head movements.
4. Leave and re-enter frame.
5. Pause for several seconds and Resume.
6. Stop, open CSV, and locate events by `timestamp_s`.
7. Confirm a timestamp gap matches Pause and a second Start creates a new file.

- [ ] **Step 3: Run final automated verification**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import ast,pathlib; files=list(pathlib.Path('src').glob('*.py'))+list(pathlib.Path('tests').glob('*.py'))+list(pathlib.Path('scripts').glob('*.py')); [ast.parse(path.read_text(encoding='utf-8')) for path in files]; print(f'syntax ok: {len(files)} files')"
```

Expected: all tests pass, no broken requirements, and every Python file parses.

- [ ] **Step 4: Run storage and privacy scans**

```powershell
rg -n "VideoWriter|imwrite|\.shot\(|\.save\(|requests\.|socket\.|urlopen" src
rg -n "landmark" src/session_recorder.py
```

Expected: no runtime media/network writer. The recorder contains no raw-landmark field or serialization. The setup downloader is the only permitted `urlopen` use and lives under `scripts/`.

- [ ] **Step 5: Perform a local model and synthetic recorder smoke test**

Construct the real Face Landmarker from the downloaded model, close it, then create a temporary recorder, write a synthetic missing-face row, close it, and parse it back. No screen capture or student data is used.

- [ ] **Step 6: Leave real-data acceptance to the user**

The user performs the documented Meet/Zoom and external-video test because it requires consented real facial input and visual timestamp comparison. Record the exact CSV path and any error message they report; never request or upload their CSV unless they explicitly choose to share it.
