# Local Whisper Transcription Improvement Design

## Purpose

Improve English transcription quality while keeping all audio and inference
local. The application continues to provide a near-real-time transcript during
the lesson, then allows the operator to generate a higher-quality final
transcript from the complete recording after Stop.

This specification supersedes the audio, transcription, and session-output
sections of `2026-09-25-multimodal-dataset-collector-design.md`. Existing
privacy boundaries, facial-feature interpretation limits, region capture, and
consent requirements remain in effect.

## Goals

- Improve quiet-speech handling without modifying the original recording.
- Use a stronger English Whisper model for live transcription when the computer
  can sustain it.
- Reprocess the complete recording with a stronger local model after Stop.
- Keep live and final text on the same session-relative timeline as facial data
  and optional video.
- Preserve `You` and `Student` as separate audio sources inside one WAV file.
- Reduce each session to four required files and one optional video file.
- Keep face tracking responsive when transcription is slow.

## Non-Goals

- Azure, cloud transcription, plugins, or uploading participant data.
- Guaranteed word-perfect transcription.
- Recovering speech that is absent from the captured signal or below the noise
  floor.
- Confusion, emotion, attention, or cognitive-load classification.
- Speaker recognition or identity inference.
- Model training or fine-tuning in this milestone.
- Languages other than English.

## User-Visible Workflow

Before recording, the operator selects the meeting region, output directory,
capture options, and confirms participant consent. The panel shows independent
audio-level meters for `You` and `Student` with concise states:

- `No signal`
- `Too quiet`
- `Good`
- `Clipping`

During recording, the transcript panel shows recent source-labelled text with a
`LIVE` marker. Live text is provisional and may change at phrase boundaries.

After Stop, `Generate Final Transcript` becomes available when `audio.wav`
exists and a final Whisper model is installed. Pressing it starts a local
background job and displays progress. On success, the transcript panel switches
to the final stream and displays `FINAL`. No additional cloud-consent control is
shown because no data leaves the computer.

The operator can cancel final transcription. Cancellation preserves the audio,
facial data, session metadata, and any completed live transcript.

## Architecture

All components share the existing `SessionClock`. Tkinter remains on the main
thread; capture, recording, live transcription, and final transcription run in
workers with bounded communication queues.

```text
Microphone ------> source normalizer --+
                                      +--> stereo audio coordinator --> audio.wav
WASAPI loopback -> source normalizer --+
                |                     |
                +--> inference copy --+--> live Whisper --> transcript.jsonl + UI

After Stop:
audio.wav --> channel reader --> inference preprocessing --> final Whisper
          --> timestamp mapping --> transcript.jsonl + UI
```

The audio coordinator is the only component allowed to write `audio.wav`. It
aligns microphone and loopback blocks against the shared session clock and
writes one common-rate stereo stream.

## Audio File And Channel Mapping

`audio.wav` is uncompressed PCM stereo:

- Left channel: `You`, captured from the selected microphone.
- Right channel: `Student`, captured from Windows WASAPI loopback.

Each device may expose a different sample rate or channel count. Before writing,
each source is downmixed to mono and resampled to the session audio rate. The
initial target is 48 kHz, subject to device compatibility testing. Source blocks
are placed at their session-derived sample positions. A late, disconnected, or
unavailable source contributes silence to its channel; it must not shift the
other channel.

Pause stops writing active audio. `session.json` records each active interval's
session start/end and WAV sample start/end. This avoids long silent pause spans
while preserving an exact conversion between WAV offsets and session time.

Ordinary stereo playback may place `You` mainly in the left speaker and
`Student` mainly in the right speaker. That channel separation is intentional.
Transcription reads the channels independently, so it does not need speaker
diarization and remains valid when both people speak at once.

## Audio Quality Pipeline

The PCM samples written to `audio.wav` are the normalized-format capture, not an
amplitude-enhanced transcription copy. Recognition preprocessing occurs in
memory or in a temporary file inside the session directory that is removed after
use.

For each source, the application calculates RMS level and peak level before
inference. Speech windows receive conservative RMS normalization with:

- A fixed target range rather than unlimited amplification.
- A maximum gain cap so background noise is not amplified without bound.
- A limiter to prevent clipping after gain.
- Silence and near-silence detection that avoids amplifying empty input.

Thresholds and applied gain are recorded in `session.json`. The level meters use
the pre-inference measurements so the operator can correct microphone or meeting
volume at the source. Preprocessing cannot guarantee recovery of speech that was
not captured clearly.

## Live Transcription

Live transcription uses `faster-whisper`, fixed English, and CPU INT8 by
default. The preferred live model is `small.en`; `base.en` remains a selectable
fallback for computers that cannot sustain the larger model while MediaPipe and
recording are active.

The worker processes rolling speech windows with overlap and retained context:

1. Receive source-labelled audio referenced to the session clock.
2. Downsample the inference copy to mono 16 kHz.
3. Measure and conservatively normalize useful speech.
4. Apply a quiet-speech-aware VAD configuration.
5. Transcribe an overlapping window with language fixed to English.
6. Keep the newest phrase provisional until enough following context exists.
7. Commit stable phrases with session-relative start/end timestamps.

The target display delay is several seconds, not sample-level real time. Queue
limits prevent transcription backlog from consuming unbounded memory. If live
transcription falls behind, the UI reports lag and capture continues. It never
silently substitutes a different audio device.

## Final Transcription

Final transcription is an explicit post-session action. It reads each stereo
channel separately and uses the full recorded context rather than independent
short live windows.

The preferred final model is `medium.en` on CPU INT8. The model choice is
configurable and recorded in `session.json`; a smaller installed model can be
selected on computers with insufficient memory. Model files are downloaded only
through an explicit setup command, never during an active session.

Final Whisper output contains word-level timestamps where supported. WAV-relative
timestamps are converted to session-relative timestamps through the active audio
interval mapping in `session.json`. Consequently, Pause/Resume gaps appear in
the transcript timeline exactly as they do in `features.csv`.

The final pass does not need to reproduce live phrase boundaries. Live and final
records are two textual interpretations attached to one session clock. Training
and analysis tools treat final records as canonical when present.

Final output is built in a temporary file and atomically replaces the combined
transcript only after successful completion. A failed or cancelled pass cannot
destroy the previous transcript.

## Session Files

An audio-and-transcript session uses this structure:

```text
session_001/
|-- audio.wav
|-- features.csv
|-- transcript.jsonl
|-- session.json
`-- video.mp4              # only when selected and successfully recorded
```

`features.csv` and `session.json` are always present. `audio.wav` is present when
at least one audio source is enabled, `transcript.jsonl` is present when
transcription is enabled, and `video.mp4` is present only when video recording
is enabled and successfully initialized. No default SRT, separate audio files,
event CSV, audio mapping CSV, video mapping CSV, or manifest file is produced.

### `features.csv`

This is the single tabular feature file. It contains the existing per-frame face
visibility, head pose, gaze, blink, brow, mouth, quality, blendshape, and
observable-action fields. Event state and strength are stored on the applicable
frame rows rather than in a separate event file.

When video recording is enabled, each row also contains the relevant video frame
index or an empty value when no frame was written. This replaces a separate video
timestamp sidecar while retaining synchronization.

### `transcript.jsonl`

This is the single transcript file. Each record includes:

```json
{"phase":"live","start_s":12.4,"end_s":15.1,"source":"system_audio","speaker":"Student","text":"I don't understand this park.","language":"en","status":"committed"}
{"phase":"final","start_s":12.3,"end_s":15.2,"source":"system_audio","speaker":"Student","text":"I don't understand this part.","language":"en","status":"canonical"}
```

Live and final records can have different text and boundaries. They remain
synchronized because all `start_s` and `end_s` values refer to the same session
clock. Consumers use `phase=final` when available and otherwise fall back to
committed live records.

### `session.json`

This file replaces the old manifest and media sidecars. It contains:

- Schema/application versions and session status.
- Start/end datetimes and duration.
- Region and enabled capture options.
- Consent attestation time.
- Audio devices, channel mapping, formats, level thresholds, and active interval
  mappings.
- MediaPipe and Whisper model/configuration details.
- Pause/Resume intervals.
- Video codec, dimensions, frame count, and dropped-frame counts.
- Transcript counts, lag/drop metrics, final-transcription status, warnings, and
  errors.
- The interpretation boundary for facial observations.

The file is updated through atomic temporary-file replacement.

## Backward Compatibility

Existing session folders are not rewritten. New code reads the new compact
schema for new sessions and may retain narrowly scoped readers for old session
metadata where existing tests or tools require them. Session schema versioning
prevents consumers from assuming the channel layout or filenames.

## Failure Handling

- Missing live model: recording continues; the panel explains which setup
  command installs the model.
- Live model too slow: lag is visible; the operator can select `base.en` for a
  future session without affecting recorded audio.
- Missing final model: the button remains unavailable with an actionable status.
- Insufficient memory or inference failure: keep all existing files and mark the
  final job failed in `session.json`.
- One audio source disconnects: write silence for that channel, report the
  failure, and continue the other source.
- Both audio sources fail: preserve face/video data and stop transcription.
- Storage failure: initiate orderly Stop because continued capture would create
  an unreliable dataset.
- Final job cancellation: terminate at a safe boundary and leave the previous
  transcript intact.

Worker shutdown is bounded so Quit cannot wait indefinitely on Whisper.

## Performance And Model Validation

No model upgrade is accepted solely because it is theoretically more accurate.
Implementation verification benchmarks `base.en`, `small.en`, and the proposed
final model on the same consented English sample. Measurements include:

- Processing time versus audio duration.
- Live display lag.
- Face-processing FPS while live transcription is active.
- Peak process memory where practical.
- Missed quiet phrases and obvious word errors from a manually prepared
  reference transcript.

The default remains `small.en` live only if it sustains acceptable capture and
UI responsiveness on the target computer. Otherwise `base.en` is the live
default and the stronger model is reserved for the final pass.

## Automated Testing

Tests use fake audio sources and transcribers; hardware and model downloads are
not required for the normal suite. Coverage includes:

- Stereo channel assignment and common-rate resampling.
- Silence insertion when one source is late, unavailable, or disconnected.
- RMS/peak classification, gain cap, limiter, and silent-window handling.
- Inference preprocessing without modification of captured PCM.
- Live rolling-window overlap and duplicate suppression.
- Provisional-to-committed live phrase behavior.
- Shared timestamps across face rows, video indices, audio intervals, and both
  transcript phases.
- Pause/Resume conversion between WAV offsets and session timestamps.
- Atomic final-transcript replacement and cancellation/failure preservation.
- Missing-model, queue-overload, audio-disconnect, and shutdown behavior.
- Compact session structure with no obsolete sidecar files.
- Existing face tracking and observable-action behavior.

## Manual Verification

1. Record consented English speech from microphone and meeting audio.
2. Confirm the two level meters react independently and warn about quiet input.
3. Confirm live transcript appears with correct `You` and `Student` labels.
4. Speak simultaneously on both sources and verify the channel labels remain
   deterministic.
5. Pause, wait, resume, and confirm the transcript, feature CSV, and optional
   video agree on the resumed session time.
6. Stop and run `Generate Final Transcript`.
7. Compare live and final text against a short manually written reference.
8. Confirm final text replaces the panel view without changing the session
   timeline.
9. Open `audio.wav` and verify `You` is left and `Student` is right.
10. Confirm an audio-and-transcript session has four core files, plus
    `video.mp4` only when enabled; disabled optional modes create no empty media
    files.
11. Disconnect one audio source and confirm the other source and face tracking
    continue with a visible warning.
12. Confirm no network access is needed after explicit model installation.

## Success Criteria

- All transcription remains local and English-only.
- One stereo WAV preserves deterministic `You` and `Student` channels.
- Quiet input is measured, visibly reported, and conservatively prepared for
  inference without altering the recorded samples.
- Live transcript remains useful for monitoring and does not materially block
  face tracking.
- The explicit final pass uses fuller context and a stronger installed Whisper
  model to improve the canonical transcript.
- Live and final records share the same session timeline as facial features and
  optional video.
- Each session contains only the agreed compact file set.
- Failures preserve usable source data and are clearly recorded.
- No output is described as a confusion or psychological label.
