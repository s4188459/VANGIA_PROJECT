# Multimodal Dataset Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing Windows meeting-region tracker into a local, consent-gated collector that synchronizes comprehensive facial features, selected-region video, separate meeting/microphone audio, and delayed English transcript output.

**Architecture:** Keep Tkinter on the main thread and run face tracking, video writing, two audio inputs, and faster-whisper in isolated workers connected by bounded queues. A shared `SessionClock` gives every output one session-relative timeline, while a `DatasetSession` owns collision-safe output allocation, manifest state, component status, and orderly shutdown.

**Tech Stack:** Python 3.12, Tkinter, MediaPipe Tasks 0.10.21, OpenCV 4.11, MSS 10.2, PyAudioWPatch 0.2.12.8, faster-whisper 1.2.1, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-25-multimodal-dataset-collector-design.md`

## Global Constraints

- Windows 10 version 2004 or newer is required for `WDA_EXCLUDEFROMCAPTURE`.
- All processing and transcription remain local after explicit model download.
- Facial CSV and events are always stored, so every session requires consent attestation.
- Optional video/audio/transcript controls default to off at application startup.
- Transcript language is fixed to English and the default model is `base.en`, CPU `int8`.
- Meeting/system and microphone audio remain separate; UI labels are `Student` and `You`.
- Current observable actions are not confusion, emotion, attention, engagement, or cognitive-load labels.
- No participant names, identity recognition, cloud services, or model training are introduced.
- This workspace is not currently a Git repository; replace commit steps with explicit test checkpoints and do not initialize Git without user instruction.

## Review Focus

- An audio device disappears during capture: close only that track, report the error, and preserve other streams.
- A transcript worker is slower than real time: bound memory, report lag/drops, and never block face capture.
- Pause/resume occurs mid-audio and mid-transcript chunk: flush a segment and preserve a real session-time gap.
- The selected region touches a monitor edge or uses negative coordinates: place and clamp the transcript panel without covering the region.
- Disk writes fail after useful data exists: stop the session, retain partial files, and leave a valid `incomplete` manifest.

---

### Task 1: Dependencies, Session Options, And Shared Clock

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Create: `src/session_types.py`
- Create: `src/session_clock.py`
- Create: `tests/test_session_types.py`
- Create: `tests/test_session_clock.py`

**Interfaces:**
- Produces: `SessionOptions(video: bool, system_audio: bool, microphone: bool, transcript: bool, consent_confirmed: bool, participant_id: str)`.
- Produces: `SessionOptions.validation_error() -> str | None` and `persistent_capture_enabled -> bool`.
- Produces: `SessionClock(clock=time.perf_counter)`, `start()`, `elapsed_s()`, and `started_at_local`.
- Produces: `ComponentState` enum and immutable `ComponentStatus` for UI/controller events.

- [ ] **Step 1: Add failing option-validation tests**

```python
class SessionOptionsTests(unittest.TestCase):
    def test_every_session_requires_consent(self):
        options = SessionOptions(consent_confirmed=False)
        self.assertEqual(options.validation_error(), "Confirm participant consent")

    def test_transcript_requires_an_audio_source(self):
        options = SessionOptions(transcript=True, consent_confirmed=True)
        self.assertEqual(options.validation_error(), "Transcript requires meeting audio or microphone")

    def test_participant_id_is_trimmed_and_rejects_path_characters(self):
        self.assertEqual(SessionOptions(participant_id="  learner-07  ").participant_id, "learner-07")
        with self.assertRaises(ValueError):
            SessionOptions(participant_id="../student")
```

- [ ] **Step 2: Add failing shared-clock tests using a fake callable clock**

```python
def test_clock_has_one_origin_and_keeps_advancing_through_pause(self):
    fake = FakeClock([100.0, 101.25, 104.0])
    clock = SessionClock(clock=fake)
    clock.start()
    self.assertEqual(clock.elapsed_s(), 1.25)
    self.assertEqual(clock.elapsed_s(), 4.0)
