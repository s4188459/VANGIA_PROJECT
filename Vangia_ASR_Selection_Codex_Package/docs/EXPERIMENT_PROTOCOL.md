# Experiment Protocol — Fair, Reproducible English ASR Model Selection

This protocol is **a proposal inspired by evidence**, not a published, universal sample-size rule. Pre-register datasets, scores, comparison direction, missing-result policy, and primary outcomes before held-out runs. The project must not simply run more models on the same 100 already-used selection samples and call that independent validation.

## Dataset governance

- **Dataset A (LEGACY DEVELOPMENT):** existing 100 audio IDs EN001–EN100, 51.8656 minutes, 5024 legacy normalized reference words. Used to select candidates: baseline/import/diagnostic only, cannot serve as an untouched confirmatory test. Original audio waveforms not in package.
- **Dataset B (NEW DEVELOPMENT):** new consented English classroom conversations; speaker/session-disjoint from confirmatory dataset. Use this split to tune chunk length, overlap, VAD and merge policy. Lock hashes and split before tuning; label any synthetic/noise-added variants as derivatives of the same parent original.
- **Dataset C (NEW HELD-OUT):** never seen during final model/pipeline tuning. Session/speaker disjoint where possible. Freeze checkpoint revision, preprocessing, normalization, decoding and live pipeline code before reveal; compare all finalists on the same files and hardware.
- **Optional independent/public English benchmarks:** AMI (far-field meeting), LibriSpeech test-clean/other (read English), TED-LIUM (speech talks), GigaSpeech (varied audio), Earnings22 (domain vocabulary), relevant subsets of common benchmark suites when usage rights allow. NEVER mix benchmark averages with local test score without flagging external domain.

## Recommended pilot sample plan [P, not evidence-based cutoff]

Start with a diverse pilot (e.g., 20+ distinct English speakers, 30+ full sessions and 10+ hours if practical, with different recording devices and noise levels), then calculate confidence interval widths and rare-error exposure. **These are suggested planning goals, not scientific sufficiency guarantees.** A final sample size should be determined by a predeclared precision/power plan, observed per-session variability, and stakeholder risk tolerance. More seconds from the same speaker are not equivalent to independent speakers. Never invent a dataset count or human-participant enrollment.

## Test families and progression

### T0 — Legacy integrity (all 27 archived configurations)

Import JSON+CSV and verify: 100 samples, audio duration, scoring normalizer, 25 completed and 2 failed, all 11 selected/recovery model records. Preserve local alias and backend flags. Report legacy whole-file inference separately from live measurements. Allow viewing all 27 configurations for historical provenance; do not add them to the new official candidate shortlist.

### T1 — New paired offline check (9 primary checkpoints across their assigned roles)

Using IDENTICAL inputs, run one baseline configuration per candidate with documented fixed CPU/thread/device and model-specific backend (do not demand a decoder setting a given model cannot support). Record multiple cold/warm repeats and randomize model order; measure WER/CER, processing and loading, resources, errors, and per-domain counts. Candidate values must not inherit legacy statuses/RTF numbers. Two recovery models run only on explicit `diagnostic-retry`, never as pass/fail ranked competitors until successful.

### T2 — Live-capable pipeline feasibility (exact 5 live candidates)

Baseline `chunked_independent` for all 5 if backend supports it, without pretending to have native stateful streaming. Use real-time-paced playback with capture timestamps and user UI (separate from naturally captured real mic); progressively test chunk duration starting at e.g. 1/2/3 seconds with fixed overlap 0 and representative overlap 0.5 s as engineering proposals, not normative chunks. Record every chunk from audio frame creation to actual/proxy UI output, queue and time. Only use an additional *native* streaming branch when model+backend+platform truly support it, and label distinct modes. Flag missing native mode as `NOT_SUPPORTED`, not erroneous model accuracy.

### T3 — Focused ablations (top candidates chosen on dev set only)

