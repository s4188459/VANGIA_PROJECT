# Research Evidence, Model Comparators, and Derived Requirements

**Vangia English-only ASR Selection Lab | evidence freeze: 2026-10-15 | purpose: tool requirements, not a model ranking or final literature review**

Evidence labels: `[E-PUB]` publication claim / reported measurements; `[E-LOCAL]` direct historical result; `[I]` inference derived from research, NOT author finding; `[P]` proposed engineering requirement; `[G]` unresolved / no supporting measurement. A paper can contain developer-run evaluation without independent confirmation. Every item below includes original URL and inspected location; paper numbers do not transfer to our models when version/mode/hardware differs.

## R01 — Independent English streaming/chunked comparison (PRIORITY)

**Title:** *Pushing the Limits of On-Device Streaming ASR: A Compact, High-Accuracy English Model for Low-Latency Inference*. **Authors:** Nenad Banfic, David Fan, Kunal Vaishnavi, Sam Kemp, Sunghoon Choi, Rui Ren, Sayan Shaw, Meng Tang (Microsoft CoreAI). **Year/status:** 2026 arXiv preprint v2 (19 Apr), **not confirmed peer-reviewed**. **Full text:** HTML inspected, specifically Sections 2, 3, 4, 5 and Table 5; https://arxiv.org/html/2604.14493 . **Hardware:** AMD EPYC 7V12 64-core CPU, inference pinned to 32 cores; GPU NVIDIA H100 for GPU work. **Datasets:** eight English datasets: AMI, Earnings22, GigaSpeech, LibriSpeech clean/other, SPGISpeech, TED-LIUM, VoxPopuli. **Mode:** separate batch, chunked and streaming; benchmark uses RTFx (audio duration / processing time) and *algorithmic* delay, not actual Vangia visual display latency.

- `[E-PUB]` Section 5.1: **Parakeet TDT 0.6B v3**, not v2, achieves 6.32% batch WER vs 9.22% in its best explored chunked condition with 2.4 s chunk/delay. This is evidence that chunking can degrade recognized text for this exact v3, not evidence of a particular v2 penalty.
- `[E-PUB]` Section 3.2: RTFx >1 is an efficiency indicator; authors explicitly distinguish processing factor and algorithmic delay. A delay formula is an **approximation**, not a visible UI measurement.
- `[E-PUB]` Section 5.3 Table 5 compares specific CPU streaming/chunked configurations for Parakeet v3, Qwen3-ASR-1.7B and Canary-1B-v2. Qwen 0.6B appears elsewhere in the paper/appendix; do not assign the 1.7B Table 5 numbers to 0.6B. Different models use different delays/context.
- `[I]` Live model *configuration* is the unit of evidence, not model family; always report `(checkpoint, backend, precision, decode, chunking/context, hardware, dataset)`.
- `[P]` Implement **batch-to-chunk degradation** as paired WER difference and optional ratio, with both batch and chunk assembled outputs on identical held-out audio. Log chunk boundaries and window parameters. Report latency with timestamp origins instead of reusing paper RTFx values.
- `[G]` Peer review of this preprint not established; its selected Nemotron checkpoint is NOT in the project's candidate list, so it must NOT be added as a new selectable model.

## R02 — Parakeet v2 official checkpoint

**Organization:** NVIDIA. **Title:** *Parakeet TDT 0.6B V2 (En) Model Card*. **Release:** 2025. **Type:** official technical documentation; https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2 . **Inspected:** Architecture, Base Performance, Noise Robustness, Inference and known limitations. **Exact checkpoint:** `nvidia/parakeet-tdt-0.6b-v2` (600M). **Published hardware/config:** model card task-specific benchmarks; hardware and complete decoding settings for every number not independently confirmed here; do not impute.

- `[E-PUB]` Vendor reports English benchmark WER and a noise-robustness breakdown; performance varies with input domain, accent, noise, speech type and context. Its model documentation cautions about incomplete word/phrase recognition.
- `[I]` Lower historical whole-file CPU RTF suggests it merits live testing, but cannot prove speech-to-visible-text lag, native stateful streaming, or quality on short uncontextualized chunks.
- `[P]` Capture v2 chunk accuracy, queue growth, omissions, VAD effects and CPU resource profile.

