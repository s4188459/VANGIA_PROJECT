# Vangia English ASR Selection & Validation Lab

Runnable local desktop and CLI implementation in Python 3.12. It imports the supplied
historical benchmark, preserves evidence and failure records, manages datasets and split
locks, runs optional local model workers, scores transcripts and supports human review.

**Historical WER and RTF are whole-file development evidence. They are not live validation.**
15% WER and 3 s P95 remain provisional proposals. Nothing in this application automatically
declares a model validated. See `IMPLEMENTATION_STATUS.md` for tested features and limitations.

## Start on this workspace

### Version 0.2: ZIP input → benchmark → CSV/JSON

Close the old application window and launch again to load the new buttons.
You no longer need to edit JSON for the normal benchmark workflow:

1. Click **New benchmark (ZIP)** at the top of the main window.
2. In **1 · Input ZIP**, choose your ZIP, then click **Inspect ZIP**.
   Audio and UTF-8 TXT are paired by matching relative path without the extension.
   Example: `lesson/EN001.m4a` and `lesson/EN001.txt`.
3. For different folder layouts, provide `metadata.csv` (inside the ZIP or via Browse).
   See [metadata.example.csv](config/metadata.example.csv). The paths are relative to ZIP
   root, e.g. `audio/EN001.wav` and `scripts/EN001.txt`. Partial metadata does not drop other audio.
4. Select a preview row and click **Edit selected pairing** to correct paths/IDs/domain or
   speaker/session metadata. Unknown grouping stays `unknown`, not a guessed independent session.
5. Enter your actual **Local consent record ID**. This is your record of permission for local
   processing, not a generated participant-consent certificate. Missing references block scoring;
   use **Confirm selected silence** only for verified nonspeech with a truly empty transcript.
6. Click **Import & validate**. This decodes WAV/M4A/MP3/FLAC, shows durations/errors and preserves
   original/converted hashes. Fix any errors and import into a **new dataset folder**. The source
   ZIP and existing runs are never overwritten.
7. In **2 · Models & Run**, Ctrl-select models. **Configure selected model** sets local weights,
   provenance JSON, worker Python, precision/device/threads/beam. Existing configured local
   small.en paths are reused in this workspace. Other checkpoints require their own environment
   and weights; **Check prerequisites** reports READY/BLOCKED. It cannot guarantee the decoder
   will load successfully; real loading failures remain recorded.
8. Select **batch_file** or **paced_replay**, repeats and chunk/overlap settings. Each repeat is
   a fresh model load; filesystem/OS caches are uncontrolled. True warm-worker repeats are not
   supported, and later repeats are not mislabeled warm.
9. Choose a new benchmark folder and click **Start benchmark**. Models run sequentially.
   **Cancel** preserves completed observations and planned cancelled rows. **Resume saved
   benchmark** requires unchanged data/config/artifact identity. For a hard-crashed unsealed
   child run use `recover` first, then resume. Fixing a model config requires a new campaign.
10. In **3 · Results & Export**, select a run, then a sample to see reference, hypothesis,
    alignment and **Play selected audio**. Run/model/status/domain filters limit displayed rows;
    run totals remain whole-run totals. **Compare 2 selected runs** requires matched mode,
    temperature, dataset and references and rejects incomplete pairs.
11. Click **Export analysis bundle**, choose a new ZIP filename. Or use **Analysis / CSV export**
    in the main window to export an existing run (including all 27 historical configurations).

The result table shows WER/CER as ratios: `0.15 = 15%`; `—` means unavailable. It does not
declare a winner or translate WER into comprehension. Paint proxy is labeled separately from
physical word presentation. Old launcher-only resource logs are excluded from aggregate RAM/CPU.

