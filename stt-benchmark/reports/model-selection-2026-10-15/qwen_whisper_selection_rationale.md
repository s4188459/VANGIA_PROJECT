> HISTORICAL ONLY ? selection withdrawn on 2026-10-20. Recommendations and
> approvals below are obsolete. No replacement model is selected by this change.
> Measurements are retained as historical evidence; continue evaluation in Vangia ASR Lab.

> Current status: no final model selection. See the [provisional candidate shortlist](english_model_decision.md) for the next evaluation. This file retains the earlier comparison only.

# Qwen and Whisper large-v3 selection rationale

Updated 2026-10-15 using the supplied English CSV and JSON.

## Measured comparison

| Metric | Qwen3-ASR-0.6B | Whisper large-v3 |
| --- | ---: | ---: |
| WER | 10.0717% | 9.1361% |
| CER | 4.5535% | 4.5613% |
| RTF | 0.7424 | 1.4236 |
| Inference time | 38.50 min | 73.84 min |
| Word edits / reference tokens | 506 / 5,024 | 459 / 5,024 |
| Character edits / reference characters | 1,160 / 25,475 | 1,162 / 25,475 |
| Successful samples | 100 / 100 | 100 / 100 |
| CPU configuration | FP32, 4 threads, no VAD | INT8, 4 threads, beam 5, VAD |

## Interpretation

The supplied English run is the primary selection evidence: 100 samples, 51.87 minutes, 5,024 reference tokens and 25,475 reference characters. Both selected models completed all samples without failures.

Qwen achieved 10.0717% WER and RTF 0.7424, versus Whisper large-v3 at 9.1361% WER and RTF 1.4236. Qwen used 38.50 minutes of inference, while Whisper used 73.84 minutes. These are whole-file measurements, excluding loading.

Whisper had the lowest WER among 25 successful configurations. Qwen had the lowest WER among successful configurations with aggregate RTF below 1, and the lowest CER among all 25. This supports an accuracy-conscious live candidate, not the fastest candidate.

The final-pass rationale is 47 fewer word edits across 5,024 reference tokens: 0.9355 percentage points or 9.29% relative WER reduction, at 1.918 times the inference time. Whisper produced two MORE character edits, so it does not win every accuracy metric.

A two-model design is justified only if this word-level gain matters enough to accept the extra cost. Reprocess recorded audio for the final pass; do not assume rewriting the live text can recover missed speech.

The earlier single-fixture Qwen smoke is historical context only. The supplied 100-sample run is stronger task evidence and supersedes it for this English offline comparison. Neither run measures actual live latency.

## Sample-level comparison

Whisper has fewer word edits on 51 samples; Qwen on 34; 15 are tied. The net reduction of 47 word edits does not mean Whisper corrects every Qwen error.

## Technical details, evidence and limits

**Decision status:** English offline benchmark supports the speed/word-error tradeoff; live deployment and Vietnamese selection remain unvalidated.

### Scope

**Live candidate:** Qwen/Qwen3-ASR-0.6B

**Final candidate:** openai/whisper-large-v3 via faster-whisper/CTranslate2

**Assumption:** Confirmed checkpoints in supplied run: Qwen/Qwen3-ASR-0.6B and faster-whisper large-v3. Proposed role assignment remains Qwen live and Whisper final.

**Tasks:** Live captions during teaching, followed by a new transcription of the recorded audio after the session. No training is required for this evaluation.

### Primary user benchmark evidence

#### Source files

**Name:** Testing_STT_Model_English_Version.csv

**Sha256:** 88ddf09f3ac8928d3fb8e1faf2b53bc2d6f110eb87d1709256964c5068e7f98c

---

**Name:** STT-EN.json

**Sha256:** 497b10681b1ae89acb7bb1db20401667227c68fea03eb706b4783d7790514351

---

**Run id:** e634c257ef69434383d580442820821e

**Run created at:** 2026-10-12T08:15:36.915688+00:00

**Run finished at:** 2026-10-13T09:41:21.887846+00:00

#### Resumptions

**At:** 2026-10-12T17:10:11.409937+00:00

**Backup:** run.before-resume-05d7a182a728457ba35ed4d6ff34d68a.json

---

**At:** 2026-10-13T03:43:30.669951+00:00