Investigate (a) fixed vs VAD boundary; (b) overlap and duplicate removal; (c) history/context retention and prompt conditioning where supported; (d) model load cold/warm; (e) CPU 4 threads vs different thread counts if feasible; (f) segmentation/resampling; (g) silence; (h) endpoint/partial update policy. Change ONE factor at a time under matched audio, keep multiple runs with deterministic random seed. Do not run a huge factorial grid by default; selection bias from repeatedly tuning on held-out data must be prevented.

### T4 — Stress / long session / real-time interactive conditions

At least a short pilot with multi-minute to session-length non-stop English dialogue, speaker switches, overlapping turns, interruptions, early/late syllables at chunk seam, pause/silence, microphone/system-loopback route variations, connection/device disruption, background computer fan/keyboard noise, far-field and natural teaching terms. Report backlog slope, dropped frames and coverage, not just mean inference per chunk. A replay test is labeled `paced_replay`; a human-operated live microphone test is labeled `live_microphone` or `live_loopback`.

### T5 — Content review / participant task usability

Two independent English-speaking reviewers where feasible annotate sampled mismatches and critical errors, adjudicate disagreements, and rate readability. Collect informed-consent pilot usability data from intended learners: follow discussion, respond to comprehension prompts, identify technical terms and meaningful negations, perceived lag annoyance and revision/flicker. Report participant/task and stimulus count, human instructions and exclusion criteria. A *same WER* comparison may behave differently depending on error types. Establish project-specific acceptance after this stage; do NOT quote a universal scientific 15% threshold.

### T6 — Final held-out confirmation and architecture decision

Freeze pipeline selection, decoder, code/version, hardware conditions, normalization and hypothesis gates. Run finalists on untouched sessions with paired outputs and CI; compare `one model live+offline` vs `two distinct models live+offline` including post-session turnaround and actual storage/compute. Label final decision as limited to English input domains/hardware tested. Flag tradeoffs without claiming absolute best model for all English speech.

## Fairness and evidence capture

- **Paired input:** models must receive bit-identical original PCM or a SHA-verifiable common resampling transform. Stream/chunk policies vary only as a named factor. Same volume and target reference; no cherry picking.
- **Backend and precision:** benchmark configurations are not directly model comparisons when `faster-whisper/INT8/VAD/beam=5` is compared to NeMo `float32/VAD OFF/beam=1`; treat these as deployment-configuration comparisons. Report controlled experiments on common settings where actually supported AND realistic end-to-end deployment performance.
- **References:** normalize reproducibly; reviewers validate a subset/full reference according to protocol; word timestamps require manually validated alignment if measuring word lag.
- **Error policy:** failed jobs are failed, timed out are censored/missing, no invented transcription. Performance rank should display both conditional mean on successful files AND completion fraction.
- **Statistics:** report paired per-session differences and cluster bootstrap confidence intervals with stable seed. If speaker/group metadata absent, limit generalization and state assumption.
- **Hardware:** serial tests unless measured deployment requires concurrency. Dedicated model worker telemetry and thermal throttle/cold-start control. Host OS, exact CPU/GPU RAM, threads, clock offset and backend versions.
- **No video workflow:** all experiments instrument audio STT and display; video upload/transcoding is explicitly outside the measured latency path.

## Experiment-ready decision answers

1. On new English classrooms, which *implementation configuration* yields low WER with acceptable end-user-visible lag and stable output?
2. Does any of the five candidate live pipelines stay within configurable provisional targets under realistic CPU workload over long sessions?
3. How much accuracy is lost due to chunking or overlap merging relative to whole-file processing for the same checkpoint?
4. Which offline candidate achieves the lowest critical errors and WER per acceptable processing-turnaround budget, with reproducible settings?
5. Is a one-model architecture comparably usable/accurate at lower costs than live-model plus separate final-model? No architecture is assumed superior before measurements.