```

- [ ] **Step 3: Run the focused tests and confirm imports fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_session_types tests.test_session_clock -v`

Expected: FAIL because `src.session_types` and `src.session_clock` do not exist.

- [ ] **Step 4: Implement immutable session types and the monotonic clock**

```python
@dataclass(frozen=True)
class SessionOptions:
    video: bool = False
    system_audio: bool = False
    microphone: bool = False
    transcript: bool = False
    consent_confirmed: bool = False
    participant_id: str = ""

    def validation_error(self) -> str | None:
        if not self.consent_confirmed:
            return "Confirm participant consent"
        if self.transcript and not (self.system_audio or self.microphone):
            return "Transcript requires meeting audio or microphone"
        return None
```

Normalize the participant ID in `__post_init__`, allow letters, digits, spaces,
underscore, and hyphen, cap it at 64 characters, and reject path separators and
`..`. Implement `SessionClock.start()` as single-use and clamp tiny negative
elapsed values to zero.

- [ ] **Step 5: Pin compatible dependencies and ignore local Whisper weights**

Append:

```text
PyAudioWPatch==0.2.12.8
faster-whisper==1.2.1
```

Add `models/faster-whisper-*/` and generated session folders to `.gitignore`
without changing existing model exclusions.

- [ ] **Step 6: Run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_session_types tests.test_session_clock -v`

Expected: PASS.

### Task 2: Collision-Safe Dataset Directory And Manifest

**Files:**
- Create: `src/dataset_session.py`
- Create: `tests/test_dataset_session.py`
- Modify: `src/recording_session.py`
- Modify: `tests/test_session_recorder.py`

**Interfaces:**
- Consumes: `SessionOptions`, `SessionClock`, and `CaptureRegion`.
- Produces: `DatasetSession.create(parent, options, region, clock, metadata) -> DatasetSession`.
- Produces: `write_feature(frame)`, `write_event(event)`, `update_component(status)`, `add_warning(text)`, `mark_drop(kind)`, and `close(status="closed")`.
- Produces properties: `directory`, `manifest_path`, `raw_row_count`, `event_row_count`, and `path` (compatibility alias for facial CSV).

- [ ] **Step 1: Write failing allocation and manifest tests**

Test that an empty parent creates `session_001/`, an existing `session_003/`
causes `session_004/`, and names such as `session_notes/` are ignored. Assert
exclusive retry when another creator wins a race.

```python
session = DatasetSession.create(folder, options, region, clock, metadata={})
manifest = json.loads((session.directory / "manifest.json").read_text("utf-8"))
self.assertEqual(manifest["status"], "recording")
self.assertEqual(manifest["region"], {"left": 10, "top": 20, "width": 300, "height": 200})
self.assertTrue(manifest["consent"]["confirmed"])
```

- [ ] **Step 2: Add failure-retention tests**

Cover empty startup removal, populated session preservation, atomic manifest
replacement, idempotent close, a simulated `OSError("disk full")`, and valid
`incomplete` JSON after a non-empty write failure.

- [ ] **Step 3: Run the focused tests and verify they fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_dataset_session -v`

Expected: FAIL because `DatasetSession` does not exist.

- [ ] **Step 4: Implement directory allocation and atomic manifest writes**

Use `mkdir(exist_ok=False)` for reservation and `manifest.json.tmp` followed by
`Path.replace()` for updates. Initialize these core files immediately:

```text
manifest.json
facial_features.csv
facial_events.csv
```

Preserve the existing `RecordingSession` public behavior as a thin compatibility
adapter only where old tests/readers require it; new sessions are owned by
`DatasetSession`.

- [ ] **Step 5: Implement close ordering and partial-data policy**

Close CSV writers before setting `status=closed`. On an error after data exists,
set `status=incomplete`, retain files, and append a structured error containing
component, message, and session timestamp. Remove the directory only when no
data rows/media samples have been accepted.

