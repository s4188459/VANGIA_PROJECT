# Configuration and Test Log — Multimodal Dataset Collector

Snapshot date: September 30, 2026. Project: `facial-cue-prototype`. Commit inspected: `7e02623`.

The configuration below was checked against the source code, Python environment, and local model directory. The application, benchmarks, and automated tests were not run during this inspection. “Not measured” does not mean zero or passed.

## TAB 1 — Configuration and Usage

### CFG-001 — Current Configuration

**Purpose:** collect multimodal data from calls or videos for research. The application currently collects facial features, observable events, optional video/audio, and English transcripts. No confusion classifier has been trained and validated on this project's dataset.

### Processing Architecture

```text
Tkinter user interface
  → Select a screen region containing one face
  → AppController coordinates the session

Visual pipeline:
  MSS captures the selected screen region
  → MediaPipe Face Landmarker
  → Feature extraction + rule-based action detection
  → Screen overlay + features.csv + events in session.json
  → video.mp4 if video recording is enabled

Audio pipeline:
  Microphone + Windows output audio (WASAPI loopback)
  → Stereo audio.wav
  → Buffering + pause detection + faster-whisper
  → LIVE transcript in the UI + transcript.jsonl

After Stop:
  Generate Final Transcript
  → Read audio.wav → FINAL recognition → transcript.jsonl
```

The visual input is the selected screen region, rather than direct webcam capture. “You” identifies microphone audio; “Student” identifies loopback audio. These labels describe technical sources, not verified speaker identities.

### Inspected Environment

| Item | Value | Verification status |
| --- | --- | --- |
| Python | 3.12.14, 64-bit | Read from the Python executable in `.venv` |
| MediaPipe | 0.10.21 | Installed; matches requirements.txt |
| OpenCV contrib | 4.11.0.86 | Installed; matches requirements.txt |
| MSS | 10.2.0 | Installed; matches requirements.txt |
| PyAudioWPatch | 0.2.12.8 | Installed; matches requirements.txt |
| faster-whisper | 1.2.1 | Installed; matches requirements.txt |
| SciPy | 1.17.1 | Installed; matches requirements.txt |
| CPU / RAM / Windows version | Not confirmed | Access to system queries was denied |
| GPU used for Whisper | No | Code specifies `device=cpu` |
| MediaPipe model | `models/face_landmarker.task` | File exists; model loading has not been tested |
| Whisper models on disk | `small.en`, `base.en` | Directories and model.bin files exist; inference has not been tested |
| Whisper medium.en | Absent from the models directory | Unavailable in the current local setup |

### Face and Action Parameters

| Parameter | Current configuration |
| --- | --- |
| MediaPipe running mode | VIDEO |
| Maximum number of faces | 1 |
| Detection / presence / tracking thresholds | 0.5 / 0.5 / 0.5 |
| MediaPipe outputs | Landmarks, blendshapes, transformation matrices |
| Baseline calibration | 2 seconds and at least 30 samples |
| Smoothing window | 0.25 seconds |
| Default action confirmation duration | 0.25 seconds; some actions have separate rules |
| Default release / cooldown duration | 0.15 / 0.30 seconds |
| Missing-face confirmation threshold | 0.20 seconds |
| Maximum actions displayed on the overlay | 4 |
| Optional video recording | MP4, mp4v codec, 20 output FPS, queue size 8 |

20 FPS is the video file setting, not a measured facial-processing rate. Actions such as head turns, blinking, and brow movements are detected using rules; they must not automatically become emotion or confusion labels.

### Audio and Transcription Parameters

| Parameter | Current configuration |
| --- | --- |
| Audio sources | Microphone and/or Windows loopback, selected per session |
| Recorded WAV | Stereo, 48 kHz; left = microphone/You, right = loopback/Student |
| Whisper input audio | Mono, resampled to 16 kHz |
| Recognition language | English, fixed to `en` |
| LIVE model | Prefers small.en, falls back to base.en; current files lead to small.en selection |
| FINAL model | Preference order: medium.en → small.en → base.en; current files lead to small.en selection |
| Device / compute type | CPU / int8 |
| CPU threads / workers | 4 / 1 |
| Beam size | 5 |
| Word timestamps | Enabled |
| VAD threshold | 0.35 |
| Utterance-ending pause | 1.0 second |
| Earliest endpoint check | After at least 1.2 seconds of buffered audio |
| Endpoint check interval | Every 0.1 seconds of new audio; examines up to the latest 2 seconds |
| Maximum LIVE window | 12 seconds |
| Overlap when continuous speech is forcibly split | 0.75 seconds |
| Transcript queue | 4096 audio packets |
| FINAL window / overlap | 30 / 0.75 seconds |

