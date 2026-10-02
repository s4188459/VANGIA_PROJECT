# Transparent Landmark Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the recursive OpenCV preview with a transparent, click-through, capture-excluded Windows overlay that draws landmarks directly over the selected meeting region.

**Architecture:** The tracking thread captures the selected MSS region and publishes immutable landmark-only `OverlayFrame` values into a coalescing latest-value slot. Tkinter polls that slot on the main thread and draws a borderless transparent Canvas positioned over the selected region. Win32 extended styles make the overlay click-through/no-activate, and `WDA_EXCLUDEFROMCAPTURE` prevents it from feeding back into MSS.

**Tech Stack:** Python 3.12, Tkinter Canvas, ctypes/Win32 User32, MSS 10.2.0, OpenCV 4.11.0.86 for color conversion and ROI selection, MediaPipe 0.10.21, unittest

**Spec:** `docs/superpowers/specs/2026-09-24-transparent-landmark-overlay-design.md`

## Global Constraints

- Windows-only transparent overlay; a non-Windows platform receives a readable Ready-state error.
- No separate captured-frame preview window.
- Overlay contains landmarks, status, and FPS only; it never receives image arrays.
- `WDA_EXCLUDEFROMCAPTURE` must succeed before starting MSS/MediaPipe tracking.
- Apply capture exclusion to both the transparent overlay and control panel; only the overlay receives click-through/no-activate styles.
- Overlay uses `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE`.
- Tkinter creation, drawing, and destruction remain on the main thread.
- Worker publishes only immutable landmark-coordinate data through a latest-value slot that drops stale frames.
- Existing MSS region restriction, one-face limit, Pause/Resume, Reselect, Quit, local-only processing, and no-storage requirements remain.
- Control-panel buttons remain authoritative; `S`, `R`, `Q`, and Escape work while the control panel has focus.
- Keep existing pinned dependencies; add no third-party package.
- The workspace has no Git repository; do not initialize Git or create commits.

## Review Focus

- Negative desktop coordinates must produce valid Tk geometry strings and correct overlay placement.
- A Win32 API return failure must prevent worker creation, destroy any partial overlay, and retain a readable error.
- Landmark publishing faster than Tk drawing must retain only the newest frame rather than growing memory.
- Pause before the first MediaPipe result must not crash and must perform no new MSS captures.
- Reselect or Quit while an overlay frame is pending must discard the pending frame and never redraw a destroyed overlay.

---

### Task 1: Landmark-Only Overlay Data

**Files:**
- Create: `src/overlay_data.py`
- Create: `tests/test_overlay_data.py`

**Interfaces:**
- Produces: `OverlayFrame(points, face_detected, fps, paused=False)` frozen dataclass
- Produces: `landmarks_to_pixels(landmarks, width: int, height: int) -> tuple[tuple[int, int], ...]`
- Produces: `connection_segments(points, connections) -> tuple[tuple[int, int, int, int], ...]`
- Produces: `LatestOverlayFrame.publish(frame)`, `take() -> OverlayFrame | None`, and `clear()`

- [ ] **Step 1: Write failing geometry and coalescing tests**

Use simple objects with normalized `x/y` fields. Assert `(0.0, 0.0) -> (0, 0)`, `(1.0, 1.0) -> (width-1, height-1)`, and values outside `0..1` clamp to the edge. Assert invalid connection indices are ignored. Publish frame A then B and assert `take()` returns B once and then `None`; `clear()` removes a pending frame.

- [ ] **Step 2: Run tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_overlay_data -v
```

Expected: FAIL because `src.overlay_data` does not exist.

- [ ] **Step 3: Implement immutable data and a lock-protected single slot**

Use `@dataclass(frozen=True)`, tuple-only points, and `threading.Lock`. Pixel conversion must use `round()` followed by clamping to `[0, width - 1]` and `[0, height - 1]`; reject non-positive width or height with `ValueError`.

- [ ] **Step 4: Run Task 1 and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_overlay_data -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass.

---

### Task 2: Windows Native Overlay Configuration

**Files:**
- Create: `src/windows_overlay.py`
- Create: `tests/test_windows_overlay.py`

**Interfaces:**
- Produces constants: `WS_EX_LAYERED`, `WS_EX_TRANSPARENT`, `WS_EX_NOACTIVATE`, `GWL_EXSTYLE`, `WDA_EXCLUDEFROMCAPTURE`
- Produces: `OverlayConfigurationError`
- Produces: `overlay_geometry(region: CaptureRegion) -> str`
- Produces: `exclude_window_from_capture(hwnd: int, *, user32=None, platform_name=sys.platform) -> None`
- Produces: `configure_capture_excluded_window(hwnd: int, *, user32=None, platform_name=sys.platform) -> None`

- [ ] **Step 1: Write failing Win32 boundary tests**

Test exact geometry for `CaptureRegion(-1820, 40, 640, 360)` as `640x360-1820+40`. Use a fake User32 recording `GetWindowLongPtrW`, `SetWindowLongPtrW`, and `SetWindowDisplayAffinity`. Assert overlay configuration ORs all three required flags and affinity is exactly `0x11`. Assert control-panel exclusion calls only `SetWindowDisplayAffinity` and never changes extended styles. Add tests that non-Windows and false affinity return raise `OverlayConfigurationError` containing a readable message/error code.

- [ ] **Step 2: Run tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_windows_overlay -v
```

