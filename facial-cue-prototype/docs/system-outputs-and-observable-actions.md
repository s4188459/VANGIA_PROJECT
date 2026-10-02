# Complete catalog of system outputs, parameters, and observable actions

> Version note (2026-09-27): this catalog includes the older facial-only
> pipeline and CSV event layout. Statements below about no audio/video storage
> and `session_NNN_events.csv` describe that earlier version, not the current
> DatasetSession runtime. Use the [current system handbook](system-understanding-guide.md)
> for the active architecture, outputs, parameter meanings and known limitations.

> Multimodal recording and transcript outputs are documented in
> [dataset-schema.md](dataset-schema.md). This catalog describes facial signals
> only; its events are not confusion labels.

This document describes the **actual outputs of the older version covered by this
catalog** of `facial-cue-prototype`. It helps readers interpret the interface,
CSV files, and code without mistaking MediaPipe values for emotions, confusion,
or mental states.

## 1. Output pipeline overview

```text
Selected screen region
  -> MSS captures pixels in RAM
  -> MediaPipe Face Landmarker
  -> FeatureFrame containing facial measurements
  -> two output branches:
       1. raw features -> control panel + session_NNN.csv
       2. temporal detector -> overlay + session_NNN_events.csv
```

The system has four output groups:

1. A transparent overlay over the selected meeting region.
2. A control panel showing the latest measurements.
3. A raw CSV with one row per processed frame.
4. An event CSV with confirmed movement intervals.

In this older pipeline, no video, images, audio, or raw facial landmarks are saved.

## 2. How to read the values

| Type | Interpretation |
|---|---|
| Score `0-1` | How strongly MediaPipe detects a blendshape. Near `0` is weak; near `1` is strong. This is not an emotion probability. |
| Normalized coordinate | Position relative to the frame. `0` is the left/top edge; `1` is the right/bottom edge. |
| Degree | Head angle in degrees; it may be negative or positive. |
| Relative value | Current value minus this session's neutral baseline. |
| Normalized action strength | Strength divided by the action threshold. `1.0` just reaches activation; values above `1.0` exceed the threshold. |
| Boolean | `true/false`, for example whether a face is visible. |
| Missing value | A blank CSV cell or `--` on the panel. The system does not replace it with `0`. |

MediaPipe blendshape scores are usually within `0-1`, but this version's code does
not clamp them. Thus **expected range `0-1`** is not an absolute mathematical bound.

## 3. Transparent overlay output

The overlay draws directly on the selected meeting region and contains:

- The facial landmark mesh and contour for one face.
- The heading `Observable actions`.
- Current FPS, for example `FPS: 030.3`.
- One special state or up to four observable actions.
- The time an action has persisted, for example `Eyes looking down  1.4s`.

### Special overlay states

| Text | Meaning |
|---|---|
| `Calibrating... N%` | The session's neutral baseline is being established. |
| `Face not detected` | No face is present in the current frame. |
| `Face detected again` | A face has returned after a confirmed loss. |
| `No observable action` | A face is present, but no action meets its conditions. |
| `Paused` | Capture and recording are paused. |

The overlay shows at most four actions. If more qualify, the system prioritizes
specific actions, then longer duration, then greater strength, and finally sorts
by action ID for stability.

## 4. Control panel output

| Row | Displayed content |
|---|---|
| `Recording` | Current raw CSV name, for example `session_001.csv`. |
| `Elapsed` | Timestamp of the latest frame, measured from Start. |
| `Face` | `Visible` or `Not detected`. |
| `Head` | `Yaw`, `Pitch`, and `Roll` with two decimal places. |
| `Gaze` | Direction with the highest score and that score, for example `Down 0.63`. If the highest score is below `0.20`, the panel shows `Center`. |
| `Blink` | Combined `blink` value, expected within `0-1`. |
| `Brow` | Combined `brow_raise` value, expected within `0-1`. |
| `Mouth` | Combined `mouth_activity` value, expected within `0-1`. |
| `Rows` | Number of raw rows written in the current session. |

The control panel shows the latest raw measurements. Confirmed actions appear on
the overlay and in the event CSV, rather than in this measurement table.

## 5. Raw CSV: session_NNN.csv

Each Start creates a new raw file. Each processed frame produces one row, even
when `face_visible=false`. Timestamps continue through Pause, but no rows are
written while paused, so timestamp gaps occur.

### 5.1 Time and status

