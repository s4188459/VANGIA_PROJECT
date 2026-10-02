# Meeting Window Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace webcam input with a lecturer-selected Google Meet or Zoom video region, controlled through a small local GUI with start, pause/resume, reselection, and clean shutdown.

**Architecture:** A Tkinter control panel owns application state on the main thread. Region selection uses one temporary MSS screenshot and OpenCV's ROI selector; a single background worker continuously captures only the selected region, runs MediaPipe Face Mesh, and displays the annotated OpenCV preview. Dependencies are injected at controller and worker boundaries so automated tests never capture the real screen.

**Tech Stack:** Python 3.12, Tkinter, MSS 10.2.0, OpenCV 4.11.0.86, MediaPipe 0.10.21, NumPy 1.26.x, `unittest`, `threading`

**Spec:** `docs/superpowers/specs/2026-09-24-meeting-window-capture-design.md`

## Global Constraints

- Process only the primary monitor and one selected rectangular region.
- After selection, every continuous MSS `grab()` call must receive only the selected region.
- Keep `mediapipe==0.10.21` and `opencv-contrib-python==4.11.0.86`; pin `mss==10.2.0`.
- Detect and draw at most one face using MediaPipe Face Mesh.
- Do not save screenshots, video, landmarks, coordinates, or image-bearing logs.
- Do not call MSS `shot()`, `save()`, or any PNG/video writer.
- Tkinter operations remain on the main thread; capture and MediaPipe inference run in one background worker.
- `S` toggles pause/resume, `R` requests reselection, and `Q` or Escape shuts down while the preview has focus.
- Reselection stops the current worker and returns to Ready; the lecturer explicitly presses Start again.
- Automated tests must use fakes and in-memory arrays, never real screen capture.
- This workspace is not a Git repository. Do not initialize Git or create commits unless the user separately requests it.

## Review Focus

- An empty or cancelled ROI must preserve the previous valid region and state.
- Closing the OpenCV preview with its window close button must stop the worker and return the controller to Ready.
- Rapid repeated Start clicks must never create more than one worker.
- Pause must stop new `grab()` and MediaPipe calls while still accepting Resume or Quit from both UI and preview.
- A capture or MediaPipe exception must close only the preview, preserve the region, and leave the control panel usable in Ready with an error message.

---

### Task 1: Dependencies, Domain Types, and Key Actions

**Files:**
- Modify: `requirements.txt`
- Create: `src/capture_types.py`
- Modify: `src/app_utils.py`
- Create: `tests/test_capture_types.py`
- Modify: `tests/test_app_utils.py`
- Modify: `tests/test_dependencies.py`

**Interfaces:**
- Produces: `CaptureRegion(left: int, top: int, width: int, height: int)`
- Produces: `CaptureRegion.as_mss_region() -> dict[str, int]`
- Produces: `AppState` enum values `NO_REGION`, `READY`, `RUNNING`, `PAUSED`, `SHUTTING_DOWN`
- Produces: `PreviewAction` enum values `NONE`, `TOGGLE_PAUSE`, `RESELECT`, `QUIT`
- Produces: `preview_action(key_code: int) -> PreviewAction`

- [ ] **Step 1: Add failing domain and shortcut tests**

Create `tests/test_capture_types.py`:

```python
import unittest

from src.capture_types import AppState, CaptureRegion


class CaptureRegionTests(unittest.TestCase):
    def test_valid_region_converts_to_mss_dictionary(self):
        region = CaptureRegion(left=100, top=200, width=640, height=360)
        self.assertEqual(
            region.as_mss_region(),
            {"left": 100, "top": 200, "width": 640, "height": 360},
        )

    def test_zero_or_negative_dimensions_are_rejected(self):
        for width, height in ((0, 10), (10, 0), (-1, 10), (10, -1)):
            with self.subTest(width=width, height=height):
                with self.assertRaises(ValueError):
                    CaptureRegion(0, 0, width, height)

    def test_application_states_are_distinct(self):
        self.assertEqual(len(AppState), 5)


if __name__ == "__main__":
    unittest.main()
```

