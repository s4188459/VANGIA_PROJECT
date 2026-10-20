# ZIP benchmark and analysis export Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; RED/GREEN tests per task.

**Goal:** Working ZIP-to-benchmark-to-analysis workflow without hand-editing JSON.
**Architecture:** Safe staged input, immutable sequential benchmark plan, audited export,
and Tk wizard reuse DatasetRegistry, runner, scoring and event timing.
**Tech Stack:** Python 3.12, Tk, sqlite3, zipfile/csv, PyAV, pytest/jsonschema.
**Spec:** ../specs/2026-10-16-analysis-workflow-design.md and the supplied user request.

## Global constraints
- Exact 9 primary and 2 explicit deferred checkpoints; English only; local/no downloads.
- Existing runs and normative resources unchanged; no edits outside vangia-asr-lab.
- Missing is not zero; failed samples remain; no automated VALIDATED claim.
- Work in the existing isolated application directory because it and all current work are
  untracked inside a dirty shared repository; no commit or worktree relocation of user files.

## Review focus
- Ambiguous/case-colliding ZIP paths and metadata omissions must not silently drop inputs.
- Incomplete/repeated/cancelled campaigns retain every planned observation.
- Historical extra configs cannot be misidentified as current candidates.
- Export paths must never mutate a sealed run or include unrequested recordings.
- Cold repeats and unknown session metadata must not acquire false independence.

### Task 1: ZIP importer
- [x] RED: tests/test_zip_dataset.py for nested mapping, missing/empty reference, bad audio,
  video, unsafe paths/symlinks/limits, original hashes and split contamination.
- [x] Implement zip_dataset.preview_zip(archive, metadata=None, limits=None) -> dict and
  import_zip(archive,out,consent_record_id,metadata=None,silence_ids=(),limits=None) -> dict.
  Preserve error rows; create dataset.json plus immutable checksums and ready split manifests.
- [x] GREEN: pytest tests/test_zip_dataset.py.

### Task 2: Sequential campaign
- [x] RED: tests/test_benchmark.py for presets, paired identities, repeats, blocked/cancelled
  jobs, resume config integrity and no reference leakage into worker config.
- [x] Implement benchmark.create_benchmark(dataset,configs,out,repeats=1,seed=42),
  run_benchmark(path,resume=False,progress=None,presenter=None), cancel_benchmark(path).
- [x] Add CLI preview-zip/import-zip/benchmark-run, preserving existing commands.
- [x] GREEN: targeted tests plus existing runner tests.

### Task 3: Analysis bundle
- [x] RED: tests/test_analysis_export.py for CSV/JSON parity, planned failures, micro/macro,
  grouped denominators, missing/proxy timing, CSV injection and source immutability.
- [x] Implement collect_results(source) -> dict, export_analysis(source,out) -> dict,
  validate_bundle(path) -> dict, comparison by selected run identity.
- [x] Add schema and dictionary for exported contracts and CLI export-analysis.
- [x] GREEN: export tests and explicit bundle validation.

### Task 4: Desktop wizard/results
- [x] RED: opt-in native Tk test importing a fixture ZIP, selecting preset, running blocked
  campaign without weights, exporting and reading results without dialog automation.
- [x] Implement benchmark_ui with preview/mapping, consent, preset form, multi-select models,
  preflight, progress/cancel/resume, result filters/playback/export/open folder.
- [x] GREEN: native desktop smoke and full suite.

### Task 5: Evidence and delivery
- [x] Run real small.en smoke on a new ZIP subset, retain provenance, export and validate.
- [x] Fresh independent code review; fix important findings with regression tests.
- [x] Update README/status, schemas/examples, verification and distribution artifacts.
- [x] Full suite incl native GUI, wheel install smoke, source/normative parity, bundle audit.

## Execution ledger
- Design and execution follow the user's supplied implement-now request. No external writes,
  downloads, sibling-project edits or changes to old evidence are required.

- 2026-10-17: ZIP importer 12 initial tests, campaign and exporter tests, native wizard import/run/export all passed.
- Independent review: six findings reproduced RED, then fixed; final full native suite 95 passed in 63.69 s.
- Reference quality mapping omission was fixed in the same archive-identity regression.
- Execution ruling: repeats use cold model loads, not warm-worker reuse; OS cache state uncontrolled. Cost: true warm experiments require a later worker lifecycle extension.
- Execution ruling: existing dirty/untracked app remains in place; no git commit/worktree relocation. No sibling project changes.
- Real ZIP smoke: small.en on EN001?EN003 completed; WER 0.06875; bundle schema/CSV parity/checksums passed.
- Packaging: isolated wheel install uses bundled resources, previews 3 ZIP samples and exports 3 observations successfully.
