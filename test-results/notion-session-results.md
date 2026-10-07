# Session Results

## Evaluation summary — read before the sheet

**The sessions document development of a multimodal collector, not 14 successful accuracy experiments.** Twelve manifests are closed; session 005 was not finalized and session 012 is incomplete. A closed session can still have recognition errors or intentionally untranscribed audio.

| Development phase | Sessions | Main question | Main finding |
|---|---|---|---|
| Establish the baseline | 001–004 | Does face/video collection operate and preserve readable data? | Stable short runs; no validated action accuracy; an odd-height video discrepancy remained. |
| Repair and verify recording | 005–007 | Why is saved audio distorted, and why does Stop fail? | Audio timing/lifecycle defects addressed; good sound reported after the fix; visible face delay remained. |
| Measure and reduce processing work | 008–010 | Which part of the visual path is expensive? | Stage tracing identified redundant conversion; the following run measured much lower conversion cost. |
| Evaluate LIVE transcription | 011–012 | Does text arrive with usable accuracy and responsiveness? | Boundary repetition and endpoint delay identified; shorter endpoint/dedup improved an offline excerpt, but a later LIVE run timed out on Stop. |
| Verify revised Stop behavior | 013–014 | Can recording stop without waiting for unfinished LIVE decoding? | 014 records clean process-policy closure and normal UI feedback; unfinished transcript coverage is explicit. |
| Improve after the last recording | No new numbered session | Can the remaining boundary case and endpoint transport be improved? | Targeted real-model replay and software tests support CFG-007; a new live run was not performed. |

Read **Purpose → What this session demonstrated → Problem → Action taken afterwards** to follow the engineering decisions. Config links each recording to the other tab. The numerical columns support those findings; they are not universal pass/fail targets.

## Session sheet

One row per recorded session. Configuration IDs refer to the Configuration History tab. Data: `D:\@_Binh's document\AI Course\VANGIA_PROJECT\test-results`. All sessions include face processing; microphone was disabled in all 14. Dates are local (UTC+07:00). V = video, A = system audio, T = LIVE transcript.