Extend `tests/test_app_utils.py` with assertions that `S/s`, `R/r`, `Q/q`, Escape, and an unrelated key map to the exact `PreviewAction` values.

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_capture_types tests.test_app_utils -v
```

Expected: FAIL because `src.capture_types`, `PreviewAction`, and `preview_action` do not exist.

- [ ] **Step 3: Implement the domain types and key mapping**

Create `src/capture_types.py` with frozen `CaptureRegion`, validation in `__post_init__`, `as_mss_region`, and the five-value `AppState` enum. Add `PreviewAction` and `preview_action` to `src/app_utils.py`. Preserve the existing `should_exit()` API for its Milestone 1 tests.

Key mapping must be:

```python
def preview_action(key_code: int) -> PreviewAction:
    if key_code in {ord("s"), ord("S")}:
        return PreviewAction.TOGGLE_PAUSE
    if key_code in {ord("r"), ord("R")}:
        return PreviewAction.RESELECT
    if key_code in EXIT_KEYS:
        return PreviewAction.QUIT
    return PreviewAction.NONE
```

- [ ] **Step 4: Pin MSS and strengthen dependency checks**

Append `mss==10.2.0` to `requirements.txt`. Extend `tests/test_dependencies.py` to import `MSS` from `mss`, assert it is callable, and retain the existing MediaPipe Face Mesh assertions.

- [ ] **Step 5: Install dependencies and run Task 1 tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest tests.test_capture_types tests.test_app_utils tests.test_dependencies -v
.\.venv\Scripts\python.exe -m pip check
```

Expected: all tests pass and pip prints `No broken requirements found.`

---

### Task 2: Primary-Monitor Region Selection

**Files:**
- Create: `src/region_selector.py`
- Create: `tests/test_region_selector.py`

**Interfaces:**
- Consumes: `CaptureRegion`
- Produces: `absolute_region(monitor_left: int, monitor_top: int, roi: tuple[int, int, int, int]) -> CaptureRegion | None`
- Produces: `select_primary_monitor_region() -> CaptureRegion | None`

- [ ] **Step 1: Write coordinate-conversion tests**

Create tests covering a normal ROI, a primary monitor with negative desktop coordinates, zero width, and zero height:

```python
class AbsoluteRegionTests(unittest.TestCase):
    def test_adds_monitor_origin_to_relative_roi(self):
        self.assertEqual(
            absolute_region(100, 50, (20, 30, 640, 360)),
            CaptureRegion(120, 80, 640, 360),
        )

    def test_supports_negative_monitor_origin(self):
        self.assertEqual(
            absolute_region(-1920, 0, (100, 40, 500, 300)),
            CaptureRegion(-1820, 40, 500, 300),
        )

    def test_empty_roi_is_cancelled(self):
        self.assertIsNone(absolute_region(0, 0, (10, 20, 0, 100)))
        self.assertIsNone(absolute_region(0, 0, (10, 20, 100, 0)))
```

- [ ] **Step 2: Run the selector tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_region_selector -v
```

Expected: FAIL because `src.region_selector` does not exist.

- [ ] **Step 3: Implement coordinate conversion**

Implement `absolute_region()` as a pure function. Convert OpenCV's ROI numbers to integers; return `None` for empty dimensions; otherwise add the monitor origin to ROI `x/y` and return `CaptureRegion`.

- [ ] **Step 4: Implement the real selector without disk writes**

Use the MSS 10.2 API:

```python
from mss import MSS

with MSS() as screen:
    monitor = screen.primary_monitor
    screenshot = screen.grab(monitor)
    frame = screenshot.to_numpy(channels="BGR")
