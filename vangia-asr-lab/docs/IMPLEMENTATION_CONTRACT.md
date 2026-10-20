# Implementation Contract — required finished engineering output

## System design

`AudioSource (mic, WASAPI loopback, consented WAV, paced replay)` -> `SampleClock/Recorder` -> `SegmentScheduler(fixed|VAD)` -> `InferenceQueue` -> `BackendAdapter (NeMo, faster-whisper, Qwen)` -> `HypothesisMerger` -> `CaptionPresenter` -> `EventLogger` + `Scorer` + `DatasetRegistry` -> `Dashboard/Reports`. The final/offline path transcribes ORIGINAL recorded audio (not the live text) through separately identified job runners.

Use modular interfaces and avoid bundling all model families into one Python process; environment conflicts are likely. Model worker can be a separate Python env or WSL2/Linux endpoint; include clock offsets and worker unique IDs. All *actual* ASR workers are optional for the historical importer; no need to download 2–6GB weights just to start UI.

## Model adapter protocol

`discover() -> capabilities, backend_versions, required_hardware`; `load(checkpoint_id, revision, config) -> provenance`; `transcribe_file(input_audio, settings) -> timestamped hypothesis`; `transcribe_chunk(audio_window, state?)`; `begin_stream()/push_audio()/finish_stream()` only if supported; `unload()`; `health()`; `get_worker_telemetry()`. `capabilities` explicitly identify unsupported/untested streaming and output timestamps, not assume all Transducers stream natively. If model supports only batch mode, chunked calls are tagged as adapted independent inference.

`experiment_config_id` is SHA256 of a canonical manifest of checkpoint, weights, device, preprocess/resampler, backend/env, chunk/context/VAD, precision, decoding, normalized-score version and merge policy; revision must be immutable per run.

## Data and log contracts

- Immutable `manifest.json`: run, dataset/split hash, input format, acquisition mode, consent level, checkpoint/revision/weights hash, package versions, CPU/GPU and settings, normalization, source refs, time/capture clock, provisional gate version, random seed.
- Append-only `events.jsonl`, event schema in `schemas/event.schema.json`, monotonic capture ns and per-device sample indexes. Every chunk, inference attempt, raw hypothesis and merge version has consistent IDs. UI timing must distinguish requested update / paint-ack / actual presented (if instrumented).
- `reference.jsonl`: manually approved transcript, transcript original, segments and optional word positions in audio samples, quality/uncertainty and annotator. `predictions.jsonl`: source model result and merged/presented transcript with revisions.
- `resources.csv`: sampled per worker telemetry with time index, CPU/RSS/disk etc; missing instrumentation labeled.
- `annotations.jsonl`: reviewer spans, categories/severity with adjudication and source audio sample references.
- `metrics.json`: numerator, denominator, version, quality and measured/unmeasured status for every metric.
- `report.md`, optional `report.html/pdf` if simple; publication-specific bibliography URLs tied to claims; no source used to assert numerical acceptance standard if none exists.
- `checksums.json`, `IMPLEMENTATION_STATUS.md`, and complete error logs.

## Tests needed

**P0:** import full original JSON/CSV and show exactly 27 model configs / 25 succeeded / 2 errors, original 100 audio sample manifest and ~51.8656 min; WER 0.11285828 Parakeet v2, 0.1267914 Parakeet v3, 0.10071656 Qwen0.6, 0.09136146 Whisper large-v3, 0.151871 small.en, 0.15425955 small, 0.09812898 large-v2, 0.10151274 Canary v2, 0.10688694 turbo. Both failed models must have `WER=null` and reason. Treat `chunk_seconds` as non-live. List missing audio waveforms.

**Metric tests:** `WER` manual S/D/I, normalizer diff, empty ref/silence, micro vs macro, missing vs silent segment; equivalence of e.g. twenty-four/24 ONLY when declared and appropriate; `square centimeters` vs `cm` meaning error. Corpus repeated sample IDs or split leakage rejected. Paired bootstrap resamples session IDs not token IDs. Reference annotation metadata required for word lag.

**Time tests:** timestamp ordering, capture clock monotonic, corrected offsets/clock uncertainty across workers, UI paint proxy vs real displayed, delayed text vs first emit, omission with null latency not zero, rerender/edit regressions, negative or nonsensical durations rejected, stale queue age growth.

**Run tests:** actual speech recording only on permission/consent; synthetic fixtures named synthetic; deterministic paced replay measured in real elapsed time, not accelerated. Model install/timeout/permission failures emit fail and do not make up predictions. Corrupt output file recoverable with append-only journal. Different checkpoint version recorded as separate config, no extrapolated WER.

**Frontend smoke:** dashboards load with only historical inputs; all 9 primary/2 deferred entries visible; no fabricated live status; start run button blocked with actionable reason when absent audio/weights. Support resume/cancel/safe shutdown. Filter by candidate role, run mode, domain, dataset, hardware, VAD, chunk policy.

## Practical delivery order

1. Import baseline + integrity / CLI + initial UI + tests.
2. Storage, registry, experiment planning and immutable manifests.
3. Real backend adapters for existing platform; scoped optional worker runners for unsupported platform.
4. True recording and paced replay with timeline instrumentation.
5. Metric and human reviewer tools, comparison charts and reports.
6. Operational docs, regression tests and real run demonstration where input/hardware exists.

Provide `README` with exact Windows setup/run/test commands and troubleshooting for PySide6, NeMo, qwen/vLLM, faster-whisper/CT2, microphone and loopback. Keep privacy-first and no silent cloud usage. Document limitations rather than claiming missing features working. Prefer a complete P0/P1 plus tested P2/P3 over empty placeholders for 100 widgets; report incomplete phases truthfully.