| Export file | Row/content |
|---|---|
| `run_summary.csv` | One model/configuration/repeat with counts, WER/CER, RTF, time, RAM, coverage |
| `sample_metrics.csv` | Every planned sample, including blocked/failed/cancelled inputs; raw/normalized S/D/I/N |
| `group_metrics.csv` | Domain/speaker/session groups; pooled counts and explicit weighting |
| `transcripts.jsonl` | Lossless reference/hypothesis plus raw/normalized alignments |
| `latency_observations.csv` | Event intervals and explicit missing word-timing summaries with endpoints/clocks |
| `resources.csv` | Recorded process-tree resource samples; scope/quality retained |
| `failures.csv` | Execution/input/scoring failures and missing reasons |
| `results.json` | Structured tables, metric envelopes, manifests and artifact provenance |
| `data_dictionary.csv` | Units, row grain, formulas, null/blank conventions and CSV escaping |
| `report.md` | Readable overview and interpretation limits |
| `export_manifest.json`, `checksums.json`, `analysis_results.schema.json` | Row counts, identity, integrity and schema |

CSV uses UTF-8 BOM for Excel and numeric ratios, with blank cells for missing values. JSON
uses `null`. Formula-like CSV strings are apostrophe-escaped; JSONL preserves original text.
Exports contain transcripts and metadata, but no audio recordings: keep them private.
Full-corpus rates are null if scoring is incomplete; `conditional_*` values cover scored
successes only. S/D/I aggregate counts explicitly refer to that scored subset.

Verified local example: `runs/analysis-demo-export-final/` (3 real legacy audio samples;
Whisper small.en; normalized micro-WER 0.06875). Open `report.md` or `run_summary.csv`.
It is development/smoke evidence, not independent validation.

Headless equivalents:

```powershell
.\asrlab.bat preview-zip --archive my-input.zip --metadata metadata.csv
.\asrlab.bat import-zip --archive my-input.zip --out runs/my-dataset --consent-record-id YOUR-RECORD
.\asrlab.bat benchmark-create --dataset runs/my-dataset/dataset.json --configs config/model-a.json config/model-b.json --out runs/my-benchmark --repeats 2
.\asrlab.bat benchmark-run runs/my-benchmark
.\asrlab.bat benchmark-cancel runs/my-benchmark
.\asrlab.bat benchmark-run runs/my-benchmark --resume
.\asrlab.bat export-analysis runs/my-benchmark --out runs/my-analysis.zip
.\asrlab.bat export-analysis runs/my-benchmark --out runs/my-analysis-folder
.\asrlab.bat validate-export runs/my-analysis-folder
```

Default archive limits: 10,000 entries, 1 GiB total uncompressed, 128 MiB per file, 2 MiB per
text file, 600 seconds per audio and 36,000 seconds total decoded audio. Video, scripts,
encrypted members, unsafe paths, symlinks and case-colliding filenames are rejected. Total
duration is enforced during decoding. Invalid rows remain visible; no subset is silently run.
Split overlap is checked within each imported registry. For formal holdout studies, also
check against all previous corpora: separate ZIP imports are not a global identity database.
Historical recordings must retain `legacy_development`; importing them again does not make
them untouched holdout data. Holdout execution still requires the preregistration workflow.

The isolated `.venv` has been created. Open `launch-asrlab.bat`, or in PowerShell:

```powershell
cd "D:\@_Binh's document\AI Course\VANGIA_PROJECT\vangia-asr-lab"
.\asrlab.bat ui --run-dir runs/historical
```

The seven views are Model Lab, Datasets & Splits, Experiment Runner, Real-time Trace,
Accuracy & Review, Latency & Reliability, and Decision & Report. Load a JSON config in the
runner. Keep Real-time Trace selected for redraw proxy acknowledgment. Hidden/minimized
windows do not produce a usable acknowledgment. Physical display timing remains unmeasured.

## Fresh Windows 11 setup

