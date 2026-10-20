# 3. Focused STT testing ? new tool

**Status: in progress; testing is not complete. No final results or model winner
are reported here.**

`vangia-asr-lab/` is the new tool for evaluating the shortlisted candidates under
more specific conditions. This stage will examine offline transcript quality
and turnaround, plus live-pipeline quality, delivery delay and backlog under
paced audio input. Paced replay must be labeled separately from a live microphone
session and from native streaming.

Candidates will be compared on matched audio and reviewed references, with model
identity, configuration, hardware, input hashes and failures recorded. Planned
measurements include WER/CER, completion coverage, loading/inference time, resource
use and clearly defined latency intervals. Missing timing measurements must remain
missing. Development data used for tuning must be distinguished from held-out
confirmation data.

Existing tool checks, synthetic fixtures and small smoke runs verify software
behavior only. They do not complete this model evaluation and are not presented
as new model results. Once the focused tests are complete, their measured results
and limitations will be added here before making a final selection.

See the [new tool setup](../../vangia-asr-lab/README.md) to continue the work.