```

Pass the in-memory `frame` to `cv2.selectROI("Select student video", frame, showCrosshair=True, fromCenter=False)`. Always call `cv2.destroyWindow()` in `finally`. Return `absolute_region(monitor.left, monitor.top, roi)`. Do not import or call `mss.tools`.

- [ ] **Step 5: Run selector and full regression tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_region_selector -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass without opening a selector because automated tests exercise only the pure conversion boundary.

---

### Task 3: Frame Conversion and Preview Rendering

**Files:**
- Create: `src/frame_processing.py`
- Create: `tests/test_frame_processing.py`

**Interfaces:**
- Produces: `prepare_frames(bgr_frame: numpy.ndarray) -> tuple[numpy.ndarray, numpy.ndarray]`
- Produces: `draw_overlay(frame: numpy.ndarray, status: str, fps: float, paused: bool = False) -> None`
- Consumes: existing `format_fps()`

- [ ] **Step 1: Write in-memory frame tests**

Use a 2x2 BGR NumPy array with distinct channel values. Assert that `prepare_frames()` returns an unchanged BGR copy for preview, an RGB array with channels reversed for MediaPipe, equal height/width, three channels, and no shared writable memory. Add an overlay smoke test asserting the input frame shape remains unchanged.

- [ ] **Step 2: Run frame tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_frame_processing -v
```

Expected: FAIL because `src.frame_processing` does not exist.

- [ ] **Step 3: Implement conversion and overlay**

`prepare_frames()` receives the BGR output from `ScreenShot.to_numpy(channels="BGR")`, copies it for preview, and uses `cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)` for MediaPipe. `draw_overlay()` draws a fixed `320x82` black panel, status text, and `FPS: 000.0`; when paused it displays `Paused` and retains the last FPS value.

- [ ] **Step 4: Run frame and regression tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_frame_processing -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass.

---

### Task 4: Screen-Capture and MediaPipe Worker

**Files:**
- Create: `src/meeting_tracker.py`
- Create: `tests/test_meeting_tracker.py`

**Interfaces:**
- Consumes: `CaptureRegion`, `PreviewAction`, `prepare_frames()`, `draw_overlay()`
- Produces: `TrackerEvent(kind: TrackerEventKind, message: str = "")`
- Produces: `TrackerEventKind` values `FACE_STATUS`, `PAUSED`, `RESUMED`, `RESELECT`, `STOPPED`, `ERROR`, `QUIT`
- Produces: `MeetingTracker(region, event_callback, *, mss_factory=MSS, face_mesh_factory=None)`
- Produces methods: `start()`, `pause()`, `resume()`, `stop()`, `is_alive() -> bool`

- [ ] **Step 1: Write worker lifecycle tests with fakes**

Create fake MSS and Face Mesh objects that record calls and return an in-memory frame/result. Test:

- `start()` creates one daemon thread and rejects a second start while alive.
- Every fake MSS `grab()` argument equals `region.as_mss_region()`.
- Face Mesh receives an RGB three-channel frame.
- Calling `pause()` prevents the fake grab count from increasing after the worker acknowledges pause.
- Calling `resume()` allows the count to increase again.
- `stop()` terminates the thread and closes the worker-owned resources.
- Capture and inference exceptions emit `ERROR` followed by `STOPPED` rather than escaping the thread.

Inject no-op preview functions in tests so `cv2.imshow()` is never called.

