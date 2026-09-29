# Observable Action Detection And Overlay Design

**Date:** 2026-09-24  
**Milestone:** 4, Part 1 - Observable Action Detection and Overlay  
**Status:** Accepted

## Goal

Convert the existing frame-level facial features into neutral, observable action labels with per-session calibration and temporal filtering. Show at most four current actions inside the selected student-video region and save completed action intervals to a separate `session_XXX_events.csv` file.

This milestone describes visible movement only. It does not classify confusion, emotion, attention, engagement, cognitive load, understanding, intent, or student performance.

## Confirmed Product Decisions

- Keep the existing MediaPipe Face Landmarker and all Milestone 3 raw-feature extraction.
- Keep the existing `session_XXX.csv` header, values, and meaning unchanged.
- Create a paired `session_XXX_events.csv` for derived action intervals.
- Use a deterministic temporal rule engine with adaptive baseline statistics. Do not train a new machine-learning model.
- Reset baseline and all temporal state on every Start.
- Preserve the existing coefficient control panel. No new controls are required for this first implementation.
- Show observable actions only in the capture-excluded overlay inside the selected region.
- Use engineering defaults stored in one configuration object. Do not present them as scientifically or clinically validated thresholds.
- Continue local-only processing. Do not save video, images, audio, screenshots, or raw landmark arrays.

## Evidence From Session 006

The supplied `session_006.csv` contains 1,229 rows over 42.211 seconds at an estimated 30.3 FPS. Every row has a visible face. Its 29-column header exactly matches the current `FeatureFrame` and raw recorder schema.

The first two seconds contain 54 valid frames. Their medians include:

```text
head_yaw_deg       9.3288
head_pitch_deg     6.3860
head_roll_deg     -0.7714
gaze_down          0.2193
blink              0.1187
brow_raise         0.3770
mouth_pucker       0.7501
mouth_activity     0.7501
```

These non-zero neutral values demonstrate why absolute zero cannot represent every student's neutral pose. The supplied observations also distinguish a false gaze-down response during brow raising (`gaze_down=0.46`, `brow_raise=0.81`) from a deliberate downward gaze (`gaze_down=0.63`, `brow_raise=0.34`). Action detection therefore uses baseline-relative values, smoothing, minimum durations, and conservative floors.

## Architecture

```text
Selected screen region
        |
        v
MSS frame in RAM
        |
        v
MediaPipe Face Landmarker
        |
        v
Immutable FeatureFrame
   |                       |
   v                       v
Raw Session Recorder    ActionDetector
session_XXX.csv            |
                           v
                     ActionSnapshot
                      |          |
                      v          v
                   Overlay   completed events
                                  |
                                  v
                         Action Event Recorder
                         session_XXX_events.csv
```

`MeetingTracker` owns one `ActionDetector` for the lifetime of one worker. Because the controller creates a new worker on every Start, calibration and temporal state cannot leak into the next session. The controller continues to own persistence and closes both recorders before replacing or destroying the worker.

## New Domain Types

### ActionDetectionConfig

One frozen configuration object owns all numeric defaults:

```text
baseline_duration_s             2.00
baseline_min_samples              30
smoothing_window_s              0.25
max_contiguous_gap_s            0.25
missing_face_hold_s             0.20
face_reacquired_display_s       1.00
minimum_action_duration_s       0.25
release_duration_s              0.15
default_cooldown_s              0.30
blink_minimum_duration_s        0.05
blink_display_duration_s        0.35
long_eye_closure_duration_s     0.80
temporal_history_s              2.00
stillness_duration_s            1.50
frequent_blink_window_s         8.00
frequent_blink_count               4
maximum_overlay_actions             4
sensitivity                     1.00
adaptive_mad_multiplier         6.00
gaze_delta_floor                0.30
gaze_dominance_margin           0.08
generic_head_speed_deg_s       20.00
generic_mouth_delta_floor       0.12
```

Action-specific floors and release floors also live in this object. Sensitivity is clamped to `[0.5, 2.0]`. Higher sensitivity lowers activation floors within guarded limits; lower sensitivity raises them. The first version exposes configuration through Python construction and tests, not additional UI controls.

### BaselineModel

For every optional numeric feature, the baseline stores:

- Median neutral value.
- Median absolute deviation (MAD).
- Valid sample count.

Only visible-face frames and finite values participate. Missing features do not block unrelated features. A feature without enough baseline samples disables only actions that require that feature.

### ActionState

Each ordinary action has:

- `inactive`, `pending`, `active`, and `cooldown` states.
- Candidate start time.
- Activation and release strengths.
- Minimum activation duration.
- Release hold duration.
- Current active duration.
- Peak strength.
- Cooldown end time.