- [ ] **Step 6: Run recorder and dataset tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_dataset_session tests.test_session_recorder tests.test_action_event_recorder -v`

Expected: PASS.

### Task 3: Comprehensive Blendshape And Collection-Quality CSV

**Files:**
- Modify: `src/feature_data.py`
- Modify: `src/session_recorder.py`
- Modify: `src/meeting_tracker.py`
- Modify: `tests/test_feature_data.py`
- Modify: `tests/test_session_recorder.py`
- Modify: `tests/test_meeting_tracker.py`

**Interfaces:**
- Extends: `FeatureFrame.blendshapes: tuple[tuple[str, float], ...]`.
- Extends: `FeatureFrame.processing_ms`, `frame_gap_ms`, and `capture_drop_count`.
- Produces: canonical `BLENDSHAPE_NAMES` and `blendshape_<snake_case_name>` CSV columns.
- Extends: `MeetingTracker(..., session_clock: SessionClock, frame_callback: Callable[[CapturedVideoFrame], None] | None)`.

- [ ] **Step 1: Write failing blendshape extraction tests**

Use a fake result containing known and unknown category order. Assert extraction
stores every finite category, orders values by canonical name, clamps no valid
MediaPipe score, and ignores non-finite scores.

```python
frame = extract_feature_frame(result, 1.25, 8)
self.assertIn(("eyeBlinkLeft", 0.72), frame.blendshapes)
self.assertIn(("mouthPressRight", 0.31), frame.blendshapes)
```

- [ ] **Step 2: Write failing CSV schema and quality-field tests**

Assert existing derived columns remain, all canonical MediaPipe blendshapes have
stable prefixed columns, missing-face rows leave blendshapes empty, and quality
fields serialize with fixed precision.

- [ ] **Step 3: Write failing tracker timestamp tests**

Inject one `SessionClock` into the tracker and assert feature and captured-frame
callbacks receive the same timestamp. Simulate a slow detection call and assert
`processing_ms` and `frame_gap_ms` reflect it without creating a second origin.

- [ ] **Step 4: Run focused tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_feature_data tests.test_session_recorder tests.test_meeting_tracker -v`

Expected: FAIL on missing fields/interfaces.

- [ ] **Step 5: Implement comprehensive feature extraction**

Keep the current named derived fields so detector/UI code remains readable.
Store all finite raw category values separately. Define canonical blendshape
headers from the MediaPipe face model's documented category set, and route any
unexpected category names to manifest warnings instead of changing a CSV header
mid-session.

- [ ] **Step 6: Make tracker use the shared clock and publish video frames**

Define an immutable frame envelope:

```python
@dataclass(frozen=True)
class CapturedVideoFrame:
    source_frame_index: int
    timestamp_s: float
    bgr: np.ndarray
```

Publish a contiguous BGR copy through `frame_callback` before MediaPipe RGB
conversion. The callback only enqueues; it must not encode synchronously.

- [ ] **Step 7: Run focused and existing action tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_feature_data tests.test_session_recorder tests.test_meeting_tracker tests.test_action_detection tests.test_action_temporal -v`

Expected: PASS.

### Task 4: Optional Selected-Region Video Writer

**Files:**
- Create: `src/video_recorder.py`
- Create: `tests/test_video_recorder.py`
- Modify: `src/dataset_session.py`

**Interfaces:**
- Consumes: `CapturedVideoFrame`, output paths, expected region size, requested FPS.
- Produces: `VideoRecorder.start()`, `submit(frame) -> bool`, `pause(timestamp_s)`, `resume(timestamp_s)`, `stop(timeout_s=5.0)`.
- Produces: `VideoStats(written_frames, dropped_frames, codec, failure)`.

- [ ] **Step 1: Write failing tests with a fake OpenCV writer**

Cover successful MP4 initialization, exact selected-region dimensions, timestamp
CSV rows only for written frames, and rejection of wrong-sized frames.

- [ ] **Step 2: Add bounded-queue and codec-failure tests**

Use a capacity-one queue and a blocked fake writer. Assert `submit()` never waits,
drops the oldest unwritten frame, increments `dropped_frames`, and face-side code
continues. Assert `isOpened() == False` raises `VideoRecorderUnavailable` before
the worker reports ready.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_video_recorder -v`