**Backup:** run.before-resume-84feecd8ab164662ad5221ecb44a78f8.json

---

#### Protocol

**Mode:** final

**Chunk seconds:** 3

**Allow cloud:** True

**Protocol:** full-file-v1

#### Dataset

**Id:** ebd4f800c0b54227a84c40bbc7818019

**Name:** 2

**Language:** en

**Created at:** 2026-10-12T08:12:11.647222+00:00

**Sha256:** f1c5b65378f03d7efc686e3de704e6da73afbc7efc8d257d89d3cb0888c6ffbd

##### Audio preprocessing

**Version:** pyav-mono-pcm16-16000-v1

**Sample rate:** 16000

**Channels:** 1

**Encoding:** pcm_s16le

**Duration s:** 3111.93575

**Sample count:** 100

**Configurations total:** 27

**Configurations successful:** 25

**Configurations failed:** 2

**Csv json numeric fields matched:** 162

**Pairwise shared samples verified:** 100

**Reference and duration match:** True

#### Derived comparison

**Wer reduction percentage points:** 0.9355095541401279

**Wer relative reduction percent:** 9.288537549407119

**Net fewer word edits with whisper:** 47

**Extra character edits with whisper:** 2

**Whisper inference time divided by qwen:** 1.917701349514426

**Whisper extra inference minutes:** 35.33397166500029

**Qwen inference minutes:** 38.5026911900001

**Whisper inference minutes:** 73.8366628550004

**Total audio minutes:** 51.86559583333334

**Whisper lower wer samples:** 51

**Qwen lower wer samples:** 34

**Equal wer samples:** 15

#### Qwen

##### Config

**Backend:** qwen-asr

**Model:** Qwen/Qwen3-ASR-0.6B

**Label:** Qwen3-ASR-0.6B

**Device:** cpu

**Python executable:** D:\@_Binh's document\AI Course\VANGIA_PROJECT\stt-benchmark\.backends\qwen-asr\Scripts\python.exe

**Compute type:** float32

**Beam size:** 1

**Cpu threads:** 4

###### Languages

- en

- vi

**Vad filter:** False

**Allow download:** False

##### Summary

**Completed:** 100

**Failed:** 0

**Cer:** 0.04553483807654563

**Character errors:** 1160

**Reference characters:** 25475

**Chunk p95 s:** Unavailable / not measured

**Lag p95 s:** Unavailable / not measured

**First text p95 s:** Unavailable / not measured

**Deadline misses:** 0

**Reference words:** 5024

**Errors:** 506

**Wer:** 0.10071656050955415

**Inference s:** 2310.161471400006

**Audio s:** 3111.93575

**Rtf:** 0.742355131014516

**Load s:** 52.94246029999704

##### Runtime

**Python:** 3.12.14 (main, Aug 25 2026, 14:01:42) [MSC v.1944 64 bit (AMD64)]

**Executable:** D:\@_Binh's document\AI Course\VANGIA_PROJECT\stt-benchmark\.backends\qwen-asr\Scripts\python.exe

###### Packages

**Torch:** 2.14.1

**Transformers:** 4.57.6

**Qwen-asr:** 0.0.6

**Requests:** 2.34.2

#### Whisper

##### Config

**Backend:** faster-whisper

**Model:** large-v3

**Label:** large-v3 [catalog]

**Device:** cpu

**Python executable:** 

**Compute type:** int8

**Beam size:** 5

**Cpu threads:** 4

###### Languages

- en

- vi

**Vad filter:** True

**Allow download:** True

##### Summary

**Completed:** 100

**Failed:** 0

**Cer:** 0.04561334641805692

**Character errors:** 1162

**Reference characters:** 25475

**Chunk p95 s:** Unavailable / not measured

**Lag p95 s:** Unavailable / not measured

**First text p95 s:** Unavailable / not measured

**Deadline misses:** 0

**Reference words:** 5024

**Errors:** 459

**Wer:** 0.09136146496815287

**Inference s:** 4430.199771300024

**Audio s:** 3111.93575

**Rtf:** 1.4236154365654958

**Load s:** 531.5413322999957

##### Runtime

**Platform:** Windows-11-10.0.26300-SP0

**Processor:** AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD

**Python:** 3.12.14

