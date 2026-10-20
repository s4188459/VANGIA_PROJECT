# STT Bench

A tool for importing audio datasets, configuring speech recognition models, and comparing benchmark metrics. General benchmark modes support manual model selection. The previous Qwen/Whisper selection was withdrawn on 2026-10-20. Its automatic experiment shortcuts have been removed from the web UI. Legacy experiment code remains for reproducing historical runs, not as an approved model choice. Continue model selection in `../vangia-asr-lab/`.

See [English experiments 2 and 3](EXPERIMENTS.md) for timing definitions, pilot/full runs, CSV exports and limitations. Select **Select models manually** under scope, choose an experiment under **Audio input protocol**, then select **Pilot: first 3 samples** or **All samples**. You do not need to check a model for these two experiment modes.

## Start the tool

From the VANGIA_PROJECT workspace in PowerShell:

```powershell
.\stt-benchmark\start.ps1
```

Open http://127.0.0.1:8766. The launcher prefers the tool's `.venv`, then the existing application environment. You can also run:

```powershell
.\facial-cue-prototype\.venv\Scripts\python.exe .\stt-benchmark\server.py
```

Stop with Ctrl+C. Interrupted runs retain saved sample results and are marked on restart. Select the interrupted run in history and click **Resume interrupted run** to continue with its original dataset, configurations and options. Saved samples (including recorded errors) are retained; only missing samples run, and a sample interrupted before saving is processed again. The tool checks dataset hashes and creates an exact `run.before-resume-<id>.json` backup beside the report before resuming. Changed or missing data blocks resumption; only one run can be active. Keep model weights and Python environments unchanged for comparable measurements across restarts.

To create a separate server environment with Python 3.10+:

```powershell
cd stt-benchmark
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.ps1
```

## Prepare a dataset

Upload a ZIP containing audio and matching UTF-8 reference transcripts:

```text
english_pilot.zip
  audio/EN001.mp3
  audio/EN002.m4a
  transcripts/EN001.txt
  transcripts/EN002.txt
```

- Accepts 1-1,000 pairs. Matching IDs are case-sensitive and must be unique across directories. EN001.mp3 and EN001.wav in the same ZIP are duplicates.
- Audio formats: WAV, MP3, M4A, FLAC, OGG, OPUS, AAC, WebM. Formats may be mixed. Each file must decode successfully and contain exactly one audio stream; not every codec/container variant is guaranteed.
- Limits: 512 MB per ZIP, 1 GB declared expanded size, 128 MB per source audio file, 10 minutes per decoded sample, and 1 GB total normalized audio.
- Originals are preserved in `originals/`. Import decodes, downmixes and resamples once into PCM16 mono 16 kHz WAV in `audio/`. All models receive the same normalized file. There is no denoising, automatic gain adjustment or speaker separation.
- Source and normalized hashes, source properties and audio-processing versions are saved. Conversion cannot restore information lost by MP3 compression. Import conversion time is excluded from model RTF.
- TXT files must contain the speech actually recorded. Omit speaker labels unless they are spoken. Listen to each recording and correct its reference before evaluation; an unchecked AI script is not ground truth.
- Import copies files to `data/datasets/<id>`. To change references, edit your source and import a new dataset version. Previously imported datasets are not rewritten.
- The prepared English scripts are in `../datasets/stt_english_ai70_general30_v1/conversations.md`. Start with a small reviewed pilot before recording all 100.

## Select models and run

1. Select a dataset and review its audio and references.
2. Choose **Benchmark scope**: manual selection, all compatible saved configurations, or all compatible catalog models plus saved configurations.
3. Review the planned configurations and skipped entries. Enable weight downloads if needed. Confirm that references have been reviewed, then select **Run evaluation**.
4. Export **Summary CSV** for one row per model, **Sample CSV** for sample details, or the full JSON report.

The catalog contains 38 presets across nine backends: Whisper, Distil-Whisper, PhoWhisper, Qwen3-ASR, Parakeet, Canary, SenseVoice, wav2vec2, MMS, Vosk and ElevenLabs/Google APIs. Catalog membership does not mean that weights are installed or that a checkpoint has been tested on this machine.

