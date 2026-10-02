# Transparent Landmark Overlay Design

## Purpose

Replace the separate OpenCV preview window with a transparent, click-through Windows overlay positioned directly over the selected Google Meet or Zoom student-video region. The overlay displays landmarks, face status, and FPS without displaying a captured copy of the meeting frame, preventing the recursive screen-within-screen effect.

## Scope

This change affects only Milestone 2 display and interaction behavior. MSS region selection, one-face MediaPipe processing, local-only execution, Start/Pause/Resume/Reselect/Quit controls, and the no-storage rule remain unchanged.

The overlay is Windows-specific. The application must fail with a readable message rather than silently showing a capturable overlay when required Win32 configuration cannot be applied.

## User Experience

- The Tkinter control panel remains available for Select Region, Start, Pause/Resume, and Quit.
- The control panel is also excluded from Windows screen capture, so moving it over the selected region cannot create recursive capture.
- Start creates a borderless transparent overlay at the exact `CaptureRegion` coordinates and dimensions.
- The underlying Meet/Zoom video remains visible; the overlay draws only landmarks plus a compact status/FPS label.
- Mouse input passes through the overlay to Meet/Zoom.
- Pause freezes the last landmark drawing and changes the label to `Paused` without calling MSS or MediaPipe.
- Resume continues capture and landmark updates.
- Select Region or `R` destroys the old overlay, opens region selection, and creates a newly positioned overlay after Start.
- Quit closes the overlay, control panel, MSS context, and MediaPipe model.
- With no focusable preview, shortcuts `S`, `R`, `Q`, and Escape are handled while the control panel has keyboard focus. Buttons remain the reliable controls.

## Windows Overlay

Create the overlay as a Tkinter `Toplevel` owned by the control-panel root:

- `overrideredirect(True)` removes title bar and borders.
- `attributes("-topmost", True)` keeps landmarks above the selected video.
- A reserved color key makes the background fully transparent.
- A Canvas draws landmark connections and status text.
- Geometry is exactly `<width>x<height>+<left>+<top>` from `CaptureRegion`.

After Tk creates the native top-level window, retrieve its HWND and apply:

- `WS_EX_LAYERED` for layered transparency.
- `WS_EX_TRANSPARENT` so pointer events pass through to windows underneath.
- `WS_EX_NOACTIVATE` so the overlay does not take keyboard focus.
- `WDA_EXCLUDEFROMCAPTURE` (`0x00000011`) through `SetWindowDisplayAffinity` so public Windows capture APIs omit the overlay.

Check every Win32 return value. If affinity configuration fails, destroy the overlay and display `Overlay capture exclusion failed` in the control panel. Do not continue with an overlay that could feed back into MSS capture.

Apply `WDA_EXCLUDEFROMCAPTURE` separately to the control-panel top-level HWND. Do not apply click-through or no-activate styles to the control panel because its buttons and keyboard shortcuts must remain interactive. If control-panel capture exclusion fails, keep Quit available but disable selection and tracking, and show `Control panel capture exclusion failed`.

## Landmark Data Flow

1. MSS captures only the selected `CaptureRegion`.
2. MediaPipe receives the RGB frame and returns zero or one face landmark set.
3. The worker converts normalized landmark coordinates to overlay-local pixel coordinates.
4. The worker publishes an immutable `OverlayFrame` containing pixel points, face-present status, and FPS. It does not publish image pixels.
5. A thread-safe latest-value slot replaces any unrendered `OverlayFrame`; old frames are dropped rather than queued.
6. Tkinter polls the slot on the main thread and redraws the Canvas using MediaPipe tessellation and contour connection indices.

Only one latest landmark frame is retained temporarily in RAM. No landmark frame is persisted or logged.

## Component Changes

### `src/meeting_tracker.py`

Remove OpenCV preview display, window visibility checks, and preview keyboard polling. Continue MSS capture and MediaPipe inference in the background. Emit status changes through existing tracker events and send `OverlayFrame` values through a separate latest-frame callback.

### `src/overlay_window.py`

Add `OverlayFrame`, normalized-to-pixel conversion, connection-line generation, Win32 style/affinity configuration, and the Tkinter overlay window. Keep pure geometry and line-generation functions independently testable without creating windows.

### `src/control_panel.py`

Own the overlay because both are Tkinter UI resources on the main thread. Mark its own top-level HWND as excluded from capture, poll the latest overlay frame, update Canvas content, bind control-panel keyboard shortcuts, and destroy the overlay during reselection or shutdown.

### `src/app_controller.py`

Create/show the overlay when tracking starts, update it from coalesced frame data, set it to Paused, and destroy it when tracking stops, errors, reselects, or shuts down.

### `src/frame_processing.py`

Retain BGR-to-RGB conversion but remove captured-frame overlay rendering from runtime use. Existing pure formatting functions may remain for compatibility.

## Error Handling

- Non-Windows platform: control panel reports that transparent capture-excluded overlay requires Windows.
- Native HWND unavailable: destroy overlay and return to Ready with an error.
- `SetWindowLongPtrW` or `SetWindowDisplayAffinity` failure: destroy overlay and return to Ready with the Windows error code.
- MSS or MediaPipe failure: preserve the selected region, destroy the overlay, and retain the readable error status.
- Overlay manually cannot be closed or focused because it is borderless, click-through, and no-activate; Quit remains available from the control panel.

## Privacy and Feedback Prevention

- The overlay never displays a captured meeting frame.
- `WDA_EXCLUDEFROMCAPTURE` must succeed before tracking is allowed to continue.
- Both the transparent landmark overlay and the visible control panel must be excluded from capture.
- Continuous MSS calls still receive only the selected region.
- No screenshot, video, landmark file, screen coordinate file, or network request is created.
- `SetWindowDisplayAffinity` reduces feedback through supported Windows capture APIs; it is not presented as DRM or a general-purpose security guarantee.

## Testing

Automated tests must cover:

- Normalized landmark to pixel conversion, including clamping at region edges.
- Connection generation ignoring invalid landmark indices.
- Latest-value coalescing drops stale overlay frames.
- Overlay geometry uses the exact selected region.
- Win32 configuration calls include click-through styles and `WDA_EXCLUDEFROMCAPTURE`.
- Control-panel configuration applies capture exclusion without click-through/no-activate styles.
- Win32 failure prevents tracking and produces a readable status.
- Worker emits landmark coordinate data but no image arrays to the UI.
- Pause stops capture and preserves the last `OverlayFrame`.
- Controller lifecycle creates, pauses, replaces, and destroys overlay resources correctly.
- Existing region selection, state, cleanup, dependency, and privacy tests continue passing.

Manual testing must verify that the overlay aligns with the selected student tile, mouse clicks reach Meet/Zoom, the overlay does not appear inside MSS capture, no recursive preview occurs, and reselection repositions the overlay.
