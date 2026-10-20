# Vangia — ASR Model Selection & Validation Lab

**Codex build-package release:** `2026-10-15-v2`  
**Experiment language:** **English only**  
**Current deliverable:** build instructions + research-grounded tool design + machine-readable config/schemas + actual historical logs. **This archive is NOT the runnable application, nor live experiment output.**

## What to do

1. Extract this ZIP into a fresh working folder (or add as `asr_lab_requirements/` to your Codex coding workspace).
2. Give Codex the whole extracted folder and paste the short prompt in `SEND_THIS_TO_CODEX.txt` (or point Codex to `CODEX_MASTER_PROMPT.md` directly).
3. Ask Codex to inspect ALL package files before coding. It must produce its own new application source, tests and executable setup directions.
4. After the historical importer passes tests, supply original audio and new independent development/held-out English sessions for actual inference and validation.

## Included files

| Path | Purpose |
|---|---|
| `CODEX_MASTER_PROMPT.md` | The complete implementation instructions; **read first** |
| `docs/RESEARCH_EVIDENCE_AND_REQUIREMENTS.md` | 17 paper/model/repository sources and explicit evidence→inference→tool requirements |
| `docs/METRIC_DICTIONARY.md` | Computations, start/end timestamps and missing-data safeguards |
| `docs/EXPERIMENT_PROTOCOL.md` | Paired experiments, split protocol, real-time paced testing, reviewer tasks |
| `docs/IMPLEMENTATION_CONTRACT.md` | Software architecture, UI, acceptance, QA and output structure |
| `config/model_registry.json` | Exact 9 distinct primary checkpoints and 2 deferred retry checkpoints plus all historical configuration data |
| `config/experiment_matrix.json` | Progressive research-driven experiments, not exhaustive blind model search |
| `config/provisional_gates.json` | 15% WER and 3s P95 as **provisional project hypotheses** |
| `schemas/event.schema.json` | Clocked append-only events, including audio and UI timestamps |
| `schemas/run_manifest.schema.json` | Per-run immutable provenance contract |
| `schemas/reviewer_annotation.schema.json` | Human semantic error review fields |
| `data/legacy/STT-EN(1).json` | Actual 100-sample, 27-config historical experiment (unchanged) |
| `data/legacy/Testing_STT_Model_English_Version(1).csv` | Original summary of that experiment (unchanged) |
| `docs/BASELINE_FACTS.md` | Selected model summary and historical validity warnings |
| `scripts/verify_inputs.py` | Optional local sanity checker for package evidence inputs |

## Files you SHOULD add separately, if available

- `EN_Audio/EN001.m4a` … `EN100.m4a`: the original audio corresponding to legacy `samples[*].original_filename`, or resampled WAV with verified mapping/hashes. **Not included.** Without these, Codex can read/summarize old results, but cannot re-run original inference or validate word-aligned audio timing.
- `new_english_dev/`: separate NEW consented live teaching/conversation sessions plus verified English reference transcript, speaker/session metadata and capture consent. Use for development, not as untouched final evaluation.
- `new_english_holdout/`: NEW locked speaker/session-disjoint English recordings never touched during tuning. Needed for confirmatory claims.
- Optional existing application source (`AppController`, microphone + WASAPI capture, existing chunk/merge pipeline) if you want reuse/integration. Tool MUST remain standalone if this source is absent.
- Optional exact model weight archives/checkpoint cache/config files and hardware specs, only when reuse is permitted. The package **does not ship checkpoint weights** or require cloud download to run legacy import.

## Existing experiment is not live evidence

- 100 English samples, 3111.93575 seconds audio, 5024 normalized reference words.
- 27 model configurations, 25 completed, 2 failed. Run protocol `full-file-v1`, mode `final` and **NOT live despite an unused chunk option**.
- NVIDIA Parakeet v2, v3 and Qwen3-ASR 0.6B; small.en/small; Whisper large-v2/v3/turbo; Canary v2 all have historic whole-file measurements; Qwen3 1.7B and MMS 1B have ERROR, NOT WER.
- CPU backends differed (NeMo vs faster-whisper vs Qwen); precision, beams and VAD differ. The benchmark ranks **deployment configurations** under its conditions, not innate architecture capability.
- Historical metric definitions: `nfkc-casefold-punctuation-to-space-v1` WER and `same-as-wer-without-whitespace-v1` CER. Do not overwrite.
- `WER ≤ 15%` and `~2–3s live lag` remain proposed goals. Papers in the source register do NOT set general standards for either.

## Research documentation caution

Sources include peer-reviewed papers, preprints, and official technical/model documentation. `docs/RESEARCH_EVIDENCE_AND_REQUIREMENTS.md` states **which exact claims** are supported and when they are not transferable. Codex should **not** treat web snippets, claims of other model versions, or external GPU results as validation on the user's CPU. If no backend/native streaming method exists in the active environment, report BLOCKED or NOT SUPPORTED and build the rest of the tool properly.
