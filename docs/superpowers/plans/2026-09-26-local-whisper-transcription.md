# Local Whisper Transcription Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve live English Whisper transcription, add a stronger local final-transcription pass, and reduce an audio-and-transcript session to one stereo WAV, one feature CSV, one transcript JSONL, one session JSON, and optional video.

**Architecture:** Two capture workers emit microphone and WASAPI chunks to one clock-aligned stereo writer and to a bounded live-transcription worker. A separate post-session worker reads the stereo channels, runs a stronger Whisper model, maps model offsets through the session audio intervals, and atomically adds canonical final records to the same transcript file.

**Tech Stack:** Python 3.12, Tkinter, NumPy, SciPy, PyAudioWPatch, faster-whisper 1.2.1, MediaPipe, OpenCV, unittest.

**Spec:** `docs/superpowers/specs/2026-09-26-local-whisper-transcription-design.md`

## Global Constraints

- All transcription remains local and English-only; no Azure, plugin, or cloud upload.
- Keep `audio.wav` PCM stereo with left=`You`/microphone and right=`Student`/WASAPI loopback.
- Preserve one shared monotonic session clock across audio, transcript, face CSV, and optional video.
- Do not amplitude-normalize the samples persisted in `audio.wav`; process only inference copies.
- Never download model files while a session is active.
- Face tracking and UI work must not block on audio encoding or Whisper inference.
- Existing sessions remain untouched; new sessions use schema version `3.0`.
- No confusion, emotion, attention, engagement, cognitive-load, or identity inference is added.
- The directory is not a Git repository, so execution records test checkpoints but does not create commits.

## Review Focus

- Different microphone/loopback sample rates and chunk arrival order must preserve left/right alignment; Task 4 tests 44.1 kHz versus 48 kHz and late chunks.
- A missing or disconnected source must become silence in only its own channel; Task 4 tests startup absence and mid-session loss.
- Pause/Resume must map final Whisper offsets back to session time without collapsing the pause; Tasks 1, 4, and 6 test interval conversion.
- Quiet speech processing must not turn silence/noise into loud fabricated input; Task 3 tests silence, gain cap, and limiter behavior.
- Cancellation, model failure, or out-of-memory during the final pass must preserve the existing live transcript; Task 6 tests atomic replacement and failure cleanup.

---

## File Structure

**Create**

- `src/audio_quality.py`: audio-level classification and non-destructive inference preprocessing.
- `src/stereo_audio.py`: session-clock alignment, stereo WAV writing, source silence, and interval statistics.
- `src/final_transcription.py`: stereo channel reading, interval mapping, cancellable final Whisper job.
- `tests/test_audio_quality.py`: deterministic level and gain tests.
- `tests/test_stereo_audio.py`: stereo alignment, resampling, silence, and pause tests.
- `tests/test_final_transcription.py`: final-pass mapping, cancellation, progress, and error tests.

**Modify**

- `src/audio_recorder.py`: make device workers emit chunks without owning output WAV files.
- `src/transcription.py`: model configuration, quality preprocessing, transcript phase/status, and stable rolling-window behavior.
- `src/transcript_writer.py`: write one JSONL file and atomically add final records; remove SRT generation.
- `src/dataset_session.py`: create `features.csv` and `session.json`, store compact metadata and audio intervals.
- `src/session_recorder.py`: add observable-action snapshot and video-index columns to the single CSV.
- `src/meeting_tracker.py`: publish the action snapshot with each feature row and capture accepted video indices.
- `src/video_recorder.py`: return reserved video indices and stop creating `video_timestamps.csv`.
- `src/session_orchestrator.py`: connect capture workers, stereo writer, level callbacks, and live transcription.
- `src/session_types.py`: add local Whisper model choices and final-transcription component states.
- `src/app_controller.py`: retain the completed session and launch/cancel final transcription.
- `src/control_panel.py`: add audio meters, local model choice, and Generate Final Transcript button.
- `src/transcript_panel.py`: show `LIVE`/`FINAL` mode and replace the visible stream after final completion.
- `src/main.py`: bind the final-transcription action.
- `scripts/download_whisper_model.py`: support explicit live/final model destinations.
- `README.md`: document setup, workflow, files, performance, and manual checks.
- `docs/dataset-schema.md`: document schema `3.0`, stereo channels, transcript phases, and fallback rules.
- Existing tests corresponding to every modified module.

