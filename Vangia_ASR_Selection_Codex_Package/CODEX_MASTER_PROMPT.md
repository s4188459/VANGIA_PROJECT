# CODEX MASTER PROMPT — Build Vangia English ASR Model Selection & Validation Lab

You are Codex acting as **staff software engineer, experimental ML engineer, and audit-focused measurement engineer**. **BUILD THE RUNNABLE APPLICATION**, not a proposal, dashboard mockup, or notebook-only demonstration. Read all files in this package and inspect the existing repository before changing code. Implement and run tests; report honestly what works.

## Read in this order (normative)

1. `README_START_HERE.md` — package navigation, missing inputs, hard boundaries.
2. `config/model_registry.json` — the **exact 9 primary checkpoints and 2 deferred failed configurations**, baseline measurements/configs and identity caveats.
3. `docs/RESEARCH_EVIDENCE_AND_REQUIREMENTS.md` — original-source evidence, applicability and research-to-feature requirements.
4. `docs/METRIC_DICTIONARY.md` — mathematical definitions, exact timestamp origins, denominators, censored observations, reproducibility.
5. `docs/EXPERIMENT_PROTOCOL.md` and `config/experiment_matrix.json` — paired, domain-stratified, progressive testing without data leakage.
6. `docs/IMPLEMENTATION_CONTRACT.md` — architecture, UX, CLI, storage, testing and delivery requirements.
7. `schemas/*.json` and `config/provisional_gates.json` — versioned data contracts and **unvalidated, configurable** engineering hypotheses.
8. `data/legacy/STT-EN(1).json` and `data/legacy/Testing_STT_Model_English_Version(1).csv` — 2026-10-12 historic whole-file result logs, not fresh validation evidence.

## EXACT SCOPE

English-only audio transcription. Primary group consists of **9 DISTINCT checkpoints**, with models allowed in multiple roles:

**LIVE CANDIDATES (5)**: `nvidia/parakeet-tdt-0.6b-v2`, `nvidia/parakeet-tdt-0.6b-v3`, `Qwen/Qwen3-ASR-0.6B`, `openai/whisper-small.en`, `openai/whisper-small`.

**OFFLINE/FINAL CANDIDATES (5)**: `openai/whisper-large-v3`, `openai/whisper-large-v2`, `Qwen/Qwen3-ASR-0.6B`, `nvidia/canary-1b-v2`, `openai/whisper-large-v3-turbo`.

**DEFERRED RECOVERY ONLY (2)**: `Qwen/Qwen3-ASR-1.7B`, `facebook/mms-1b-all`. Previous run failed: DO NOT invent WER, silently promote them, or block core application waiting for a retry. Enable explicit English-only diagnostic retry.

You may implement **multiple backends / pipelines for exactly these checkpoints** when technically supported, but distinguish checkpoint identity, inference algorithm, backend, precision, VAD, chunking and device as *separate configuration dimensions*. Do not add another model candidate or another language. A mention of another model in research is context ONLY, not permission to benchmark it. Do not equate the historic `turbo` faster-whisper selector with a verified HF weight revision until you establish artifact provenance.

**Scope audio processing, not a video upload pipeline**. Capture microphone/system loopback if permitted; enable controlled real-time-paced replay on audio recordings. Never call accelerated file playback a real-time trial.

## NON-NEGOTIABLE SCIENTIFIC RULES

- Historic 100 English recordings, 3111.93575 seconds, 5024 legacy normalized reference words; 27 historic configs, 25 completed and 2 failed. The original run was **whole-file `mode=final`, `protocol=full-file-v1`**, despite `chunk_seconds=3` in options. Existing whole-file WER and RTF say NOTHING about measured speech-to-visible-caption live lag.
- Historic data participated in model shortlisting; it is **development/selection evidence**, NOT untouched final validation. Create a held-out evaluation workflow with sample IDs, immutable split manifests, speaker and session non-leakage.
- **WER <= 0.15** and **P95 live lag <= 3 s** are configurable `[P]` provisional target hypotheses. No original paper verified either as a universal acceptability threshold. Never report VALIDATED purely from these numbers. Include human usability, content-critical error and robustness evidence plus explicit sign-off.
- Use *WER = (S + D + I) / N*, not “100% minus WER means speech comprehension”. Report raw and normalized WER separately; micro and macro rates not interchangeable. Document how punctuation, numbers, contractions and technical terms are normalized; never overwrite historical scoring policy.
- Distinguish **RTF**, **RTFx**, processing throughput, algorithmic delay, acoustic-end to model emission, first-viewable-caption latency, committed-text latency, cold start and end-to-end offline turnaround. Timestamp definitions and monotonic clock relationships are mandatory. Avoid deriving word-level lag from a segment-level timestamp without an explicit uncertainty flag.
- Never call `label.setText()`/websocket send a *measured screen presentation*. Track UI update request, paint/render acknowledgment and any verified display timing separately. If physical presentation cannot be observed, report latency proxy, not true visible latency.
- Preserve omissions: undetected words have no finite word latency and must count in coverage/error. Do not compute percentiles only on successfully displayed words and claim full coverage.
- Do not substitute models, convert a batch decoder into “native streaming” by name, or invent successful native streaming support. Qwen native streaming documentation currently identifies a vLLM backend; naive chunked calls are NOT equivalent. Parakeet v2/v3 may require adapted chunked inference and can suffer context losses.
- Never transfer published WER/RTFx numbers to current CPU/hardware without local tests. Record `model_id`, repository commit/weight SHA, backend/commit, precision/quantization, beam/decoding, threads, VAD, CPU/GPU, sample rate, active memory and operating environment.
- No hidden cloud calls or audio uploads. Explicit consent, local storage default, delete/redact controls, access safeguards, opt-in external dataset downloads subject to license. Do NOT bundle model weights, actual user recordings, or PII.
- Keep `[E] directly observed/published`, `[I] derived inference`, `[P] provisional engineering proposal`, `[G] gap/not measured` visible in all reports, along with provenance and source URLs.

