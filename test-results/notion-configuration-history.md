# Configuration History

## Project overview — read this first

**The project builds a local tool for collecting timestamped facial signals and speech during teaching–learning conversations. The current deliverable is the data-collection and transcription prototype; a model that assesses student understanding has not yet been trained or validated.**

The broader research direction is AI-assisted teaching support. This stage establishes whether useful recordings, observable facial measurements and transcripts can be collected reliably enough for later evaluation and annotation. Facial movements alone are not treated as evidence that a student is confused or understands a lesson.

| Supervisor's question | Current answer |
|---|---|
| Who would use it? | A lecturer or researcher observing a consented conversation or test video. |
| What does the user do? | Select one face-containing screen region, choose a save folder and optional modalities, confirm consent, then Start, Pause/Resume and Stop. |
| What is the visual input? | Pixels displayed inside the selected meeting/video rectangle, captured by MSS. It is not direct access to the remote camera or a meeting account. |
| What is the audio input? | Windows system-output loopback and/or microphone. The reviewed 14-session series used no microphone-enabled run. |
| Where is AI used? | Pretrained MediaPipe estimates facial geometry/blendshapes; Silero detects speech activity; Whisper produces English text and estimated word times. No model weights were trained or fine-tuned in this work. |
| What is implemented by the project? | Session coordination, data storage, timing/alignment, observable-action rules, buffering, transcript boundary handling, diagnostics and cancellation behavior. |
| What does it show? | Facial landmarks, up to four observable action labels, recording status and delayed LIVE transcript text. |
| What does it save? | One new session folder containing metadata and per-frame features, plus optional audio, transcript and video; recent sessions also include detailed visual-stage timing. |
| How does processing run? | Tkinter handles the UI; workers handle capture/recording; current LIVE Whisper and endpoint detection run in a separate process that can be terminated at Stop. Models run locally after setup. |
| What has been evaluated? | Fourteen short development recordings, targeted offline replays, manual observations and software regression tests. These are engineering checks, not a representative classroom benchmark. |
| What is the present result? | Audio capture and shutdown defects have been addressed; image conversion is cheaper; Stop no longer drains pending LIVE audio; one remaining overlap error was fixed in replay. General STT accuracy and long-session performance remain open. |

### How the information flows

```text
Selected screen region -> MediaPipe -> facial features -> temporal action rules
                                                    -> overlay + saved feature rows

System audio / microphone -> saved stereo WAV
                          -> buffered speech -> Whisper -> LIVE text + transcript file

Shared session timestamps connect the outputs.
Stop cancels unfinished LIVE recognition and records what remains unprocessed.
An optional, explicitly requested FINAL pass reprocesses the saved audio.
```

For example, speech occurring at session seconds 12–15 should be compared with facial measurements from seconds 12–15, even if its transcript appears later. Sharing a clock supports this alignment; it does not establish perfect hardware synchronization or eliminate display delay.

### Outputs and their research meaning

| File | Contains | Evaluation use / limitation |
|---|---|---|
| session.json | Options, capture region, timestamps, component states, available model settings, errors, events and media mappings | Identifies run conditions and incomplete coverage; older sessions lack some diagnostics and exact source/model hashes. |
| features.csv | 89 per-frame columns, including 52 blendshape coefficients, derived pose/eye/mouth measures and observable-action snapshots | Supports replay/analysis of rules; does not contain complete landmark arrays or verified understanding labels. |
| landmark-timing.csv | Timestamps for capture, inference, action preparation and UI/render stages | Measures software-path costs; not physical gesture-onset-to-screen latency. |
| audio.wav | PCM16 stereo audio; microphone left, system loopback right | Source for listening review and ASR evaluation; source labels do not verify speaker identity. |
| transcript.jsonl | LIVE and optional FINAL text with estimated times and source labels | Hypotheses to compare with listener-checked references. FINAL is not automatically ground truth. |
| video.mp4 | Optional selected-region video | Can support later manual annotation; separate from the WAV, not a video with embedded audio. |

### How to read the two tabs

**This tab explains what was configured and why it changed. The Session Results tab provides one spreadsheet row per recording, followed by an assessment of the evidence.** Read CFG-001 to CFG-007 as an incremental development sequence. Read session 014 as the last recorded live test, and CFG-007 as the later code revision checked offline; they are not the same checkpoint.

