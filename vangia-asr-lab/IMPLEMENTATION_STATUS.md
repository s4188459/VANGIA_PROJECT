# Implementation status — 2026-10-17

## Version 0.2 ZIP benchmark / analysis workflow

The new **New benchmark (ZIP)** and **Analysis / CSV export** buttons are implemented.
The existing seven views remain. Restart the application to use the new code.

| New capability | Status | Evidence / limitation |
|---|---|---|
| ZIP + TXT + optional metadata.csv | WORKING | Nested pairing, editable metadata, consent, reference quality, silence confirmation, duration/size bounds, hashes; input errors block execution and are retained |
| Multiple model configurations/repeats | WORKING | Exact registry, form presets, sequential jobs, immutable plan, stable config identity across repeats, cancel/resume; each repeat is a fresh worker, not warm inference |
| Analysis bundle | WORKING | CSV BOM, JSON/JSONL, dictionary, metric envelopes, report, schema/checksums; parity validation; no audio bundled |
| Result table/review/export | WORKING | Run/model/domain/status filters, sample alignment/playback, paired selected-run comparison, result folder/export controls |
| Failure/missingness handling | WORKING | Shared failures, cancelled pending samples and invalid duplicate user IDs remain observable; full-corpus rates null when incomplete |
| Real inference demonstration | WORKING | New ZIP of EN001–EN003 processed by existing local small.en worker; 3/3 completed; normalized WER 0.06875; validated analysis export |
| Warm repeats / global corpus governance | PARTIAL | True warm reuse unsupported; split contamination checked within imported registry, not across every separate ZIP ever imported |
| All backend environments / real word display timing | BLOCKED where unavailable | Preflight is not a guarantee that optional backend loads; no fabricated weights, physical display measurement or human study |

Independent review findings were reproduced with six failing regressions and fixed: total
decode budget, cancel during resume, stable configuration identity, invalid duplicate IDs,
cancelled prediction statuses and archive-bound silence confirmation. Reference quality is
preserved in the wizard mapping. The prior 89-test native suite passed before this fix pass.
Final complete native suite: **95 passed in 63.69 s**, no skips, 2026-10-17.
Final verification and release hashes are recorded in `docs/analysis-workflow-verification.json`.
The verified real output is `runs/analysis-demo-export-final/`.

## Earlier 0.1 implementation record

Version 0.1.0 is a runnable local Windows desktop and headless CLI application. P0 historical
ingestion is complete and tested. Later phases have working implementations with the limits
below; not every research requirement or backend has been empirically validated. No candidate
has been declared VALIDATED.

The original package is normative. Research documents, registry, experiment matrix, gates and
schemas are copied unchanged into `docs/`, `config/` and `schemas/`. No additional candidate
or language was introduced. Existing sibling applications were not edited. Local weights
were reused, not bundled or downloaded.

## Evidence matrix