## Task 1: Compact Session Schema And Timeline Metadata

**Files:**
- Modify: `src/dataset_session.py`
- Modify: `src/session_types.py`
- Modify: `tests/test_dataset_session.py`
- Modify: `tests/test_session_types.py`

**Interfaces:**
- Produces: `DatasetSession.session_path: Path`, `record_audio_interval(interval: dict) -> None`, `set_audio_metadata(metadata: dict) -> None`, `set_transcription_metadata(metadata: dict) -> None`, and `snapshot() -> dict`.
- Preserves: `directory`, `raw_path`, `raw_row_count`, `write_feature`, `write_event`, `update_component`, `add_warning`, `add_error`, `mark_drop`, and idempotent `close` for current callers.

- [ ] **Step 1: Write failing schema tests**

Add tests that create a session and assert the initial file set is exactly `features.csv` and `session.json`, schema version is `3.0`, audio interval metadata survives an atomic update, action events are stored inside `session.json`, and Pause intervals can represent `{session_start_s, session_end_s, wav_start_frame, wav_end_frame}`.

```python
session = DatasetSession.create(folder, options, region, clock)
self.assertEqual(
    {path.name for path in session.directory.iterdir()},
    {"features.csv", "session.json"},
)
session.record_audio_interval({
    "session_start_s": 0.0,
    "session_end_s": 5.0,
    "wav_start_frame": 0,
    "wav_end_frame": 240000,
})
self.assertEqual(session.snapshot()["audio"]["intervals"][0]["wav_end_frame"], 240000)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_dataset_session tests.test_session_types -v`

Expected: FAIL because the current implementation creates `manifest.json`, `facial_features.csv`, and `facial_events.csv` and has no compact metadata methods.

- [ ] **Step 3: Implement schema `3.0`**

Change session creation to open only `features.csv`, initialize `session.json`, and use one locked helper for atomic JSON writes. Keep events as compact JSON records so current detector callbacks do not lose completed event information.

```python
self.session_path = directory / "session.json"
self._session = {
    "schema_version": "3.0",
    "status": "recording",
    "audio": {"file": None, "channels": {}, "intervals": []},
    "transcription": {"live": {}, "final": {"status": "not_started"}},
    "observable_events": [],
    "components": {}, "warnings": [], "errors": [], "drops": {},
}
```

Make `write_event(event)` append `asdict(event)` to `observable_events` and atomically persist. Ensure `remove_if_empty=True` removes only a newly created session that contains no feature rows or media.

- [ ] **Step 4: Run focused tests**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_dataset_session tests.test_session_types -v`

Expected: PASS.

- [ ] **Step 5: Run current controller/session regressions**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_app_controller tests.test_session_recorder -v`

Expected: PASS after updating filename expectations from `facial_features.csv`/`manifest.json` to `features.csv`/`session.json`.

## Task 2: One Feature CSV With Action And Video Alignment

**Files:**
- Modify: `src/feature_data.py`
- Modify: `src/session_recorder.py`
- Modify: `src/meeting_tracker.py`
- Modify: `src/video_recorder.py`
- Modify: `src/app_controller.py`
- Modify: `tests/test_session_recorder.py`
- Modify: `tests/test_meeting_tracker.py`
- Modify: `tests/test_video_recorder.py`
- Modify: `tests/test_app_controller.py`

**Interfaces:**
- Produces: `RecordedFeature(frame: FeatureFrame, action_snapshot: ActionSnapshot | None, video_frame_index: int | None)`.
- Changes: video callback returns `int | None`; an integer is the reserved MP4 frame index and `None` means the frame was not accepted.
- Changes: feature callback consumes one `RecordedFeature` rather than a bare `FeatureFrame`.

