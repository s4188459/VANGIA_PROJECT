# Vangia ASR Lab implementation plan

Spec: supplied CODEX_MASTER_PROMPT.md and the copied normative docs, config and schemas.
Architecture: independent Python core, local SQLite metadata and immutable evidence files,
Tk desktop UI, optional isolated Python model workers. No automatic downloads or cloud calls.
User explicitly requested immediate implementation through runnable delivery.

1. P0: tests for exact historical JSON/CSV reconciliation, 100 IDs, 27 configs, normalization,
   errors, original hashes and null live metrics; implement legacy.py, reports.py, CLI and registry UI.
2. P1: tests for strict schemas, event chronology/duplicates, immutable manifests, split leakage,
   audio-only consented datasets; implement storage.py and datasets.py.
3. P2: tests for exact checkpoint restrictions, provenance, missing prerequisites, worker failures,
   cancellation/resume; implement adapters.py, worker.py and runner.py.
4. P3: tests for S/D/I, raw/normalized CER/WER, missing speech, timestamps, clock uncertainty,
   revisions, backlog and chunk seams; implement metrics.py, timing.py and audio.py.
5. P4: test paired corpus rejection and session bootstrap, progressive experiment plans,
   human annotation and sign-off policy; implement experiments.py and review.py.
6. P5: connect seven desktop views to real services, run UI smoke and full regression suite,
   produce reports, precise Windows commands and an honest implementation evidence matrix.

For each implementation unit: write tests, run to observe missing behavior, implement, rerun suite.
Review focus: corrupt journals, path traversal, failed/missing samples, false validation claims,
and UI responsiveness during worker timeout. Preserve the existing modified projects.