- [ ] **Step 2: Run worker tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_meeting_tracker -v
```

Expected: FAIL because `MeetingTracker` and tracker events do not exist.

- [ ] **Step 3: Implement thread lifecycle and pause control**

Use `threading.Event` instances named `_stop_event` and `_pause_event`. `start()` must raise `RuntimeError("Tracker is already running")` if the previous thread is alive. `stop()` sets the stop event and joins from non-worker threads with a short bounded timeout; the worker closes its MSS/MediaPipe context and OpenCV preview in `finally`.

While paused, do not call MSS or MediaPipe. Continue displaying the last frame with a Paused overlay and poll `cv2.waitKey(20)` so preview shortcuts remain responsive.

- [ ] **Step 4: Implement the processing loop**

Create MediaPipe Face Mesh with the Milestone 1 settings: `max_num_faces=1`, `refine_landmarks=True`, and detection/tracking confidence `0.5`. For each frame:

1. Call `screen.grab(region.as_mss_region())`.
2. Convert via `screenshot.to_numpy(channels="BGR")` and `prepare_frames()`.
3. Call `face_mesh.process(rgb_frame)`.
4. Draw tessellation and contours for the one returned face.
5. Emit `FACE_STATUS` only when detected/not-detected status changes.
6. Draw status and FPS, show the preview, and translate the key through `preview_action()`.
7. `S` toggles the worker pause event; `R` emits `RESELECT` and exits; `Q`/Escape emits `QUIT` and exits.
8. Detect manual preview closure with `cv2.getWindowProperty(..., cv2.WND_PROP_VISIBLE) < 1`, then exit normally with `STOPPED`.

- [ ] **Step 5: Run worker and full tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_meeting_tracker -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass; tests do not capture or display the real screen.

---

### Task 5: Application Controller State Machine

**Files:**
- Create: `src/app_controller.py`
- Create: `tests/test_app_controller.py`

**Interfaces:**
- Consumes: `AppState`, `CaptureRegion`, `MeetingTracker`, `select_primary_monitor_region()`
- Requires view methods: `render(state: AppState, status: str) -> None`, `schedule(callback: Callable[[], None]) -> None`, `close() -> None`
- Produces controller methods: `select_region()`, `start()`, `toggle_pause()`, `handle_tracker_event(event)`, `shutdown()`

- [ ] **Step 1: Write state transition tests with fake view/selector/tracker**

Cover all transitions in the spec and Review Focus:

- Initial state is `NO_REGION`; Start and pause do nothing.
- Successful selection sets `READY`; cancelled initial selection stays `NO_REGION`.
- Start creates exactly one tracker and sets `RUNNING`; repeated Start does not create another.
- Toggle moves `RUNNING -> PAUSED -> RUNNING` and calls worker pause/resume once.
- Cancelled reselection preserves the old region. If the previous state was `RUNNING` or `PAUSED`, it creates a fresh worker for the old region and restores that exact state; if it was `READY`, it remains `READY`.
- Successful reselection stops the worker, replaces the region, and sets `READY`.
- `STOPPED` from preview closure returns to `READY` unless shutdown is in progress.
- `ERROR` preserves the region and renders a readable Ready-state error.
- `QUIT` invokes shutdown.
- Shutdown is idempotent and closes the view once.

- [ ] **Step 2: Run controller tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_app_controller -v
```

Expected: FAIL because `AppController` does not exist.

- [ ] **Step 3: Implement controller transitions**

Keep state writes in one `_set_state(state, status)` helper that calls `view.render`. `select_region()` records the previous state and region, then stops any current worker before opening selection. On cancellation, recreate the worker for the old region when necessary and restore `RUNNING` or `PAUSED`; a paused restoration starts the worker and immediately pauses it. `handle_tracker_event()` must always enter through `view.schedule(...)` when called from the worker so Tkinter is never touched from the worker thread.

Use the following visible status strings exactly:

```text
No region selected
Ready
Running - Face detected
Running - Face not detected
Paused
Selection cancelled
Ready - <error message>
```

- [ ] **Step 4: Run controller and full tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_app_controller -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass.

---

### Task 6: Tkinter Control Panel and Entry Point

**Files:**
- Create: `src/control_panel.py`
- Replace: `src/main.py`
- Create: `tests/test_main_import.py`

**Interfaces:**
- Consumes: `AppState`, controller callback methods
- Produces: `ControlPanel(root: tkinter.Tk)` implementing `render`, `schedule`, and `close`
- Produces: `ControlPanel.bind_actions(on_select, on_start, on_toggle_pause, on_quit) -> None`
- Produces: `main.run() -> int`

- [ ] **Step 1: Write import-safety and availability tests**

