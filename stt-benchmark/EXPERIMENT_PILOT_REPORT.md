> HISTORICAL ONLY ? selection withdrawn on 2026-10-20. Recommendations and
> approvals below are obsolete. No replacement model is selected by this change.
> Measurements are retained as historical evidence; continue evaluation in Vangia ASR Lab.

# English experiment pilot verification

Verification date: 2026-10-15. Both experiments completed the first three samples
of dataset `ebd4f800c0b54227a84c40bbc7818019` (88.576 seconds of audio).
These are functional pilots, not the full 100-sample evaluation.

| Experiment | Run | Completed | WER | Selected timing result |
| --- | --- | ---: | ---: | --- |
| Qwen real-time replay | [JSON](data/runs/cec1f73bcb594a10861eecdfed2041fa/run.json) | 3/3 | 8.125% | First text from VAD onset: median 14.680 s, p95 15.757 s |
| Whisper offline | [JSON](data/runs/40b2d2c0dcbf44f5962d6102e5aca8ab/run.json) | 3/3 | 5.000% | Per-file completion: median 33.857 s, maximum 56.918 s |

Qwen's EOF finalization delay had median 7.885 s and maximum 9.707 s.
The current live configuration does not demonstrate the provisional 2–3-second
target. Its 12-second forced window and inference costs are relevant contributors;
this pilot is not a controlled attribution study. The timing is callback delivery,
not UI rendering, and speech-onset timestamps are VAD estimates.

Whisper's pilot was interrupted after two samples and resumed for the third.
The prior JSON was backed up; completed sample rows were retained. Its timings
therefore span two sessions and are not a controlled repeated-performance result.
Loading is separately recorded in `load_sessions`. At three samples, nearest-rank
p95 is the maximum and should not be generalized to a population.

Automated verification: 48 benchmark Python tests, 10 JavaScript UI/request tests,
and 239 desktop application tests passed. Coverage includes paced replay with EOF
draining, cancellation, timing aggregation, English-only validation, automatic model
selection, pilot limits, CSV fields, and backup-preserving resume.

Use [EXPERIMENTS.md](EXPERIMENTS.md) to run all samples. No full 100-sample results
are claimed by this report. Existing datasets and the original model-selection
benchmark were not replaced.