### ActionSnapshot

Each processed frame produces one immutable snapshot containing:

- Mode: `calibrating`, `tracking`, `face_missing`, or `paused`.
- Calibration progress from `0.0` to `1.0`.
- Up to four active display actions.
- Each display action's neutral label, stable action ID, duration, and normalized strength.
- Optional transient `Face detected again` state.

### ActionEvent

An event contains:

```text
start_time_s
end_time_s
action
duration_s
peak_strength
status
```

`status` is `completed` after normal release and `interrupted` when Pause, Stop, a large frame gap, or confirmed face loss ends the observation.

## Baseline Calibration

Calibration begins with the first valid face frame. It completes only after both conditions hold:

1. At least `baseline_min_samples` valid frames have been collected.
2. Accumulated contiguous valid-face observation time reaches `baseline_duration_s`.

Missing-face time and timestamp gaps larger than `max_contiguous_gap_s` do not count toward baseline duration. Missing and invalid feature values are ignored independently. The overlay displays `Calibrating...` and progress while calibration is incomplete. No ordinary action labels or events are produced during this phase.

If the face disappears during calibration, the overlay immediately displays `Face not detected`. Valid calibration samples already collected remain, but progress resumes only from new contiguous valid observations after the face returns.

Baseline resets only on a new Start. Pause, Resume, and temporary face loss retain the completed baseline.

## Adaptive Thresholds

For a baseline-relative scalar feature:

```text
relative_value = smoothed_value - baseline_median
noise_allowance = baseline_MAD * adaptive_mad_multiplier
activation_threshold = max(engineering_floor, noise_allowance) / sensitivity
```

Thresholds are clamped to action-specific safe ranges so near-zero MAD cannot create an unusably low threshold. Release thresholds are lower than activation thresholds, normally about 60 percent of activation, to provide hysteresis.

Directional gaze compares each direction with its own baseline. A gaze action requires:

- Baseline-relative directional strength above `max(0.30, 6 * MAD) / sensitivity`.
- At least `0.08` dominance over the next strongest relative direction.
- The ordinary minimum action duration.

This default deliberately rejects the observed false `gaze_down=0.46` when the baseline is approximately `0.219`, while retaining the observed deliberate `gaze_down=0.63`. Raw scores remain available in the unchanged raw CSV.

## Smoothing And Frame Gaps

Each supported scalar feature has a timestamped rolling window covering `smoothing_window_s`. Its smoothed value is the median of finite values in that window. Median smoothing rejects isolated spikes without requiring future frames.

A timestamp gap above `max_contiguous_gap_s`:

- Ends active events at the last observed timestamp with `status=interrupted`.
- Clears pending states, rolling windows, and movement histories.
- Preserves a completed baseline.
- Starts fresh temporal observation on the next frame.

This prevents Pause time or stalled capture time from inflating action duration.

## Observable Action Rules

All ordinary actions require multiple frames and state-machine confirmation. Thresholds below are initial engineering defaults and remain configurable.

### Face Tracking

- `face_not_detected`: overlay state is immediate; an event activates after `0.20` seconds of continuous absence.
- `face_detected_again`: emitted only after confirmed face loss, shown for `1.00` second, and saved as a completed point event with zero physical duration.

Confirmed face loss interrupts every ordinary active action. Face states do not participate in baseline calculations.

### Head Orientation

Head angles use smoothed differences from baseline:

```text
Head turned left/right      yaw delta activation 15 degrees, release 9 degrees
Head raised/lowered         pitch delta activation 12 degrees, release 7 degrees
Head tilted left/right      roll delta activation 12 degrees, release 7 degrees
```

Only one action per axis may be active. Direction labels follow the tested MediaPipe transformation convention. The README requires a mirrored-video acceptance check because meeting software may mirror local self-view.

### Head Movement Over Time

The detector keeps two seconds of smoothed yaw, pitch, and roll history.

- `nodding`: pitch produces at least two alternating turning-point excursions with at least 10 degrees per excursion inside 1.5 seconds.
- `shaking_head`: yaw produces at least two alternating turning-point excursions with at least 12 degrees per excursion inside 1.5 seconds.
- `head_movement_detected`: median combined yaw/pitch/roll angular speed remains above 20 degrees per second for `0.25` seconds but does not meet nodding or shaking rules.
- `head_mostly_still`: yaw, pitch, and roll ranges each remain below 3 degrees for `1.50` seconds.

Nodding or shaking suppresses generic head movement. Any movement action suppresses `head_mostly_still`.

### Eye Direction

Supported labels are:

- `eyes_looking_left`
- `eyes_looking_right`
- `eyes_looking_up`
- `eyes_looking_down`