Prepared 7 October 2026. Project: `AI Course/VANGIA_PROJECT`. CFG identifiers below are retrospective reporting labels, not identifiers originally saved by the app. Session options and capture regions are listed in the Session Results tab. A stage does not prove the exact capture-time source commit.

## Shared baseline

| Component | Configuration retained through the reviewed stages |
|---|---|
| Platform | Local Windows application; Python 3.12.14; Tkinter; operator-selected screen region and output folder |
| Libraries | MediaPipe 0.10.21; OpenCV contrib 4.11.0.86; MSS 10.2.0; faster-whisper 1.2.1; CTranslate2 4.8.2; NumPy 1.26.4; SciPy 1.17.1; PyAudioWPatch pinned to 0.2.12.8 |
| Face inference | Face Landmarker; VIDEO mode; one face; detection, presence and tracking thresholds 0.5 |
| Action baseline | At least 2 s and 30 valid samples; median/MAD; sensitivity 1.0 |
| Action timing | 0.25 s median smoothing; typical 0.25 s activation, 0.15 s release and 0.30 s cooldown; asymmetric eye/brow hold 0.30 s |
| Optional video | mp4v; 20 output FPS; queue capacity 8; output FPS differs from measured feature FPS |
| Audio | 1,024 native samples per capture packet; saved PCM16 stereo at 48 kHz; microphone left, system loopback right |
| LIVE model | small.en preferred; base.en fallback; CPU INT8; 4 threads; 1 worker; beam size 5; English; word timestamps |
| LIVE buffering | Minimum 1.2 s; endpoint check every 0.1 s of new audio; maximum 12 s; forced overlap 0.75 s; queue capacity 4,096 packets |
| Decoder VAD / word grouping | VAD threshold 0.35; decoder silence setting and word-gap grouping 1.0 s; separate from LIVE endpoint pause |
| FINAL | Explicit user action; 30 s windows and 0.75 s overlap; medium.en -> small.en -> base.en preference; medium.en absent in inspected models |
| Interpretation | Observable facial actions and ASR estimates; no trained or validated understanding/confusion classifier |

## Configuration changes by stage

Each row inherits unchanged settings from the preceding accepted configuration and the baseline above.

| Configuration | Introduced / applicable sessions | Audio timing and cleanup | Visual processing and diagnostics | LIVE segmentation / deduplication | Decoder controls | LIVE Stop policy | Why changed | Verification / remaining limit |
|---|---|---|---|---|---|---|---|---|
| CFG-001 | Initial baseline; sessions 001-005 | Read-time-based packet positioning; original stream shutdown | Original image conversion; processing_ms only | Endpoint 1.0 s; VAD context 2.0 s; 12 s window; whole-segment cutoff | Explicit temperature and quality guards later found missing in this checkout | In-process inference; drain/flush with 10 s grace; synchronous cleanup | Establish basic face/video/audio operation | 001-004 closed; 005 exposed distorted audio and exit on Stop. Transcript was disabled in all five. |
| CFG-002 | After 005; sessions 006-007 | Sample-count continuity; Pause re-anchor; capture worker owns stream closure; polling, pause draining and overflow reporting; device metadata and fault logs added | Existing visual pipeline retained; region-size experiment in 007 | Unchanged; transcription off in these runs | Unchanged | Audio lifecycle corrected; LIVE policy not yet redesigned | Address reproduced packet-timing and native-stream lifecycle defects | 006 closed and user reported very good audio; visible landmark delay persisted. Exact original native crash cause not proven. |
| CFG-003 | After 007; session 008 | CFG-002 retained | Add per-frame capture/conversion/inference/features/action/UI/render timestamps and outcomes; 20,000-frame diagnostic cap | Unchanged; transcription off | Unchanged | Unchanged | Locate visible-path costs instead of relying on processing_ms alone | 008 measured 17.154 ms mean conversion and 113.992 ms mean capture-to-render return. Instrumentation itself is not a speedup. |
| CFG-004 | After 008; sessions 009-011 | Retained | Direct OpenCV BGRA-to-RGB; BGR only for optional video; timing retained | Endpoint 1.0 s, context 2.0 s; original cutoff; LIVE enabled in 011 | Guards still absent before post-011 restoration | Original LIVE drain/flush policy | Remove measured unnecessary color copies | 009 conversion mean 1.763 ms; action computation faster, mesh delay unresolved. Other-checkout render optimizations are not included. |
| CFG-005 | After 011; session 012 | Retained | Direct conversion retained; prepare_capture_frame helper restored | Endpoint 0.6 s; context 1.6 s; timed_suffix_prefix_v1; 0.35 s midpoint tolerance; 64-word history; 12 s maximum retained | Explicit temperature=0, previous-text conditioning=false, hallucination silence=1 s; reject log probability below -1.0 / compression ratio above 2.4 and nonfinite values | Original LIVE drain/flush policy | Reduce pause waiting and overlap repetition; resolve missing decoder/helper regressions | 226 tests passed; historical offline WER 9.09% -> 5.56% on the same excerpt. Session 012 still repeated words and timed out on Stop. |
| CFG-006 | After 012; sessions 013-014; process policy directly recorded in 014 | Reject new capture at Stop; worker-owned closure retained | Freeze session elapsed time; STOPPING blocks restart; background closure and stale-callback guards | CFG-005 settings retained; Whisper/VAD owned by spawned process; dedup v1 | Retained | cancel_without_flush; terminate inference owner; preserve committed text; record phase, coverage and pending intervals | Avoid waiting for unfinished recognition and make partial coverage explicit | Seven Stop tests passed; 014 closed, user reported normal UI. 013 had transcription off; 014 stopped while waiting_audio. |
| CFG-007 | After 014; current code; no new live session recorded | Retained | Runtime face/action/render behavior retained; timing-dependent Pause test repaired | timed_suffix_prefix_v2: guarded clipped-first-word match with two timed anchors; protect changed negations; send only 1.6 s endpoint context across IPC | Retained | CFG-006 retained | Fix reproduced gonna/to boundary variation and eliminate unused endpoint transport | Specific 014 boundary fixed in real-model offline replay; endpoint audio payload 86.7% smaller for a 12 s buffer; latest recorded suite 236 passed. Overall live speedup and universal dedup correctness not established. |