Install Python 3.12 with **Tcl/Tk and IDLE** selected. In the application directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
.\launch-asrlab.bat
```

Alternatively run `powershell -File .\setup-windows.ps1`. If `py` is absent, pass the exact
Python executable: `powershell -File .\setup-windows.ps1 -Python 'C:\Python312\python.exe'`.
The core installation downloads only Python dependencies, never checkpoint weights or audio.
The UI uses Tk, so PySide6 is not required. Install/run commands are local; no server or browser
authentication is involved. The editable install supplies `.venv\Scripts\asrlab.exe`.

## Reproduce the historical import

Use a **new output directory** for each import:

```powershell
.\asrlab.bat import-legacy --json "../Vangia_ASR_Selection_Codex_Package/data/legacy/STT-EN(1).json" --csv "../Vangia_ASR_Selection_Codex_Package/data/legacy/Testing_STT_Model_English_Version(1).csv" --out runs/historical-new
.\asrlab.bat audit runs/historical-new
.\asrlab.bat report runs/historical-new --format md,json,html
.\asrlab.bat list-models
```

Expected: 100 samples, 3111.93575 seconds, 5024 normalized reference words, 27 archived
configurations, 25 completed and 2 errors. Exactly 9 primary checkpoints and 2 deferred
recovery checkpoints are available for new runs. Qwen 0.6B belongs to both live and offline
roles. Other archived rows remain read-only historical evidence. The importer checks JSON/CSV
reconciliation and copies originals byte-for-byte with hashes. `live_lag_p95_s` stays null.

### Bind the separately supplied original audio

This workspace also contains `../Vangia_ASR_Selection_Codex_Package/TEST (3).zip`.
Although the initial package describes missing audio, all 100 original audio files, 100
reference source files and 100 converted canonical WAVs in this archive were verified against
the historical hashes. The historical import remains log-only; the separate binding is in
`runs/bound-legacy-audio/binding.json`. To reproduce it into a new directory:

```powershell
.\.venv\Scripts\python.exe -m pip install ".[audio]"
.\asrlab.bat bind-legacy-audio --archive "../Vangia_ASR_Selection_Codex_Package/TEST (3).zip" --json "../Vangia_ASR_Selection_Codex_Package/data/legacy/STT-EN(1).json" --out runs/bound-legacy-audio-new --consent-record-id YOUR-LOCAL-PROCESSING-RECORD
```

This creates `dataset/split-legacy_development.json`. Source identity does not establish
participant consent provenance, reference correctness or untouched validation. Unknown
speakers and sessions are conservatively grouped into one correlated cluster.

## Fixture, planning and scoring

```powershell
.\asrlab.bat run --config config/fixture.json
.\asrlab.bat run --config config/fixture.json --resume
.\asrlab.bat plan --matrix config/experiment_matrix.json --out runs/plan.json
.\asrlab.bat score --reference reference.jsonl --predictions predictions.jsonl --out scores.json
```

Fixture output is prominently `SYNTHETIC`: it exercises storage, events, scoring and reporting,
and performs no ASR. It is not usable accuracy evidence. JSONL scoring uses rows such as
`{"sample_id":"s1","text":"hello world","session_id":"session-1","domain":"classroom"}`.
Prediction IDs must match exactly. Explicit `status: "failed"` rows preserve missingness;
they do not silently become empty successful predictions. Empty verified references have
undefined WER and separate hallucination counts. Raw WER uses whitespace tokenization;
the legacy normalizer applies NFKC, casefolding and punctuation-to-space except apostrophes.
Numeric words are not silently equated to digits. Normalized CER excludes whitespace.

## Add consented audio and freeze splits

Edit `config/sample.example.json` with genuine consent and speaker/session metadata:

```powershell
.\asrlab.bat dataset-add --registry runs/datasets --sample config/sample.example.json
.\asrlab.bat dataset-lock --registry runs/datasets --split development
```

Input must be **mono 16 kHz PCM16 WAV**. Video is rejected. Convert external audio explicitly,
retain original hashes and record the preprocessing policy. Source recordings remain outside
the app by default. Split locks reject subsequent additions; corrections are separate
reference revisions and never alter locked manifests. Derivatives must retain the parent ID
and split. Legacy samples were used for selection and cannot become untouched holdout data.

## Optional real inference

Edit `config/batch.example.json` or `config/replay.example.json`. Required inputs:

1. A locked dataset manifest with real consent, references and WAV hashes.
2. Local weights for the exact checkpoint and backend.
3. A provenance JSON **outside the weights directory**, with `model_id`, immutable `revision`,
   and `files` mapping every relative artifact filename to its SHA256. Record converted-weight
   repository/revision and source checkpoint separately; an alias such as `turbo` proves neither.
4. Optional `worker_python` pointing to an isolated Python environment with that backend.

```powershell
.\.venv\Scripts\python.exe -m pip install ".[whisper]"
.\asrlab.bat preflight --config config/batch.example.json
.\asrlab.bat run --config config/batch.example.json
.\asrlab.bat run --config config/replay.example.json
.\asrlab.bat cancel runs/replay-small-en
```

Missing weights, WAV, consent or backend yields `BLOCKED` with reasons and no invented
predictions. `run` exits 3 for blocked/failed/cancelled, 2 for invalid input, 0 for completed.
Resume requires unchanged configuration, dataset, artifact identity and intact evidence.
Completed samples are skipped; attempts remain in the append-only attempt journal. Live
microphone sessions cannot resume: start a new session or replay the saved recording.

After an unexpected process crash with no terminal checksum seal, use explicit recovery:

```powershell
.\asrlab.bat recover runs/interrupted-job
.\asrlab.bat audit runs/interrupted-job
.\asrlab.bat run --config config/my-job.json --resume
```

Recovery checks immutable manifest/reference witnesses, preserves damaged originals,
reconstructs durable attempts, and marks the run failed until resumed. It cannot repair
altered immutable input or old runs without a manifest witness. A normally failed/cancelled
sealed run uses `--resume` directly. Live capture is never silently resumed.

The adapters implement faster-whisper, NeMo Parakeet/Canary, qwen-asr and opt-in English MMS
diagnostics. Configure `diagnostic_retry: true` for Qwen 1.7B or MMS; these are not promoted to
primary candidates. Do not mix incompatible ML dependencies into the core environment.
For NeMo/Qwen use a separately provisioned environment and `worker_python`. Linux/WSL2 may
be needed for particular packages/devices. This release has a local process transport, not
a transparent WSL/remote RPC bridge. Run the CLI in Linux with Linux paths when necessary.
Cross-process absolute clock subtraction is unavailable without calibration; worker service
durations are measured within the worker's own monotonic clock.

`trace-summary` derives queue dwell, host inference roundtrip, request-to-redraw proxy and
source-start-to-first-nonempty-emission distributions from an audited event journal:

```powershell
.\asrlab.bat trace-summary runs/real-replay-release --out runs/replay-trace-summary.json
```

Distributions include P50/P90/P95/P99/max, observed count, denominator, coverage and missing
endpoints. Host roundtrip includes transport; it differs from worker service time. Neither
emission nor redraw delay is word-to-visible-caption latency. Headless redraw coverage is
zero. New runs include these summaries in `metrics.json`. Resource samples cover the worker
process tree, including Windows venv launcher descendants. Summed RSS can count shared pages
twice, excludes the UI and does not measure GPU memory. CPU uses one core as 100%; initial
observations have no prior CPU interval.

Native stateful streaming is capability-blocked in this release. Independent chunk calls
are labeled adapted inference and are not renamed native streaming. Optional `vad` settings
`{"min_s":0.5,"max_s":3,"silence_s":0.3,"threshold":0.015}` select an explicitly labeled RMS
energy boundary heuristic for replay, with zero overlap. It preserves all audio including
silence. It is not Silero VAD. Fixed windows support overlap and explicit lexical prefix
deduplication; genuine repeated words at seams still need human review.

## Capture and human review

```powershell
.\.venv\Scripts\python.exe -m pip install ".[capture]"
.\asrlab.bat capture --out runs/consented.wav --seconds 10 --consent-record-id ACTUAL-RECORD-ID --device 1
```

Use `python -c "import sounddevice as sd; print(sd.query_devices())"` in the capture environment
to select a device. For online microphone captions edit `config/live.example.json`, provide
actual consent and explicit device, and run in the desktop. No microphone recording was made
during development. WASAPI loopback remains explicitly BLOCKED. There is no audio upload.

Select a prediction for full raw/normalized alignment, playback when original audio exists,
and reviewer annotation. Annotation categories cover terminology, numbers, units, negation,
omissions, chunk seams and silence hallucinations. Adjudicated labels require an adjudicator.
Sign-off records a human rationale and retains missing-evidence warnings.

Paired comparison accepts JSONL with `sample_id`, `session_id`, `pcm_sha256`,
`reference_revision`, `N` and `errors`. Use `compare --a A.jsonl --b B.jsonl`. It rejects
unpaired inputs and uses at least 2000 session-cluster bootstrap draws with a fixed seed.
The reported difference is **B minus A**. Small cluster counts are labeled unstable.
Completed real runs export `paired_scores.jsonl` with required identity fields. Pair runs on
the same audio/reference revisions; an unmatched or incomplete corpus is rejected.

### Holdout preregistration and participant responses

Freeze a genuinely new, speaker/session-disjoint holdout with `dataset-lock --split holdout`:

```powershell
.\asrlab.bat preregister --dataset runs/datasets/split-holdout.json --configs config/holdout.json --outcomes normalized_wer word_first_presented_lag_p95_s --owner REVIEWER-ID --out runs/registration.json
```

Set `dataset_manifest`, `dataset_split: "holdout"` and `preregistration` in the run config.
Registration freezes declared values and artifact-provenance contents, not merely paths.
Also archive code/environment and specify defaults for a formal study: source code and
installed backend packages are not locked by this registration.

Use `study-add --study runs/study --response response.json` and `study-report --study runs/study`
for consented responses. Each requires `response_id`, pseudonymous `participant_id`,
`consent_record_id`, `task_id`, `stimulus_run_id`, `stimulus_sha256`, `group`, `task_score` in
[0,1], and `readability_rating` plus `lag_annoyance_rating` on 1..5 scales. Summaries are
descriptive, not automatic evidence of effectiveness. No human responses were fabricated.

## Privacy, artifacts and troubleshooting

Run directories contain immutable `manifest.json`, state, events, predictions, references,
annotations, metrics, reports and checksums. Historical imports also contain original logs,
sample index and SQLite metadata. Reviews are append-only additions followed by resealing.
Hashes detect accidental edits; they are not cryptographic signatures against a malicious
actor able to rewrite the run. Keep evidence in a private user folder with Windows access
controls. The app opens no network listener and provides no multi-user authentication.

Use the redacted-summary export to omit transcripts, IDs, paths and reviewer identities.
Deleting a run does not delete external original recordings; erase those separately under
your retention policy. Do not distribute `runs/`, model caches or participant recordings.

If Tk says `init.tcl` is missing, verify Python was installed with Tcl/Tk. In this Codex
environment, sandbox restrictions also prevent Tk startup; the native Windows GUI smoke
test succeeds outside that sandbox. A backend timeout kills its worker and preserves stderr.
Windows symlink privilege issues and unavailable CUDA are reported failures, not WER results.

Run all desktop tests from a normal Windows terminal:

```powershell
$env:ASRLAB_TEST_UI='1'
.\.venv\Scripts\python.exe -m pytest -q
.\asrlab.bat ui --run-dir runs/historical --smoke
```

See copied normative research documents in `docs/`. Adapter API checks used the official
[faster-whisper repository](https://github.com/SYSTRAN/faster-whisper),
[Qwen3-ASR repository](https://github.com/QwenLM/Qwen3-ASR) and
[Canary model card](https://huggingface.co/nvidia/canary-1b-v2). Published performance numbers
are not transferred to this hardware.
