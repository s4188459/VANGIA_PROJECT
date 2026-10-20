# 2. Candidates for focused STT testing

The preliminary run narrows the next test round to **9 distinct checkpoints**:
5 live candidates and 5 offline candidates, with Qwen3-ASR-0.6B shared between
the two groups. This is the shortlist already configured in the new tool's
[model registry](../../vangia-asr-lab/config/model_registry.json), not a final
selection or proof that these models meet deployment requirements.

The live group explores quality and processing headroom; the offline group
focuses on accuracy and processing turnaround. It is a comparison plan rather
than a mechanical top-N ranking or a universal acceptance threshold.

| Candidate checkpoint | Next test role | Historical WER (%) | Historical RTF |
|---|---|---:|---:|
| `nvidia/parakeet-tdt-0.6b-v2` | live | 11.2858 | 0.2534 |
| `nvidia/parakeet-tdt-0.6b-v3` | live | 12.6791 | 0.2655 |
| `Qwen/Qwen3-ASR-0.6B` | live / offline | 10.0717 | 0.7424 |
| `openai/whisper-small.en` | live | 15.1871 | 0.2002 |
| `openai/whisper-small` | live | 15.4260 | 0.2752 |
| `openai/whisper-large-v3` | offline | 9.1361 | 1.4236 |
| `openai/whisper-large-v2` | offline | 9.8129 | 1.5071 |
| `nvidia/canary-1b-v2` | offline | 10.1513 | 1.0691 |
| `openai/whisper-large-v3-turbo` | offline | 10.6887 | 1.0051 |

Parakeet v2/v3 and Whisper small variants provide useful live speed/quality
comparisons. Qwen 0.6B bridges the live/offline groups. Whisper large-v3/large-v2,
Canary v2 and Whisper turbo provide offline accuracy/turnaround comparisons.
Whisper small.en and small exceed the provisional 15% WER target in the old run;
they are comparison candidates, not models that have passed that target.

The other successful configurations remain visible in the complete preliminary
results. Omission from this shortlist is not a universal claim that a model is
unsuitable. Qwen 1.7B and MMS remain optional diagnostic retries only; they cannot
be ranked on accuracy until they run successfully.

The earlier decision to use Qwen for live and Whisper large-v3 for final output
has been withdrawn. No replacement winner or one-model/two-model architecture
has been decided.

Next: [focused testing introduction](03-focused-testing-introduction.md).