- [ ] **Step 1: Write failing combined-row tests**

Assert `CSV_FIELDS` includes `video_frame_index`, `action_mode`, `active_action_ids`, `active_action_strengths`, and `action_calibration_progress`. Verify one written row contains a detector snapshot and video index without creating an event CSV.

```python
record = RecordedFeature(
    FeatureFrame(1.25, 7, True),
    ActionSnapshot(ActionMode.TRACKING, actions=(ActionDisplay("blink", "Blink", .1, .8),)),
    video_frame_index=3,
)
recorder.write(record)
self.assertEqual(row["video_frame_index"], "3")
self.assertEqual(row["active_action_ids"], "blink")
```

- [ ] **Step 2: Write failing video reservation tests**

Change the fake video writer test to assert `submit(frame) == 0` for the first accepted frame and `None` when a full queue rejects a new frame. Assert no timestamp sidecar is created.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_session_recorder tests.test_video_recorder tests.test_meeting_tracker tests.test_app_controller -v`

Expected: FAIL because snapshots and video indices are not part of feature rows and video currently creates a sidecar.

- [ ] **Step 4: Implement recorded feature rows**

Add the immutable wrapper and serialize action lists deterministically with `|` separators. In `MeetingTracker._run`, call `detector.update(feature_frame)` before publishing the feature, reserve the video index, then publish one combined record.

```python
video_index = self._frame_callback(captured) if self._frame_callback else None
snapshot, action_events = detector.update(feature_frame)
self._feature_callback(RecordedFeature(feature_frame, snapshot, video_index))
```

Change `VideoRecorder.submit` to reject the newest frame when full, reserve monotonically increasing indices before enqueue, and write MP4 only. Store final written/dropped counts through `VideoStats` in `session.json`.

- [ ] **Step 5: Adapt controller presentation without changing displayed values**

`AppController` passes `record.frame` to `ControlPanel.publish_features` while sending the complete `RecordedFeature` to the CSV recorder. Keep stale-generation guards and existing overlay behavior.

- [ ] **Step 6: Run focused tests**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_session_recorder tests.test_video_recorder tests.test_meeting_tracker tests.test_app_controller -v`

Expected: PASS.

## Task 3: Audio Level Analysis And Non-Destructive Inference Preparation

**Files:**
- Create: `src/audio_quality.py`
- Create: `tests/test_audio_quality.py`
- Modify: `src/transcription.py`
- Modify: `tests/test_transcription.py`

**Interfaces:**
- Produces: `AudioLevelState`, `AudioLevelMetrics(rms, peak, state)`, `analyze_level(samples) -> AudioLevelMetrics`.
- Produces: `prepare_inference_audio(samples, target_rms=0.10, max_gain=8.0, limit=0.98) -> tuple[np.ndarray, float]` where the second value is applied gain.
- Consumes: float32 mono samples in `[-1, 1]`; never mutates the input array.

- [ ] **Step 1: Write failing audio-quality tests**

Cover empty/silent input, `Too quiet`, `Good`, clipping, maximum gain, limiting, and immutability.

```python
source = np.full(1600, 0.002, np.float32)
prepared, gain = prepare_inference_audio(source, max_gain=4.0)
self.assertEqual(gain, 4.0)
self.assertLessEqual(float(np.max(np.abs(prepared))), 0.98)
np.testing.assert_array_equal(source, np.full(1600, 0.002, np.float32))
```

