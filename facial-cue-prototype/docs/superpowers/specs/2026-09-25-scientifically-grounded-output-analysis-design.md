# Scientifically Grounded Observable Output And Analysis Design

## Purpose

Improve the current prototype as a local, rule-based facial-feature data
collection tool. The system continues to use MediaPipe outputs and temporal
engineering rules. It does not train a new AI model and does not infer
confusion, attention, engagement, cognitive load, emotion, intention, or
understanding.

The change has two goals:

1. Reduce avoidable false observable-action detections caused by unstable
   calibration, single-frame noise, and overly broad signal names.
2. Produce objective session analysis that can support later manual labeling
   and model development without treating current detector output as ground
   truth.

## Binding Scientific Boundary

The implementation keeps these levels separate:

```text
MediaPipe coefficient
  -> estimated physical movement
  -> derived observable feature
  -> temporally segmented observable event
  -> no psychological interpretation
```

A MediaPipe blendshape coefficient is not:

- an emotion probability;
- a FACS Action Unit;
- a physical percentage of movement;
- a confusion, attention, or cognitive-load score.

All current numeric thresholds remain engineering heuristics pending empirical
validation. Documentation must call the robust statistic used by the detector
**median absolute deviation (MAD)**, not merely MAD where the meaning could be
confused with mean absolute deviation.

## Scope

### Included

- Keep rule-based detection from MediaPipe numeric features.
- Keep the raw 29-column CSV schema unchanged.
- Keep existing action IDs for backward compatibility.
- Improve session-reference calibration quality handling.
- Correct baseline-relative comparisons where current rules are too broad.
- Improve temporal head-motion robustness.
- Replace overclaiming display labels with measurement-faithful labels.
- Add objective per-session analysis output.
- Add detector/configuration metadata needed to interpret a collected session.
- Add read-only replay and synthetic verification.
- Update user and technical documentation.

### Excluded

- Training any machine-learning model.
- Automatic confusion or emotion labels.
- Student identity recognition.
- Participant names or personally identifying metadata.
- Audio, video, screenshot, or raw-landmark recording.
- Live lecturer alerts.
- Automatic ground-truth labels.
- Cloud services or network transmission.

## Compatibility Contract

### Raw CSV

`session_NNN.csv` remains byte-schema-compatible at the header level with the
current Milestone 3/4 format. No fields are added, removed, renamed, or
reordered.

### Event CSV

`session_NNN_events.csv` retains its six-column schema:

```text
start_time_s,end_time_s,action,duration_s,peak_strength,status
```

Existing snake-case action IDs remain unchanged so old and new sessions can be
analyzed together. Display labels may change without changing IDs.

### New files

Each successfully started session also allocates:

```text
session_NNN_analysis.csv
session_NNN_metadata.json
```

All four files share the same session number. Exclusive allocation must never
overwrite an existing member or reuse a number occupied by any member.

## Terminology Revisions

The code and documentation use **session reference baseline** rather than
**neutral baseline**. The application can instruct the user to hold still and
look approximately forward, but it cannot verify psychological or FACS-defined
neutrality.

Display labels change as follows while IDs remain stable:

| Existing ID | Existing label | Revised display label |
|---|---|---|
| `eyes_looking_left` | Eyes looking left | Eye-look estimate: left |
| `eyes_looking_right` | Eyes looking right | Eye-look estimate: right |
| `eyes_looking_up` | Eyes looking up | Eye-look estimate: up |
| `eyes_looking_down` | Eyes looking down | Eye-look estimate: down |
| `frequent_blinking` | Frequent blinking | Blink cluster detected |
| `brows_raised` | Brows raised | Brow-up signal detected |
| `brows_lowered` | Brows lowered | Outer brows lowered |
| `asymmetric_brow_movement` | Asymmetric brow movement | Outer-brow-raise asymmetry |
| `mouth_movement_detected` | Mouth movement detected | Selected mouth/jaw movement detected |

Other action labels remain descriptive and unchanged. Documentation explicitly
states that nodding does not prove agreement, long eye closure does not prove
fatigue, and mouth-corner elevation does not prove happiness.

## Session Reference Calibration

### Existing minimum requirements retained

- At least 2.00 seconds of accepted reference observation.
- At least 30 accepted visible-face frames.
- Per-feature median and median absolute deviation.
- Missing values disable only dependent actions.
- Missing-face intervals and gaps above 0.25 seconds do not add reference time.

