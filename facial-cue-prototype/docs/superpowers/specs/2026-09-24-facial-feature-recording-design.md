# Facial Feature Recording Design

**Date:** 2026-09-24  
**Milestone:** 3 - Facial Feature Recording  
**Status:** Accepted

## Goal

Extend the local meeting-region tracker so each tracking session converts one visible face into timestamped facial-feature rows, displays the latest coefficients on the control panel, and saves them to a user-selected local directory as `session_XXX.csv`.

This milestone records derived numeric features only. It does not record video, audio, screenshots, raw frames, or raw landmark arrays. It does not classify confusion, emotion, cognitive load, or student performance.

## Confirmed Product Decisions

- Pressing **Start** begins tracking and CSV recording together.
- The user selects a save directory with **Choose Save Folder** before Start.
- The app automatically allocates the next unused `session_XXX.csv` filename without overwriting an existing file.
- Current facial coefficients are shown on the control panel, not over the student's face.
- Pause stops capture, inference, and row creation while leaving the CSV open.
- Resume continues the same file. Session-relative timestamps continue advancing during Pause, leaving an explicit time gap that remains aligned with an external test video.
- Stop flushes and closes the current CSV and returns the app to Ready.
- Reselect and Quit close the active session cleanly before continuing or exiting.
- Missing faces produce rows with `face_visible=false`; they do not stop the session.
- The `confidence` column remains blank because Face Landmarker does not expose a per-frame detection confidence in `FaceLandmarkerResult`.

## MediaPipe Architecture

Replace the legacy `mp.solutions.face_mesh.FaceMesh` inference path with MediaPipe Tasks Face Landmarker in `VIDEO` mode:

- `num_faces=1`
- `output_face_blendshapes=True`
- `output_facial_transformation_matrixes=True`
- `min_face_detection_confidence=0.5`
- `min_face_presence_confidence=0.5`
- `min_tracking_confidence=0.5`

The task uses a local `models/face_landmarker.task` model bundle. A setup command downloads the official model before the app runs. Runtime tracking performs no network access. If the model is absent or invalid, Start fails with a readable error and no recording worker remains active.

Face Landmarker receives monotonically increasing integer timestamps in milliseconds. The same result fans out to three consumers:

1. Pixel landmark coordinates for the existing transparent overlay.
2. A coalescing latest-value slot for control-panel coefficients.
3. A CSV recorder that writes every processed result.

Captured image pixels remain in the tracking worker and are never sent to the control panel or recorder.

## Data Flow

```text
Selected Meet/Zoom region
        |
        v
MSS BGRA frame in RAM
        |
        v
RGB MediaPipe Image + monotonic timestamp
        |
        v
Face Landmarker result
        |
        v
Immutable FeatureFrame
   |              |                 |
   v              v                 v
Landmark       Latest-value      CSV row
overlay        control panel     recorder
```

CSV writing occurs on the existing tracking worker, away from Tk's main thread. The file is line-buffered and flushed during Stop, Reselect, error handling, and Quit. A write failure emits an error, stops tracking, and closes the file while preserving rows already written.

## Feature Model

Each processed result becomes one immutable feature record.

### Timing And Presence

- `timestamp_s`: seconds since Start from a monotonic clock, written to three decimal places.
- `frame_index`: zero-based processed-result index.
- `face_visible`: `true` when Face Landmarker returns one face, otherwise `false`.
- `confidence`: blank for every row. This column is retained for schema compatibility and documented as unavailable, not estimated.

### Head Position And Orientation

- `head_center_x`: mean landmark x-coordinate, normalized to `[0, 1]`.
- `head_center_y`: mean landmark y-coordinate, normalized to `[0, 1]`.
- `head_depth`: mean relative landmark z-coordinate.
- `head_yaw_deg`, `head_pitch_deg`, `head_roll_deg`: Euler angles derived from the rotation component of the facial transformation matrix and written in degrees. The convention is pitch around X, yaw around Y, and roll around Z, with a tested gimbal-lock branch.

The README will document the Euler-axis convention and note that these values describe model-relative orientation, not medical-grade measurements.

### Gaze

Directions are from the student's perspective. They map from MediaPipe blendshapes as follows:

- `gaze_left`: mean of `eyeLookOutLeft` and `eyeLookInRight`.
- `gaze_right`: mean of `eyeLookInLeft` and `eyeLookOutRight`.
- `gaze_up`: mean of `eyeLookUpLeft` and `eyeLookUpRight`.
- `gaze_down`: mean of `eyeLookDownLeft` and `eyeLookDownRight`.

The control panel displays the strongest direction, or `Center` when no direction exceeds a documented neutral threshold. CSV retains all four scores.

### Blink

- `blink_left`: `eyeBlinkLeft`.
- `blink_right`: `eyeBlinkRight`.
- `blink`: arithmetic mean of left and right blink scores.

### Brow

- `brow_inner_up`: `browInnerUp`.
- `brow_outer_up_left`: `browOuterUpLeft`.
- `brow_outer_up_right`: `browOuterUpRight`.
- `brow_down_left`: `browDownLeft`.
- `brow_down_right`: `browDownRight`.
- `brow_raise`: maximum of inner-up and both outer-up scores.

### Mouth

- `jaw_open`: `jawOpen`.
- `mouth_smile_left`: `mouthSmileLeft`.
- `mouth_smile_right`: `mouthSmileRight`.
- `mouth_pucker`: `mouthPucker`.
- `mouth_funnel`: `mouthFunnel`.
- `mouth_activity`: maximum of the five recorded mouth scores.

