# Measurement Dictionary — Normative Computing Contract

Every displayed metric MUST carry: `metric_id`, `definition_version`, `model_config_id`, `dataset_id`, `split_id`, `input_mode`, `unit`, `numerator`, `denominator/n_observations`, `value|null`, `missing_reason|null`, `coverage`, `uncertainty/CI`, `clock_basis`, `source_run_ids`, and `evidence_class`. Report `not_measured`, `not_supported`, `insufficient_alignment`, `clock_unsynchronized`, `reference_unreviewed`, `missing_audio` as distinct missing reasons.

## A. Word / character recognition accuracy

| Metric ID | Exact definition / procedure | Pitfalls |
|---|---|---|
| `wer_micro` | `(sum substitutions + sum deletions + sum insertions) / sum reference words` across valid scored examples. Normalizer version is part of metric ID | NOT "accuracy=1-WER". May exceed 1. Denominator is reference words, not hypothesis words. |
| `wer_macro_utterance` | arithmetic average per-utterance WER over non-empty reference utterances | different from micro. State N and weighting. |
| `wer_macro_domain` | arithmetic average of per-domain micro WER among listed eligible domains | domains with different prevalence are weighted equally. |
| `wer_p50/p90/p95`, `fraction_above_gate` | across per-utterance WERs; gate is provisional | do not hide extreme failures behind aggregate WER. |
| `cer_raw`, `cer_normalized` | `(S_c + D_c + I_c) / N_char`, specifying whether spaces/case/punctuation retained | legacy CER uses normalized text without whitespace, versioned separately. |
| `S,D,I` | minimum edit distance alignment with deterministic tie breaking and full error spans | return tokens, offsets and alignment mapping for audit. |
| `normalized_wer` | WER after explicit normalization policy, for example historic `nfkc-casefold-punctuation-to-space-v1` | new normalization versions MUST NOT mutate old results. Numbers, compound words and contractions require documented policy. |
| `raw_wer` | WER on raw reference/hypothesis with declared tokenization | quantify style effects; still word-error metric, not semantic comprehension. |
| `term_recall`, `term_precision`, `term_miss_rate` | reference occurrence-level technical glossary matching with exact/approved equivalent strings, report TP/FP/FN and glossary revision | terms may consist of multiple tokens; do not count segment-level term accuracy as full WER. |
| `number_unit_error_rate`, `negation_error_rate` | manually adjudicated target occurrences with reference count and error count, include concrete span | include false positives, missing values, sign, amount, unit, negation. |
| `meaning_changing_errors` | reviewer-labeled error spans, severity and error type; report cases per 1000 reference words and per-session count | human judgment; not interchangeable with WER. Require review sampling and agreement. |
| `speech_coverage` | verified spoken-word span/text covered by matched presented/assembled words, measured with alignment confidence and omissions | crucial to avoid selecting only emitted words. |
| `silence_hallucination` | predicted nontrivial text during human-verified nonspeech intervals; count words/events per minute verified nonspeech | VAD decisions alone are not ground truth. |
| `turn_omissions` | verified speaker turns/utterances fully absent from final text, per number of reference turns | does not require automatic diarization; may be manual. |
| `chunk_seam_errors` | boundary-window substitution/omission/duplication, error rate against tokens near an actual chunk seam and whole-text | log distance to seam and overlap/merger settings. |
| `offline_final_wer` | WER after all long-form segmentation+merging on original audio | not WER of the live transcript. |

For silence reference `N=0`, WER is undefined; create hallucination/false-positive counts instead of dividing by zero. If references imperfect, mark `reference_quality=unverified|reviewed|adjudicated`; do not assume every annotator is correct. For relative WER improvement, `(WER_baseline-WER_candidate)/WER_baseline`; absolute difference in percentage points must be separately stated.

## B. Timing origins and observability

All related time readings MUST share one monotonic time domain OR carry a measured clock offset/drift estimate. Record `monotonic_ns`, `clock_id`, `utc_iso8601` for audit; wall clock is NOT subtraction basis due to system adjustments.

Audio chronology uses integer source PCM sample start/end index and sample rate. Audio word end time is annotated against source audio and projected to capture time using a measured recording start, calibration, capture buffering uncertainty and any source/output transport delays. A reference timestamp from forced alignment is a candidate until checked by a reviewer; it is NOT magically true ground truth. For loopback or remotely received speech, the user may want to measure against **received audio at this PC**, not remote speaker source; label the start explicitly.

Use these anchor events:
`audio_frame_captured` (source clock/time/sample-index); `speech_start`; `chunk_ready`; `inference_enqueued`; `inference_started`; `inference_done`; `hypothesis_available`; `merged_text_available`; `caption_update_requested`; `caption_paint_ack` (proxy, if supported); `caption_presentation_verified` (only if real verification exists); `caption_committed`; `utterance_finalized`; `offline_job_requested`; `offline_job_started`; `offline_job_finished`.

### Latency metrics (do not interchange)