## USER EXPERIENCE — deliver a working desktop application AND headless CLI

Primary platform Windows 11, Python 3.12. Use a testable core separate from UI; **PySide6 suggested**, SQLite for metadata plus append-only JSONL and raw WAV/FLAC for evidence. NeMo/vLLM/WSL2 limitations must be stated, not patched by silent backend substitution. Support a separate worker (e.g. WSL2/Linux) when required, with clock-sync limitations documented. The app must work in `historical-import / comparison / simulated-test-fixture` mode even if weights, microphone, or GPU are missing.

Views:
1. **Model Lab / Registry:** two role-specific tables, historical WER/RTF and status, backend compatibility, exact configs, progress, missing requirements; 9 primary checkpoints plus 2 deferred. Show model *configurations* as separate rows under the same checkpoint.
2. **Datasets and Splits:** audio/reference import, hashes, alignment status, real vs synthetic/replay labels; speaker/session grouping, consent flags, held-out locks; controlled noise/domain conditions.
3. **Experiment Runner:** configure paired offline comparisons; sequential chunked (fixed and VAD-adaptive), overlap/context, optional native streaming ONLY when truly available; live mic/loopback or paced replay; cold/warm run repetitions; resumable jobs with machine-readable failure reasons.
4. **Real-time Trace:** waveform/source status, live provisional captions, event track with capture→buffer→queue→decode→merge→UI acknowledgment, queue/backlog, revision/stability; visible measurement confidence/proxy flag.
5. **Accuracy & Error Review:** per-model WER/CER and S/D/I, per-domain/speaker metrics, technical-term review, units/numbers/negation errors, silent hallucinations, turn omissions, adjudicated semantic severity. Allow audio-segment playback and reviewer annotation.
6. **Latency, Resource & Reliability:** per-word and per-utterance lag when validated, start-to-first-caption, P50/P90/P95/P99/max WITH n/coverage, RTF/RTFx separately, queue dwell, CPU/RAM/disk, dropouts and sustained long-session backlog.
7. **Comparative Decision & Report:** paired differences plus uncertainty intervals; Pareto frontier *by mode/configuration*, candidate status: `ELIGIBLE`, `BORDERLINE`, `FAILED`, `NOT MEASURED`, `BLOCKED`, `INSUFFICIENT EVIDENCE`. Show dual-model architecture vs single-model alternatives using actual matched evidence; allow reviewer sign-off; export comprehensive English reports and machine-readable artifacts.

## ENGINEERING PHASES (DO NOT STOP AT A PLAN)

P0. **Historical ingestion immediately runnable.** Load supplied JSON+CSV, reconcile exact per-model rows, preserve original hashes, produce static baseline dashboard and English report. Verify 100 sample IDs, historic normalization, all 27 configurations, primary 9 and deferred 2. Never relabel RTF as lag; show live metric fields `null`.

P1. **Storage / schema / trace / dataset manager.** Immutable run manifests; audio sample indexes, monotonic ns + calibrated clock IDs; append-only ordered events; versioned validators; reference correction, split locks and versioned annotations.

P2. **Model abstraction and real inference.** Per-family adapters (NeMo Parakeet/Canary, qwen-asr, faster-whisper). Distinct batch, paced-chunk, and explicitly supported native streaming capabilities; opt-in environment install, weight hash, workers and cancellation. Use historic config as a reproducibility starting point, not an enforced fairness config. Surface BLOCKED accurately.

P3. **Metric engine and live instrumentation.** Event-derived stage latencies, reliable paint proxy, coverage, revisions/commits, WER/CER, term/semantic review, clock checks, omission handling, segmentation ablations, speaker/session-level grouping, paired bootstrap CIs.

P4. **Experiments and human validation.** Paired stage-1 shortlist, stage-2 new sessions, stage-3 adversarial/robustness, stage-4 user study, held-out final. Do not run a giant unconstrained Cartesian product. Save randomized run order and identical audio inputs.

P5. **Usable desktop dashboard, reports, tests, docs.** Real run evidence references, failures and gaps, source traceability, decision rubric and experiment export.

## REQUIRED COMMANDS / DELIVERABLES

Create and test runnable `src/`, `tests/`, `pyproject.toml`, `README.md`, `docs/`, `config/`, `schemas/`, CLI, desktop launcher (`.bat` for Windows), `IMPLEMENTATION_STATUS.md`. CLI must provide at least:

- `asrlab import-legacy --json <path> --csv <path> --out <run-dir>`
- `asrlab list-models`
- `asrlab audit <run-dir>`
- `asrlab score --reference <...> --predictions <...>`
- `asrlab plan --matrix config/experiment_matrix.json`
- `asrlab run --config <...>` (runs actual models only when installed; otherwise BLOCKED with reason)
- `asrlab report <run-dir> --format md,json`
- `asrlab ui`

Add tests for historical parity, exact model identity, duplicate job/event IDs, real/synthetic labeling, invalid time order, cross-process clock uncertainty, chunk boundary omissions/repeats, missing word timestamps, UI update not equated to screen presentation, fatigue/backlog during long sessions, unpaired corpus rejection, video data accidentally included, and split contamination. All data-dependent services degrade gracefully.

At completion provide actual files, successful commands, test results, screenshots if obtained from a real UI, and an evidence matrix showing WORKING vs PARTIAL vs BLOCKED. **Do not report an experiment as run unless real weights and audio were processed.**

**Begin implementation now. Read all attachments, inspect any existing project code, implement P0 and run its unit tests, then work forward.**