| Session | Date | Config | Purpose / change for this run | Modes | Region (px) | Duration (s) | Feature FPS | Post-action mean / p95 (ms) | Render-return mean / p95 (ms) | What this session demonstrated | Problem / limitation | Action taken afterwards |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 001 | 2026-10-01 | CFG-001 | Establish face + video baseline | V | 1158 x 641 | 64.308 | 19.383 | Not recorded | Not recorded | Closed; readable features/video; user reported good tracking and no jitter/freezing | Encoded height 640 instead of 641; accuracy and physical latency unmeasured | Keep baseline; compare video-on/off later. No algorithm change established. |
| 002 | 2026-10-01 | CFG-001 | Repeat with slightly changed region | V | 1146 x 649 | 62.403 | 21.250 | Not recorded | Not recorded | Closed; user reported stability comparable to 001 | Encoded height 648 instead of 649; changed region prevents strict causal comparison | Disable video for 003. No source improvement inferred from faster FPS. |
| 003 | 2026-10-01 | CFG-001 | Disable video; retain 002 region | None | 1146 x 649 | 61.693 | 21.531 | Not recorded | Not recorded | Closed face-only run; user noticed no difference | Small performance difference does not establish video overhead | Repeat face-only baseline; keep models/rules unchanged. |
| 004 | 2026-10-01 | CFG-001 | Face-only repeat; reselect region after account change | None | 1151 x 643 | 61.452 | 21.997 | Not recorded | Not recorded | Closed; no unusual behavior reported | Not an exact repeat; audio/STT not evaluated | Proceed to system-audio test with English source material. |
| 005 | 2026-10-01 | CFG-001 | Enable system audio; larger region and new source | A | 1745 x 993 | Manifest unfinished; WAV 93.991 | 15.029 | Not recorded | Not recorded | Saved readable WAV and feature evidence for diagnosis | User reported severe saved-audio distortion and app exit on Stop; manifest still recording | Implement sample-count timing, worker-owned stream cleanup, pause draining, overflow/device diagnostics -> CFG-002. |
| 006 | 2026-10-01 | CFG-002 | Retest audio correction | A | 1850 x 1054 | 86.176 | 12.378 | Not recorded | Not recorded | Closed; user reported very good audio; fewer short zero runs in historical waveform analysis | Visible landmark delay; larger region and different source extent limit comparison | Keep audio fix; reduce region for 007. |
| 007 | 2026-10-01 | CFG-002 | Reduce region while retaining audio settings | A | 1403 x 807 | 90.373 | 17.247 | Not recorded | Not recorded | Closed; processing improved versus 006 | User still perceived similar landmark delay; FPS alone did not explain it | Add per-frame pipeline timing -> CFG-003. |
| 008 | 2026-10-01 | CFG-003 | Diagnose capture-to-render stages | A | 1405 x 800 | 57.772 | 14.628 | 67.943 / 84.188 | 113.992 / 143.764 | Located 17.154 ms mean conversion cost; user reported good audio; action processing itself only 0.545 ms mean | High perceived mesh delay; temporal decision rules introduce separate delay | Replace redundant image copies with direct OpenCV conversion -> CFG-004. |
| 009 | 2026-10-01 | CFG-004 | Retest direct color conversion | A | 1403 x 803 | 37.680 | 19.280 | 51.316 / 62.788 | 108.990 / 138.271 | Conversion mean fell to 1.763 ms; user tentatively described action detection as near real time | Mesh still perceived as very delayed; 87/713 overlays replaced; not action accuracy validation | Retain conversion fix; investigate rendering separately. Review made no code change. |
| 010 | 2026-10-02 | CFG-004 | Audio-only baseline before LIVE comparison | A | 1404 x 804 | 65.163 | 22.239 | 44.294 / 51.350 | 94.210 / 117.488 | Closed; user reported improved/good landmark latency | Other checkout's 36.798 s session 010 is different; its render optimizations cannot be attributed here | Enable LIVE for 011 with same region. |
| 011 | 2026-10-02 | CFG-004 | Add LIVE transcription | A + T | 1404 x 804 | 72.922 | 20.458 | 48.247 / 64.690 | 105.289 / 144.177 | Closed; audio/Stop good by user report; seven LIVE segments; excerpt WER 9.09% | Text slow after pauses; repeated boundary phrases; last metrics are not session averages | Add dedup v1, 0.6 s endpoint, explicit decoder/quality controls; reject 6/8 s trials, retain 12 s -> CFG-005. |
| 012 | 2026-10-03 | CFG-005 | Test shorter endpoint and dedup v1 | A + T | 1405 x 807 | 94.239, includes old shutdown wait | 10.429 | 94.904 / 123.860 | 224.540 / 306.959 | Preserved evidence of timeout and slower stages; historical excerpt WER 6.25%; offline replay found additional tail speech | Incomplete: 10 s LIVE Stop timeout; repetitions remained; resource contention not proven; excerpt WER excludes tail | Implement process cancellation, background closure and explicit pending coverage -> CFG-006. |
| 013 | 2026-10-06 | CFG-006 period; ASR off | Check recording/face behavior without transcription | A | 1407 x 791 | 48.949 | 22.288 | 44.139 / 52.987 | 93.980 / 116.170 | Clean closure; structurally readable WAV and continuous feature data | Cannot validate Whisper cancellation because transcription was disabled | Review only; use 014 for transcript-enabled evidence. |
| 014 | 2026-10-06 | CFG-006 | Enable LIVE with recorded spawn/cancel policy | A + T | 1407 x 791 | 51.343 | 16.865 | 58.542 / 75.212 | 123.000 / 164.574 | Closed without recorded errors; user reported normal UI; retained committed transcript and recorded pending coverage | 10.6487 s pending audio; waiting_audio at Stop, not active decode; repeated prefix remained; no full reference WER | Scoped Stop review accepted; offline boundary fix v2 and bounded VAD transport -> CFG-007. No live session 015 yet. |

## What has been achieved, and how strong is the evidence?

| Area | Initial problem | Result achieved | Evidence strength / remaining weakness |
|---|---|---|---|
| Audio integrity | Distorted saved sound and unstable Stop in 005 | Sample-count timing and safe stream ownership; 006 closed and sounded good to the operator | Reproduced software defects plus manual retest support improvement. Exact original crash cause, long-term drift and all devices are not validated. |
| Visual computation | Unexplained visible delay and unnecessary image copies | Conversion mean 17.154 → 1.763 ms; post-action callback mean 67.943 → 51.316 ms across 008–009 | Live timing supports reduced computational cost. Conditions varied; physical mesh latency and action accuracy are separate. |
| Transcript quality | Repeated words across overlapping windows | Post-011 offline reference WER 9.09% → 5.56%; post-014 replay removes a specific repeated prefix | Improvements on particular recordings. Multiple settings changed in the first comparison; not corpus-wide or teaching-domain accuracy. |
| Stop responsiveness | Old 10 s drain timed out in 012 | Separate inference process, immediate cancellation request and background file closure; 014 closed with normal UI reported | Seven focused tests and one relevant manual observation. 014 was waiting for audio at Stop; active-decode cancellation has test evidence. End-to-end Stop time was not measured. |
| Coverage transparency | Missing tail text could be overlooked | 014 records 10.6487 s unprocessed audio and coverage_complete=false | Successfully closing files does not imply transcribing every spoken word. An explicit FINAL pass remains available. |
| Endpoint overhead | Sending a full buffer when VAD needs only recent context | Payload 2,304,000 → 307,200 audio bytes for the 12 s / 48 kHz case | 86.7% smaller payload and equivalent VAD input verified; not an 86.7% whole-system speedup. |
| Software verification | Historical failing regressions and a timing-sensitive test | Latest recorded full suite: 236 passed on October 6, including Stop and boundary cases | Tests cover specified behavior, often with fake devices. They do not certify recognition accuracy, classroom usability or long-session reliability. |