### Reference-frame quality gate

A visible frame is accepted into the session reference only when:

- yaw, pitch, and roll are finite;
- bilateral blink aggregate is available;
- the frame-to-frame combined head angular speed is no more than 20 degrees per
  second after the first reference frame;
- blink is below 0.55, preventing a sustained eye closure from becoming the
  eye-open reference;
- the timestamp is strictly increasing and the gap is no more than 0.25 seconds.

Rejected visible frames do not add samples or reference duration. They do not
cause an application error. The overlay shows:

```text
Hold still for reference
```

Calibration progress is calculated only from accepted frames and accepted
contiguous duration.

These quality-gate values are engineering defaults, not validated behavioral
thresholds. They live in `ActionDetectionConfig` and are recorded in metadata.

### Coverage and stability diagnostics

After the minimum sample/time requirements are met, the reference is considered
usable when all detector-critical feature groups have sufficient finite values:

- head pose: yaw, pitch, roll;
- gaze: left, right, up, down;
- eye closure: left, right, bilateral aggregate;
- brow features used by implemented brow actions;
- mouth features used by implemented mouth actions.

An unavailable group disables only its dependent actions. Calibration does not
stall forever because one optional blendshape is unavailable. Metadata records
per-feature sample counts and unavailable action IDs.

## Detector Accuracy Improvements

The term "accuracy improvement" means engineering robustness verified by
synthetic timelines and replay invariants. It is not a claim of population-level
accuracy until labeled validation data exists.

### Eye-look direction

Direction selection uses raw baseline-relative deltas:

```text
delta_direction = smoothed_direction - reference_median_direction
```

The winning direction must:

- exceed its own adaptive threshold;
- exceed the second-largest raw delta by at least 0.08;
- remain active for the normal minimum duration.

Normalization by each direction's threshold occurs only after the winner is
selected. This prevents directions with different noise estimates from being
ranked using incomparable normalized ratios.

### Eye-closure asymmetry

The detector uses a session-relative asymmetry measure:

```text
current_asymmetry = abs(blink_left - blink_right)
reference_asymmetry = median(abs(reference_left - reference_right))
relative_asymmetry = current_asymmetry - reference_asymmetry
```

The existing action ID remains `asymmetric_eye_closure`. The engineering floor
remains configurable and the event still requires temporal confirmation.

### Blink cluster

The existing ID `frequent_blinking` remains for compatibility, but its display
label becomes `Blink cluster detected`. Its operational meaning is exactly:

```text
at least N completed detected blinks inside T seconds
```

The default remains four detected blinks in eight seconds until validation.
The analysis output reports the count/window condition and never describes it as
abnormal, physiological, or evidence of fatigue/stress.

### Head movement

Generic angular movement no longer depends on only the last two frames. It uses
the median of timestamped combined angular speeds within the smoothing window.
This reduces sensitivity to one noisy pose step.

Nod and shake turning points require:

- a velocity sign change outside the deadband;
- the configured excursion amplitude;
- a minimum 0.10-second separation between accepted turning points;
- two qualifying alternating excursions inside the existing temporal window.

Static orientation remains independent from nod/shake detection.

### Broad brow and mouth outputs

Detection formulas and compatible IDs remain unchanged in this iteration. The
more precise display labels and metadata disclose the exact monitored inputs.
Further expansion to additional MediaPipe mouth coefficients is deferred until
the collection protocol provides examples and labels for those movements.

## Output Data Model

### Runtime snapshot

`ActionSnapshot` gains objective diagnostics:

```text
reference_quality: collecting | unstable | usable
unavailable_action_ids: tuple[str, ...]
```

The overlay does not display numeric scientific confidence. It displays one of:

- `Calibrating reference... N%`
- `Hold still for reference`
- current observable action labels;
- existing face/pause/no-action states.

### Analysis CSV

`session_NNN_analysis.csv` is written when the session closes. It contains one
row per action ID that occurred, plus a final session row.

Header:

```text
record_type,action,count,completed_count,interrupted_count,total_duration_s,mean_duration_s,max_peak_strength,first_start_s,last_end_s
```

For `record_type=action`, `action` is the stable event ID. For
`record_type=session`, fields have these exact meanings:

- `action` is blank;
- `count` is the total number of event rows;
- `completed_count` and `interrupted_count` count all event statuses;
- `total_duration_s` is the final processed session timestamp, including Pause
  gaps represented by the timestamp clock;