## R03 — Parakeet v3 official checkpoint and research context

**Organization:** NVIDIA. **Title:** *Parakeet TDT 0.6B V3 Model Card*, **release:** 2025. Official technical docs https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 . **Inspected:** Key Features (long audio, timestamps), architecture, usage. **Exact checkpoint:** `nvidia/parakeet-tdt-0.6b-v3`.

- `[E-PUB]` NVIDIA describes v3 as a successor to v2 with broader language training and full/local attention long-form inference. v2 English benchmark numbers MUST NOT be relabeled v3.
- `[I]` On English-only audio, v3 is a reasonable **comparison**, but its broader training does not itself imply better English WER.
- `[P]` Test v2 and v3 on identical English segments/sessions using same type of backend where possible, then separately compare chunk policies.

## R04 — Canary v2 and Parakeet v3 primary technical report

**Title:** *Canary-1B-v2 & Parakeet-TDT-0.6B-v3: Efficient and High-Performance Models for Multilingual ASR and AST*. **Authors:** Monica Sekoyan, Nithin Rao Koluguri, Nune Tadevosyan, Piotr Żelasko, Travis Bartley, Nick Karpov, Jagadeesh Balam, Boris Ginsburg. **Year/status:** 2025 arXiv preprint (peer review not confirmed). https://arxiv.org/html/2509.14128 . **Inspected:** Section 6.1, Tables 5 and 6, long-form/timestamp discussions. **English applicability ONLY:** restrict evaluation to English columns; paper multilingual analyses do not authorize multilingual scope. **Hardware/config:** dependent on paper table; do not treat benchmark RTFx as local CPU speed.

- `[E-PUB]` Vendor report compares **Canary-1B-v2**, **Parakeet TDT 0.6B-v3** and **Whisper large-v3** on public benchmarks and noise-augmented clean speech. A different dataset/metric aggregation can invert local rank.
- `[E-PUB]` Section 6.1.3 Table 6 reports noise-induced WER changes for Canary v2 and Parakeet v3, not for Parakeet v2.
- `[I]` Domain, noise and long-form tests should be stratified instead of declaring a universal WER winner based on one average.
- `[P]` Include additive noise SNR conditions where lawful and reproducible; preserve clean originals and exact augmentation seeds; compare 1-minute and long-session segmentation.

## R05 — Canary official model card

**Organization:** NVIDIA, *Canary-1B-v2 Model Card*, 2025, official docs. https://huggingface.co/nvidia/canary-1b-v2 . **Inspected:** model/inference, Long-form Inference, Noise Robustness. **Checkpoint:** `nvidia/canary-1b-v2`.

- `[E-PUB]` Long-form inference uses dynamic chunking and 1-second chunk overlap under described conditions; reported timestamps are model/aligner outputs and do not directly provide independently checked word-level reference timing.
- `[I]` Offline WER and gaps/duplicates at long-chunk boundaries must be measured independently from short-file WER.
- `[P]` Test short vs multi-minute vs full-session with long-form policy recorded.

## R06 — Qwen3-ASR technical report (exact 0.6B)

**Title:** *Qwen3-ASR Technical Report*. **Organization/authors:** Qwen Team / Xian Shi et al. **Year/status:** 2026 arXiv preprint (peer review unconfirmed). https://arxiv.org/html/2601.21337 . **Inspected:** architecture/Section 4 English ASR and Section 4.5 streaming, Table 8. **Model:** `Qwen3-ASR-0.6B` distinct from 1.7B. **Datasets:** Table 8 includes English LibriSpeech clean/other and FLEURS-en. **Hardware:** for Table 8 not fully verified in this package; mark `not reported/unchecked`, not local CPU.

- `[E-PUB]` Table 8 shows differing offline vs streaming WER for the exact 0.6B model under a streaming strategy with 2-second chunks, a token fallback and unfixed chunks. These are authors' own results.
- `[I]` Successive independent chunk calls may behave differently from stateful streaming with retained history; separate these in the tool.
- `[P]` Represent `chunked_independent` and `native_streaming` as different pipeline modes with different output timelines and comparable final assembled WER.