1.2 seconds and 12 seconds are buffer parameters, not measured latency. Transcript delay also depends on pauses, queueing, inference, and UI updates.

### Running a Session

From the `facial-cue-prototype` directory, run in PowerShell:

```powershell
.\.venv\Scripts\python.exe .\src\main.py
```

1. Open a test video or call with participant consent.
2. Click **Select Region** and select a region containing one face.
3. Click **Choose Save Folder**.
4. Record whether Video, Meeting audio, Microphone, and Transcript are enabled. Transcript requires at least one audio source.
5. Enter a participant ID if needed and check **Consent confirmed**.
6. Click **Start** and maintain a stable forward-facing pose until calibration finishes.
7. Follow the same scenario when comparing runs. Record every Pause/Resume.
8. Click **Stop** and inspect the outputs and session status.
9. If recorded audio is available, optionally click **Generate Final Transcript** and measure FINAL processing time separately.

### Session Outputs

| File | Contents / use |
| --- | --- |
| session.json | Capture region, options, runtime packages, LIVE configuration, component states, errors, drops, events, and synchronization metadata |
| features.csv | Per-frame data, face_visible, features, processing_ms, frame_gap_ms, and action information |
| video.mp4 | Available when video is enabled; use to inspect the captured region |
| audio.wav | Available when an audio source is enabled; use for quality checks and FINAL transcription |
| transcript.jsonl | Available when transcription is enabled or FINAL is generated; distinguish live and final phases |

Each Start creates a new `session_XXX` directory in the selected save folder. The session clock continues during Pause, leaving timestamp gaps. Use session timestamps and interval mappings when checking synchronization, rather than media playback position alone.

### Additional Information to Record for Each Run

- CPU, RAM, and Windows version when confirmed.
- Capture region size (width × height), video/call application, and audio devices.
- Input video/audio and a reference transcript when evaluating recognition.
- Enabled features, duration, lighting/noise conditions, and background applications.
- Configuration ID, commit, any uncommitted source changes, and the full session path.

## TAB 2 — Test Log

### Summary Table — One Row per Run

| Run ID | Date | Configuration | Scenario | Session / path | Processing p50 / p95 (ms) | Processing FPS | LIVE lag (s) | Errors / drops | Conclusion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RUN-001 | Not run | CFG-001 | Face only | Not available | Not measured | Not measured | N/A | Not checked | Not evaluated |

RUN-001 is a planned run, not an experimental result. If multiple lag samples are collected, specify whether the value is p50, p95, maximum, or a single observation.

### Metric Definitions and Sources

| Metric | Definition / source | Interpretation |
| --- | --- | --- |
| Processing time (ms) | `features.csv.processing_ms`: from before screen capture until after feature extraction | Does not include all action processing, CSV writing, and UI drawing; not end-to-end latency |
| Frame gap (ms) | `features.csv.frame_gap_ms`: timestamp difference between consecutive processed frames | Exclude the first frame and Pause intervals when summarizing active processing speed |
| Processing FPS | Can be calculated as 1000 / mean valid frame_gap_ms | Document the calculation; MP4 output FPS is not processing FPS |
| Face visible (%) | Rows with face_visible=true / total rows in the evaluation interval × 100 | Indicates face-result availability, not landmark accuracy |
| LIVE lag (s) | UI “Transcript lag”; code calculates processing completion time minus the end time of the audio buffer | Not the delay from speech ending to text being drawn on screen |
| Transcript display latency (s) | Time text appears in the UI minus the reference speech end time | Requires a separate measurement; transcript.jsonl does not contain display timestamps |
| RTF | Processing time for one buffer / duration of that audio buffer | Calculated by the code; RTF < 1 for a buffer does not guarantee that the whole system keeps up |
| Drops / errors | session.json: drops, drop_details, errors, media_stats | Inspect each component; do not assume every counter covers every data-loss path |
| Transcript quality | Compare LIVE and FINAL against the same reference transcript; WER can be used | Not measured during this inspection |
| FINAL processing time | Time from clicking Generate Final Transcript until completion | Record audio duration and selected model alongside it |

