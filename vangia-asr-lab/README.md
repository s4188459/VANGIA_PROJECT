# Vangia ASR Lab ? focused evaluation tool

**The focused model evaluation is not finished.** Read the STT documentation in order:

1. [Preliminary results: all 27 configurations](../docs/stt/01-preliminary-results.md)
2. [Candidate shortlist](../docs/stt/02-candidate-shortlist.md)
3. [Focused testing introduction](../docs/stt/03-focused-testing-introduction.md)

## Setup and continue on Windows

Install Python 3.12 with Tcl/Tk, then run:

```powershell
cd vangia-asr-lab
.\setup-windows.ps1
.\launch-asrlab.bat
```

Setup creates `.venv`, installs dependencies and runs software tests. Model weights
and optional backend environments must be provisioned separately. Update local
model paths and worker Python paths for the current machine; example paths from
the old workstation are not portable.

## Benchmark workflow

1. Choose **New benchmark (ZIP)**. Inspect audio and UTF-8 TXT pairings, or supply
   metadata using `config/metadata.example.csv`.
2. Review pairings/references, enter the actual local consent record ID, and import
   into a new dataset folder.
3. Select and configure candidates. **Check prerequisites** reports setup status,
   not a model-quality result.
4. Select `batch_file` or `paced_replay`, repeats and chunk settings. Start the
   benchmark. Cancellation preserves completed work; resume requires unchanged
   data and configuration. Each repeat loads a fresh model; this is not a warm-worker test.
5. Review samples and export an analysis bundle. WER/CER are ratios (`0.15 = 15%`).
   Failures and missing results remain explicit; exports do not declare a winner.

CLI help: `.\asrlab.bat --help`. Configuration templates are in `config/`.
Local `runs/`, environments, model weights and recordings are excluded from Git;
copy needed inputs/results separately when moving machines. Exports may contain
reference/hypothesis text and metadata. UI paint proxies are not physical display
measurements. Historical data is development evidence, not held-out confirmation.
