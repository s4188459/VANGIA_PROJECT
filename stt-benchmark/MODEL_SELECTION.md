> HISTORICAL ONLY ? selection withdrawn on 2026-10-20. Recommendations and
> approvals below are obsolete. No replacement model is selected by this change.
> Measurements are retained as historical evidence; continue evaluation in Vangia ASR Lab.

﻿# Model Selection for English Video and Live Transcription

Analysis date: October 13, 2026.

## Requirements and recommendations

- **Video input:** prioritize the accuracy of the final transcript.
- **Live transcription:** English, with a target latency of approximately 2–3 seconds. The quality target is WER no higher than 15%, with WER no higher than 20% as the minimum acceptable quality level.

| Purpose | Recommendation | Status |
| --- | --- | --- |
| Video transcription | **Whisper large-v3 via faster-whisper** | Lowest WER among models that completed the current benchmark successfully |
| Live transcription | **Parakeet-TDT-0.6B-v2** | Preferred candidate; live testing is required before confirming that it meets the requirements |
| Live fallback | **Whisper small.en via faster-whisper** | Faster than Parakeet in whole-file testing, but its quality is close to the acceptance threshold |
| Video transcription with a shorter wait | **Qwen3-ASR-0.6B** | Alternative that balances speed and quality |

## Data sources and scope

This analysis is based on run `e634c257ef69434383d580442820821e`:

- [JSON report and per-sample results](data/runs/e634c257ef69434383d580442820821e/run.json).
- User-provided CSV: `C:/Users/LENOVO/Downloads/e634c257ef69434383d580442820821e-summary.csv`.
- Dataset: **100 English samples**, totaling **3,111.94 seconds**, or **51.87 minutes**.
- Evaluation mode: `final`, using the `full-file-v1` protocol for whole-file recognition.
- The compared configurations run on **CPU**, configured with 4 threads. Faster-whisper uses INT8, beam size 5, and VAD; Parakeet and Qwen use float32 through separate backend environments.
- The run was interrupted and later resumed, so the final results combine multiple execution sessions. Timing reflects this benchmark run rather than repeated measurements under controlled machine load.

Every model in the table below successfully processed the same 100 samples. Two other models, Qwen3-ASR-1.7B and MMS-1B, failed on all samples and therefore provide insufficient evidence for assessing transcription quality. The `common_sample_count` column is 0 because it computes the intersection across all models, including failed models. This does not prevent comparison among models that successfully processed all 100 samples.

## Interpreting the metrics

- **WER** = (word substitutions + deletions + insertions) / reference word count. Lower is better.
- **100% − WER** is only a convenient conversion for comparison with the requested 80–85% target. It is not the probability that an individual word is correct, the percentage of entirely correct sentences, or a measure of semantic accuracy.
- **RTF** = inference time / audio duration. An RTF below 1 means total processing time is shorter than the audio duration in the measured mode.
- Aggregate WER is calculated from total word counts, rather than the arithmetic mean of the 100 sample WER values. The aggregate score does not guarantee that every sample meets the threshold.
- Estimated processing time for one hour of audio = `RTF × 60 minutes`. This excludes model loading, audio extraction from video, subtitle export, and other processing steps. It is not a runtime guarantee for every video.

## Key results

| Model | WER ↓ | 100% − WER ↑ | RTF ↓ | Estimated inference time for 1 hour of audio |
| --- | ---: | ---: | ---: | ---: |
| **Whisper large-v3** | **9.14%** | **90.86%** | 1.424 | 85.4 minutes |
| Whisper large-v2 | 9.81% | 90.19% | 1.507 | 90.4 minutes |
| **Qwen3-ASR-0.6B** | **10.07%** | **89.93%** | 0.742 | 44.5 minutes |
| Whisper turbo | 10.69% | 89.31% | 1.005 | 60.3 minutes |
| **Parakeet-TDT-0.6B-v2** | **11.29%** | **88.71%** | **0.253** | **15.2 minutes** |
| Parakeet-TDT-0.6B-v3 | 12.68% | 87.32% | 0.266 | 15.9 minutes |
| **Whisper small.en** | **15.19%** | **84.81%** | **0.200** | **12.0 minutes** |
| Whisper base.en | 22.15% | 77.85% | 0.066 | 4.0 minutes |

