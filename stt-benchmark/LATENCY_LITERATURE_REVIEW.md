# Live transcription latency: evidence and validation plan

Research date: 2026-10-14. Language: English. This is a focused literature scan, not a systematic review.

## Conclusion

Treat **2–3 seconds as a provisional engineering target**, not a demonstrated result or a universally acceptable UX threshold. We need both end-to-end measurements on the deployment device and a task-specific user evaluation. Limited hardware explains a tradeoff; it does not itself establish that users find the delay acceptable.

## What our benchmark actually establishes

Source: [existing model analysis](MODEL_SELECTION.md), run `e634c257ef69434383d580442820821e` (100 English samples, 3,111.94 seconds of audio, whole-file `final` / `full-file-v1`, CPU with four configured threads).

| Model | Aggregate WER | RTF | Approximate inference time per hour of audio |
| --- | ---: | ---: | ---: |
| Whisper large-v3 | 9.14% | 1.424 | 85.4 minutes |
| Qwen3-ASR-0.6B | 10.07% | 0.742 | 44.5 minutes |
| Parakeet-TDT-0.6B-v2 | 11.29% | 0.253 | 15.2 minutes |

These extrapolations exclude model loading, video extraction and export. The interrupted/resumed run is not a repeated controlled timing experiment. Live latency fields are empty. RTF below one indicates whole-file throughput; it does not prove 2–3-second visible caption delay. Chunking, repeated decoding, buffering and rendering can change both speed and WER.

Whisper large-v3 remains the accuracy-first video candidate. Qwen is a faster video alternative and a live candidate requiring validation. The existing English analysis actually prioritizes Parakeet v2 for live evaluation. None is yet confirmed to meet the live latency target. English results do not validate Vietnamese or mixed Vietnamese-English speech.

Report WER directly. For Qwen, 100% minus WER is 89.93%, but this is not a probability of word correctness or a measure of comprehension.

## Evidence register

### 1. Technical streaming baseline: Machacek, Dabre and Bojar (2023)