Expected: FAIL because `src.windows_overlay` does not exist.

- [ ] **Step 3: Implement ctypes boundary with checked results**

Default `user32` to `ctypes.windll.user32` only on Windows. `exclude_window_from_capture()` calls and validates `SetWindowDisplayAffinity`. Overlay configuration reads the current extended style, ORs the required flags, writes it, then delegates affinity to `exclude_window_from_capture()`. Set ctypes argument/return types for real DLL calls. For the style write, clear/read last error because zero can be a valid previous style. Raise `OverlayConfigurationError` before tracking when any required call fails.

- [ ] **Step 4: Run Task 2 and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_windows_overlay -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass.

---

### Task 3: Transparent Tkinter Overlay Window

**Files:**
- Create: `src/overlay_window.py`
- Create: `tests/test_overlay_window.py`

**Interfaces:**
- Consumes: `CaptureRegion`, `OverlayFrame`, `LatestOverlayFrame`, `connection_segments`, `overlay_geometry`, `configure_capture_excluded_window`
- Produces: `LandmarkOverlay(root, region, *, configure_native=configure_capture_excluded_window)`
- Produces methods: `publish(frame)`, `draw_pending()`, `set_paused()`, `destroy()`

- [ ] **Step 1: Write failing rendering-boundary tests with fake Toplevel/Canvas**

Assert constructor applies exact geometry, borderless/topmost/transparent-color settings, calls native configuration with `winfo_id()`, and destroys the partial Toplevel when native configuration raises. Assert `publish(A); publish(B); draw_pending()` draws only B. Assert `destroy()` clears pending data and later `draw_pending()` does nothing. Assert negative-coordinate geometry is passed unchanged.

- [ ] **Step 2: Run tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_overlay_window -v
```

Expected: FAIL because `src.overlay_window` does not exist.

- [ ] **Step 3: Implement Toplevel and Canvas drawing**

Create a reserved transparent color such as `#010203`, configure the Toplevel, call `update_idletasks()`, then configure Win32 using the native HWND. Draw tessellation lines in a restrained cyan and contours in green; draw a compact black status rectangle with status/FPS text. Store MediaPipe connection index tuples as module constants derived from `FACEMESH_TESSELATION` and `FACEMESH_CONTOURS`. Never draw or retain captured image pixels.

- [ ] **Step 4: Run Task 3 and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_overlay_window -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass without opening a real Toplevel.

---

### Task 4: Headless Tracking Worker

**Files:**
- Modify: `src/meeting_tracker.py`
- Replace: `tests/test_meeting_tracker.py`

**Interfaces:**
- Consumes: `OverlayFrame`, `landmarks_to_pixels`
- Changes constructor to: `MeetingTracker(region, event_callback, overlay_callback, *, mss_factory=MSS, face_mesh_factory=None, sleep_func=time.sleep)`
- Removes: `OpenCVPreview`, preview backend injection, `cv2.imshow`, `cv2.waitKey`, and preview keyboard handling

- [ ] **Step 1: Rewrite worker tests first and verify RED**

Keep fake MSS/Face Mesh boundaries. Assert one captured frame produces an `OverlayFrame` whose points match the fake normalized landmarks and whose callback value contains no NumPy array. Assert face status events still emit only on change. Assert pause stabilizes MSS grab count and publishes a paused copy of the latest overlay frame. Assert capture errors emit ERROR then STOPPED. Assert no test fake exposes or expects preview methods.

