# STT Bench ? preliminary screening tool

STT evaluation documentation has exactly three stages:

1. [Complete preliminary results](../docs/stt/01-preliminary-results.md)
2. [Candidates for focused testing](../docs/stt/02-candidate-shortlist.md)
3. [Focused testing introduction ? unfinished](../docs/stt/03-focused-testing-introduction.md)

## Run the old tool

```powershell
cd stt-benchmark
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.ps1
```

Open http://127.0.0.1:8766. Configure backend environments and local model paths
for this machine. Import a ZIP with matching audio/TXT references, review them,
select model configurations explicitly and run the comparison. Export summary
CSV, per-sample CSV or JSON. `install-backend.ps1` installs optional backends.
Existing data lives in `data/`, which Git excludes. Historical experiment code
remains for reproducibility; it does not define an approved model pair.