**Turning Whisper into Real-Time Transcription System.** IJCNLP-AACL System Demonstrations, pp. 17–24. DOI: [10.18653/v1/2023.ijcnlp-demo.3](https://doi.org/10.18653/v1/2023.ijcnlp-demo.3). [Publisher record](https://aclanthology.org/2023.ijcnlp-demo.3/). [Local PDF](research/papers/machacek_2023_whisper_streaming.pdf).

The paper reports about 3.3 seconds average latency for English ESIC transcription on an NVIDIA A40 GPU, using Whisper large-v2 with a streaming agreement policy. Its computationally aware metric accounts for processing time and aligns emitted words with reference timing. See the introduction and evaluation sections.

Use this as a technical precedent for a seconds-scale streaming target. It does not demonstrate user acceptance of a particular delay, CPU feasibility, or performance of our large-v3/Qwen adapters. Mean latency is also not equivalent to a p95 requirement.

### 2. Caption user experience: Arroyo Chavez et al. (2024)

**How Users Experience Closed Captions on Live Television: Quality Metrics Remain a Challenge.** CHI 2024; author manuscript on arXiv. DOI: [10.1145/3613904.3641988](https://doi.org/10.1145/3613904.3641988). [Record](https://arxiv.org/abs/2404.10153). [Local PDF](research/papers/arroyo_chavez_2024_caption_experience.pdf).

The mixed-methods study includes deaf, hard-of-hearing and hearing viewers. Accuracy-oriented metrics correlated weakly with subjective quality ratings; following the captions and their appearance also mattered. This supports evaluating comprehension and presentation alongside WER. It does not establish a universal 2–3-second acceptance threshold. This note draws on the abstract; consult the full manuscript before discussing detailed experimental results.

### 3. General interaction guidance: Nielsen (1993)

**Response Times: The 3 Important Limits.** [Original NN/g article](https://www.nngroup.com/articles/response-times-3-important-limits/), excerpt from *Usability Engineering*.

The guidance distinguishes roughly 0.1 seconds for instantaneous feedback, 1 second for uninterrupted flow, and 10 seconds for maintaining attention. This is general HCI guidance, not a controlled live-caption study. Being below ten seconds does not mean a delay is good. Apply immediate feedback to recording controls and visible processing status; evaluate ongoing caption delay separately. The article is linked, not archived as a research paper.

### 4. Exploratory counter-evidence: Liaqat (2018)

**Evaluating Usability of a Real Time Augmented Reality Audio Captioning System.** University of Toronto CSC2526 course report, author-hosted manuscript. [Original PDF](https://www.cs.toronto.edu/~sliaqat/augmented_reality_glasses.pdf). [Local PDF](research/papers/liaqat_2018_ar_captioning_course_report.pdf).

Section 4.1 reports mean noticeable, annoying and unusable delays of 1.05, 2.15 and 3.35 seconds, respectively. However, there were only five participants, none deaf or hard of hearing, and delays increased in a fixed sequence. The manuscript contains placeholder publication metadata; do not present it as a verified peer-reviewed ACM paper. It is exploratory counter-evidence against declaring 2–3 seconds universally comfortable, not a reliable population threshold.

## Define latency before reporting it

| Metric | Start | End | Purpose |
| --- | --- | --- | --- |
| Control feedback | User presses Record | UI shows recording state | Interface responsiveness |
| Time to first text | First speech onset | First visible partial caption | Initial wait |
| Stable-word delay | End of the spoken reference word | Corresponding stable word is rendered | Ongoing caption lag |
| Finalization delay | End of utterance | Final transcript is rendered | Wait after speaking |
| Video completion time | Upload accepted / local processing requested | Complete transcript available | Whole-job wait; specify upload inclusion |

Use a common clock or synchronized audio/UI capture. State the reference alignment convention, excluded words and alignment coverage. Incorrect or deleted words must remain visible in WER reporting; do not quietly omit difficult cases to improve latency. Distinguish partial text that may change from stable text. Current chunk replay metrics are useful diagnostics but do not include the entire microphone-to-screen path.

## Next experiment on our device

1. Preserve the existing run and create separate live runs. Compare Qwen3-ASR-0.6B with Parakeet v2 on the same 100 English clips, replayed at real-time speed; keep large-v3 as the offline quality baseline. Start with one-second and two-second chunk configurations, documenting overlap, context, VAD and finalization rules.
2. Record CPU/GPU, RAM, OS, package versions, precision, thread counts, model revision and power mode. Use the actual deployment laptop; distinguish it from the A40 research setup. Measure loading separately and test warm operation under realistic application load.
3. Measure median, p95 and maximum first-text and stable-word delays, finalization delay, queue growth, WER, failures and memory. Include sustained 10–15-minute sessions to detect accumulating backlog. Repeat timing runs at least three times with model order varied.
4. Proposed engineering gate, **not a literature-derived standard**: p95 stable-word delay at most 3 seconds, WER at most 15% on the live protocol, and no sustained queue growth. Aim for faster first text and record it separately. A mean of 2–3 seconds alone does not satisfy this gate.
5. Run a small formative study with intended users doing the intended lecture/conversation task. Compare controlled delays (for example 1, 2, 3 and 5 seconds) with equivalent caption accuracy and presentation, counterbalance order, and measure comprehension, missed turns and perceived acceptability. Separately evaluate the actual model outputs, including revisions. A convenience pilot identifies issues; it does not establish a population-wide threshold.
6. Select the model based on the observed accuracy/latency tradeoff. Report failures honestly. Run Vietnamese-English evaluation separately before making multilingual claims.

## Suggested message to the supervisor

> I checked the distinction between throughput and latency. Our current 100-sample English benchmark measures whole-file WER and RTF; it does not yet verify 2–3-second live caption latency. I should describe 2–3 seconds as our target. Whisper-Streaming provides a technical precedent around 3.3 seconds on an A40 GPU, but that does not establish user acceptance or performance on our laptop. I have saved the papers and will measure end-to-end median/p95 latency and WER on our device, then evaluate whether the delay is acceptable for our intended task.

## Literature-review wording

Prior work motivates evaluating streaming recognition through both transcription quality and delivery delay. However, technical latency results, general interaction guidance and caption-user studies answer different questions. Accordingly, this project treats a three-second p95 stable-caption target as a design hypothesis to validate on the deployment hardware and with intended users, rather than an established universal usability threshold.

PDF originals are retained for research reading in `research/papers/`. Follow their individual licenses when redistributing. No existing benchmark results were changed for this review.