Expected: FAIL because the recorder does not exist.

- [ ] **Step 4: Implement the writer worker and timestamp sidecar**

Use `cv2.VideoWriter_fourcc(*"mp4v")` as the first codec. Record the actual codec
and dimensions. Queue operations use `put_nowait`; on full, remove one old item
then retry once. `video_timestamps.csv` has exactly:

```text
video_frame_index,source_frame_index,timestamp_s
```

- [ ] **Step 5: Integrate video ownership into `DatasetSession`**

Create the video files only when requested and initialization succeeds. Report
unavailability as a component status before capture starts. Include write/drop
counts and codec in final manifest.

- [ ] **Step 6: Run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_video_recorder tests.test_dataset_session -v`

Expected: PASS.

### Task 5: Separate WASAPI Loopback And Microphone Recording

**Files:**
- Create: `src/audio_devices.py`
- Create: `src/audio_recorder.py`
- Create: `tests/test_audio_devices.py`
- Create: `tests/test_audio_recorder.py`
- Modify: `src/dataset_session.py`

**Interfaces:**
- Produces: `AudioSource` enum with `SYSTEM_AUDIO` and `MICROPHONE`.
- Produces: `AudioDeviceInfo(index, name, sample_rate, channels, loopback)`.
- Produces: `discover_default_devices(pyaudio_factory) -> dict[AudioSource, AudioDeviceInfo]`.
- Produces: `AudioRecorder(source, device, wav_path, segment_callback, status_callback, clock, ...)` with `start/pause/resume/stop`.
- Produces: `AudioChunk(source, segment_index, start_s, end_s, sample_rate, channels, pcm_bytes)`.

- [ ] **Step 1: Write failing device-discovery tests**

Mock PyAudioWPatch and assert the default WASAPI loopback device is selected for
system audio, the default input for microphone, exact device names are retained,
and absence raises a source-specific `AudioDeviceUnavailable`.

- [ ] **Step 2: Write failing WAV and segment tests**

Use fake byte chunks and clock values. Assert each source writes its own WAV,
`audio_segments.csv` maps sample offsets to session time, Pause closes a segment,
Resume starts a new one after a real timestamp gap, and no silence is inserted.

- [ ] **Step 3: Add disconnect and blocking-read tests**

Make the fake stream raise midway and assert only that recorder emits `ERROR`.
Make `read()` block and assert `stop(timeout_s=2.0)` returns by closing the stream
before joining. Verify buffered valid samples remain in WAV.

- [ ] **Step 4: Run focused tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_audio_devices tests.test_audio_recorder -v`

Expected: FAIL because audio modules do not exist.

- [ ] **Step 5: Implement lazy PyAudioWPatch discovery**

Import `pyaudiowpatch` inside the default factory, not at module import. Use the
package's WASAPI helpers to find the default loopback endpoint. Return readable,
source-specific errors without preventing the application window from opening.

- [ ] **Step 6: Implement one recorder per source**

Write PCM WAV through the standard `wave` module. Capture in short hardware
chunks and aggregate transcript windows separately. Never mix sources. Call
`segment_callback` with immutable chunks after their WAV data has been accepted.

- [ ] **Step 7: Integrate tracks and `audio_segments.csv`**

The dataset owns one shared sidecar writer but receives source-tagged segment
records. Final manifest records selected device, format, sample count, segment
count, and source-specific errors.