## R07 — Official Qwen code and streaming limitations

**Organization:** QwenLM, *Qwen3-ASR Repository*, 2026 living implementation docs, https://github.com/QwenLM/Qwen3-ASR ; exact streaming example https://github.com/QwenLM/Qwen3-ASR/blob/main/examples/example_qwen3_asr_vllm_streaming.py . **Inspected:** streaming inference README and example; code example uses `init_streaming_state` and `streaming_transcribe`. **Backends:** native streaming described with **vLLM** in current official docs, with no timestamp return/batch streaming in that functionality.

- `[E-PUB]` Native streaming capability is backend-specific.
- `[I]` A Windows CPU failure to install/use vLLM does not make a model inherently inaccurate; mark `backend unavailable` and test independent chunking only where supported.
- `[P]` Adapter capability flags `batch`, `independent_chunks`, `stateful_streaming`, `timestamp_output`, `required_accelerator`, `worker_platform`; *never* silently fall back.

## R08 — Whisper family and large-v3 official documentation

**Organization:** OpenAI / Hugging Face, *Whisper large-v3 Model Card*, released 2023, official technical docs https://huggingface.co/openai/whisper-large-v3 . Other exact comparison cards: https://huggingface.co/openai/whisper-large-v2 , https://huggingface.co/openai/whisper-large-v3-turbo , https://huggingface.co/openai/whisper-small.en , https://huggingface.co/openai/whisper-small . **Inspected:** model cards/identifiers, 30-second processing and long-form approaches, performance/limitations.

- `[E-PUB]` Whisper models include sequential or chunked long-form transcription and carry hallucination/insertion risks; newer version does not guarantee better local WER for every session. `small.en` and `small` are different trained checkpoints; `turbo` is an alias that must be resolved to an exact weight identity in deployment.
- `[I]` For offline role, prioritize completed-session WER, omissions/meaning errors, processing turnaround, reproducibility and resources. For `small` models evaluated live, distinguish sliding chunk inference from true native streaming.
- `[P]` Use exact weight revision/hash, backend, beam, language settings, VAD, conditioning and silence controls. Always transcript from ORIGINAL AUDIO for final stage, not from the live hypothesis.

## R09 — Original Whisper research

**Title:** *Robust Speech Recognition via Large-Scale Weak Supervision*. **Authors:** Alec Radford, Jong Wook Kim, Tao Xu, Greg Brockman, Christine McLeavey, Ilya Sutskever. **Year/status:** 2023, peer-reviewed ICML, https://proceedings.mlr.press/v202/radford23a.html . **Inspected:** abstract and original paper landing page. **Version caveat:** published BEFORE large-v3 checkpoint; no reported results may be attributed to large-v3 from this paper.

- `[E-PUB]` Motivates examining generalization across speech conditions rather than only one clean benchmark.
- `[P]` Evaluate real speech, microphones and noise separate from clean/read speech.

## R10 — Peer-reviewed streaming pipeline research

**Title:** *Turning Whisper into Real-Time Transcription System*. **Authors:** Dominik Macháček, Raj Dabre, Ondřej Bojar. **Year/status:** 2023, peer-reviewed IJCNLP-AACL system demonstration, https://aclanthology.org/2023.ijcnlp-demo.3/ . **Inspected:** Sections 2–5 and latency methodology. **Exact published version:** Whisper **large-v2** via faster-whisper; **NOT large-v3**. **Domain:** English European Parliament speeches (ESIC); paper also other cases. **Hardware:** A40/L40 used in reported experiments; not equivalent to local CPU.

- `[E-PUB]` Work defines word-level latency from when word spoken to when its output appears and uses LocalAgreement for stability; VAD trade-offs can involve increased delay.
- `[I]` Stable / confirmed / first seen captions measure different user experiences. Reprocessing recent context may reduce boundary errors but increase compute and revisions.
- `[P]` Log provisional timeline, stable/committed policy, revision counts and truly presented/paint-acknowledged captions, with valid source word times.

## R11 — Accessible lecture transcript usability, no 15% cutoff