Blendshape lookup is name-based rather than index-based. A missing expected blendshape is left blank instead of silently using an unrelated score.

### Missing Face Rows

When no face is visible, the row contains valid `timestamp_s`, `frame_index`, and `face_visible=false`. `confidence` and all head, gaze, blink, brow, and mouth fields are blank. The overlay and panel display `Face not detected`, and the session continues.

## CSV Schema

Column order is stable:

```text
timestamp_s,frame_index,face_visible,confidence,
head_center_x,head_center_y,head_depth,
head_yaw_deg,head_pitch_deg,head_roll_deg,
gaze_left,gaze_right,gaze_up,gaze_down,
blink_left,blink_right,blink,
brow_inner_up,brow_outer_up_left,brow_outer_up_right,
brow_down_left,brow_down_right,brow_raise,
jaw_open,mouth_smile_left,mouth_smile_right,
mouth_pucker,mouth_funnel,mouth_activity
```

The physical CSV header is one line without the formatting line breaks shown above. Files use UTF-8, comma delimiters, platform-correct newlines through Python's `csv` module, lowercase booleans, and fixed numeric formatting.

## Session File Allocation

The control panel stores the selected directory for the current application run. The next filename is computed from files matching exactly `session_[0-9]+.csv`. Allocation uses exclusive file creation so an existing file is never overwritten, even if the directory changes between preview and Start.

Examples:

- Empty directory -> `session_001.csv`
- Existing `session_001.csv` and `session_003.csv` -> `session_004.csv`
- Unrelated CSV files do not affect numbering.

If the directory is missing, not writable, or file creation fails, Start remains in Ready with an actionable error.

## Control Panel

The operational control panel remains compact and adds:

- **Choose Save Folder** button.
- Selected-folder path and next-session filename.
- **Stop** button alongside Start, Pause/Resume, Select Region, and Quit.
- Recording filename, elapsed time, and rows-written count.
- Latest Face, Head, Gaze, Blink, Brow, and Mouth values.

Start is enabled only when a valid region and save directory are selected. During recording, Start and folder selection are disabled; Pause and Stop are enabled. Stop closes the file and preserves the selected region and folder for the next session.

Control-panel updates use a latest-value slot polled on the Tk main thread. Worker callbacks never call Tk directly, and slow UI rendering cannot create an unbounded callback queue.

## State And Cleanup

- **Start:** allocate file, initialize the local model/task, start the worker, then expose Running/Recording state.
- **Pause:** stop new MSS grabs and inference; keep the file open; write no rows.
- **Resume:** continue the same worker and file with the original session clock.
- **Stop:** join the worker, flush and close CSV, destroy the landmark overlay, return to Ready.
- **Reselect:** perform Stop semantics first, then open desktop region selection.
- **Error:** stop worker activity, flush/close CSV, remove overlay, retain the error message and partial CSV.
- **Quit:** idempotently stop and close all resources before destroying Tk.

Model initialization should occur before the file is considered an active recording. If initialization fails after a file has been allocated, the empty/header-only file is removed when safe to do so.

## Error Handling

Readable errors are required for:

- Missing or invalid `face_landmarker.task`.
- Invalid or unwritable output directory.
- Exclusive file creation failure.
- MSS capture failure or unexpected frame format.
- Face Landmarker initialization or inference failure.
- CSV write, flush, or close failure.
- Malformed transformation matrices or missing optional outputs.

A malformed optional feature does not crash the session. Its related fields remain blank, while unrecoverable capture, inference, or storage failures stop the session cleanly.

## Privacy And Scope

Facial coefficients are biometric/behavioral data even though they are not images. The README and UI must make recording state and output location visible. Use requires appropriate student consent and institutional policy compliance.

The milestone remains local-only and excludes:

- Video, image, audio, and raw-landmark storage.
- Confusion, emotion, attention, or cognitive-load classification.
- Lecturer alerts.
- Cloud upload or account integration.
- Model training.

## Verification

Automated tests cover:

- Name-based blendshape extraction and missing blendshapes.
- Head center/depth and matrix-to-Euler conversion.
- Aggregate gaze, blink, brow, and mouth calculations.
- Missing-face feature rows.
- Stable CSV header, formatting, and timestamp ordering.
- Session numbering and no-overwrite behavior.
- Pause producing no rows and Resume retaining the session clock.
- Recorder closure on Stop, Reselect, errors, and Quit.
- Coalescing real-time panel updates without Tk calls from the worker.
- Missing-model and unwritable-directory errors.
- Existing overlay, capture exclusion, and region-selection regressions.

Manual acceptance uses an externally recorded test video with a visible timer:

1. Choose a region and save directory, then Start near video time zero.
2. Confirm the panel coefficients update in real time.
3. Blink, look in four directions, raise brows, move the mouth, and rotate the head.
4. Leave the frame and return; confirm recording continues.
5. Pause and Resume; confirm the CSV has a timestamp gap.
6. Stop and verify the CSV opens, has ordered timestamps, and contains no image data.
7. Compare visible events in the video with the nearest CSV timestamps.
8. Start another session and verify a new file is created without overwriting the first.

## Success Criteria

- Start automatically creates and records to the next session CSV in the chosen directory.
- Real-time coefficients are visible on the control panel.
- CSV timestamps are monotonic and usable for external-video alignment.
- Missing faces and missing optional features do not stop recording.
- Pause creates no rows while preserving elapsed-time alignment.
- Stop and Quit leave a valid, closed CSV.
- No existing file is overwritten.
- No video, image, audio, raw landmark array, or network payload is stored.