| Requirement | Status | Implemented and verified | Remaining boundary |
|---|---|---|---|
| P0 legacy importer | WORKING | JSON/CSV reconciliation; original bytes/hashes; 100 IDs; 27 configurations; 25 successes and 2 preserved failures; SQLite/English reports | Whole-file development evidence; live lag null |
| Exact registry | WORKING | 9 distinct primary checkpoints, 5 live/5 offline roles, shared Qwen 0.6B, 2 opt-in deferred diagnostics | Extra archived rows cannot become new candidates |
| CLI and desktop | WORKING | Required commands, Windows launchers, seven functional Tk views; native GUI smoke | Tk replaces suggested PySide6 |
| Storage/audit/splits | WORKING | Supplied schemas, immutable manifests, append-only events, hashes, reference revisions, split locks | Hashes do not protect against an actor rewriting hashes; OS folder access controls apply |
| Crash/cancel/resume | WORKING | Durable-attempt recovery, preserved corrupt tails, continued journals, exact-input resume, process-tree termination | Requires immutable witness; interrupted live capture starts a new run |
| Original audio binding | WORKING | 100 audio, 100 reference source and 100 canonical WAV hashes matched | Participants/speakers/sessions and reference correctness not independently verified |
| Batch/paced replay | WORKING | Real faster-whisper small.en CPU/int8; randomized jobs; fixed/overlap and RMS-adaptive windows; queue trace | Smoke subsets only; independent chunks are adapted inference |
| Other family adapters | PARTIAL | NeMo, qwen-asr, MMS diagnostic code, provenance/preflight and separate-worker interface | No real inference verification for these families in this delivery |
| Native streaming/WSL/loopback | BLOCKED | Explicit unsupported states, no substitution | No native stateful stream, WSL RPC bridge or WASAPI loopback backend |
| Microphone | PARTIAL | Optional sounddevice, explicit consent/device, online chunks, saved recording | Physical microphone trial not performed |
| Accuracy | WORKING | Historical normalization parity, raw/normalized WER/CER, S/D/I, micro/macro/domain scores, missingness, terms, paired exports | Semantic correctness requires human review; no comprehension inference |
| Stage timing | WORKING | Queue dwell, host roundtrip, first emission, redraw proxy with n/coverage; per-session backlog/revisions | Segment stages are not word lag; short replay is not sustained-session reliability evidence |
| Word/display timing | PARTIAL | Reviewed-word engine, clock uncertainty, omission censoring, redraw acknowledgment | No real reviewed word alignment or physical display instrument; live word lag null |
| Resources | WORKING | Worker-process-tree CPU/RSS/I/O sampling including Windows launcher children | Sampled RSS sums may count shared pages twice; excludes UI/GPU; first CPU sample lacks prior interval |
| Comparative experiments | PARTIAL | Progressive plans, paired session-cluster bootstrap (>=2000 draws), Pareto grouping, measured single/dual comparison function | No all-candidate campaign or actual dual-model study |
| Human review/study | PARTIAL | Audio playback, annotations/adjudication, signoffs, response collection, descriptive utility and agreement | No human study, adjudicated corpus or independent holdout result supplied |
| Preregistration | PARTIAL | Locked dataset/config/provenance-content identities; holdout relabeling rejected | Does not automatically freeze code, omitted defaults or backend binaries |
| Reports/privacy | WORKING | English Markdown/JSON/HTML, source/evidence tags, redacted summary, exact-ID deletion | Full metric envelopes cover core timing/RTF records, not every nested statistic |
| Dashboard depth | PARTIAL | Registry, datasets, runner, waveform/trace, error review, resources and decision panels | Some advanced filters/comparisons require CLI/Python; no full interactive comparison chart suite |

## Verification actually performed

- Full suite including native Windows desktop: **64 passed in 34.65 s**, 2026-10-16.
- Tests cover historical normalization/error parity, exact model identity, duplicate IDs,
  split contamination, corrupt-tail recovery, clocks/order, UI request/paint/physical
  distinctions, chunk seams, missing timestamps, session backlog, paired identity, descendant
  memory accounting and process termination.
- Paired exports retain shared failures, preventing successful-only comparison bias.
- Archive conversion passed with PyAV 19.0.1. No microphone was recorded during development.
- See [verification record](docs/VERIFICATION.md) and local run evidence. `runs/`, `.venv/`,
  model weights and participant recordings are excluded from distribution.

## Scientific interpretation

Historical totals are 3111.93575 seconds and 5024 normalized reference words. Those recordings
were used for shortlisting and cannot become untouched validation through import or replay.
WER <=15% and P95 <=3 s remain [P] provisional proposals.

Local small.en experiments demonstrate executable inference and measurement, not a winner.
References remain unverified. Converted local artifacts are hashed and identified as small.en;
the conversion's upstream OpenAI weight revision was not established and remains an explicit gap.

Earlier resource logs measured only the Windows Python launcher. Their RSS/CPU/I/O values
must not be used as model resource evidence. `runs/real-replay-release` uses corrected
process-tree measurement. Also exclude the old `runs/real-replay-smoke` global backlog slope,
which mixed acquisition with queue drain. New slopes use acquisition-only observations per
session; a short session still cannot establish fatigue or sustained reliability.

A final decision needs independently consented, speaker/session-disjoint recordings, reviewed
references and alignments, required backend environments, repeated paired/robustness trials,
human task evidence and an owner-approved acceptance policy.