**Title:** *Measuring the Acceptable Word Error Rate of Machine-Generated Webcast Transcripts*. **Authors:** Cosmin Munteanu, Gerald Penn, Ron Baecker, Elaine Toms, David James. **Year/status:** 2006, peer-reviewed Interspeech, https://www.isca-archive.org/interspeech_2006/munteanu06_interspeech.html ; original PDF https://www.cs.toronto.edu/~gpenn/papers/mcosmin-interspeech06.pdf . **Inspected:** abstract/full paper previously examined; this packaged summary is based on abstract and paper results, not new PDF screenshot reinspection. **Use case:** seeking information in ARCHIVED educational webcast videos. **Conditions:** 0%, 25%, 45% WER and no transcript; NOT a 15% live speech study.

- `[E-PUB]` Utility varies with task; degraded transcripts may still help compared with none for some tasks, but very high errors can harm.
- `[I]` A quality gate for Vangia classroom captions must come from task performance and readers, not borrowing 25% or guessing 15%.
- `[P]` Add human comprehension / task completion and subjective rating study with measured WER/lag attached to stimuli.

## R12 — Human caption ratings not reducible to WER

**Title:** *Evaluating the Usability of Automatically Generated Captions for People who are Deaf or Hard of Hearing*. **Authors:** Sushant Kafle and Matt Huenerfauth. **Year/status:** 2017, peer-reviewed ACM ASSETS. Original https://doi.org/10.1145/3132525.3132542 ; accessible author preprint https://arxiv.org/abs/1712.02033 . **Inspected:** full text in previous evidence pass, usability findings. **Stimuli:** deliberately differing errors, some equal WER, not Vangia classroom live speech.

- `[E-PUB]` Different word errors at equal WER can have different usability consequences.
- `[I]` Semantic severity, error span, technical terms, negation, units and amounts need human review beyond global WER.
- `[P]` Reviewer annotation schema with severity, content-category, transcript excerpt and audio time, reviewer/adjudicator identities.

## R13 — Recent latency and caption usability evidence

**Title:** *Are Caption Metrics Broken? Latency, Deaf and Hard of Hearing User Ratings, and Bias across Technologies*. **Authors:** Bernard Thompson et al. **Year/status:** 2026 arXiv preprint (peer review not confirmed). https://arxiv.org/html/2609.11408 . **Inspected:** study methodology (delay assignment) and results/discussion. **Data:** live-TV style caption stimuli; ASR delay condition artificially set mean 2 s with jitter, TV delay typically longer. **NOT:** Parakeet or Whisper, and NOT a 2-second normative upper bound.

- `[E-PUB]` Perceived quality and comprehension are affected by delay and other factors not represented by WER alone.
- `[I]` A 2–3 second project objective is a hypothesis worth testing, but literature provides no universal pass/fail from this study.
- `[P]` Human evaluation should compare naturally observed configurations under consent, with latency distributions and caption revisions recorded.

## R14 — Independent ASR scoring infrastructure

**Organization:** Hugging Face Audio Team, *Open ASR Leaderboard* (living technical benchmark), https://github.com/huggingface/open_asr_leaderboard . **Inspected:** README, evaluation scripts, normalization diagnostics. **Updated 2026;** runs use prescribed hardware, but historical runs need individually checked settings and checkpoint revisions. **English benchmark:** includes AMI, Earnings, GigaSpeech, LibriSpeech, etc.; scoring may use normalizers that alter numeric spellings.

- `[E-PUB]` Benchmark code distinguishes word error and inference RTFx; normalizer changes can affect rank and benchmarks may have imperfect references.
- `[I]` Must preserve each normalization version and manually adjudicate discrepant references; do not average unpaired leaderboards into project-specific accuracy.
- `[P]` Store reference/source/revision, normalized tokens, exact S/D/I alignment, per-domain micro-WER, unweighted domain macro-WER separately. Keep a raw WER view.

## R15 — W3C live caption requirements (accessibility context)

**Organization:** W3C WAI, *Understanding Success Criterion 1.2.4: Captions (Live)*. Official standards interpretation, https://www.w3.org/WAI/WCAG21/Understanding/captions-live . **Inspected:** criterion and intent. **Applicability:** guidance for live synchronized media, not an automatic regulatory conclusion for a private two-way educational call.