## Rejected experiment

| Experiment | Settings tested | Result | Final decision |
|---|---|---|---|
| Post-011 maximum-window trials | 6 s / 8 s / 12 s; replay wall time 59.287 / 52.143 / 48.523 s; 18 / 16 / 13 decoder calls | Shorter windows introduced additional fragments/repetition. These were offline replays, not extra numbered sessions. | Retain 12 s; do not describe 6 s or 8 s as the deployed configuration. |

Current strengths: local processing, preserved session evidence, stage-level measurements, improved audio continuity, responsive LIVE cancellation and explicit unfinished coverage. Current weaknesses: delayed chunked text, heuristic boundary matching and action rules, unknown long-session drift/concurrent performance, no validated learning-state classifier, and no full teaching-domain STT benchmark.

## Essential terminology

| Term | Plain-English meaning |
|---|---|
| STT / ASR | Speech-to-text / automatic speech recognition. |
| VAD / endpoint | Speech-activity detection / deciding when enough trailing silence has occurred to transcribe a buffered segment. |
| Blendshape | A model-estimated facial movement coefficient; not an emotion probability. |
| Calibration / MAD | Establishing a session reference using medians and median absolute deviation; this does not train the face model. |
| Smoothing / persistence | Reduce fluctuations / require evidence to last before declaring an action; both affect responsiveness. |
| Overlap / deduplication | Reuse audio near a split to retain context / avoid publishing the same recognized words twice. |
| CPU INT8 / beam 5 | CPU inference using reduced numerical precision / decoder search with beam size five; these settings do not establish accuracy. |
| IPC | Communication between the main program and the inference process. A smaller message reduces transport work, not necessarily total app latency by the same percentage. |
| LIVE / FINAL | Delayed recognition while recording / a separate user-requested pass over saved audio. Neither is a human-verified reference. |

## Current configuration in one sentence

**One-face MediaPipe tracking with unchanged temporal action rules, sample-timed 48 kHz stereo recording, and local small.en CPU INT8 transcription using four threads, beam five, a 0.6 s LIVE endpoint, a 12 s maximum window, 0.75 s forced overlap, deduplication v2 and process-based cancellation without tail flushing.**

Sources: session manifests; session_005/change-log.md; landmark-latency-change-log.md; session_008/change-log.md; sessions-010-011-corrected-review.md; session_011/change-log.md; session_012/cause-investigation.md; immediate-stop-change-log.md; live-transcript-improvement-2026-10-06/change-log.md; current source configuration. Earlier documentation is not a per-session source snapshot.
