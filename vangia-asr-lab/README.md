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

## Simple workflow

The app opens directly into three steps; no need to navigate the full laboratory.

1. **Input ZIP**: choose audio + matching TXT, enter your consent record ID, click
   **1. Check ZIP**, review the pairs, then **2. Use this dataset**.
2. **Models & Run**: choose **Offline group (6)** or **Live group (5)**. Click rows
   to add/remove models without Ctrl. Offline uses whole files; Live uses paced
   replay. Qwen 1.7B is included in Offline. Click **Check setup** and resolve any
   missing paths with **Configure model**, then **Start benchmark**.
3. **Results & Export**: watch automatic progress, select results to inspect samples,
   then **Export results**. WER is a ratio (`0.15 = 15%`). Errors remain explicit.

Only one repeat runs by default. Expand **Advanced run settings** for repeats,
chunk/overlap, seed, output folder and JSON configuration. Input pairing/storage
options and additional result analysis are also collapsed by default.
**Tools > Advanced laboratory** opens the original detailed tools when needed.
Cancellation is available in the always-visible progress area; **Resume saved
benchmark** continues unchanged data/configuration.

On this workstation Qwen 1.7B already has local weights, provenance and a worker
Python configured and passes preflight. On a new machine these assets/environments
must be copied or installed and their paths reconfigured; Git does not carry them.
`Check setup` verifies prerequisites, not model quality or successful inference.

CLI help: `.\asrlab.bat --help`. Local `runs/`, weights, environments and recordings
are excluded from Git. Each repeat loads a fresh model; no warm-worker guarantee.
Paced replay and UI paint proxies are not real microphone-to-display latency.