- `mean_duration_s` and `max_peak_strength` are blank because they would mix
  unrelated event types;
- `first_start_s` is `0.000`;
- `last_end_s` is the final processed session timestamp.

The analysis is descriptive only. It does not rank students, compare students,
or calculate confusion/attention/emotion scores.

### Metadata JSON

`session_NNN_metadata.json` contains no name or identity. It records:

```json
{
  "schema_version": "1.0",
  "detector_version": "observable-actions-v2",
  "raw_csv": "session_NNN.csv",
  "event_csv": "session_NNN_events.csv",
  "analysis_csv": "session_NNN_analysis.csv",
  "started_at_local": "ISO-8601 timestamp",
  "ended_at_local": "ISO-8601 timestamp",
  "reference": {
    "accepted_frames": 0,
    "accepted_duration_s": 0.0,
    "feature_sample_counts": {},
    "unavailable_action_ids": []
  },
  "detector_config": {},
  "interpretation_boundary": "Observable engineering events only; no psychological inference."
}
```

No participant ID is collected in this iteration. A later consented dataset
milestone may add a pseudonymous participant identifier and separate label file.

## Recording Lifecycle

- Start exclusively allocates all four same-number session files before capture.
- Raw, event, and analysis CSV files receive valid headers immediately.
- Metadata contains valid `status: recording` JSON immediately, so an abnormal
  process exit does not leave an empty or unparsable file.
- Raw and event rows remain line-buffered during capture.
- Event aggregates are maintained in memory without retaining images or raw
  landmarks. Analysis rows and final `status: closed` metadata are written
  during orderly close using the already exclusively allocated handles.
- Pause/Stop/face loss/gaps continue to emit interrupted events before close.
- If startup fails before any data row, all files created by that attempt are
  removed.
- If any raw or event data exists, partial files are preserved after an error.
- Analysis/metadata write failures are reported as recording errors without
  deleting raw/event data already collected.

## Future Manual Labels

This iteration does not create labels. Future labels must be stored separately:

```text
session_NNN_labels.csv
```

Potential future fields are:

```text
start_time_s,end_time_s,label,label_source,annotator_id
```

Current observable events must not be copied into a `confusion` label. Future
training labels require an independent source such as consented self-report,
task response, or documented manual annotation. Dataset splits must be by
participant rather than by random frame to avoid identity leakage.

## Replay And Verification

A read-only replay command consumes an existing raw CSV and produces an analysis
preview in a temporary location or stdout. It never edits the source CSV.

Automated tests cover:

- raw and event CSV backward compatibility;
- four-file collision-safe session allocation;
- reference quality-gate acceptance and rejection;
- missing-face and gap time exclusion;
- raw-delta gaze dominance;
- baseline-relative eye asymmetry;
- median head-speed filtering;
- separated nod/shake turning points;
- revised labels with stable IDs;
- analysis aggregation and metadata completeness;
- Pause/Stop/error close ordering;
- no image, audio, video, network, identity, or psychological output.

Replay acceptance uses the existing `session_006.csv` read-only and reports:

- reference completion time;
- rejected reference-frame count;
- action IDs and event counts;
- maximum simultaneous overlay actions;
- unavailable action IDs;
- objective analysis rows.

The known synthetic distinction remains required:

- `gaze_down=0.46`, `brow_raise=0.81` must not produce
  `eyes_looking_down` under the supplied reference profile;
- sustained `gaze_down=0.63`, `brow_raise=0.34` must produce it.

## Manual Validation Boundary

The user performs consented manual tests for observable movement only. A future
validation protocol may measure event precision, recall, F1, false events per
minute, onset/offset error, and duration error against independently annotated
movements. Until that study exists, the application and documentation must not
publish an accuracy percentage.

## Success Criteria

- Existing raw and event CSV readers continue to work.
- Existing event IDs remain stable while revised labels are visible on overlay.
- Unstable reference frames no longer contaminate accepted calibration time.
- Gaze direction ranking uses comparable raw reference-relative deltas.
- Eye asymmetry accounts for the participant/session reference asymmetry.
- Generic head movement is less sensitive to a one-frame pose spike.
- Each session produces objective analysis and non-identifying detector metadata.
- Outputs never claim confusion, attention, engagement, emotion, fatigue,
  agreement, understanding, or academic performance.
- No new AI model is trained or introduced.