###### Packages

**Faster-whisper:** 1.2.1

**Ctranslate2:** 4.8.2

**Av:** 18.1.0

**Torch:** not installed

**Transformers:** not installed

**Qwen-asr:** not installed

**Nemo toolkit:** not installed

**Funasr:** not installed

**Vosk:** not installed

**Google-cloud-speech:** not installed

**Requests:** not installed

#### Ranking by wer

**Model:** large-v3 [catalog]

**Wer:** 0.09136146496815287

**Cer:** 0.04561334641805692

**Rtf:** 1.4236154365654958

---

**Model:** large-v2 [catalog]

**Wer:** 0.09812898089171974

**Cer:** 0.05197252208047105

**Rtf:** 1.5071397902414847

---

**Model:** Qwen3-ASR-0.6B

**Wer:** 0.10071656050955415

**Cer:** 0.04553483807654563

**Rtf:** 0.742355131014516

---

**Model:** canary-1b-v2 [catalog]

**Wer:** 0.10151273885350319

**Cer:** 0.04891069676153091

**Rtf:** 1.069143471197955

---

**Model:** turbo [catalog]

**Wer:** 0.10688694267515923

**Cer:** 0.05209028459273798

**Rtf:** 1.005110432019682

---

**Model:** large-v1 [catalog]

**Wer:** 0.1080812101910828

**Cer:** 0.05719332679097154

**Rtf:** 1.38299099652043

---

**Model:** parakeet-tdt-0.6b-v2

**Wer:** 0.11285828025477707

**Cer:** 0.05844946025515211

**Rtf:** 0.2533924505028739

---

**Model:** medium [catalog]

**Wer:** 0.11325636942675159

**Cer:** 0.05574092247301276

**Rtf:** 0.7754599315233343

---

**Model:** medium.en [catalog]

**Wer:** 0.12022292993630573

**Cer:** 0.058174681059862614

**Rtf:** 0.7674741080370922

---

**Model:** distil-large-v3.5-ct2 [catalog]

**Wer:** 0.12101910828025478

**Cer:** 0.05982335623159961

**Rtf:** 0.9328824054288398

---

**Model:** parakeet-tdt-0.6b-v3 [catalog]

**Wer:** 0.12679140127388536

**Cer:** 0.05899901864573111

**Rtf:** 0.26554402146638667

---

**Model:** distil-large-v2 [catalog]

**Wer:** 0.151671974522293

**Cer:** 0.07866535819430814

**Rtf:** 0.9410048230912224

---

**Model:** small.en

**Wer:** 0.15187101910828024

**Cer:** 0.07685966633954858

**Rtf:** 0.20015926553110713

---

**Model:** distil-large-v3 [catalog]

**Wer:** 0.15286624203821655

**Cer:** 0.08125613346418056

**Rtf:** 1.0434358108132527

---

**Model:** small [catalog]

**Wer:** 0.15425955414012738

**Cer:** 0.0775269872423945

**Rtf:** 0.2752490816367218

---

**Model:** distil-small.en [catalog]

**Wer:** 0.20660828025477707

**Cer:** 0.11403336604514229

**Rtf:** 0.2197665694093946

---

**Model:** SenseVoiceSmall

**Wer:** 0.2115843949044586

**Cer:** 0.10143277723258096

**Rtf:** 0.1357931162942633

---

**Model:** base.en

**Wer:** 0.22153662420382167

**Cer:** 0.11481844946025516

**Rtf:** 0.06631677090376084

---

**Model:** base [catalog]

**Wer:** 0.2294984076433121

**Cer:** 0.1154072620215898

**Rtf:** 0.09609842346519822

---

**Model:** distil-medium.en [catalog]

**Wer:** 0.24203821656050956

**Cer:** 0.15795878312070658

**Rtf:** 0.550518385606128

---

**Model:** tiny [catalog]

**Wer:** 0.29737261146496813

**Cer:** 0.15081452404317958

**Rtf:** 0.05727150353280265

---

**Model:** tiny.en [catalog]

**Wer:** 0.33738057324840764

**Cer:** 0.18425907752698725

**Rtf:** 0.05820216969453512

---

**Model:** wav2vec2-large-960h-lv60-self [catalog]

