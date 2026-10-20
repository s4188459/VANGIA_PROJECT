# Machine handoff ? 2026-10-20

Model selection is pending. Previous model recommendations are withdrawn.
Continue evaluation in `vangia-asr-lab/`; see its README and the three documents in `docs/stt/`.
The old web benchmark remains available for explicit model comparisons. Historical
experiment implementations and reports are retained only for reproducibility.
The facial collector uses its earlier prototype defaults, not a newly selected model.

## New Windows machine

1. Clone/pull this repository and install Python 3.12.
2. Run `vangia-asr-lab/setup-windows.ps1` to create its environment and run tests.
3. Start `vangia-asr-lab/launch-asrlab.bat`.
4. Configure model paths and worker Python paths for the new machine; existing
   absolute paths in example configurations describe the original workstation.

Git does not transfer model weights, virtual environments, recordings, local run
folders, benchmark data/cache, backups, or the original TEST (3).zip input archive.
Copy any needed data separately before leaving the old machine. Source code,
configuration templates, tests, preliminary evidence and the three STT documents are
included. No new model has been approved by this handoff.