- [ ] **Step 2: Run the new tests and verify failure**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_audio_quality -v`

Expected: FAIL because `src.audio_quality` does not exist.

- [ ] **Step 3: Implement deterministic level and gain functions**

Use RMS `sqrt(mean(samples**2))`, absolute peak, fixed thresholds, a silence floor that returns an unchanged zero copy, `min(target_rms/rms, max_gain)`, and `np.clip` at the limiter. Avoid automatic noise reduction or filters in this milestone.

- [ ] **Step 4: Apply preprocessing only inside `LocalEnglishTranscriber`**

After resampling to 16 kHz, call `prepare_inference_audio`; preserve the original `AudioChunk.samples`. Pass explicit quiet-speech-aware VAD parameters and keep fixed English.

```python
audio, gain = prepare_inference_audio(audio)
segments, _ = self._model.transcribe(
    audio,
    language="en",
    task="transcribe",
    vad_filter=True,
    vad_parameters={"threshold": 0.35, "min_silence_duration_ms": 500},
    beam_size=5,
)
```

- [ ] **Step 5: Run quality and transcription tests**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_audio_quality tests.test_transcription -v`

Expected: PASS, including the existing 48 kHz to 16 kHz assertion.

## Task 4: Clock-Aligned Stereo WAV Recording

**Files:**
- Modify: `src/audio_recorder.py`
- Create: `src/stereo_audio.py`
- Modify: `tests/test_audio_recorder.py`
- Create: `tests/test_stereo_audio.py`

**Interfaces:**
- Produces: `AudioCaptureWorker(source, device, chunk_callback, status_callback, clock, stream_factory, frames_per_buffer=1024)`.
- Produces: `AudioInterval(session_start_s, session_end_s, wav_start_frame, wav_end_frame)`.
- Produces: `StereoAudioStats(sample_rate, written_frames, intervals, source_failures)`.
- Produces: `StereoAudioWriter(path, interval_callback, level_callback, status_callback, sample_rate=48000, queue_size=64)` with `start()`, `submit(AudioChunk) -> bool`, `pause(timestamp_s)`, `resume(timestamp_s)`, and `stop() -> StereoAudioStats`.

- [ ] **Step 1: Refactor capture tests first**

Write a fake stream test proving `AudioCaptureWorker` emits mono float chunks with source timestamps but creates no WAV file. Preserve overflow handling and bounded stop behavior.

- [ ] **Step 2: Write failing stereo tests**

Use tiny sample rates for deterministic arrays. Assert microphone samples appear only on the left, system samples only on the right, missing source samples become zero, 44.1/48 kHz inputs are resampled to the target rate, out-of-order/late chunks do not shift the opposite channel, and Pause creates two `AudioInterval` records.

```python
writer.submit(chunk(AudioSource.MICROPHONE, start_s=0.0, rate=4, samples=[.1, .2]))
writer.submit(chunk(AudioSource.SYSTEM_AUDIO, start_s=0.0, rate=4, samples=[.7, .8]))
left, right = read_stereo(path)
np.testing.assert_allclose(left[:2], [.1, .2], atol=1/32768)
np.testing.assert_allclose(right[:2], [.7, .8], atol=1/32768)
```

- [ ] **Step 3: Run focused tests and verify failure**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_audio_recorder tests.test_stereo_audio -v`

Expected: FAIL because each current recorder owns a separate WAV and no stereo coordinator exists.

- [ ] **Step 4: Implement source-only capture workers**

Keep `pcm16_to_mono`, but remove file ownership from device capture. Report device exceptions once and stop that source without terminating the other worker.

- [ ] **Step 5: Implement the stereo writer**

Resample chunks with `scipy.signal.resample_poly`, place samples by active-interval/session position, quantize only at PCM16 write time, and use silence for missing channel ranges. Bound the queue and report drops. On pause, flush the active interval; on resume, begin a new WAV-to-session mapping without writing pause-length silence.

- [ ] **Step 6: Run focused tests**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_audio_recorder tests.test_stereo_audio -v`

Expected: PASS.

## Task 5: Stronger Live Whisper With Stable Provisional Output

**Files:**
- Modify: `src/transcription.py`
- Modify: `src/transcript_writer.py`
- Modify: `tests/test_transcription.py`
- Modify: `tests/test_transcript_writer.py`