| Column | Type/range | Source and meaning |
|---|---|---|
| `timestamp_s` | Seconds, `>=0` | Time since Start, recorded to three decimal places. |
| `frame_index` | Integer, `>=0` | Sequence number of the processed frame. |
| `face_visible` | Boolean | Whether MediaPipe returned at least one face. |
| `confidence` | Currently blank | The Face Landmarker API in use does not provide a suitable detection confidence for each result; the application does not fabricate one. |

### 5.2 Head center position

These three values are averages over all facial landmarks in the frame.

| Column | Type/range | Formula/meaning |
|---|---|---|
| `head_center_x` | Normalized, usually near `0-1` | Mean landmark `x`; left to right. |
| `head_center_y` | Normalized, usually near `0-1` | Mean landmark `y`; top to bottom. |
| `head_depth` | Relative value with no fixed range | Mean landmark `z`; not centimeters or physical distance. |

Normalized landmarks can fall slightly outside `0-1` when a face is near the
frame edge. The raw CSV retains model values; only coordinates used to draw the
overlay are clamped to the frame.

### 5.3 Head orientation

| Column | Unit | Meaning |
|---|---|---|
| `head_yaw_deg` | Degrees | Left/right turn. Under the convention used here, negative is left and positive is right. |
| `head_pitch_deg` | Degrees | Raising/lowering the head. Negative is raised; positive is lowered. |
| `head_roll_deg` | Degrees | Head tilt. Negative is left; positive is right. |

Angles are derived from the facial transformation matrix. They are model
estimates, not clinical measurements. Under this version's formula, yaw is
approximately within `-90..90`; pitch and roll may be within `-180..180`.

### 5.4 Gaze scores

All have an expected range of `0-1`.

| Column | MediaPipe blendshape formula |
|---|---|
| `gaze_left` | Mean(`eyeLookOutLeft`, `eyeLookInRight`). |
| `gaze_right` | Mean(`eyeLookInLeft`, `eyeLookOutRight`). |
| `gaze_up` | Mean(`eyeLookUpLeft`, `eyeLookUpRight`). |
| `gaze_down` | Mean(`eyeLookDownLeft`, `eyeLookDownRight`). |

If a required component is missing, the corresponding combined value is blank.
Gaze estimates eye movement from blendshapes; it is not precise eye tracking to
a point on the screen.

### 5.5 Eye closure/blink scores

| Column | Expected range | Formula/meaning |
|---|---|---|
| `blink_left` | `0-1` | Blendshape `eyeBlinkLeft`. |
| `blink_right` | `0-1` | Blendshape `eyeBlinkRight`. |
| `blink` | `0-1` | Mean(`blink_left`, `blink_right`). |

### 5.6 Brow scores

| Column | Expected range | Formula/meaning |
|---|---|---|
| `brow_inner_up` | `0-1` | Blendshape `browInnerUp`. |
| `brow_outer_up_left` | `0-1` | Blendshape `browOuterUpLeft`. |
| `brow_outer_up_right` | `0-1` | Blendshape `browOuterUpRight`. |
| `brow_down_left` | `0-1` | Blendshape `browDownLeft`. |
| `brow_down_right` | `0-1` | Blendshape `browDownRight`. |
| `brow_raise` | `0-1` | Max(inner up, outer left up, outer right up). |

### 5.7 Mouth scores

| Column | Expected range | Formula/meaning |
|---|---|---|
| `jaw_open` | `0-1` | Blendshape `jawOpen`. |
| `mouth_smile_left` | `0-1` | Blendshape `mouthSmileLeft`. |
| `mouth_smile_right` | `0-1` | Blendshape `mouthSmileRight`. |
| `mouth_pucker` | `0-1` | Blendshape `mouthPucker`. |
| `mouth_funnel` | `0-1` | Blendshape `mouthFunnel`. |
| `mouth_activity` | `0-1` | Maximum of the five direct mouth scores above. |

High `mouth_activity` does not mean someone is speaking. This older pipeline
has no audio and does not create a `Speaking` label.

## 6. Processing before action detection

The action detector does not make an immediate decision from one raw score.

### Calibration baseline

- At least `2.00` seconds of valid face observations are required.
- At least `30` valid frames are required.
- Each feature has its own median and MAD.
- A missing value for one feature does not block other features.
- Time during face loss or a frame gap greater than `0.25s` does not count.
- The baseline resets at the start of a new session; Pause/Resume and temporary
  face loss do not reset it.

### Smoothing and thresholds

- Rolling median window: `0.25s`.
- Typical adaptive threshold:

```text
relative = rolling_median - baseline_median
threshold = max(engineering_floor, baseline_MAD * 6) / sensitivity
strength = directional_relative / threshold
```

- `sensitivity` defaults to `1.0`; the code allows `0.5..2.0`.
- A typical action must persist for at least `0.25s`.
- An action releases when strength remains below `60%` of its threshold for `0.15s`.
- Cooldown after an event: `0.30s`.
- A gap greater than `0.25s`, Pause, Stop, or confirmed face loss interrupts an action.

## 7. Complete list of observable actions

There are **27 observable action IDs** and **2 face lifecycle event IDs**.

### 7.1 Head orientation: 6 actions

Thresholds are relative to the baseline and can increase when baseline MAD is high.

| Overlay label | Event ID | Primary input | Default condition |
|---|---|---|---|
| Head turned left | `head_turned_left` | `head_yaw_deg` | Negative yaw delta with magnitude at least `15 deg`. |
| Head turned right | `head_turned_right` | `head_yaw_deg` | Positive yaw delta of at least `15 deg`. |
| Head raised | `head_raised` | `head_pitch_deg` | Negative pitch delta with magnitude at least `12 deg`. |
| Head lowered | `head_lowered` | `head_pitch_deg` | Positive pitch delta of at least `12 deg`. |
| Head tilted left | `head_tilted_left` | `head_roll_deg` | Negative roll delta with magnitude at least `12 deg`. |
| Head tilted right | `head_tilted_right` | `head_roll_deg` | Positive roll delta of at least `12 deg`. |

### 7.2 Head movement over time: 4 actions

| Overlay label | Event ID | Default condition |
|---|---|---|
| Nodding | `nodding` | Pitch has at least two alternating excursions, each `>=10 deg`, within `1.5s`. |
| Shaking head | `shaking_head` | Yaw has at least two alternating excursions, each `>=12 deg`, within `1.5s`. |
| Head movement detected | `head_movement_detected` | Combined rate of change in yaw/pitch/roll reaches `20 deg/s` and persists for the minimum duration. |
| Head mostly still | `head_mostly_still` | The ranges of yaw, pitch, and roll are each `<3 deg` for at least `1.50s`. |

`Nodding` and `Shaking head` suppress the general `Head movement detected` label.
Any head movement suppresses `Head mostly still`.

### 7.3 Gaze direction: 4 actions

| Overlay label | Event ID | Input | Default condition |
|---|---|---|---|
| Eyes looking left | `eyes_looking_left` | `gaze_left` | Relative delta reaches the gaze threshold. |
| Eyes looking right | `eyes_looking_right` | `gaze_right` | Relative delta reaches the gaze threshold. |
| Eyes looking up | `eyes_looking_up` | `gaze_up` | Relative delta reaches the gaze threshold. |
| Eyes looking down | `eyes_looking_down` | `gaze_down` | Relative delta reaches the gaze threshold. |

The gaze threshold floor is `0.30`; the strongest direction must exceed the
second strongest by at least `0.08`. Only one gaze direction is active at a time.
Gaze and head orientation are independent; pitch does not automatically produce
a gaze label.

### 7.4 Blink and eye closure: 4 actions

| Overlay label | Event ID | Default condition |
|---|---|---|
| Blinking | `blinking` | `blink` exceeds its threshold for at least 2 frames and `0.05s`, then the eyes reopen before `0.80s`. The label remains for `0.35s` to make it visible. |
| Long eye closure | `long_eye_closure` | Continuous closure for at least `0.80s`. |
| Frequent blinking | `frequent_blinking` | At least 4 completed blinks in an `8.0s` window. |
| Asymmetric eye closure | `asymmetric_eye_closure` | `abs(blink_left - blink_right) >= 0.25` for `0.30s`. |

Blink threshold:

```text
max(0.55, baseline_blink + baseline_MAD * 6) / sensitivity
```

`Long eye closure` suppresses `Blinking` while the longer closure is active.

### 7.5 Brows: 4 actions

| Overlay label | Event ID | Input/calculation | Engineering floor |
|---|---|---|---|
| Inner brows raised | `inner_brows_raised` | Relative `brow_inner_up` | `0.15` |
| Brows raised | `brows_raised` | Relative `brow_raise` | `0.20` |
| Brows lowered | `brows_lowered` | Mean relative brow down left/right | `0.15` |
| Asymmetric brow movement | `asymmetric_brow_movement` | Difference between relative outer left/right | `0.18`, held for `0.30s` |