**Wer:** 0.3590764331210191

**Cer:** 0.13538763493621198

**Rtf:** 0.5281424685904902

---

**Model:** vosk-model-en-us-0.22 [catalog]

**Wer:** 0.39669585987261147

**Cer:** 0.20278704612365064

**Rtf:** 0.6484761968173631

---

**Model:** Vosk small EN

**Wer:** 0.553343949044586

**Cer:** 0.2765063788027478

**Rtf:** 0.12821126207377712

---

#### Limitations

- All records use final/full-file-v1. The stored chunk_seconds=3 setting is inactive in this protocol. Chunk P95, lag P95 and first-text P95 are null, not zero.

- The global common_sample_count is zero because the comparison includes two models with no successful samples. The Qwen/Whisper pair itself has 100 matching successful sample IDs with identical references and durations, verified directly from JSON.

- Qwen uses CPU float32, beam setting 1 and no VAD; Whisper uses CPU int8, beam size 5 and VAD. Both configure four threads. This compares deployed configurations, not architecture alone. Beam settings do not imply equivalent decoders.

- The run was resumed twice. Load/download/cache conditions and machine contention may differ between configurations. Loading times should not be interpreted as standardized cold-start latency.

- No repeated-run variance, hardware utilization or peak-memory measurement is available. Server package entries marked not installed do not invalidate isolated-worker packages recorded under model runtime.

- The source contains English only. It does not establish Vietnamese accuracy, live latency or continuous-session stability.

- Reference quality and topic distribution were not independently audited against the audio here. The intended 70/30 topic mix is not verified by these aggregate files.

- Qwen 1.7B failed with a Windows privilege/symlink error and MMS failed with a backend timeout. These are execution failures, not evidence of inferior recognition accuracy.

### Model specifications

**Model:** Qwen3-ASR-0.6B

**Nominal parameters billion:** 0.6

**Languages:** 30 languages plus 22 Chinese dialects; includes English and Vietnamese

**Modes:** Offline and streaming supported by the family

**Streaming constraint:** The qwen-asr toolkit documentation specifies vLLM for streaming; the current local adapter instead uses from_pretrained() and transcribe().

#### Source ids

- Q1

- Q2

**Published performance context:** The author report cites average TTFT as low as 92 ms and aggregate throughput of 2000 audio seconds per second at concurrency 128. These are author-system results, not this laptop or single-stream end-to-end latency. Hardware/runtime details must accompany any reuse of these numbers.

#### Current configuration

**Backend:** qwen-asr

**Device:** cpu

**Compute type:** float32

**Cpu threads:** 4

**Max inference batch size:** 1

**Max new tokens:** 4096

**Current streaming status:** Independent-file/chunk inference, not native stateful streaming

---

**Model:** Whisper large-v3

**Nominal parameters billion:** 1.55

**Languages:** Multilingual; supports English and Vietnamese

**Architecture:** Encoder-decoder Transformer

**Mel frequency bins:** 128

#### Training audio hours

**Weakly labeled:** 1000000

**Pseudo labeled:** 4000000

**Published comparison:** The model card reports 10-20% relative error reduction versus large-v2 across a wide variety of languages. This is not a comparison with Qwen and not a predicted gain on the project dataset.

#### Source ids

- W1

- W2

**Configuration status:** Verified in the supplied STT-EN.json run; all 100 English samples completed.

**Streaming constraint:** Standard Whisper transcribes windows; low-latency applications require a streaming wrapper with buffering and transcript-stability logic.

#### Measured configuration

**Backend:** faster-whisper

**Model:** large-v3

**Label:** large-v3 [catalog]

**Device:** cpu

**Python executable:** 

**Compute type:** int8

**Beam size:** 5

**Cpu threads:** 4

##### Languages

- en

- vi

**Vad filter:** True

**Allow download:** True

---

### Parameter memory estimates

**Classification:** Arithmetic estimates only, not measured RAM/VRAM or installation size

**Formula:** nominal parameter count multiplied by bytes per stored weight; decimal GB

#### Qwen 0 6b

**Fp32 gb:** 2.4

**Fp16 bf16 gb:** 1.2

#### Whisper 1 55b

**Fp32 gb:** 6.2

**Fp16 gb:** 3.1

**Idealized int8 gb:** 1.55