**Interfaces:**
- Changes: `TranscriptSegment` includes `phase: str = "live"` and `status: str = "committed"`.
- Produces: `TranscriptStore(path)` with `append_live(segment)`, `replace_with_final(segments)`, `read_phase(phase)`, and `close()`.
- Changes: `LocalEnglishTranscriber(model_path, model=None, model_factory=None, beam_size=5, phase="live")`.

- [ ] **Step 1: Write failing transcript-schema tests**

Assert JSONL contains one file only, writes `phase=live` and `status=committed`, does not create SRT, and preserves Unicode text.

- [ ] **Step 2: Write rolling-window regression tests**

Add tests for overlapping duplicate suppression, a phrase that crosses a window boundary, separate buffers for `You` and `Student`, queue overload accounting, and stop flushing only stable non-empty text.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_transcription tests.test_transcript_writer -v`

Expected: FAIL because phase/status and the single-file store are absent.

- [ ] **Step 4: Implement transcript phase and store**

Remove SRT handling. Serialize source enum values and append flushed live records to `transcript.jsonl`. Keep the file line-buffered during recording.

- [ ] **Step 5: Stabilize rolling output**

Retain the existing bounded source buffers and overlap, increase default window to 5 seconds, use `beam_size=5`, and suppress a candidate when its normalized text and time range are already covered by a committed segment for that source. Keep the last boundary phrase provisional until the next window or Stop.

- [ ] **Step 6: Run focused tests**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_transcription tests.test_transcript_writer -v`

Expected: PASS.

## Task 6: Local Final Transcription And Atomic Canonical Output

**Files:**
- Create: `src/final_transcription.py`
- Create: `tests/test_final_transcription.py`
- Modify: `src/transcript_writer.py`
- Modify: `tests/test_transcript_writer.py`

**Interfaces:**
- Produces: `map_wav_time_to_session(offset_s: float, sample_rate: int, intervals: Sequence[AudioInterval]) -> float | None`.
- Produces: `FinalTranscriptionJob(audio_path, intervals, model_path, store, progress_callback, completion_callback, transcriber_factory=LocalEnglishTranscriber)` with `start()`, `cancel()`, and `join(timeout_s)`.
- Consumes: left channel as `AudioSource.MICROPHONE`, right channel as `AudioSource.SYSTEM_AUDIO`.

- [ ] **Step 1: Write failing timestamp-mapping tests**

Test a two-interval session where WAV second `7.0` maps after a five-second Pause, offsets at interval boundaries, and offsets outside recorded ranges return `None`.

```python
intervals = (
    AudioInterval(0.0, 5.0, 0, 80000),
    AudioInterval(10.0, 15.0, 80000, 160000),
)
self.assertEqual(map_wav_time_to_session(7.0, 16000, intervals), 12.0)
```

- [ ] **Step 2: Write failing final-job tests**

Create a temporary stereo WAV and fake transcriber. Assert both channels are transcribed with deterministic speaker labels, progress is monotonic, final records use `phase=final/status=canonical`, and live records remain in the same file.

- [ ] **Step 3: Write atomic-failure tests**

Seed `transcript.jsonl` with live lines. Make the fake transcriber raise and separately cancel mid-job. Assert the original file is byte-for-byte unchanged and temporary files are removed.

- [ ] **Step 4: Run focused tests and verify failure**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_final_transcription tests.test_transcript_writer -v`

Expected: FAIL because the final job and atomic replacement do not exist.

- [ ] **Step 5: Implement channel reading and timeline conversion**

Read PCM16 stereo with `wave`, convert each channel to float32, split work by audio intervals so Pause mappings stay explicit, and call the supplied final transcriber with `phase="final"`. Never feed a mixed channel to Whisper.

- [ ] **Step 6: Implement cancellable atomic replacement**

Write all existing live records plus sorted final records to `transcript.jsonl.tmp`, flush and close it, then use `Path.replace` only after both channels succeed. Check a cancellation event between inference units and before replacement.

- [ ] **Step 7: Run focused tests**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_final_transcription tests.test_transcript_writer -v`

