> HISTORICAL ONLY ? selection withdrawn on 2026-10-20. Recommendations and
> approvals below are obsolete. No replacement model is selected by this change.
> Measurements are retained as historical evidence; continue evaluation in Vangia ASR Lab.

# Provisional STT candidates for the next evaluation

## Status: shortlist only, no final selection

Earlier Parakeet-live / Whisper-large-v3-final assignments were provisional. The available dataset and single whole-file run are insufficient for a final deployment decision.

The next tool will screen candidate configurations before deployment. Parakeet v2 and Whisper large-v3 remain candidates, not confirmed winners. The decision to use two different models is also open.

## Available evidence

The supplied English CSV and JSON cover 100 samples, 51.87 minutes, and 25 successful configurations out of 27. Results use whole-file inference. This is preliminary evidence from the provided recording distribution, not a broad or repeated live benchmark. The number of samples alone does not establish representative coverage.

Sources: Testing_STT_Model_English_Version.csv and STT-EN.json. Run ID: `e634c257ef69434383d580442820821e`.

## Live transcription candidates

Order below is for presentation, not a final ranking. All numbers are observed English whole-file results.

| Candidate | WER | CER | RTF | Why retain it |
| --- | ---: | ---: | ---: | --- |
| parakeet-tdt-0.6b-v2 | 11.29% | 5.84% | 0.253 | Strong preliminary speed/accuracy tradeoff; test actual live latency. |
| parakeet-tdt-0.6b-v3 [catalog] | 12.68% | 5.90% | 0.266 | Nearby alternative; one run is insufficient to exclude it. |
| Qwen3-ASR-0.6B | 10.07% | 4.55% | 0.742 | Lower offline WER; check whether live latency remains acceptable. |
| small.en | 15.19% | 7.69% | 0.200 | Boundary candidate: WER 15.19% exceeds the provisional 15% threshold; not currently a passing configuration. |
| small [catalog] | 15.43% | 7.75% | 0.275 | Boundary candidate: WER 15.43%; retain to compare the multilingual checkpoint, with Vietnamese evaluation still required. |

## Final transcript candidates

Order below is for presentation, not a final ranking. All numbers are observed English whole-file results.

| Candidate | WER | CER | RTF | Why retain it |
| --- | ---: | ---: | ---: | --- |
| large-v3 [catalog] | 9.14% | 4.56% | 1.424 | Lowest observed WER; test robustness on more speakers and conditions. |
| large-v2 [catalog] | 9.81% | 5.20% | 1.507 | Close accuracy baseline; verify whether the v3 advantage persists. |
| Qwen3-ASR-0.6B | 10.07% | 4.55% | 0.742 | Competitive WER and lowest observed CER; potential single-model solution. |
| canary-1b-v2 [catalog] | 10.15% | 4.89% | 1.069 | Close WER alternative for independent comparison. |
| turbo [catalog] | 10.69% | 5.21% | 1.005 | Whisper-family speed/accuracy alternative; repeat with the target deployment. |

The provisional live target is corpus WER <= 15%. small.en and small are deliberately included as boundary candidates despite exceeding that target in the current run. Their inclusion does not mean the threshold has been relaxed. Offline RTF does not prove low live latency.

## Optional retries after environment repair

- Qwen3-ASR-1.7B: the supplied run failed with a Windows privilege/symlink error. Recognition quality remains unknown.
- MMS-1B-all: the supplied run failed with a backend timeout. Recognition quality remains unknown.

These are unmeasured retry candidates, not ranked alternatives. The shortlist is intentionally smaller than the full catalog; omission does not prove another model is unsuitable.

## What the new tool should establish

1. Treat model + backend + precision + decoder + hardware as a configuration; snapshot each run.
2. Evaluate actual live capture-to-caption P50/P95, time to first text, finalization delay, queue growth, transcript revisions and dropouts. Label fixed-chunk simulation separately.
3. For final transcripts, measure corpus WER/CER, sample failure coverage, technical terms, numbers, omissions and silence hallucinations.
4. Add more speakers, accents, recording conditions, noise, long sessions and interruptions; review references against audio. Record speaker and recording-session IDs.
5. Use speaker/session-separated development and held-out evaluation sets. Do not tune and declare a winner on the same 100 examples.
6. Repeat timing runs, separate loading from inference, record peak memory and variability. Where available use paired sample/speaker-aware uncertainty estimates for accuracy.
7. Evaluate English and Vietnamese separately; these English results do not establish language eligibility or quality for Vietnamese.
8. Compare one-model and two-model workflows; select two models only if the final quality gain justifies the extra cost.
9. Do not score failed model loading as bad recognition or zero error; retry environment failures separately.

## How to reach a final decision

For live use, first verify the agreed accuracy threshold, then compare actual live latency and stability under the target workload. For the final transcript, compare accuracy and failure cases against total processing cost. Repeat across representative data and report uncertainty. A single model may satisfy both tasks.

Configurations in the existing test used different backends, precision and VAD settings. Preserve those differences in the report and avoid attributing every difference to model architecture. The current run was resumed twice, so its loading times are not standardized cold-start measurements.

The global common-sample count is zero because two configurations failed. Each shortlisted successful configuration completed 100 samples, but future partial failures must be compared on matching successful samples while reporting coverage.

Vietnamese is a separate evaluation track. Do not assume every English-shortlisted checkpoint supports it. No Vietnamese winner is identified here.

## Related records

- [Structured shortlist](english_model_decision.json)
- [Earlier Qwen/Whisper comparison](qwen_whisper_selection_rationale.md): retained as historical evidence, not the current selection decision.