Batch selection filters by dataset language and prefers matching saved configurations. New catalog presets use CPU INT8 for faster-whisper and CPU float32 otherwise. Saved configurations retain their settings. Up to 50 configurations run sequentially; a model failure is recorded and the next model continues. Missing backends, recorded import failures and unconfigured/unauthorized cloud services are listed as skipped. Missing weights fail unless downloads are enabled. Dependencies and cloud permissions are never enabled automatically.

To customize a model, choose a catalog entry, click **Use this preset**, review the backend, Python executable, device, languages and model path, then **Save configuration**. English-only `.en` models cannot evaluate Vietnamese datasets. Use a compatible multilingual or Vietnamese checkpoint. Local paths must match the selected backend's model format. CUDA requires a suitable GPU environment.

On initial setup the tool detects existing base.en/small.en directories in the application without copying their weights. New Hugging Face downloads use `data/hf-cache`; legacy cached weights can still be read offline. Official Vosk aliases download and extract into `data/model-cache` when downloads are permitted, or you can provide an extracted model directory.

## Backend environments

Install individual backends from the workspace:

```powershell
.\stt-benchmark\install-backend.ps1 -Backend transformers-whisper
.\stt-benchmark\install-backend.ps1 -Backend vosk
.\facial-cue-prototype\.venv\Scripts\python.exe .\stt-benchmark\check-backends.py
```

Backend keys: `faster-whisper`, `transformers-whisper`, `transformers-ctc`, `qwen-asr`, `nemo`, `sensevoice`, `vosk`, `elevenlabs`, `google-chirp`.

The installer creates `.backends/<backend>`. Refresh the page and reselect a preset to fill its Python path, or provide your own local interpreter. Workers run on the same OS; automatic WSL/remote execution is not supported. Import results are stored in `data/backend-checks.json`, package versions in `data/backend-environments`, and checkpoint smoke results in `data/backend-smoke`.

The tested machine uses a Ryzen 7 5800U (8 cores/16 threads), about 14 GiB RAM and integrated AMD graphics, without CUDA. Each local backend has a successful checkpoint smoke test, but not all catalog checkpoints have been validated. An import check does not prove sufficient memory or acceptable performance. See QA_REPORT.md for evidence and limits.

## Metrics and measurement protocol

- WER = (substitutions + deletions + insertions) / reference tokens. Corpus WER divides total errors by total reference tokens; it can exceed 100%.
- Normalization uses NFKC, case folding and punctuation-to-space, while retaining apostrophes and Vietnamese accents. Numeric spellings are not unified: `20` and `twenty` can count as different words. Vietnamese WER uses whitespace-separated tokens, approximately syllables, rather than linguistic word segmentation.
- CER uses the same normalization, removes whitespace, and divides total character errors by total reference characters.
- Per-model scores include successful samples only. Common scores use the intersection of samples successful across every model. Check failure counts and coverage before comparing. If one model fails every sample, common scores can be unavailable; blank does not mean zero errors.
- RTF = total successful inference time / corresponding audio duration. Inference includes audio decoding, VAD when enabled, consuming output generators, and worker IPC. API timing includes upload and provider response time. Loading, input hashing, scoring and import conversion are excluded. There is no separate warm-up; the first sample may be slower.
- Whole-file mode passes the complete audio to the adapter. Transformers and SenseVoice split long audio into blocks of at most 30 seconds without overlap; boundaries can affect accuracy. CTC uses greedy decoding without an external language model. Whisper beam size is configurable; other backends use their default decoder.
- Sequential-chunk mode decodes independent fixed 1-15 second chunks without overlap or cross-chunk context. A simulated single-worker queue uses `emitted_at = max(chunk_end, previous_emitted_at) + processing_time`, without sleeping in real time. Reports include nearest-rank P95 chunk processing time, lag after chunk end, first nonempty result time, and chunks slower than their audio duration. These are not native-streaming or microphone measurements.
- Main timing/P95 columns use each model's successful samples. JSON also contains `common_summary`. Compare matching dataset versions, languages and protocols. RAM/VRAM and API costs are not measured.