Expected: PASS.

## Task 7: Orchestration, Audio Meters, And Final-Transcript UI

**Files:**
- Modify: `src/session_orchestrator.py`
- Modify: `src/app_controller.py`
- Modify: `src/control_panel.py`
- Modify: `src/transcript_panel.py`
- Modify: `src/main.py`
- Modify: `tests/test_session_orchestrator.py`
- Modify: `tests/test_app_controller.py`
- Modify: `tests/test_control_panel_keys.py`
- Modify: `tests/test_transcript_panel.py`

**Interfaces:**
- `SessionOrchestrator` accepts `audio_level_callback(source, metrics)` and creates one `StereoAudioWriter` plus zero-to-two `AudioCaptureWorker`s.
- `ControlPanel.bind_actions(...)` gains `on_generate_final` and `on_cancel_final` callbacks.
- `ControlPanel.publish_audio_level(source, metrics)` updates fixed-width meter labels without changing layout.
- `TranscriptPanel.set_phase("live" | "final")` updates the heading and clears/reloads visible rows when final output becomes canonical.
- `AppController.generate_final_transcript()` operates only on the most recently stopped eligible session.

- [ ] **Step 1: Write failing orchestrator tests**

Assert requesting both sources constructs one stereo writer at `audio.wav`, starts two source workers, writes channel metadata/intervals to the dataset, sends chunks to both stereo and live transcription, and continues when one source factory fails.

- [ ] **Step 2: Write failing controller lifecycle tests**

Assert Generate Final is disabled before Stop, enabled only for a completed session containing audio and an installed final model, starts once, reports progress, can cancel, and does not permit Start/region reselection to race an active final job.

- [ ] **Step 3: Write failing UI tests**

Patch `ttk.Progressbar` and `ttk.Combobox` in the existing fake UI. Verify stable meter widgets for both sources, states `No signal/Too quiet/Good/Clipping`, local model choice `Balanced (small.en)` versus `Fast (base.en)`, final button state, and transcript heading changes from `LIVE` to `FINAL`.

- [ ] **Step 4: Run focused tests and verify failure**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_session_orchestrator tests.test_app_controller tests.test_control_panel_keys tests.test_transcript_panel -v`

Expected: FAIL because the current orchestrator owns separate WAV workers and the UI has no meters/final action.

- [ ] **Step 5: Rewire the orchestrator**

Create `audio.wav` once, route every chunk to the stereo writer, analyze levels before scheduling UI updates, and submit inference copies to live transcription. Persist audio metadata and intervals through `DatasetSession`; remove `audio_segments.csv`, source WAV filenames, SRT, and video timestamp paths.

- [ ] **Step 6: Implement final job lifecycle in the controller**

Store the last closed `DatasetSession.directory`, stop all live workers before enabling final generation, schedule progress/status updates onto Tk, and keep Quit bounded by cancelling and joining the final worker.

- [ ] **Step 7: Implement the compact UI**

Use two fixed-width meter rows and one `ttk.Progressbar`. Add one `ttk.Combobox` for live quality and one `Generate Final Transcript` button. Do not add cloud consent or long explanatory copy. Preserve the existing readable panel minimum size and capture exclusion.

- [ ] **Step 8: Run focused tests**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_session_orchestrator tests.test_app_controller tests.test_control_panel_keys tests.test_transcript_panel -v`

Expected: PASS.

## Task 8: Model Setup, Schema Documentation, And Migration Cleanup

**Files:**
- Modify: `scripts/download_whisper_model.py`
- Modify: `README.md`
- Modify: `docs/dataset-schema.md`
- Modify: `tests/test_dependencies.py`
- Add or modify: `tests/test_main_import.py`

**Interfaces:**
- Setup supports `base.en`, `small.en`, and `medium.en` with deterministic default directories `models/faster-whisper-<model-name-with-hyphens>`.
- Runtime resolves model names to explicit local paths and never downloads them.