LIVE lag and RTF are not currently saved as complete time series in CSV/JSONL. After a successful Stop, transcript media_stats may retain last_metrics; this is the last sample and cannot establish session-wide p95. Full-session statistics require additional metric logging or a separate measurement method.

### Detailed Run Record — Copy for Each Test

**Run ID:** RUN-___

**Date / operator:** …

**Configuration / commit:** CFG-___ / …

**Objective:** …

**Changes since the previous run:** …

**Input / conditions:** video name or scenario; duration; region size; audio devices; lighting; noise; background applications.

**Options:** Video [on/off]; Meeting audio [on/off]; Microphone [on/off]; Transcript [on/off].

**Actual models:** LIVE …; FINAL …; verify against session.json.

**Steps and timestamps:** …

**Measurements:** processing p50/p95 …; FPS …; LIVE lag …; display latency …; drops …; FINAL processing time …; transcript quality …

**Observed behavior:** …

**Evidence:** session path, logs, or demonstration clip …

**Acceptance criteria defined before the run:** …

**Conclusion and next step:** …

### Three Suggested Initial Scenarios — Not Yet Executed

| Scenario | Enabled features | Procedure | Purpose |
| --- | --- | --- | --- |
| T01 | Face only | Use the same 60-second face video | Establish baseline processing time, FPS, and face visibility |
| T02 | Face + one audio source + transcript | Use the same video, with English speech, a reference transcript, and pauses | Measure additional LIVE workload, recognition errors, and lag |
| T03 | Face + video + both audio sources + transcript | Use a fixed scenario with separate segments for each audio source and a 5-second Pause | Check all outputs, synchronization, drops, and FINAL transcription |

For meaningful comparisons, keep the input and capture region constant and repeat each scenario, for example three times. Document model-loading time for the first run. Acceptance thresholds should follow the intended use; no thresholds have been validated in this inspection.

### Previously Documented Automated Test Results

According to `docs/testing.md`, the September 29, 2026 run recorded 208 tests: 204 passed, 2 failures, and 2 errors. `pip check` and compilation passed. The hardware checklist was not performed during that run. These are historical results; the checks were not rerun on September 30, 2026.

The four documented issues are: the paused audio worker does not drain the stream as expected by its test; prepare_capture_frame is missing although a test imports it; the decoder does not provide the temperature parameter expected by a test; and uncertain/repetitive segment filtering does not match test expectations.

## Update Rules

1. Rerunning the same setup: add a RUN and retain the CFG.
2. Changing code, models, parameters, or the environment: copy the configuration record into a new CFG and describe the differences.
3. Record scenario-specific option changes in each RUN; assign a separate CFG if treating those options as a fixed configuration for comparison.
4. Preserve previous results and evidence. Do not overwrite old configurations with new values.
5. Use “Not measured” for unmeasured fields and “N/A” for disabled or inapplicable features.

## Project Sources Inspected

- `requirements.txt`: direct dependency versions, checked against `.venv`.
- `src/main.py`, `src/app_controller.py`: startup and session coordination.
- `src/meeting_tracker.py`, `src/face_landmarker.py`: visual pipeline and processing-time measurement.
- `src/action_types.py`, `src/action_detection.py`: action parameters and rules.
- `src/session_orchestrator.py`, `src/transcription.py`, `src/final_transcription.py`: models, buffering, VAD, LIVE/FINAL, and metrics.
- `src/video_recorder.py`, `src/dataset_session.py`, `src/control_panel.py`: video, metadata, and displayed metrics.
- `docs/testing.md`, `docs/dataset-schema.md`: verification history and output definitions.