- [ ] **Step 8: Run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_audio_devices tests.test_audio_recorder tests.test_dataset_session -v`

Expected: PASS.

### Task 6: Local English Faster-Whisper And Transcript Files

**Files:**
- Create: `src/transcription.py`
- Create: `src/transcript_writer.py`
- Create: `scripts/download_whisper_model.py`
- Create: `tests/test_transcription.py`
- Create: `tests/test_transcript_writer.py`
- Modify: `.gitignore`
- Modify: `src/dataset_session.py`

**Interfaces:**
- Consumes: `AudioChunk` from either source.
- Produces: `TranscriptSegment(segment_id, start_s, end_s, source, speaker, text, language="en")`.
- Produces: `LocalEnglishTranscriber(model_path, model_factory=None)` with `transcribe(chunk) -> tuple[TranscriptSegment, ...]`.
- Produces: `TranscriptionWorker.submit(chunk) -> bool`, `start()`, `stop(grace_s=10.0)`, `lag_s`, and `dropped_chunks`.
- Produces: `TranscriptWriter.write(segment)` and `close()` for JSONL/SRT.

- [ ] **Step 1: Write failing timestamp/source mapping tests**

Fake Whisper segments at 0.25-to-1.50 seconds inside a chunk beginning at 12.0.
Assert output is 12.25-to-13.50, system source maps to `Student`, microphone maps
to `You`, empty/whitespace text is discarded, and language remains `en`.

- [ ] **Step 2: Write failing invocation and model-error tests**

Assert model construction uses local path, `device="cpu"`, `compute_type="int8"`;
transcription passes `language="en"`, `task="transcribe"`, and VAD filtering.
Assert a missing model raises `TranscriptionUnavailable` without attempting a
network download.

- [ ] **Step 3: Write failing queue-overload and slow-worker tests**

Block the fake model, fill a bounded queue, and assert additional submissions
return immediately, increment `dropped_chunks`, and do not affect a fake face
callback. Test bounded Stop grace records unfinished work instead of hanging.

- [ ] **Step 4: Write failing JSONL/SRT tests**

Assert UTF-8 JSON Lines fields and SRT numbering/timestamps. Include overlapping
`You` and `Student` segments and verify both survive in start-time order.

- [ ] **Step 5: Run focused tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_transcription tests.test_transcript_writer -v`

Expected: FAIL because transcription modules do not exist.

- [ ] **Step 6: Implement lazy local model loading and transcription**

Import `WhisperModel` only when transcription starts. Pass in-memory mono
`float32` audio normalized from PCM bytes, so no temporary audio file or system
FFmpeg executable is needed. Reject a missing local model directory before model
construction.

- [ ] **Step 7: Implement the bounded worker and transcript writers**

One worker services source-tagged chunks in queue order. Publish accepted
segments through a callback, write JSONL immediately, and maintain SRT with
stable segment IDs. Expose queue age as transcript lag and all drop counts for
the UI/manifest.

- [ ] **Step 8: Add explicit model download script**

The script accepts `--model base.en` and `--output models/faster-whisper-base-en`,
uses faster-whisper/Hugging Face download behavior only during setup, prints the
resolved local directory, and exits nonzero with a readable network/disk error.
Normal app startup never invokes this script.

- [ ] **Step 9: Run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_transcription tests.test_transcript_writer -v`

Expected: PASS.

### Task 7: Capture-Excluded Transcript Panel

**Files:**
- Create: `src/transcript_panel.py`
- Create: `tests/test_transcript_panel.py`
- Modify: `src/control_panel.py`
- Modify: `tests/test_windows_overlay.py`

**Interfaces:**
- Produces: `transcript_panel_geometry(region, panel_size, work_area) -> str`.
- Produces: `TranscriptPanel(root, region, exclude_native=...)` with `publish(segment)`, `draw_pending()`, `set_region(region)`, `set_collapsed(bool)`, and `destroy()`.
- Extends view: `show_transcript_panel(region)`, `publish_transcript(segment)`, and `hide_transcript_panel()`.

- [ ] **Step 1: Write failing placement tests**

Test right-side placement, left fallback, clamping on top/bottom edges, negative
monitor coordinates, and a region wider than remaining work area. Assert the
panel never intentionally overlaps the selected region when either side has
enough space.

- [ ] **Step 2: Write failing capture-exclusion and lifecycle tests**

Use fake Tk objects/native function. Assert `exclude_window_from_capture` is
called after native window creation, recent transcript segments are bounded,
collapse retains data, reposition follows region changes, and destroy is
idempotent.

- [ ] **Step 3: Run focused tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_transcript_panel tests.test_windows_overlay -v`