## Why choose large-v3 for video?

`large-v3` has the lowest WER among models that completed successfully, making it suitable when final transcript quality matters more than waiting time. In this benchmark, it was both more accurate and faster than `large-v2`.

The main tradeoff is CPU speed: its RTF is approximately 1.424, meaning processing takes longer than the audio itself. If waiting approximately 85 minutes of inference for a one-hour video is too long, **Qwen3-ASR-0.6B** offers a balanced alternative: its WER is approximately **0.94 percentage points** higher than large-v3, while its inference time is roughly half as long.

This recommendation is based on the available dataset. It does not establish that large-v3 is always best across all accents, noise conditions, or topics. The benchmark does not separately assess subtitle timestamp accuracy, punctuation, or speaker diarization. Its WER scores should not be used to guarantee those capabilities.

## Why prioritize Parakeet v2 for live transcription?

Parakeet v2 offers the best balance of quality and speed among the candidates considered:

- WER of **11.29%**, leaving a margin below the 15% WER target.
- RTF of **0.253**, equivalent to processing approximately **3.95 times faster than real time** in whole-file testing.
- Compared with small.en, its WER is approximately **3.90 percentage points** lower, at the cost of approximately 27% more inference time.
- On this English dataset, v2 has lower WER and is faster than v3. These results provide no reason to prefer v3.

`small.en` is a useful comparison baseline and fallback because it is faster, but its converted score of 84.81% is already close to the threshold. If 85% is a strict requirement, even its whole-file result falls short. `base.en` is fast, but its WER of 22.15% exceeds the proposed maximum of 20%.

Qwen3-ASR-0.6B offers good quality, but its RTF of 0.742 leaves less processing capacity available than Parakeet. `turbo` has an RTF of approximately 1.005 on this machine, so its name alone does not make it the fastest live option.

Parakeet v2 is designed for English. NVIDIA describes the model as using full attention, and the project's current adapter calls `transcribe` on files. These results do not validate a continuous recognition system with interim and finalized text. See the [official NVIDIA model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2).

## Important limitation: 2–3-second live latency is not yet verified

All current results come from whole-file evaluation. The CSV columns `chunk_p95_s`, `lag_p95_s`, and `first_text_p95_s` are empty. Live latency and WER on short audio chunks therefore cannot be inferred directly from these results.

User-visible latency includes audio buffering, queueing, inference, and text updates or finalization. Buffering a full 3 seconds before starting recognition can push latency beyond 3 seconds. A low RTF is a promising sign of processing capacity, but it is not evidence of end-to-end latency.

Inspection of individual Parakeet v2 samples shows:

- **77/100 samples** have WER no higher than 15%.
- **87/100 samples** have WER no higher than 20%.

The converted aggregate score of 88.71% therefore does not guarantee that every segment reaches 85%. Short chunks can lose context and introduce errors at word boundaries. Their quality must be measured separately rather than assumed to match whole-file scores.

## Tests required before selecting the live model

1. Compare **Parakeet v2 and small.en** on the same English data using **1-second and 2-second chunks**. Keep other settings consistent and save the results as new benchmark runs.
2. Target **WER ≤15%**, with **WER ≤20%** as the minimum acceptable quality level. Report both aggregate scores and the proportion of samples meeting each threshold, rather than only an average.
3. Use the proposed criterion that **95% of text updates have latency no greater than 3 seconds**. Record time to first text and time to finalized text separately.
4. Run continuously long enough to detect an accumulating audio backlog, including conditions where the actual application also consumes CPU resources.
5. After simulation, test with a real microphone, expected noise conditions, and representative speakers. Pay particular attention to words that are cut off, repeated, or omitted at chunk boundaries.
6. Load the model before starting the live session. Benchmark loading times may include weight downloads and initialization, so they should not be treated as the latency of each text update.

The existing `live_replay` mode only simulates independent fixed-size chunks without overlapping context. It does not measure the complete microphone-to-interface path. It is useful for screening configurations, but end-to-end testing is still required.

**Current decision:** use **large-v3 for video transcription when quality is the priority**; evaluate **Parakeet v2 in the next live benchmark**, with **small.en as the comparison baseline**. Confirm support for English live transcription at 2–3-second latency and the required quality only after obtaining the corresponding measurements.