Only the strongest baseline-relative direction can become active. Head orientation does not create or suppress an eye-direction action; the two remain separate observations.

### Eye Activity

- `blinking`: both-eye mean rises above `max(0.55, baseline + adaptive allowance)` for at least two frames and `0.05` seconds, then releases before the long-closure duration.
- `long_eye_closure`: blink remains above the activation threshold for at least `0.80` seconds.
- `frequent_blinking`: at least four completed blink events occur within eight seconds.
- `asymmetric_eye_closure`: the absolute left/right blink difference remains above `max(0.25, baseline asymmetry + adaptive allowance)` for `0.30` seconds.

A completed normal blink receives a `0.35` second display lifetime so it disappears naturally. This specialized transient detector intentionally does not use the ordinary `0.25` second minimum. Long eye closure suppresses the ordinary blinking label while closure remains active. Frequent blinking may coexist because it summarizes a recent temporal pattern.

### Eyebrow Movement

- `inner_brows_raised`: `brow_inner_up` rises at least 0.15 above baseline.
- `brows_raised`: the strongest outer/aggregate raise rises at least 0.20 above baseline.
- `brows_lowered`: mean brow-down score rises at least 0.15 above baseline.
- `asymmetric_brow_movement`: left/right outer-brow change differs by at least 0.18 for `0.30` seconds.

Specific inner or asymmetric movement is preferred over the generic brows-raised label when both describe the same frames.

### Mouth Movement

Each direct score is compared with its own baseline rather than with `mouth_activity`, because session 006 shows a neutral `mouth_pucker` and `mouth_activity` near 0.75.

- `jaw_opened`: `jaw_open` rises at least 0.20 above baseline.
- `smile_movement_detected`: mean left/right smile rises at least 0.20.
- `mouth_puckered`: `mouth_pucker` changes at least 0.18 from baseline in the positive direction.
- `mouth_funnel_detected`: `mouth_funnel` rises at least 0.15.
- `mouth_movement_detected`: at least one direct mouth score changes by 0.12 or more from baseline for the minimum duration without a more specific mouth action.

Specific mouth actions suppress generic mouth movement. No action is named `Speaking` because there is no audio evidence.

## Action Arbitration And Display Order

At most four actions appear. Before ranking, redundant generic actions are suppressed:

```text
long_eye_closure          suppresses blinking while active
nodding                   suppresses head_movement_detected
shaking_head              suppresses head_movement_detected
any head movement         suppresses head_mostly_still
specific brow action      suppresses generic brows_raised when redundant
specific mouth action     suppresses mouth_movement_detected
```

Remaining actions sort by:

1. Specific actions before generic summaries.
2. Current active duration, descending.
3. Normalized strength, descending.
4. Stable action ID as a deterministic tie-breaker.

The same order is retained between frames when ranking inputs are equal, preventing visual label jumping.

## Overlay Design

The overlay reserves a stable upper-left panel large enough for one heading and four action rows. Dynamic labels do not resize the selected region or move the underlying meeting layout.

Tracking example:

```text
Observable actions                    FPS: 30.3
Eyes looking down                         1.4s
Head lowered                              1.1s
Brows raised                              0.8s
```

Special states replace the action rows:

```text
Calibrating... 64%
Face not detected
Face detected again
No observable action
Paused
```

The panel uses neutral white/green text and never red warning styling. Because the current Tk overlay uses a transparent color key rather than per-pixel alpha, the dark backing uses a fixed checkerboard/dither pattern of transparent and dark pixels to provide visually semi-transparent coverage without capturing the underlying video or introducing a duplicate preview.

For very small selected regions, text and row count are clamped to the available dimensions. The renderer must never draw outside the selected area.

## Pausing, Resuming, And Cleanup

### Pause

- Stop capture and raw-row creation as in Milestone 3.
- Interrupt active events at the last observed timestamp.
- Clear pending states, smoothing windows, and movement histories.
- Preserve the completed baseline.
- Show `Paused` without stale actions.

### Resume

- Keep the baseline.
- Begin fresh smoothing and movement windows.
- Do not reconnect pre-Pause and post-Resume actions.

### Face Loss

- Show `Face not detected` immediately.
- Confirm the face-loss event after its hold duration.
- Interrupt active ordinary events when face loss is confirmed.
- Clear temporal windows.
- Preserve the completed baseline.

### Stop, Reselect, Error, And Quit

- Interrupt every active event at the last observed timestamp.
- Publish final events before the worker emits STOPPED.
- Join the worker before either recorder closes.
- Flush and close both files.
- Keep both partial files after any event has been written.
- Remove both header-only files when startup fails before a processed frame.

## Paired Session Files

Each Start exclusively allocates a pair:

