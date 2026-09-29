# Multimodal Dataset Collector Design

## Purpose

Extend the existing local meeting-region face tracker into a consent-gated,
multimodal dataset collection prototype for future confusion-signal research.
The application records synchronized observable data that can later be labeled
and used to train a separate model. This version does not infer confusion,
emotion, attention, engagement, cognitive load, understanding, or intent.

This specification supersedes the recording/output scope in
`2026-09-25-scientifically-grounded-output-analysis-design.md`. The scientific
boundaries and observable-action robustness requirements from that document
remain applicable where they do not conflict with this specification.

## Goals

- Continue tracking one face inside a user-selected meeting region.
- Save comprehensive MediaPipe-derived facial features and observable events.
- Optionally record only the selected screen region as video.
- Optionally record meeting/system audio and microphone audio as separate tracks.
- Produce local English transcript segments with source labels and timestamps.
- Show near-real-time transcript text beside the selected region.
- Keep every output aligned to one session-relative monotonic clock.
- Keep recording local and require an explicit consent attestation.
- Preserve face tracking responsiveness when media or transcription is slow.

## Non-Goals

- Automatic confusion or emotion labels.
- Training or evaluating a confusion model.
- Identity recognition or participant names.
- Speaker identity recognition or diarization within one audio source.
- Capturing the complete desktop or meeting window outside the selected region.
- Sending audio, video, transcript, or facial features to a cloud service.
- Supporting languages other than English in the first version.
- Editing transcript text inside the application.
- Treating the operator's consent checkbox as proof of legal or institutional
  compliance.

## Privacy And Consent Boundary

Video, audio, transcript, and facial features can be sensitive personal data.
The operator is responsible for obtaining valid participant consent and meeting
applicable institutional and legal requirements.

The control panel provides four independent options:

- Record selected-region video.
- Record meeting audio.
- Record microphone.
- Generate English transcript.

All optional recording controls default to off when the application starts.
Transcript requires at least one audio source. Facial features and events are
always persisted, so every session requires the operator to check
`I confirm participant consent` before Start becomes available. The checkbox
records an operator attestation and timestamp; it is not presented as a
consent-management system.

No participant name is requested. The operator may enter an optional
pseudonymous participant ID. The application displays an unambiguous recording
indicator whenever persistent capture is active.

Meeting audio uses Windows WASAPI loopback. It can contain notifications or
audio from other applications routed to the same output device. The UI warns
about this limitation before recording.

## Chosen Architecture

The application uses independent workers in one Python process. Workers exchange
small immutable messages through bounded queues and share a read-only session
context. Tkinter remains confined to the UI thread.

```text
Selected screen region
        |
        +--> face worker --> features/events --> dataset writer
        |
        +--> video queue --> video writer

WASAPI loopback --> system WAV writer ----+
                                           +--> transcript queue --> faster-whisper
Microphone ------> microphone WAV writer -+                         |
                                                                      v
                                                       transcript file + UI panel
```

The initial implementation keeps workers as threads because it fits the current
Tkinter architecture and is easier to shut down and test than a process graph.
The transcription interface remains isolated so it can later move to a separate
process without changing the controller or output schema.

## Session Clock And Synchronization

`SessionClock` owns a `time.perf_counter()` origin created immediately before
workers start. Every timestamp is seconds relative to that origin. Wall-clock
time is stored only as session metadata.

Pause stops capture and recording work but does not stop the session clock.
After Resume, new records therefore contain a timestamp gap. No fake frames or
silent audio are inserted to hide that gap.

- Facial rows store `timestamp_s` and `frame_index`.
- Video mapping stores each written frame index and session timestamp.
- Audio segment mapping stores source, sample offsets, and session start/end.
- Transcript segments store session-relative start/end timestamps derived from
  their source audio segment.

Timestamps, rather than file playback position alone, are the authoritative
alignment mechanism.

## Session Directory

Each Start allocates a collision-safe directory without overwriting old data:

```text
session_001/
|-- manifest.json
|-- facial_features.csv
|-- facial_events.csv
|-- selected_region.mp4          # only when enabled and available
|-- video_timestamps.csv         # only with video
|-- system_audio.wav             # only when enabled and available
|-- microphone_audio.wav         # only when enabled and available
|-- audio_segments.csv           # when at least one audio source is enabled
|-- transcript.jsonl             # only when transcript is enabled
`-- transcript.srt               # only when transcript is enabled
```

The directory is created with exclusive allocation. A failed startup removes an
empty directory. Once any valid data exists, partial output is preserved and
marked incomplete rather than deleted.

## Manifest

`manifest.json` is valid JSON from session creation onward. It contains:

- Schema and application versions.
- Session number and optional pseudonymous participant ID.
- Local start/end datetimes and final session duration.
- Final status: `recording`, `closed`, `incomplete`, or `failed`.
- Selected-region coordinates and dimensions.
- Requested and successfully active capture options.
- Video dimensions, requested FPS, actual written frames, codec, and drops.
- Audio device names, sample rate, channels, sample format, and chunk counts.
- MediaPipe package/model and faster-whisper/model configuration.
- Consent attestation value and local timestamp.
- Worker warnings and errors.
- Output filenames and row/segment counts.
- The interpretation boundary stating that outputs are observations, not
  psychological labels.

Manifest writes use an atomic temporary-file replacement so readers do not see
partially written JSON during orderly updates.

## Facial Feature Output

`facial_features.csv` replaces the legacy 29-column raw file for new multimodal
sessions. It contains:

- Session timestamp and frame index.
- Face visibility and MediaPipe result availability.
- Normalized head center and relative yaw, pitch, and roll.
- Derived gaze, blink, brow, jaw, and mouth aggregates used by the UI.
- Every MediaPipe face blendshape category returned by the configured model,
  using stable prefixed column names.
- Frame processing duration, inter-frame gap, and dropped-frame counters needed
  to assess collection quality.

When no face is visible, a row is still written with `face_visible=false` and
unavailable face fields empty. MediaPipe does not expose a suitable per-result
detection confidence through the current Face Landmarker result, so the system
must not invent one. Model coefficients remain model outputs in approximately
the 0-to-1 range; they are not probabilities of emotions or mental states.

`facial_events.csv` retains stable rule-based observable-action IDs and event
timing. These events are convenience annotations, not ground-truth confusion
labels. Detector configuration and reference-calibration diagnostics are stored
in the manifest.

The first version does not save all 478 landmark XYZ coordinates. They are large
and privacy-sensitive, while consented video permits later re-extraction with a
chosen model version. All returned blendshapes and the current geometric pose
features are saved.

## Video Recording

Video recording is optional and off by default. It receives the same selected
region frames already captured for processing; it never performs whole-screen
capture. The transparent landmark overlay, transcript panel, and control panel
are excluded from MSS capture using the existing Windows capture-exclusion
mechanism.

The writer targets MP4 with an OpenCV-supported codec and records the codec in
the manifest. Writer initialization is validated before the worker reports
ready. If no supported writer can be opened, video is marked unavailable and
other enabled streams may continue after a clear warning.

The video queue is bounded. When it is full, capture drops the oldest unwritten
video frame, increments a drop counter, and continues face tracking. Every
successfully written frame is represented in `video_timestamps.csv`:

```text
video_frame_index,source_frame_index,timestamp_s
```

This variable-timestamp sidecar is required because a conventional constant-FPS
video file cannot represent every capture delay or Pause gap exactly.

## Audio Recording

`PyAudioWPatch` provides Windows WASAPI loopback and microphone input compatible
with Python 3.12. Audio is written as uncompressed PCM WAV for lossless local
processing and simple recovery.

- Meeting/system audio is displayed as `Student` in the prototype UI.
- Microphone audio is displayed as `You`.
- Stored source IDs remain `system_audio` and `microphone_audio` because these
  describe the actual technical source without claiming speaker identity.
- Tracks remain separate and are never destructively mixed.
- Device formats are normalized to a supported PCM representation per output
  file, with exact format metadata stored in the manifest.

`audio_segments.csv` maps each contiguous active recording interval:

```text
source,segment_index,start_s,end_s,start_sample,end_sample,sample_rate,channels
```

Separate mapping is necessary because Pause creates a session-clock gap while
the WAV files contain only captured samples.

Failure of one audio source does not stop the other sources. Transcript remains
available for any successfully active source.

## Local English Transcription

Transcription uses `faster-whisper` locally with an English-only model. The
default prototype configuration is `base.en` on CPU with INT8 computation. The
model name and compute mode are configurable and recorded in the manifest.

A setup script downloads the selected model before normal offline use. Runtime
does not silently download a missing model. If model files are unavailable,
audio recording can continue while live transcription is disabled with a clear
status message.

Each audio worker emits short source-tagged chunks to a bounded transcript queue.
The transcription worker:

1. Receives approximately 3-to-5-second audio windows.
2. Skips windows without useful speech where supported by the transcription
   engine's voice activity filtering.
3. Transcribes with language fixed to English.
4. Converts model-relative segment times to the shared session timeline.
5. Publishes immutable transcript segments to the UI and dataset writer.

The intended display delay is approximately 2-to-5 seconds on suitable hardware,
but it is not a hard real-time guarantee. If transcription falls behind, the UI
shows lag while face tracking and media recording continue. The bounded queue
prevents unlimited memory growth; dropped transcript chunks are counted and
reported in the manifest.

`transcript.jsonl` is the authoritative machine-readable transcript. Each line
contains:

```json
{"segment_id": 1, "start_s": 12.4, "end_s": 15.8, "source": "system_audio", "speaker": "Student", "text": "I do not understand this part.", "language": "en"}
```

`transcript.srt` is a human-readable companion generated from the same accepted
segments. Overlapping `You` and `Student` segments are allowed. The application
does not claim that `Student` identifies a particular person; it is merely the
UI label for loopback audio in the intended one-on-one use case.

## Transcript Panel

A separate borderless transcript panel is positioned next to the selected
region:

- Prefer the right side with a small screen-space gap.
- Move to the left when the right side lacks usable monitor space.
- Clamp size and position to the selected region's monitor work area.
- Move whenever the capture region is changed.
- Remain excluded from screen capture.
- Show recent segments with speaker label, timestamp, and wrapped text.
- Allow collapse/expand without stopping transcription.
- Never edit or reinterpret transcript text.

UI updates are scheduled onto Tkinter's main thread. The panel retains a bounded
number of displayed segments; complete accepted segments remain in the output
files.

## Control Panel And Lifecycle

The existing panel gains:

- Capture-option checkboxes.
- Consent checkbox and short WASAPI privacy warning.
- Optional pseudonymous participant ID.
- Component statuses for face, video, system audio, microphone, and transcript.
- Session elapsed time, transcript lag, dropped-frame/chunk counts, and estimated
  session output size.

Start is enabled only when a region and save folder exist, requested components
are valid enough to start, transcript has an audio source, and consent is
checked. Consent is required even when all optional media controls are off
because the session always saves facial features and events.

Start creates the session context and output directory, validates requested
devices/writers/model, then starts workers. If a requested optional component is
unavailable, the UI reports it before recording begins and allows the operator
to disable that component or proceed with the available set. It never silently
records a different source.

Pause stops accepting new screen and audio samples, flushes current chunks, and
keeps the session clock running. Resume starts new mapped media segments. Stop:

1. Prevents new input.
2. Flushes face events and media buffers.
3. Gives queued transcript work a bounded grace period.
4. Marks unfinished transcript chunks if the grace period expires.
5. Closes WAV, video, CSV, JSONL, and SRT handles.
6. Atomically finalizes the manifest.
7. Returns the UI to Ready.

Quit during recording asks for confirmation and then uses the same orderly Stop
path. Worker joins always have timeouts so a failed dependency cannot freeze the
UI indefinitely.

## Error Isolation

Components report structured status events to the controller. A recoverable
component failure disables only that component:

- Missing loopback or microphone device: affected audio source unavailable.
- Audio device disconnect: close that track, record error, continue others.
- Missing faster-whisper model/dependency: preserve audio, disable transcript.
- Video writer failure: close video, record error, continue face/audio.
- Transcript queue overload: count dropped chunks and continue capture.
- Face loss: write invisible-face rows without stopping the session.

Critical storage errors, including an unwritable output directory or disk-full
condition, initiate orderly Stop because continuing would create an unreliable
dataset. The manifest records all detected failures and whether shutdown was
complete.

## Performance Rules

- No media encoding or transcription runs on the Tkinter thread.
- Face tracking retains priority over optional display and transcript work.
- Queues have explicit capacities and observable drop counters.
- UI values are throttled to a practical refresh interval.
- Transcript rendering retains only recent visible lines.
- Shutdown and queue draining are bounded.
- Tests use fake capture/audio/transcription adapters and require no hardware.

## Dependencies And Offline Behavior

New runtime dependencies are pinned after compatibility verification:

- `PyAudioWPatch` for Windows audio input and WASAPI loopback.
- `faster-whisper` for local transcription.

The existing MediaPipe, OpenCV, MSS, and Tkinter architecture remains. No plugin
is required for transcription. Model weights are downloaded explicitly during
setup and stored locally; normal capture/transcription does not contact a cloud
service.

## Automated Verification

Automated tests cover:

- Consent and Start eligibility for every option combination.
- Transcript requiring at least one audio source.
- Collision-safe session-directory allocation.
- Valid recording and final manifest states.
- One shared monotonic timeline across feature, video, audio, and transcript
  records.
- Pause/resume timestamp gaps and media segment mapping.
- Separate system and microphone tracks.
- `Student` and `You` display mapping without changing stored source IDs.
- Fixed-English faster-whisper invocation.
- Bounded queue behavior and drop accounting.
- Face tracking continuing during slow/failing transcription.
- Component-level failure isolation.
- Critical storage-error shutdown.
- Transcript JSONL and SRT formatting, including overlapping sources.
- Transcript-panel placement to the right, left fallback, screen clamping, and
  capture exclusion.
- Existing face tracking, overlay, action, and CSV tests.

## Manual Verification

Manual testing uses only the operator or a participant who has consented:

1. Select a visible one-on-one meeting tile and enable all four outputs.
2. Confirm the app cannot start until consent is checked.
3. Speak English through both meeting/system audio and microphone.
4. Confirm transcript appears beside the region with `Student` and `You` labels.
5. Confirm panel, overlay, and control window are absent from recorded video.
6. Confirm facial overlay remains responsive while transcription runs.
7. Pause, wait, resume, and verify matching gaps in timestamp sidecars.
8. Stop and play both WAV tracks separately.
9. Compare transcript timestamps, facial rows, and video timestamps against a
   visible timer.
10. Disconnect or disable one audio source and verify remaining components keep
    running with a clear error state.
11. Verify no unexpected files are created outside the selected session folder
    and no network traffic is required after model setup.

## Success Criteria

- The app records only the selected region when video is enabled.
- Video, two separate audio tracks, facial data, events, and transcript share a
  documented session timeline.
- Transcript is local, English-only, source-labeled, and displayed beside the
  selected region with acceptable delayed updates.
- Optional media capture cannot start without explicit consent attestation.
- Slow or failed transcription does not materially delay face tracking.
- Expected component failures are visible and do not unnecessarily destroy
  usable data from other components.
- Outputs contain enough metadata to reproduce feature extraction and interpret
  missing/dropped data.
- No current output is presented as a confusion label or psychological truth.
- No cloud service, plugin, identity recognition, or model training is added.