References are used only for scoring and are never sent to model workers. Reports snapshot configurations, protocol, environment/dependency versions, dataset hashes, references and predictions. Remote revisions are not pinned and full weight files are not hashed; use an immutable local model directory for stricter reproducibility.

Results are saved after each sample in `data/runs/<id>/run.json`. Cancellation is checked between samples/chunks and cannot immediately interrupt loading, downloading or inference. Worker timeouts are 30 minutes for loading and 10 minutes per inference.

## Optional cloud services

ElevenLabs requires `ELEVENLABS_API_KEY`. Google requires Application Default Credentials, `GOOGLE_CLOUD_PROJECT` and a suitable `GOOGLE_CLOUD_LOCATION`. The Google adapter uses synchronous Recognize and limits samples to 60 seconds. Set credentials before starting the server; keys are not entered in model configurations or saved in reports. Audio is uploaded only when a cloud model is selected and cloud consent is checked. Charges may apply. Cloud packages have been imported, but live account requests have not been validated.

## Extend and verify

An adapter implements `load()`, `transcribe(audio_path, language)` and `close()`. Transcription returns `{"text": "...", "segments": [...]}` without receiving a reference. Register it in `ADAPTERS` and add backend configuration validation/UI support; dataset import, scoring and persistence remain shared.

From `stt-benchmark`, using a Python environment with the tool dependencies:

```powershell
..\facial-cue-prototype\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/test_ui.cjs
node --check web/app.js
..\facial-cue-prototype\.venv\Scripts\python.exe tests/smoke_http.py --audio data/smoke/SMOKE001.mp3
```

Regression tests use temporary datasets and explicitly fake adapters to check scoring, validation, persistence and HTTP behavior. Real checkpoint smoke tests are documented separately. JavaScript tests use a minimal DOM/network harness and do not replace visual browser checks.


## Vietnamese-English candidate sets

Choose **Vietnamese / Vietnamese with English terms** when importing reviewed mixed-language audio. Preserve spoken English terms in the reference transcripts. These candidate lists are not claims of measured Vietnamese-English accuracy.

In **Benchmark scope**, select:

- **Vietnamese-English ? Video (5 candidates)**: Whisper large-v3, large-v2, Qwen3-ASR-1.7B, Qwen3-ASR-0.6B, PhoWhisper-large. The input protocol is whole file.
- **Vietnamese-English ? Live (5 candidates)**: multilingual Whisper small, medium, Qwen3-ASR-0.6B, PhoWhisper-small, and Fun-ASR-MLT-Nano-2512. Run once with 1-second chunks, then start a separate run with 2-second chunks. This is independent-chunk simulation, not native streaming or microphone-to-screen latency.

Each set uses one CPU baseline per candidate: 4 threads, INT8 with beam 5 and VAD for faster-whisper; float32 for other backends, beam 5 for Transformers Whisper and default decoding elsewhere. Saved configurations are deliberately not substituted. For custom settings or local checkpoint paths, use manual selection instead. Download permission starts off and is controlled by the existing checkbox.

The plan lists cache hints and skipped backends. A detected cache is not proof of complete weights; loading validates the actual model. A missing cache may require downloading several GB. Missing backends are skipped, so check that all five candidates are included before making a five-model comparison.

The new `fun-asr-mlt` backend uses the installed FunASR implementation, not downloaded Python code. It prefers `.backends/fun-asr-mlt` and can reuse `.backends/sensevoice` if present. To install a separate environment:

```powershell
.\stt-benchmark\install-backend.ps1 -Backend fun-asr-mlt
```

Use the exact checkpoint `FunAudioLLM/Fun-ASR-MLT-Nano-2512`, not the non-MLT Nano checkpoint. Its snapshot must include `Qwen3-0.6B/config.json`. This adapter uses float32, Vietnamese/English language prompts, deterministic decoding without ITN, and 30-second blocks for long files. Live simulation supplies shorter chunks. Its real checkpoint accuracy, memory use, and CPU latency still need measurement; registration and import checks are not inference validation.

Existing datasets, configurations, and run reports are not migrated or rewritten by selecting these sets. New evaluations create new run IDs; interrupted-run resume remains available.