| Metric | Start timestamp | End timestamp | Requirements / interpretation |
|---|---|---|---|
| `speech_to_first_caption_s` | verified speech segment START at local acquisition boundary | first *presentation-verified* matching caption update (else name `*_paint_proxy_s`) | includes initial speech, buffering and inference; not individual word lag. |
| `word_first_emit_lag_s` | human-verified word acoustic END (projected capture monotonic) | first time that word occurs in a model hypothesis aligned to same reference word | emission only; cannot call visible caption latency. |
| `word_first_paint_proxy_lag_s` | verified word acoustic END | first matched rendered/paint callback time for correct word | proxy: QPainter callback may precede physical display. |
| `word_first_presented_lag_s` | verified word acoustic END | first *externally/physically verified* presentation time | only if measured presentation instrument supports it; otherwise null. |
| `word_commit_lag_s` | verified word acoustic END | first irrevocable commit of that correct word under declared stable-output policy | if no commit mechanism, null. Unchanged later != irrevocably committed. |
| `chunk_ready_delay_s` | chunk first captured sample OR last captured sample (two separate metrics) | chunk ready | don't hide 2s buffering in model-only inference. |
| `queue_wait_s` | inference enqueued | model inference started | wait due to concurrent workers and resource contention. |
| `inference_service_s` | inference started | inference finished | whole-file service is not live delay. |
| `postprocess_merge_s` | inference finished | merged text available | text normalization/dedup/context. |
| `render_pipeline_s` | caption update requested | paint ack or verified presentation | use correct endpoint name. |
| `offline_turnaround_s` | job requested / session ended (report BOTH if applicable) | final output persisted and ready to user | measure with warm vs cold distinction. |
| `model_load_s`, `cold_start_to_first_caption_s` | model initialization requested/session beginning | model ready/first matching caption | separately report cold and warm paths. |

**If a reference word is omitted:** `word_*_lag_s=null`, `missing_reason="not_emitted_or_not_presented"`, count toward coverage failure and WER; do not drop it from denominator invisibly. Report lag percentiles with both `n_matched` and `n_total` plus missing fraction. The P95 is the empirical percentile of *valid timed observations*, NOT a bound on all words; it is invalid as overall acceptance without coverage.

**Queue/backlog:** log PCM total captured, audio time queued/awaiting first processing, oldest unprocessed timestamp, model worker busy time, transcription completions. `oldest_pending_age_s` and pending audio seconds are different. Long-session backlog slope should be measured per session and under concurrency; no queue-clear-after-session illusion.

**RTF:** `total wall-clock measured inference service duration / total input audio duration` (lower generally faster). **RTFx:** reciprocal if computed with exactly same service intervals/overheads; `audio duration / processing duration` (higher faster). Preserve definition scope `inference_only` vs `preprocess+inference+merge`; queue and model load separate. Whole-file RTF <1 indicates throughput potential but not bounded P95 lag in a live pipeline.

**Algorithmic delay:** lookahead/buffer imposed by architecture or chunk policy (e.g. 2-second chunk schedule), not wall-clock inference or UI visibility. **Effective-delay estimates** from a paper are labeled estimated with assumptions; DO NOT export as measured word lag.

**Transcript stability:** log every complete visible caption revision with version numbers; compute changed token count, edit distance from previous caption, flicker/revision-per-100-words, time from first emit to first stable prefix, time from first emit to commit, number of post-commit modifications (violation), and final-vs-first mismatch. Protect against artificial zero revision by showing delayed-first-caption latency and coverage jointly.

## C. Robustness and reliability

- `error_count`, `error_rate_per_audio_hour`, `timeout_count`, `retry_count`, `worker_restart_count`, `model_load_failure_count`, `audio_capture_overrun_count`, `dropped_sample_duration_ms`, `silent_gap_count`, `audio_processed_ratio`, `successful_session_fraction`.
- `CPU_utilization_per_process`, `peak_RSS_bytes`, `RAM_total_available_bytes`, `GPU_used/peak`, `threads`, `process_count`, `disk_IO_bytes`, `model_file_bytes`, `model_load_time_ms`, `energy` ONLY when actual probe exists. Do not assign app/UI process CPU to separate NeMo workers.
- `noise_condition` metadata: SNR and noise file + random seed, not a claim that real background noise has that exact SNR. Acoustic input source, mic model/driver when available, sample rate and clock drift.
- `concurrent_runs`, queue saturation and throttling; audio source dropout; initial session cold-start and mid-session model crash recovery.

## D. Statistical comparison

- Pair candidate A and B on **identical reference units**. Compute corpus micro-WER per model and per-session differences; if units are session/participant correlated, resample at session/speaker level rather than independent words.
- Paired bootstrap 95% interval on difference of aggregate WER (or per-session metric); fixed seed, >=2,000 bootstrap replicates proposed; show method, N, and assumptions. If sample set too small, mark interval unstable.
- Report all failures and `missingness` separately; never compute winner by excluding difficult files that failed one model.
- Draw Pareto tradeoffs (WER, P95 valid caption lag + coverage, RAM, dropout), **do not create one pseudo-objective weighted score without declared stakeholder weights**.
- Compare one-model vs two-model architectures with measured total resources and whether offline transcript improves meaning or readability. Model selection is a decision after measurements, not a hard-coded expected winner.

## E. Acceptance policy (proposed; not scientific standards)

- Initial live exploratory `wer_micro <= 0.15` **[P]** and `P95 lag <= 3.0 s` **[P]**, where endpoint is *specified and truly measured*. If only paint proxy exists, report provisional proxy gate, and NOT a pass on true visible latency.
- `no sustained backlog growth`, `no unreviewed critical meaning errors`, `adequate coverage`, `user readability/comprehension` have NOT YET been assigned universal numeric targets. Display `NOT YET SPECIFIED` until owners set and validate thresholds from pilot feedback.
- Offline acceptance MUST consider accuracy + turnaround + critical errors, not just model size or faster-than-real-time RTF.
- Full project status can be `RESEARCH CANDIDATE`, `MEETS EXPLORATORY GATES`, `NOT PROVEN`, `VALIDATED FOR SPECIFIED USE CASE`, or `REJECTED`, requiring human sign-off; never `VALIDATED` purely from imported historical test.