- [ ] **Step 1: Write failing setup-script tests**

Extract and test `model_output_path(model_name, root=Path("models"))`:

```python
self.assertEqual(
    model_output_path("medium.en"),
    Path("models/faster-whisper-medium-en"),
)
```

Assert unsupported names raise `ValueError` and dependency tests still import faster-whisper, SciPy, PyAudioWPatch, MediaPipe, MSS, and OpenCV.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_dependencies tests.test_main_import -v`

Expected: FAIL on the new model-path assertions until the script is refactored.

- [ ] **Step 3: Update explicit model setup**

Support these commands without changing runtime dependencies:

```powershell
.\.venv\Scripts\python.exe .\scripts\download_whisper_model.py --model small.en
.\.venv\Scripts\python.exe .\scripts\download_whisper_model.py --model medium.en
```

Keep `base.en` as the documented low-latency fallback. Do not download either model during automated tests.

- [ ] **Step 4: Update user and schema documentation**

Document the four required files, optional video, stereo channel mapping, LIVE versus FINAL semantics, Pause mapping, quiet/clipping meter states, explicit model downloads, no-cloud guarantee, and exact run/check commands. Remove obsolete SRT, separate WAV, event CSV, manifest, and timestamp sidecar descriptions.

- [ ] **Step 5: Run documentation-adjacent tests**

Run: `\.venv\Scripts\python.exe -m unittest tests.test_dependencies tests.test_main_import -v`

Expected: PASS.

## Task 9: Full Regression, Performance Gate, And Manual Test Script

**Files:**
- Modify only files implicated by failures from this task.
- Record measured results in `README.md` only after running them on the target machine.

**Interfaces:**
- Consumes all preceding tasks.
- Produces a release-ready local prototype and an explicit list of hardware checks that remain manual.

- [ ] **Step 1: Run the complete automated suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
```

Expected: all tests pass, `pip check` reports no broken requirements, and compileall exits `0`.

- [ ] **Step 2: Verify compact output with fake integrations**

Run the integration-level session test and assert a completed audio/transcript session contains only:

```text
audio.wav
features.csv
transcript.jsonl
session.json
video.mp4      # only when enabled
```

Expected: no `manifest.json`, `facial_events.csv`, separate source WAV, SRT, or timestamp CSV appears in a new schema `3.0` session.

- [ ] **Step 3: Benchmark installed live models on one consented sample**

Run the same 30-to-60-second English sample through `base.en` and `small.en`, recording processing time/audio duration, visible transcript errors, quiet-phrase misses, and face FPS while live capture is active. Use `small.en` as the default only when live lag remains usable; otherwise retain `base.en` live and reserve the stronger model for final processing.

- [ ] **Step 4: Benchmark the installed final model**

Run `medium.en` on the same stopped session and compare its canonical output against a manually written reference. Record that final processing may be slower than real time on CPU; do not claim accuracy improvement unless the measured sample supports it.

- [ ] **Step 5: Perform the manual hardware acceptance checklist**

Verify microphone-only, loopback-only, both sources, simultaneous speech, quiet speech, clipping, Pause/Resume, one-device disconnect, optional video capture exclusion, final cancellation, final retry, Q/Escape shutdown, and no network activity after model installation.

- [ ] **Step 6: Review scope and privacy language**

Search UI/docs/output metadata for claims of confusion, emotion, attention, identity, or psychological truth. Confirm consent remains required for persisted data and no cloud setting or credential was introduced.

## Completion Criteria

- New sessions use the compact schema specified above; disabled optional audio,
  transcript, or video modes create no empty media files.
- Automated checks pass without webcam, microphone, meeting software, or model download.
- Hardware testing demonstrates correct stereo channels and shared timestamps.
- Live transcript remains responsive enough for monitoring on the target machine.
- Final transcript is generated locally, survives Pause mapping, and replaces nothing unless the complete job succeeds.
- Any unperformed manual benchmark or hardware check is reported explicitly rather than assumed to pass.