**Whisper to qwen parameter ratio:** 2.5833

**Limits:** Runtime memory also includes activations, caches, workspaces and framework overhead. Quantization adds scales and may retain some higher-precision tensors. This ratio is not a speed ratio, and does not imply the current Qwen adapter supports INT8.

### Task rationale

**Task:** Live transcription

**Candidate:** Qwen3-ASR-0.6B

**Input:** Incoming microphone audio via an actual streaming deployment, or explicitly labelled chunk simulation during preliminary testing

**Output:** Provisional captions, which may be revised

**Reason:** Best observed WER among the successful configurations with aggregate offline RTF below 1. This supports testing Qwen as an accuracy-conscious live candidate; actual capture-to-caption latency is not measured.

#### Priority order

- P95 visible caption latency

- Stable queue under continuous speech

- WER/CER and technical-term recall

- Caption revision rate and robustness

**Failure condition:** Reject the live configuration if captions accumulate delay or omit too much speech, even when a short sample appears fast.

---

**Task:** Final transcription

**Candidate:** Whisper large-v3

**Input:** Recorded audio, reprocessed independently after the session

**Output:** A separate final transcript with provenance and review status

**Reason:** Lowest corpus WER in the supplied successful English configurations, with 47 fewer word edits than Qwen. Its slower inference can be scheduled after the session. CER is marginally worse than Qwen, so the quality benefit is specifically word-level.

#### Priority order

- Corpus WER/CER

- Technical-term recall and omissions

- Hallucinations during silence

- Total completion time and memory

**Failure condition:** Reject the second model if it does not improve the target-language transcript enough to justify its cost. Do not automatically replace a better Qwen transcript.

---

### Pipeline

- Capture and retain one continuous recording with timestamps.

- Send live audio to the selected live deployment and display provisional captions.

- After recording, send recorded audio to the final model; preserve both outputs separately.

- Compare against human-reviewed references during evaluation. In production, label the final output as automatic and allow correction.

- Do not merge transcripts by guessing which wording sounds better. If reconciliation is needed, evaluate it as an additional stage with audio-grounded checks.

### Benchmark plan

**Dataset:** English 100-sample whole-file baseline is now available and analyzed. Next validate live behavior, repeated timings and a separately reviewed Vietnamese set. Verify audio/reference quality and topic labels before broader claims.

#### Conditions

- Record actual spoken text rather than assuming the script was read exactly.

- Include accents, short pauses, technical vocabulary, numbers, noise and silence.

- Use identical audio normalization, language settings, hardware and documented decoding parameters for controlled comparisons.

- Run Qwen offline, Whisper large-v3 offline and Qwen native streaming separately. Optional chunk replay is a distinct protocol.

- Record cold loading separately; repeat warm runs and report variability.

- If tuning on this dataset, reserve untouched evaluation samples or collect a held-out set.

#### Metrics

**Name:** WER

**Definition:** Total substitutions + deletions + insertions divided by total reference tokens; Vietnamese tokens are whitespace-separated.

---

**Name:** CER

**Definition:** Total character edits divided by reference characters after documented normalization; preserve Vietnamese accents.

---

**Name:** RTF

**Definition:** Inference seconds divided by audio seconds; below 1 means faster than audio duration for that measured protocol, but does not guarantee low P95 live latency.

---

**Name:** P95 live latency

**Definition:** Measure capture-to-visible-caption delay and finalization delay separately in the actual application. Simulated chunk lag is not a substitute.

---

**Name:** Reliability

**Definition:** Successful/failed sample counts, common-sample coverage, queue growth, silence hallucinations and omitted technical terms.

---

**Name:** Resources

**Definition:** Peak RAM/VRAM, model loading, total session processing time and energy/cost where measured.

---

**Acceptance policy:** Define latency, quality and final-processing budgets with the supervisor before ranking. Select two models only if the live candidate meets the latency budget and the final candidate delivers a meaningful measured quality gain. Otherwise prefer one model or test another allocation.

**Existing tool limits:** Current tool measures WER/CER, processing time, RTF and simulated chunk metrics. Native microphone latency, caption stability, terminology recall and peak RAM/VRAM require additional instrumentation or manual evaluation.

### Tradeoffs and alternatives

