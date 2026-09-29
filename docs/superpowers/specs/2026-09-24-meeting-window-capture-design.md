# Milestone 2: Meeting Window Capture Design

## Purpose

Replace the default webcam input from Milestone 1 with a user-selected screen region containing one student's video in Google Meet or Zoom. The application remains a local face-landmark tracking prototype. It does not integrate with meeting accounts and does not infer confusion, emotion, or cognitive load.

## Success Criteria

- A lecturer can select a rectangular student-video region with the mouse.
- The application captures only the selected region after selection is complete.
- MediaPipe detects at most one face and draws its landmarks in the preview.
- The preview displays `Face detected` or `Face not detected` and a fixed-position FPS value.
- A control panel provides Select Region, Start, Pause/Resume, and Quit actions.
- Keyboard shortcuts provide `R` to reselect, `S` to pause/resume, and `Q` or Escape to quit while the preview is focused.
- Reselecting a region updates the active capture area without restarting the application.
- Pausing stops screen capture and MediaPipe processing while keeping the application open.
- Closing either the control panel through Quit or the preview through its exit keys releases resources cleanly.
- No screenshots, video, landmarks, or other personal data are saved or transmitted.

## Scope

### Included

- Local screen capture with MSS.
- Selection from the primary monitor using an OpenCV region selector.
- Processing of one selected rectangular region.
- One-face MediaPipe Face Mesh tracking.
- A small Tkinter control panel and a separate OpenCV preview window.
- Runtime status and actionable error messages.

### Excluded

- Webcam capture as an alternate input mode.
- Automatic discovery of Google Meet or Zoom windows.
- Browser extensions or Google/Zoom APIs.
- Multi-student tracking and automatic participant-tile selection.
- Audio, conversation, emotion, confusion, or cognitive-load analysis.
- Recording, screenshots, landmark storage, analytics, lecturer alerts, and cloud services.
- Dragging or resizing the capture boundary while tracking is running. The lecturer uses Select Region or `R` to replace it.

## User Experience

The application opens a compact Tkinter control panel. It contains:

- `Select Region`: takes a temporary primary-monitor screenshot and opens the selector.
- `Start`: starts tracking after a valid region has been selected.
- `Pause` / `Resume`: toggles processing without discarding the selected region.
- `Quit`: stops processing and closes all windows.
- A status label showing one of: `No region selected`, `Ready`, `Running - Face detected`, `Running - Face not detected`, `Paused`, or an error message.

Before a region exists, Start and Pause are disabled. After a successful selection, Start is enabled. While running, Start is disabled and Pause is enabled. While paused, the same button reads Resume. Selecting a new region stops the current capture first, replaces the region, and returns the application to Ready so the lecturer explicitly starts it again.

The region-selection window displays a temporary screenshot. The lecturer drags a rectangle and confirms it using OpenCV's selector controls. Cancelling or selecting a zero-sized rectangle preserves the previous valid region, if one exists, and reports that selection was cancelled.

The preview window displays only the selected region plus the local status/FPS overlay. It must not display pixels outside the selected rectangle.

## Architecture

### `src/main.py`

Creates the application controller and starts the Tkinter event loop. It remains the executable entry point.

### `src/control_panel.py`

Owns the Tkinter widgets and reflects application state. Button callbacks delegate actions to the controller rather than performing screen capture or MediaPipe work directly.

### `src/region_selector.py`

Captures one temporary primary-monitor screenshot through MSS, displays it with OpenCV, and returns a validated `CaptureRegion`. The full screenshot is held only in memory for the duration of selection.

### `src/meeting_tracker.py`

Owns the background tracking worker. It repeatedly captures the selected rectangle through MSS, converts BGRA to BGR/RGB as required, sends RGB frames to MediaPipe, draws landmarks on the BGR preview, computes FPS, and publishes lightweight status updates to the controller.

### `src/app_controller.py`

Owns the state machine, active region, and worker lifecycle. It translates UI and keyboard actions into select, start, pause/resume, reselect, and shutdown operations. Tkinter widget updates are scheduled on the Tkinter main thread.

### `src/app_utils.py`

Retains pure formatting and key-handling helpers from Milestone 1. It may gain pure conversion or validation helpers only when they are useful to automated tests.

## Core Data Types and States

`CaptureRegion` is an immutable value containing integer `left`, `top`, `width`, and `height`. Width and height must both be greater than zero. The values passed to MSS use the same desktop coordinates.

The controller state is one of:

- `NO_REGION`: no valid region is available.
- `READY`: a valid region exists but capture is stopped.
- `RUNNING`: capture and MediaPipe processing are active.
- `PAUSED`: the region is retained but no new frames are captured or processed.
- `SHUTTING_DOWN`: new actions are ignored while resources are released.

Allowed transitions:

```text
NO_REGION -> READY                    successful selection
READY -> RUNNING                      Start
RUNNING -> PAUSED                     Pause or S
PAUSED -> RUNNING                     Resume or S
RUNNING/PAUSED/READY -> READY          successful reselection
any state -> SHUTTING_DOWN             Quit, Q, Escape, or window close
```

Cancelling selection leaves the previous state and region unchanged.

## Data Flow

1. The lecturer requests region selection.
2. MSS captures the primary monitor once for the selector.
3. OpenCV returns a rectangle relative to that screenshot.
4. The selector converts the rectangle to absolute desktop coordinates and validates it.
5. On Start, the worker creates its own MSS context and MediaPipe Face Mesh instance.
6. MSS captures only the active `CaptureRegion` on each iteration.
7. The BGRA MSS image is converted to BGR for display and RGB for MediaPipe.
8. MediaPipe returns zero or one face-landmark collection.
9. Landmarks, status, and FPS are drawn on the selected-region frame.
10. OpenCV displays the preview and checks keyboard shortcuts.
11. Only text state changes are sent back to Tkinter; image data is not retained by the controller.

## Concurrency

Tkinter must remain on the main thread. Continuous capture and MediaPipe inference run in one background thread so the control panel stays responsive. A thread-safe stop event and pause event control the worker. The worker must not update Tkinter widgets directly; status updates are polled or scheduled by the controller on the Tkinter event loop.

Only one worker may exist at a time. Reselection and shutdown signal the worker to stop and wait for it to finish before replacing the region or destroying windows.

## Error Handling

- MSS missing: exit with an installation command that points to `requirements.txt`.
- MediaPipe or OpenCV missing: retain the Milestone 1 beginner-readable dependency errors.
- Screen capture permission or MSS failure: stop the worker, preserve the selected region, and display an error in the control panel.
- Region selection cancelled or empty: preserve the previous valid region and show a non-fatal message.
- MediaPipe initialization or inference failure: stop tracking, close the preview, and report the error without closing the control panel unexpectedly.
- Preview window manually closed: stop tracking and return to Ready.
- Repeated Start clicks: ignored because Start is disabled while running.
- Shutdown: signal the worker, wait for it to exit, close OpenCV windows, destroy the Tkinter root, and terminate without a background thread left running.

`Face not detected` is a normal processing result, not an error.

## Privacy and Data Lifetime

- Selection requires one full primary-monitor screenshot, held temporarily in RAM and discarded immediately after selection.
- Continuous capture requests only the chosen rectangle from MSS.
- Frames are overwritten during processing and are not appended to a collection.
- No call writes images, video, landmarks, logs containing image data, or screen coordinates to disk.
- No network or cloud API is used.
- The README must remind the lecturer to select only the student's video tile and obtain any consent required by their institution or lesson context.

## Dependencies

- Python 3.12
- `mediapipe==0.10.21`
- `opencv-contrib-python==4.11.0.86`
- `mss==10.2.0`, whose current stable package supports Python 3.12
- Tkinter from the Python standard library

The implementation must preserve the compatible MediaPipe/OpenCV/NumPy dependency set established in Milestone 1.

## Testing Strategy

Automated tests must avoid opening the real screen selector or capturing personal screen content. Tests will cover:

- Valid and invalid `CaptureRegion` values.
- Conversion from selector-relative coordinates to absolute monitor coordinates.
- Controller state transitions for select, start, pause, resume, reselect, cancel, and shutdown.
- Prevention of Start without a region and prevention of duplicate workers.
- Conversion of an MSS-like BGRA NumPy frame to BGR/RGB with expected dimensions and channels.
- Shortcut mapping for `R`, `S`, `Q`, and Escape.
- Cleanup behavior using injected fake worker/capture dependencies.
- Existing status-text and FPS formatting behavior.
- Dependency compatibility and import checks.

Manual acceptance testing will verify selection against an actual Google Meet or Zoom student tile, preview cropping, face/no-face transitions, responsive buttons, shortcut behavior, reselection after moving the meeting window, and clean application exit.

## README Changes

The README will contain exact environment update and run commands, button and shortcut behavior, privacy limitations, expected error messages, and a step-by-step manual Meet/Zoom test. It will explicitly state that moving the meeting window requires selecting the region again with Select Region or `R`.