- `[E-PUB]` Live captions should represent synchronized audio content and, when relevant, identify speakers and significant audio cues. **No numerical WER=15% or lag=3 s threshold is specified there.**
- `[I]` Completeness/synchronization and speaker turns may matter beyond lexical WER.
- `[P]` Optionally capture speaker attribution and significant non-speech cue annotation as accessibility metrics; if there is no diarization system, mark unavailable rather than invent speakers.

## R16 — VAD implementation evidence (not a candidate ASR)

**Organization:** Silero, *silero-vad* official repository, https://github.com/snakers4/silero-vad . Living technical docs; inspected README and parameter/FAQ context. **Type:** optional segmentation utility, **NOT an additional ASR model candidate**.

- `[E-PUB]` VAD supports configurable speech/silence thresholds and padding affecting the endpoints of captured speech segments.
- `[I]` VAD may reduce wasted compute but may truncate initial/final words or add wait time at the end of an utterance.
- `[P]` Ablate VAD OFF vs ON under selected configurations; record VAD probabilities/threshold/padding and truncation/missing words; do not assert VAD universally improves ASR accuracy.

## R17 — Streaming decoder architecture background

**Title:** *Efficient Sequence Transduction by Jointly Predicting Tokens and Durations*. **Authors:** Hainan Xu, Fei Jia, Somshubra Majumdar, He Huang, Shinji Watanabe, Boris Ginsburg. **Year/status:** 2023 ICML peer-reviewed. https://proceedings.mlr.press/v202/xu23g.html . **Inspected in earlier specification:** title/abstract technical rationale; exact Parakeet checkpoint experimental results not reported here.

- `[E-PUB]` Transducer decoding can represent token durations, motivating different runtime behavior from seq2seq Whisper.
- `[I]` Decoder architecture is a reason to measure and profile rather than a guarantee of live latency; all numbers remain checkpoint/backend-specific.
- `[P]` Capture inference stage profile and emissions with optional token/duration telemetry only where API exposes it.

## Cross-source research-to-requirement conclusions

| Inference / requirement | Evidence basis | Research strength | Tool obligation |
|---|---|---|---|
| Never equate batch WER and short-chunk WER | R01, R06, R07 | high for NEED to test; not a transferable delta | paired batch-to-chunk evaluation |
| No universal WER <=15% acceptance | R11, R12, R13, R15 | absence of universal cutoff; project proposal | configurable acceptance plus task/human study |
| 2–3 sec is NOT confirmed live lag | R10, R13, R15 | proposed engineering target only | precise time origins, paint proxy, percentile + coverage |
| Compare on one common English corpus | R01, R04, R14 | strong experimental-design rationale | paired manifests, same normalization, stratification |
| Protect against lost semantics | R12, R14, R15 | strong for error-category recording | term, negation, unit, omission, reviewed severity |
| Test sustained performance | R01, R10 | derived real-time systems inference | queue backlog slope, per-chunk deadlines, dropout |
| Test noise/domain differences | R02, R04, R09 | vendor metrics plus foundational evidence | stratified held-out acoustic testing |
| Offline role requires final output and turnaround | R05, R08, R14 | directly relevant technical docs + engineering inference | full-session output and minutes-to-ready, resource measures |
| A model ID alone is not reproducibility | R01, R14 and software reproducibility practice | strong | checkpoint SHA, environment, config and source artifacts |

## Not in scope / explicit gaps

- No source examined establishes an across-application normative **15% live WER**, **3-second P95 word display lag**, or a **9% offline WER** requirement. All are project-specific proposals until user evidence and use-case objectives support them.
- No published source above measured these 9 precise checkpoints *on your hardware with your live UI*; their results are comparators and test motivations only.
- Some source cards provide per-dataset benchmarking but not every combination of preprocessing, beam, threads, quantization, timestamp origins and hardware: **mark these fields `not reported` until verified**.
- A paper's "streaming" mode may be a native stateful implementation, concatenated independent chunks, or a simulation. Record which.
- Existing test corpus drove model choice. It must not be presented as untouched held-out confirmation. Fresh real English conversation from the intended context is required.
- Public benchmarks are optional supplementary English tests, not a substitute for consented and representative classroom conversations.

