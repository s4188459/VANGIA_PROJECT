# STT Bench verification record

## English interface update - 2026-10-11

Interface labels, metric explanations, catalog notes, backend validation/errors and documentation now use English. Completed historical runs display English status labels; stored reports, user names, transcripts and dataset files are preserved. Vietnamese test fixtures remain to verify accent-sensitive scoring. Regression results for this update are recorded below after execution.

## Current backend verification - 2026-10-10

- Nine of nine backend imports passed; evidence: `data/backend-checks.json`. Package versions: `data/backend-environments`.
- Real checkpoint inference succeeded for all seven local backends: faster-whisper base/small, PhoWhisper tiny, Vietnamese wav2vec2 250h, Qwen3-ASR 0.6B, SenseVoiceSmall, Parakeet TDT 0.6B v2, and Vosk English/Vietnamese. Additional results: `data/backend-smoke`.
- NeMo 3.0.0 / Parakeet v2 succeeded on Windows CPU after missing snapshot metadata was downloaded.
- Ten configurations have cached weights. Other checkpoints download on demand; all 36 local catalog checkpoints have not been validated. The two cloud backends are installed but have not been tested with live accounts. No cloud audio uploads were made.
- Vietnamese checkpoint technical smoke tests used an English fixture with Vietnamese decoding. They do not establish Vietnamese recognition accuracy.
- Hardware: Ryzen 7 5800U, 8 cores/16 threads, about 14 GiB RAM, integrated AMD graphics, no CUDA. New weights use `data/hf-cache` on D; legacy caches remain readable offline. Official Vosk catalog aliases can download when permitted.
- Six-model HTTP smoke passed for base.en, small.en, Vosk small EN, Qwen3-ASR-0.6B, Parakeet TDT 0.6B v2 and SenseVoiceSmall: MP3 upload, preview, inference, WER/CER, sample CSV, summary CSV and JSON parity. Report: `data/smoke/http-14608a24d4da44bc964c9d21522dc7ad/runs/cc6d1aade51c423eb6305b4c3c147c89/run.json`. Synthetic speech verifies the pipeline, not model quality.
- Regression suite at that point: 32 Python and 5 JavaScript tests passed. No visual browser QA.

## Earlier verification and repaired defects

- Windows CRLF transcript hash mismatch: consistent newline normalization and UTF-8 storage, with separate original source hashes.
- Stale report responses overwriting the current report or reopening a cleared selection: request invalidation and selection checks.
- Viewing history enabling Run while another benchmark is active: background status tracked separately.
- Fractional/boolean beam/thread values and null model names accepted: strict type validation.
- Renamed English-only model folders bypassing language checks: inspect loaded model multilingual capability.
- Windows duplicate server binding: exclusive sockets where available, no address reuse, and bind before interrupted-run recovery. Regression confirms failed second startup does not alter saved run state.
- Regression tests reproduced these defects before their fixes.
- WER matched an independent recursive edit-distance oracle on 930 short sequence pairs, including repeated tokens and empty hypotheses. CER matched an independent oracle on 961 string pairs. These are tested cases, not proofs over all inputs.
- A synthetic 100-pair dataset through two fake adapters produced 200 results, 100 common samples and 200 CSV rows. This checks orchestration and persistence, not speech recognition.
- Audio tests encode/decode WAV, MP3, M4A, FLAC, OGG, OPUS, AAC and WebM, verify preserved originals/hashes and shared PCM16 mono 16 kHz output, reject duplicate IDs and invalid audio, and enforce decoded size/duration limits.
- Coverage includes unsafe ZIPs, missing/duplicate pairs, corrupt/truncated audio, empty/non-UTF-8 references, Vietnamese Unicode, corpus weighting, model load/decode failures, cancellation, concurrent-run prevention, restart recovery, HTTP upload/preview/exports, CSV formula escaping and input tampering.
- Multi-backend coverage includes catalog/language validation, cloud consent, preset defaults, common-sample comparisons, fixed-chunk tails, causal queue timing and cancellation.

### Historical real-model evidence

- Initial base.en/small.en synthetic WAV (~6.53 seconds): `data/smoke/state/runs/e9b3192c1c3244a2bca2c07cf1cd22a4/run.json`.
- HTTP WAV with multiline CRLF reference, preview, scoring and export parity: `data/smoke/http-67ecfe1f75fb4fd696c8b8468c139c69/runs/f19a820d5acb4a4a843a77cee46965d0/run.json`.
- MP3 normalization and original preservation: `data/smoke/http-9f08f28705c144a2a14b229409958296/runs/7aec36ec3e684418bf12fbf807f58b48/run.json`.
- Multi-backend metrics update, base.en/small.en HTTP: `data/smoke/http-bcc58c3718714f44a7342b3fb3425a47/runs/3cdf75ed62424df0bf6de18918f3244e/run.json`.
- Vosk 0.3.45 / small-en-us-0.15, isolated worker, whole-file and 3-second chunks: `data/smoke/multibackend-20261009`.
- PhoWhisper tiny returned text with Transformers 5.19.0 / Torch 2.14.1 CPU on canonicalized audio. A raw non-16k fixture was correctly rejected first.
- Earlier regression totals grew from 21 Python/3 JavaScript to 23/3, 26/3, 31/4 and finally 32/5. Current results take precedence.

## Remaining limits

No visual browser, file-picker or playback verification has been performed. HTTP and JavaScript harness tests do not substitute for these checks. No complete 100-recording user dataset evaluation, CUDA performance test, or live cloud account test has been performed. Checkpoint, OS and package compatibility must still be verified for configurations outside the recorded smoke tests. Workers support local Python environments, not automatic WSL execution.

WER distinguishes numeric spellings such as `20` and `twenty`; it measures normalized text differences, not semantic accuracy. Chunk replay simulates a queue and is not a native-streaming or application latency measurement. Not every audio codec/container variant is tested. Model loading/download/inference cannot be cancelled immediately; worker timeouts are 30 minutes for loading and 10 minutes per inference.

## Reproduce checks

From `stt-benchmark`:

```powershell
..\facial-cue-prototype\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/test_ui.cjs
node --check web/app.js
..\facial-cue-prototype\.venv\Scripts\python.exe -m compileall -q benchmark server.py
..\facial-cue-prototype\.venv\Scripts\python.exe tests/smoke_local_models.py --audio data/smoke/SMOKE001.wav
..\facial-cue-prototype\.venv\Scripts\python.exe tests/smoke_http.py --audio data/smoke/SMOKE001.mp3
```

English update verification: 32 Python tests and 5 JavaScript tests passed on 2026-10-11. JavaScript syntax and Python compilation passed. Restarted the idle server and verified HTTP 200, English HTML/catalog notes, 10 saved configurations, 38 catalog entries and 3 retained datasets. No visual browser verification was performed.