```text
session_006.csv
session_006_events.csv
```

Allocation scans names matching either exact pattern and chooses a number unused by both files. It creates both paths with exclusive mode. If another process wins a race for either name, the allocator removes only its own new header-only file and retries the next number. Existing files are never overwritten or deleted.

The raw CSV remains byte-schema-compatible with Milestone 3. The event CSV header is:

```text
start_time_s,end_time_s,action,duration_s,peak_strength,status
```

Formatting:

- Times and duration: three decimal places.
- Peak strength: four decimal places.
- Stable snake-case action IDs.
- UTF-8 and Python `csv` newline handling.
- Line-buffered writes.

The event file is created at Start even when no events occur, leaving a valid header-only file. An event-recorder write failure is a fatal storage error: tracking stops, both files close, and already written data is preserved.

## Controller And Thread Ownership

The tracking worker performs MediaPipe inference, raw-row callback invocation, action detection, and event callback invocation. It never calls Tk directly.

The controller owns a paired recording session. Generation tokens guard raw-feature and event callbacks so stale workers cannot write to a closed or newer session. Stop invalidates the generation, joins the worker, then closes both recorders.

The control panel continues to receive raw coefficient updates through its latest-value slot. Observable actions travel only through the existing overlay latest-value slot.

## Error Handling

Readable errors are required for:

- Failure to allocate either member of the CSV pair.
- Raw-row or event-row write failure.
- Invalid detector configuration.
- Non-monotonic action timestamps.
- Missing required values for one detector.
- Existing capture, model, overlay, and cleanup failures.

Missing optional features disable only dependent actions and do not stop the session. A malformed detector input resets that detector's pending state rather than inventing a value. Non-monotonic timestamps are a programming/storage alignment error and stop the session.

## Privacy And Interpretation

- All inference and action detection remain local.
- The event CSV contains derived movement intervals but no images, audio, raw landmarks, emotions, or confusion labels.
- Labels describe observable motion only and must not be interpreted as evidence of understanding, intention, engagement, mental state, or academic performance.
- Appropriate participant consent and institutional policy remain required because facial features and derived movement events are behavioral data.

## Automated Verification

Tests use synthetic `FeatureFrame` timelines and fake recorders. Coverage includes:

- Baseline uses only finite visible-face values and requires duration plus sample count.
- Non-zero baseline and MAD adaptive floors.
- Calibration, face-missing, reacquisition, and paused snapshots.
- Rolling-median smoothing and large-gap reset.
- Activation hold, release hysteresis, duration, peak, cooldown, and interruption.
- Every supported orientation, gaze, eye, brow, and mouth action.
- Nodding and shaking require repeated temporal direction changes.
- Generic/specific suppression and deterministic four-action ranking.
- Raw CSV schema remains exactly unchanged.
- Paired exclusive file allocation survives raw-file and event-file races.
- Event formatting, header-only sessions, and partial-file preservation.
- Pause, Stop, Reselect, ERROR, and Quit flush events before recorder closure.
- Stale generation callbacks cannot write either file.
- Overlay states, durations, stable dimensions, maximum rows, and bounded rendering.
- Existing capture exclusion, overlay click-through, feature panel, and privacy tests remain green.

## Manual Acceptance

Use a consented test subject or prerecorded consented test video:

1. Start while holding a neutral pose until calibration completes.
2. Verify no ordinary action appears during calibration.
3. Perform every supported action separately and hold it past the minimum duration.
4. Confirm eye direction and head orientation remain separate.
5. Raise brows without looking down and verify no false `Eyes looking down` label.
6. Blink normally, hold eyes closed, blink asymmetrically, and blink repeatedly.
7. Nod and shake the head; verify a single static angle does not trigger either repeated action.
8. Leave and re-enter frame; verify both face labels and temporal reset behavior.
9. Pause during an active action and verify the event becomes `interrupted` without including Pause time.
10. Stop and compare raw timestamps with event start/end timestamps.
11. Confirm overlay never exceeds four action rows or leaves the selected area.
12. Start a second session and confirm neither raw nor event files are overwritten.

## Success Criteria

- A new session calibrates from valid face frames and produces no ordinary action before completion.
- Observable labels use smoothed, baseline-relative, multi-frame evidence.
- All requested supported categories have neutral labels and temporal behavior.
- Missing faces, Pause, gaps, Stop, and errors produce deterministic cleanup.
- The overlay displays no more than four stable, non-warning action rows inside the selected region.
- Raw CSV behavior and schema remain unchanged.
- Paired event CSV records start, end, duration, peak, and completion status without overwriting files.
- No confusion, emotion, attention, cognitive-load, engagement, or performance classification is introduced.
