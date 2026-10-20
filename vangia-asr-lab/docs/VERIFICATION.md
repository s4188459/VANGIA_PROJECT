# Local verification record — 2026-10-16

Commands run from `vangia-asr-lab` under Python 3.12. No model weights or audio are included
in the distributable wheel.

## Automated tests

```powershell
$env:ASRLAB_TEST_UI='1'
.\.venv\Scripts\python.exe -m pytest -q --basetemp .verification-final-paired-20261016 -p no:cacheprovider
```

Result: **64 passed in 34.65 s**. Native Tk tests ran outside the Codex sandbox, which prevents
Tcl/Tk initialization on this machine. Normal headless testing skips the opt-in GUI test.
PyAV was installed, so the full archive conversion test executed.

Independent review found session mixing, missing explicit crash recovery, provenance frozen
by path only, inline holdout relabeling and incompatible paired exports. Each received a
failing regression test followed by a fix. Runtime inspection also found launcher-only
resource sampling; an actual parent/child process test verifies memory accounting and
termination. Trace tests cover absent acknowledgments, different attempts/clocks and first
nonempty emission per session.
The final paired-export regression retains failed rows even when both configurations fail
on the same sample. The final change affects export handling only; the real release replay
below was captured immediately before it and has no failed samples.

## Original evidence/audio

`runs/historical` includes original JSON/CSV copies, indexes, reports and hashes. Totals:
100 samples, 27 configurations, 25 completed, 2 failed; historical live lag null.

`runs/bound-legacy-audio/binding.json` records:

- Original audio: 100/100 hashes match.
- Reference source files: 100/100 hashes match.
- Canonical mono 16 kHz PCM16 WAV: 100/100 hashes match.
- Archive SHA256: `c6abed0f012f89be3591c7a841285027dfaab57975d989ca13d928d6ba279bd5`.
- Legacy JSON SHA256: `497b10681b1ae89acb7bb1db20401667227c68fea03eb706b4783d7790514351`.
- Decoder PyAV 19.0.1; locked split `legacy_development`.

Archive: `../Vangia_ASR_Selection_Codex_Package/TEST (3).zip`. Identity parity does not establish
participant consent provenance or reference correctness.

## Real model smoke runs

The existing `../facial-cue-prototype/models/faster-whisper-small-en` converted artifact and
its existing worker environment were reused. Backend faster-whisper 1.2.1, CPU/int8, four
threads, beam 5, VAD false. Complete hashes: `runs/local-small-en.provenance.json`.

Converted revision: `d1d751a5f8271d482d14ca55d9e2deeebbae577f`.
`model.bin` SHA256: `62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a`.
The upstream OpenAI weight revision remains unknown.

| Run | Observed input/outcome | Interpretation |
|---|---|---|
| `runs/fixture` | Deterministic SYNTHETIC transcript plumbing | No ASR evidence |
| `runs/decoder-diagnostic` | Real decoder; generated one-second silence; one output word | SYNTHETIC diagnostic, not speech WER; hallucination retained |
| `runs/real-batch-smoke` | EN001–EN003; N=160, S=9/D=1/I=1; normalized WER 0.06875; RTF about 0.288 | Three legacy files; no population claim; old resource telemetry invalid |
| `runs/real-replay-smoke` | EN001 paced, independent overlapping two-second calls | Old global backlog calculation superseded; original evidence preserved |
| `runs/real-replay-verified` | EN001 completed; inference RTF 1.9982; acquisition-only backlog growth | Corrected backlog; old launcher-only resources invalid |
| `runs/real-replay-release` | EN001; WER 0.428571; inference RTF 1.965879; 53.388 s worker service; 59.094 s turnaround; peak summed RSS 739282944 bytes | Process-tree telemetry, 469 samples; P95 queue dwell 24.43915 s; redraw coverage zero |

Speech runs preserve manifest, configuration/artifact identities, references, predictions,
events, resources, reports and checksum seals. They ran headlessly: no redraw acknowledgment
or physical display was measured. Word-to-visible-caption lag is null. EN001 lasts about 27
seconds and is insufficient for long-session reliability conclusions.

```powershell
.\asrlab.bat run --config runs/real-replay-release-config.json
.\asrlab.bat audit runs/real-replay-release
.\asrlab.bat trace-summary runs/real-replay-release --out runs/replay-trace-summary.json
```

The release run was already executed. To repeat, copy its config and choose a new `out`
directory. A completed run is not overwritten; resume requires identical config/input.

## Distribution

```powershell
.\.venv\Scripts\python.exe -m pip wheel . --no-deps --no-build-isolation --no-cache-dir --wheel-dir dist
```

The final verification JSON records source hashes, run audits and packaging smoke results.
The wheel bundles all three normative schemas and registry/config JSON. An isolated-target
installation checks that bundled resources work without source-tree paths. The workspace
retains source, tests, launchers and documentation separately.
See [machine-readable verification](verification-results.json). The source ZIP includes
source/tests/docs/launchers; full historical tests still require the original normative
package next to the extracted application. The ZIP excludes environments, runs and recordings.
