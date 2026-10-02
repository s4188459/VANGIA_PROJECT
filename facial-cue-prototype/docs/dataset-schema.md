# Dataset Schema

For implementation details and known gaps in metadata/drop reporting, see the
[current system handbook](system-understanding-guide.md). A field existing
in the schema does not imply every runtime path populates it completely.

## Interpretation Boundary

The dataset contains pixels, sound, transcript text, MediaPipe coefficients,
derived geometry, and rule-based events. None is a confusion, emotion, attention,
engagement, cognitive-load, or understanding label.

## Session Timeline

All time fields use one monotonic session clock. Pause stops collection while the
clock continues, so resumed data contains a gap. Use timestamps in `features.csv`
and interval mappings in `session.json` rather than playback position alone.

## session.json

Stores session status, pseudonymous ID, region, requested options, consent
attestation time, component states, warnings, errors, and drop counts. Consent is
an operator attestation, not proof of legal or institutional compliance.

## features.csv

One row is written per processed frame, including missing-face rows.

- `timestamp_s`, `frame_index`: alignment identifiers.
- `face_visible`: whether one Face Landmarker result exists.
- `confidence`: empty because the current API has no suitable value.
- `head_center_*`, `head_*_deg`: normalized center and relative pose.
- `gaze_*`, `blink*`, `brow_*`, `jaw_open`, `mouth_*`: derived coefficients.
- `processing_ms`, `frame_gap_ms`, `capture_drop_count`: quality fields.
- `blendshape_*`: canonical MediaPipe face blendshape coefficients.

Blendshapes are not physical percentages or mental-state probabilities. Missing
values are empty, not zero.

Observable action state and strength are stored on the corresponding feature
rows. Completed event summaries are retained in `session.json`; they remain
engineering observations, not ground-truth labels.

## Video

`video.mp4` contains only the selected rectangle. Accepted video frame indices
are stored in `features.csv`; aggregate video statistics are in `session.json`.

## Audio

`audio.wav` is PCM stereo. Its left channel is microphone/`You`; its right
channel is WASAPI loopback/`Student`. Pause/Resume interval mappings are stored
in `session.json`.

Loopback may include any sound routed to the Windows output device.

## Transcript

`transcript.jsonl` is generated locally with English fixed. Rows have
`phase=live` or `phase=final`; final rows are canonical when present. Audio is
converted to mono 16 kHz before inference. Live endpoint checks begin after
1.2 seconds of buffered audio; ongoing speech can reach a 12-second forced
split with 0.75 seconds of overlap. JSONL fields are:

```text
segment_id,start_s,end_s,source,speaker,text,language,phase,status
```

Text/timestamps are estimates and may be wrong. Overlapping sources are valid.

## Future Labels

Do not copy observable events into a confusion label. Future labels need an
independent source such as consented self-report, task response, or manual
annotation. Split future datasets by participant, not random frame.