`Inner brows raised` or `Asymmetric brow movement` suppresses the general
`Brows raised` label when they occur together.

### 7.6 Mouth: 5 actions

| Overlay label | Event ID | Input/calculation | Engineering floor |
|---|---|---|---|
| Jaw opened | `jaw_opened` | Relative `jaw_open` | `0.20` |
| Smile movement detected | `smile_movement_detected` | Mean relative smile left/right | `0.20` |
| Mouth puckered | `mouth_puckered` | Relative `mouth_pucker` | `0.18` |
| Mouth funnel detected | `mouth_funnel_detected` | Relative `mouth_funnel` | `0.15` |
| Mouth movement detected | `mouth_movement_detected` | Maximum absolute relative change among the five direct mouth scores | `0.12` |

A specific mouth action suppresses `mouth_movement_detected` to avoid duplicate
labels. For example, `mouth_pucker=0.75` could be neutral for a session; the
detector compares it with the baseline rather than treating `0.75` as an action.

### 7.7 Face lifecycle: 2 event IDs

| Overlay text / event | Event ID | Condition |
|---|---|---|
| Face not detected | `face_not_detected` | Overlay changes immediately; an event is recorded after `0.20s` of continuous face loss. |
| Face detected again | `face_detected_again` | A point event is recorded when a face returns after confirmed loss; the overlay holds for `1.00s`. |

These events concern face presence, not facial movement.

## 8. Event CSV: session_NNN_events.csv

Each raw CSV has an event CSV with the same session number.

```text
session_001.csv
session_001_events.csv
```

The event CSV records only actions confirmed by the detector. It contains no
images or raw landmarks.

| Column | Type/format | Meaning |
|---|---|---|
| `start_time_s` | Seconds, three decimal places | Start of the candidate/active interval. |
| `end_time_s` | Seconds, three decimal places | Time the action ends or is interrupted. |
| `action` | Snake-case string | One of 27 observable IDs or 2 face lifecycle IDs. |
| `duration_s` | Seconds, three decimal places | `end_time_s - start_time_s`; a point event may equal `0`. |
| `peak_strength` | Float, four decimal places | Maximum strength during the event; usually a ratio to the threshold, not limited to `0-1`. |
| `status` | Enum | `completed` or `interrupted`. |

### Status meanings

- `completed`: the action ends normally after release confirmation.
- `interrupted`: Pause, Stop, confirmed face loss, or a frame gap ends the action.

`peak_strength` is **not confidence**. A value of `1.0` usually means the signal
reaches the threshold; `1.5` means 1.5 times the threshold. Lifecycle events
use a conventional strength of `1.0`.

## 9. Application states and messages

The control panel may show these states/statuses:

| Status | Meaning |
|---|---|
| `No region selected` | No capture region has been selected. |
| `Selection cancelled` | The user canceled region selection. |
| `Ready` | Ready to Start. |
| `Ready - Choose a save folder` | No CSV save folder has been selected. |
| `Running - Face detected` | The worker is running and the frame contains a face. |
| `Running - Face not detected` | The worker is running but the frame has no face. |
| `Paused` | Capture and raw-row recording are paused. |
| `Closing` | The application is shutting down. |
| `Control panel capture exclusion failed` | Windows could not exclude the panel from MSS capture; capture buttons are disabled to prevent recursive capture. |
| `Ready - <error>` | A capture, MediaPipe, storage, overlay, or cleanup error is shown in the interface. |

## 10. Outputs the system does not produce

The version covered by this catalog does not output:

- A confusion score or `confused/not confused` label.
- Emotion labels.
- Attention, engagement, or cognitive-load labels.
- Academic performance predictions.
- Speaking/silence labels.
- Identity or face recognition.
- Raw facial landmarks in CSV.
- Captured images, video, or audio recordings.
- Cloud/network results.

## 11. Interpretation cautions

- A high score only indicates a stronger blendshape/model signal; it does not explain why.
- `Eyes looking down` does not prove a student is distracted.
- `Brows raised` does not prove a student is confused.
- `Head mostly still` does not prove a student is attentive.
- Several actions may be valid together, but the overlay displays only four prioritized actions.
- Lighting, glasses, occlusion, video quality, camera angle, and mirroring can distort measurements.
- Consent and appropriate policies are needed because raw features and derived
  events are still behavioral facial data.

This document reflects the implementation of the older pipeline described above.
If thresholds, schema, or action rules change, this catalog should be updated.