Expected: FAIL because the panel does not exist.

- [ ] **Step 4: Implement the borderless panel**

Use one capture-excluded `tk.Toplevel`, a compact header, collapse icon button,
and a read-only wrapping text/list area. Keep a fixed responsive width and clamp
height to the monitor work area. Use `LatestTranscriptSegments` plus the existing
Tk callback/draw pattern so worker threads never touch Tk.

- [ ] **Step 5: Wire panel methods into `ControlPanel`**

Create the panel only when transcript is enabled and the session starts. Keep it
beside the selected region, hide it at Stop, and destroy it at Quit. Capture
exclusion failure disables transcript display and reports a component error; it
must not create an infinite capture loop.

- [ ] **Step 6: Run focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_transcript_panel tests.test_windows_overlay tests.test_overlay_window -v`

Expected: PASS.

### Task 8: Controller, Consent UI, And Worker Orchestration

**Files:**
- Create: `src/session_orchestrator.py`
- Create: `tests/test_session_orchestrator.py`
- Modify: `src/app_controller.py`
- Modify: `src/control_panel.py`
- Modify: `src/main.py`
- Modify: `src/capture_types.py`
- Modify: `tests/test_app_controller.py`
- Modify: `tests/test_control_panel_keys.py`
- Modify: `tests/test_main_import.py`

**Interfaces:**
- Produces: `SessionOrchestrator(dataset, options, region, clock, callbacks, factories)` with `start()`, `submit_video(frame)`, `pause()`, `resume()`, and `stop()`.
- Extends view: `get_session_options() -> SessionOptions`, `publish_component_status(status)`, `publish_session_stats(stats)`, and confirmation callback for Quit while recording.
- Changes controller recorder factory to a dataset/orchestrator factory while preserving dependency injection for tests.

- [ ] **Step 1: Write failing orchestrator startup/rollback tests**

Assert startup order is dataset, video, audio sources, transcription, then tracker
attachment. Simulate each factory failing. Assert already-started workers close
in reverse order, empty startup output is removed, and failures identify the
component rather than raising through Tkinter.

- [ ] **Step 2: Write failing component-isolation tests**

Simulate microphone disconnect, unavailable loopback, video writer failure, and
Whisper failure. Assert available components continue, manifest errors are
updated, and transcript remains active if at least one requested audio source is
still producing chunks.

- [ ] **Step 3: Write failing critical-storage and shutdown tests**

Raise `OSError("disk full")` from facial, audio-sidecar, video-sidecar, and
transcript writes. Assert the controller begins one orderly Stop, leaves a valid
incomplete manifest, applies worker join timeouts, and ignores stale callbacks
using the existing generation guard.

- [ ] **Step 4: Write failing UI eligibility tests**

Test these exact Start conditions:

```text
region + folder + consent                         -> enabled
missing consent                                   -> disabled
transcript + no audio                             -> disabled with explanation
transcript + meeting audio + consent              -> enabled
transcript + microphone + consent                 -> enabled
running/paused/shutting down                      -> disabled
```

Also assert options default off, participant ID is optional, WASAPI warning is
visible near audio controls, and component status text does not resize the
button layout.

- [ ] **Step 5: Run focused tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_session_orchestrator tests.test_app_controller tests.test_main_import -v`

Expected: FAIL on missing orchestration/options interfaces.

- [ ] **Step 6: Implement `SessionOrchestrator`**

Own optional video/audio/transcript workers and route immutable events. Start
only explicitly requested sources. Keep all queues bounded. Pause flushes active
audio/transcript windows, pauses video acceptance, and leaves the shared clock
running. Stop prevents new submissions, stops producers, drains consumers for
their bounded grace periods, closes dataset writers, and finalizes manifest.