- Two passes roughly require two recognition workloads per session; exact cost is measured, not inferred from parameter counts.

- Running both models concurrently can compete for CPU/RAM and worsen live latency. On the current CPU laptop, schedule the final pass after the session or evaluate a separate compatible machine.

- Evaluate Qwen for both passes, Whisper for both passes with a suitable wrapper, and the two-model pipeline. The architecture should follow results rather than assume that different tasks require different models.

- Neither base ASR model automatically provides dependable teacher/student speaker attribution; diarization is a separate evaluated component.

- A transcript preserves spoken words; summarization or rewriting is a separate task and should not silently alter the reference used for WER.

**Defensible conclusion:** The English results support Qwen3-ASR-0.6B as a candidate for responsive transcription because it has the lowest WER among tested successful configurations with RTF below 1. Whisper large-v3 is supported for a WER-prioritized final pass because it has the lowest WER overall: 9.1361% versus 10.0717%, a 9.29% relative reduction. It takes 1.918 times as long and has marginally worse CER. This justifies evaluating two passes, but does not establish native live suitability, Vietnamese superiority, or that two models are always necessary.

### Sources

**Id:** Q1

**Title:** Official Qwen3-ASR repository

**Url:** https://github.com/QwenLM/Qwen3-ASR

**Accessed:** 2026-10-15

---

**Id:** Q2

**Title:** Qwen3-ASR Technical Report

**Url:** https://arxiv.org/abs/2601.21337

**Accessed:** 2026-10-15

---

**Id:** W1

**Title:** Whisper large-v3 model card

**Url:** https://huggingface.co/openai/whisper-large-v3

**Accessed:** 2026-10-15

---

**Id:** W2

**Title:** OpenAI Whisper repository

**Url:** https://github.com/openai/whisper

**Accessed:** 2026-10-15

---

**Id:** F1

**Title:** faster-whisper implementation

**Url:** https://github.com/SYSTRAN/faster-whisper

**Accessed:** 2026-10-15

---

**Id:** L1

**Title:** Inspected local configuration and implementation

#### Paths

- stt-benchmark/data/models.json

- stt-benchmark/benchmark/extra_adapters.py

- stt-benchmark/benchmark/catalog.py

- stt-benchmark/data/backend-smoke/qwen-asr-Qwen3-ASR-0.6B.json

---

**Id:** U1

**Title:** User-supplied English benchmark CSV and full JSON

#### Files

- C:\Users\LENOVO\Downloads\Testing_STT_Model_English_Version.csv

- C:\Users\LENOVO\Downloads\STT-EN.json

**Role:** Primary measured evidence; web model cards remain sources for published specifications only.

---

### Historical smoke context

**Classification:** Older one-fixture technical check; not the main model-selection evidence

**Rtf:** 1.391850530850553

**Source:** stt-benchmark/data/backend-smoke/qwen-asr-Qwen3-ASR-0.6B.json

**Interpretation:** Different fixture/run from the supplied 100-sample evaluation. Do not average these RTFs or replace the new benchmark with the older smoke.

### Alternatives from same run

#### Parakeet v2

##### Summary

**Completed:** 100

**Failed:** 0

**Cer:** 0.05844946025515211

**Character errors:** 1489

**Reference characters:** 25475

**Chunk p95 s:** Unavailable / not measured

**Lag p95 s:** Unavailable / not measured

**First text p95 s:** Unavailable / not measured

**Deadline misses:** 0

**Reference words:** 5024

**Errors:** 567

**Wer:** 0.11285828025477707

**Inference s:** 788.5410254999988

**Audio s:** 3111.93575

**Rtf:** 0.2533924505028739

**Interpretation:** English latency-first alternative: 11.2858% WER and RTF 0.2534; Qwen took 2.930 times as long but had 1.2142 percentage points lower WER. This checkpoint is English-only in the run configuration.

**One model qwen:** Keeps 10.0717% WER and slightly better CER without a second inference pass. Consider this if the 0.9355-point WER improvement is not worth the cost.

**Large v2:** 9.8129% WER and RTF 1.5071: large-v3 has lower WER and lower RTF in this run.

**Turbo:** 10.6887% WER and RTF 1.0051: Qwen has lower WER and lower RTF in this run.