## Overall assessment for the supervisor

**Current engineering contribution:** an implemented local collector with traceable session outputs, diagnostic measurements, targeted performance improvements, explicit partial-transcript handling and regression-tested cancellation.

**Current strengths:** local inference, preservation of original data, common timestamps for analysis, clear separation between observations and psychological interpretations, and documented links from problems to changes and verification.

**Current weaknesses:** chunked transcript delay, heuristic overlap/action rules, uncontrolled differences between short test runs, limited verified speech references, no microphone-enabled run in this series, and unmeasured long-session synchronization and concurrent workload behavior. No trained student-understanding classifier or validated facial-action benchmark is claimed. The early one-pixel video-height discrepancy remains unresolved.

The project is ready to move from debugging selected examples toward a defined evaluation dataset and protocol. It is not yet supported as a validated real-time teaching-support system. The planned 100 conversations are future evaluation material, not results included in this sheet.

## Decisions requested from the supervisor

| Decision | Proposed next step for discussion | Why it matters |
|---|---|---|
| Main next milestone | Prioritize a defensible STT/data-collection evaluation before claiming student-understanding assessment | Establishes what the project should demonstrate and how the broader research goal will be reached. |
| The 100-conversation dataset | English teaching–learning dialogues, including technical terms, numbers, negation, pauses and legitimate repetition; agree on synthetic versus human audio | Tests the relevant domain and avoids evaluating only easy, clean scripted examples. |
| Reference quality | Pair each actual recording with a listener-checked transcript; agree on second-review/disagreement handling | A generated script or FINAL ASR output alone is not verified ground truth. |
| Success criteria | Agree on WER, critical-word errors, missing/repeated text, visible-text delay and recording/Stop requirements before final evaluation | Prevents selecting success criteria after seeing results. No numerical acceptance targets are claimed here. |
| Evaluation separation | Reserve recordings, scripts and speakers for held-out evaluation before tuning | Reduces overfitting to the same development passages. |
| Role of facial data | Retain observable features as exploratory data until an independent annotation protocol exists | Avoids treating a facial movement as a direct understanding/confusion label. |

## How to interpret the sheet

- Feature FPS = (feature rows - 1) / feature timestamp span. It is not the fixed 20 FPS video encoding setting.
- Post-action timing = overlay_callback_s - capture_start_s. Render-return timing = render_end_s - capture_start_s, for rendered frames. Neither is physical gesture-onset-to-display latency.
- Not recorded means no timing trace was saved; it does not mean zero. Percentiles use linear interpolation.
- Closed means the recorded session finalized; it does not guarantee perfect transcript coverage, recognition accuracy or subjective UI quality.
- Session 005's zero manifest duration reflects unfinished finalization. Session 012's manifest duration includes the old Stop wait.
- WER values use supplied excerpts with different extents. They are not directly comparable whole-recording scores or measures of student understanding.
- Regions, source timing and background load varied. This is a development history, not a controlled comparison isolating every code change.
- The current code is CFG-007, but 014 was captured with CFG-006 / dedup v1. Later replay results do not rewrite old sessions.

| Metric | Definition / practical meaning |
|---|---|
| FPS | Processed feature frames per second over the saved timestamp span; throughput, not recognition accuracy. |
| Mean / p95 | Average / value at or below which approximately 95% of the observations fall. A lower p95 suggests fewer long delays for that measured boundary. |
| WER | (Word substitutions + deletions + insertions) / reference word count. It is a transcription error measure, not semantic or student-understanding accuracy. |
| RTF | Decode processing time / audio duration. A value below one for a buffer does not guarantee the whole concurrent application keeps up. |
| Last metrics | The most recent completed-decode snapshot; not a full-session mean, p95 or exact queue state at Stop. |
| Replaced overlay | A pending display frame superseded by a newer one; not automatically a lost feature row or dropped audio. |

### Evidence boundaries

Session metrics come from saved manifests/CSV, manual observations from the operator's reviews, and offline results from dated change logs. The report was assembled on October 7; the 236-test result is the recorded October 6 run. No new classroom experiment or hardware test was performed to create these tabs. Historical documents and the other project copy can contain different configurations; this sheet consistently uses the stated data root.

Sources: each session's session.json, features.csv, available landmark-timing.csv, technical/manual reviews and change logs; corrected sessions-010-011 review; immediate Stop and post-014 improvement records. All original recordings remain unchanged.