- [ ] **Step 2: Run worker tests and confirm failure against preview-based implementation**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_meeting_tracker -v
```

Expected: FAIL because the constructor lacks `overlay_callback` and runtime still expects a preview backend.

- [ ] **Step 3: Remove preview behavior and publish landmark-only frames**

Retain BGRA-to-BGR and BGR-to-RGB conversion for inference. Convert only the first face's normalized landmarks with selected-region width/height, compute FPS, and call `overlay_callback(OverlayFrame(...))`. On no face publish empty points. Pause performs no MSS/MediaPipe call and publishes one paused frame only when pause state changes, then sleeps until resume/stop.

- [ ] **Step 4: Run worker and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_meeting_tracker -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass and no GUI opens.

---

### Task 5: Controller and Control-Panel Overlay Lifecycle

**Files:**
- Modify: `src/app_controller.py`
- Modify: `src/control_panel.py`
- Modify: `tests/test_app_controller.py`
- Create: `tests/test_control_panel_keys.py`

**Interfaces:**
- View adds: `show_overlay(region)`, `publish_overlay(frame)`, `pause_overlay()`, `hide_overlay()`
- Control panel owns: `self._overlay: LandmarkOverlay | None`
- Controller passes `view.publish_overlay` as the worker's overlay callback
- Control panel initialization calls `exclude_window_from_capture(root.winfo_id())` without applying overlay styles

- [ ] **Step 1: Add failing controller lifecycle tests**

Extend FakeView to record overlay calls. Assert Start calls `show_overlay(region)` before creating/starting a worker; overlay configuration failure creates no worker and leaves `READY` with the exact error. Assert pause calls `pause_overlay`, resume does not recreate overlay, successful reselection hides it, worker ERROR hides it but retains the error status, STOPPED hides it, and shutdown hides it once.

Add a control-panel native-boundary test asserting its HWND receives `WDA_EXCLUDEFROMCAPTURE` while buttons remain enabled when configuration succeeds. On failure, Select/Start/Pause are disabled, Quit remains enabled, and status is exactly `Control panel capture exclusion failed`.

- [ ] **Step 2: Add failing keyboard mapping tests**

Test a pure `control_shortcut(keysym: str) -> PreviewAction` mapping for `s/S`, `r/R`, `q/Q`, `Escape`, and unrelated keys. The Tk root binds these keys to controller actions only after `bind_actions()`.

- [ ] **Step 3: Run tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_app_controller tests.test_control_panel_keys -v
```

Expected: FAIL because overlay lifecycle methods and control-panel shortcut mapping do not exist.

- [ ] **Step 4: Implement overlay ownership and startup gating**

`ControlPanel.show_overlay()` constructs `LandmarkOverlay`; if this raises, no overlay reference remains. `AppController._start_worker()` calls it before tracker construction and catches `OverlayConfigurationError`/runtime errors into `Ready - <message>`. Hide overlay before selector opens and on every terminal worker path. Publish from the worker only into `LandmarkOverlay.publish()`, which is lock-protected and never calls Tkinter.

- [ ] **Step 5: Bind shortcuts on the control panel**

Bind `<KeyPress>` on the root and dispatch `TOGGLE_PAUSE`, `RESELECT`, or `QUIT` to the same controller callbacks used by buttons. Overlay remains no-activate/click-through and never receives focus.

- [ ] **Step 6: Run controller, key, and full tests**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_app_controller tests.test_control_panel_keys -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all tests pass.

---

### Task 6: Documentation and Final Verification

**Files:**
- Modify: `README.md`
- Modify: `.superpowers/sdd/2026-09-24-meeting-window-capture/progress.md`

**Interfaces:**
- Documents the overlay behavior delivered by Tasks 1-5.

- [ ] **Step 1: Update README behavior and Windows requirement**

Remove references to a separate preview window. Explain that landmarks appear directly over the selected tile, no captured video copy is displayed, and both overlay and control panel are excluded from supported Windows capture APIs. Explain that only the overlay is click-through, shortcuts require control-panel focus, and buttons remain reliable controls. State the Windows 10 2004+ requirement for full `WDA_EXCLUDEFROMCAPTURE` behavior.

- [ ] **Step 2: Add manual feedback-prevention checks**

Document this exact sequence:

1. Select a Meet/Zoom student tile and press Start.
2. Verify no separate video preview opens.
3. Verify landmarks align over the live tile.
4. Click controls inside the tile and confirm input passes through.
5. Verify the overlay does not appear recursively or inside captured image content.
6. Move the control panel over the selected tile and verify it does not appear recursively in captured content.
7. Pause and confirm landmarks freeze while the underlying meeting video continues.
8. Move the meeting window, reselect, and verify the new overlay position.
9. Quit and verify both overlay and control panel close.

- [ ] **Step 3: Run final automated verification**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import ast, pathlib; files=list(pathlib.Path('src').glob('*.py'))+list(pathlib.Path('tests').glob('*.py')); [ast.parse(path.read_text(encoding='utf-8')) for path in files]; print(f'syntax ok: {len(files)} files')"
```

Expected: all tests pass, pip reports no broken requirements, and syntax parsing succeeds.

- [ ] **Step 4: Run privacy and removed-preview scans**

```powershell
rg -n "imshow|waitKey|VideoWriter|imwrite|to_png|\.shot\(|\.save\(|requests\.|socket\." src
```

Expected: no runtime match for preview display, media writing, or network calls. `selectROI` remains allowed for region selection.

- [ ] **Step 5: Perform manual Windows overlay acceptance**

The lecturer performs the eight README checks because they require real desktop composition, Meet/Zoom content, and pointer interaction. Record the exact control-panel error if Win32 affinity configuration fails.