Create `tests/test_main_import.py` to import `tkinter`, `src.control_panel`, and `src.main` without creating a `Tk()` root or opening any window. Assert that `src.main.run` is callable and the window title constant equals `Milestone 2 - Meeting Window Capture`.

- [ ] **Step 2: Run import tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_main_import -v
```

Expected: FAIL because the new control panel and title do not exist.

- [ ] **Step 3: Implement the compact control panel**

Build one non-resizable Tkinter window with:

- Heading `Meeting Window Capture`.
- A wrapping status label.
- Buttons `Select Region`, `Start`, `Pause`, and `Quit` in one predictable grid.
- Button states derived solely from `AppState`.
- Pause button text changing to `Resume` only in `PAUSED`.
- `WM_DELETE_WINDOW` delegated to controller shutdown.

Construct the panel before the controller, then call `bind_actions()` after the controller exists. This avoids creating the Tk root or controller at module import time and avoids circular construction.

Use standard `ttk` widgets and platform-default colors. Do not place instructions, screenshots, captured frames, or extra feature descriptions in the control panel.

- [ ] **Step 4: Replace the webcam entry point**

`src/main.py` must set `MPLCONFIGDIR` before importing MediaPipe-dependent modules, provide beginner-readable missing dependency messages for OpenCV, MediaPipe, and MSS, create `Tk`, `ControlPanel`, and `AppController`, wire callbacks, call `root.mainloop()`, and return `0` after shutdown. Keep all object creation inside `run()` so import tests remain headless.

- [ ] **Step 5: Run import and full tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_main_import -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

Expected: all tests pass, no GUI opens during tests, and pip reports no broken requirements.

---

### Task 7: Documentation and Manual Acceptance

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents the executable interface implemented by Tasks 1-6.

- [ ] **Step 1: Rewrite README scope and architecture**

Change the title to Milestone 2 and explain MSS, the primary-monitor region selector, Tkinter control panel, MediaPipe processing, and the fact that Milestone 1 webcam input has been replaced. Preserve the explicit statement that no video, images, or landmarks are saved.

- [ ] **Step 2: Add exact setup and run commands**

Document:

```powershell
cd .\facial-cue-prototype
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\src\main.py
```

Document the four buttons and `S`, `R`, `Q`, Escape shortcuts. State that the preview window must have focus for shortcuts and that moving/resizing Meet or Zoom requires `R` or Select Region.

- [ ] **Step 3: Add exact manual acceptance procedure**

Document these checks:

1. Open a Meet/Zoom test call and show one participant tile on the primary monitor.
2. Start the app and choose Select Region.
3. Drag a rectangle containing only that tile and confirm the selection.
4. Press Start; verify the preview contains no pixels outside the rectangle.
5. Move a face into/out of the tile; verify status and landmarks change correctly.
6. Pause for several seconds; verify the preview says Paused and does not update.
7. Resume; verify processing continues.
8. Move the meeting window, press `R`, select the new location, and press Start again.
9. Test both `Q` and Escape in separate runs and verify the control panel and preview close.
10. Confirm no image or video files were created in the project directory.

- [ ] **Step 4: Run final automated verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import ast, pathlib; [ast.parse(path.read_text(encoding='utf-8')) for path in pathlib.Path('src').glob('*.py')]; [ast.parse(path.read_text(encoding='utf-8')) for path in pathlib.Path('tests').glob('*.py')]; print('syntax ok')"
.\.venv\Scripts\python.exe -c "from mss import MSS; import cv2, mediapipe as mp, tkinter; print('mss import ok'); print('opencv', cv2.__version__); print('mediapipe', mp.__version__); print('tkinter', tkinter.TkVersion)"
```

Expected: all tests pass, dependencies are consistent, syntax prints `syntax ok`, and all GUI/capture imports print their versions without opening a window.

- [ ] **Step 5: Perform manual acceptance with the lecturer**

The lecturer runs the ten README checks because they require permission to view the real screen and meeting content. Record any failed step and its exact visible error before changing code.