- [ ] **Step 7: Extend the control panel without nested card layouts**

Add a compact `Data collection` section with checkboxes, participant ID, consent,
component status rows, elapsed time, transcript lag, drop counts, and estimated
size. Increase minimum geometry and use a scrollable content region only if the
current display height cannot fit controls. Preserve DPI awareness and stable
button dimensions.

- [ ] **Step 8: Refactor `AppController` to coordinate one session lifecycle**

Create the shared clock once, create `DatasetSession`, initialize requested
workers, then pass the same clock and video submit callback to `MeetingTracker`.
All worker callbacks go through `view.schedule`. Use generation IDs to discard
late status/transcript callbacks after Stop or reselection.

- [ ] **Step 9: Add Quit confirmation and clean dependency errors**

Quit while running/paused asks once. Confirm follows orderly Stop; cancel keeps
the session unchanged. Missing PyAudioWPatch/faster-whisper/model paths appear as
component availability messages and never prevent a face-only session or app
startup.

- [ ] **Step 10: Run integration-focused tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_session_orchestrator tests.test_app_controller tests.test_control_panel_keys tests.test_main_import -v`

Expected: PASS.

### Task 9: Setup, Documentation, And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/system-outputs-and-observable-actions.md`
- Create: `docs/dataset-schema.md`
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Test: all files under `tests/`

**Interfaces:**
- Documents exact install, model-download, run, consent, manual test, and output
  interpretation procedures.

- [ ] **Step 1: Install pinned dependencies into the existing virtual environment**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Expected: installation succeeds on Python 3.12 and `pip check` reports no broken
requirements. If dependency resolution changes a current package, record the
resolved version in verification notes and rerun the full suite before accepting
it.

- [ ] **Step 2: Download the local English model explicitly**

Run:

```powershell
.\.venv\Scripts\python.exe .\scripts\download_whisper_model.py --model base.en --output .\models\faster-whisper-base-en
```

Expected: the script reports a local model directory containing the model config
and weights. This is the only setup step that downloads model weights.

- [ ] **Step 3: Update README with exact commands and privacy warnings**

Document Python 3.12, dependency installation, both model download scripts, app
run command, four checkboxes, mandatory consent, `Student`/`You` source meaning,
WASAPI whole-output limitation, Pause timestamp gaps, clean Stop/Quit, and how to
run without optional media.

- [ ] **Step 4: Document every dataset field and interpretation boundary**

`docs/dataset-schema.md` lists each file, column/JSON field, unit, missing-value
meaning, source, alignment rule, and whether the value is raw model output or a
derived engineering feature. Update the existing output catalog to link to it
and state that observable events are never ground-truth confusion labels.

- [ ] **Step 5: Run the complete automated suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

Expected: all tests pass and dependencies are consistent.

- [ ] **Step 6: Run static import and syntax checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
.\.venv\Scripts\python.exe -c "from src.main import run; from src.transcription import LocalEnglishTranscriber; from src.audio_recorder import AudioRecorder; print('imports ok')"
```

Expected: exit code 0 and `imports ok`.

- [ ] **Step 7: Perform the hardware-dependent manual checklist**

Run the app and verify consent gating, selected-region-only MP4, separate WAV
playback, English `Student`/`You` transcript beside the selected region, no UI in
captured video, acceptable face FPS while transcription runs, Pause gaps, audio
device failure isolation, and timestamp alignment against a visible timer.
Document hardware/model performance and any transcript lag; do not claim the
manual items passed unless they were actually observed.

## Completion Evidence

Implementation is complete only when the full automated suite and `pip check`
pass, model setup succeeds, and the user receives exact manual webcam/meeting,
audio, video, transcript, privacy, and synchronization test steps. Hardware-only
acceptance items remain explicitly marked for user verification if this session
cannot operate the user's meeting and audio devices.
