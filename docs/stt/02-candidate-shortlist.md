# 2. Candidates for focused STT testing

The preliminary run narrows the next test round to **10 distinct checkpoints**:
5 live candidates and 6 offline candidates, with Qwen3-ASR-0.6B shared between
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
| `Qwen/Qwen3-ASR-1.7B` | offline | 8.2006 (recovery) | Not comparable; retest |
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
unsuitable.

## Update after recovery (2026-10-22)

Qwen 1.7B and MMS now both have 100/100 successful preliminary results.
Qwen 1.7B achieved WER 8.2006%, lower than the original best observed 9.1361%
from Whisper large-v3. It merits consideration as an additional offline candidate;
its speed must be retested because this recovery contains an extreme elapsed-time
observation. It is not a final selection. It is now enabled as an offline candidate in the new tool.

MMS achieved WER 37.7588% on this dataset, providing no accuracy-based reason to
promote it into the current shortlist. This is limited to the tested configuration
and corpus, not a universal rejection of MMS.

The registry and default experiment plan now include 10 primary candidates and
one diagnostic model (MMS). Qwen 1.7B is included in the Offline group without
requiring diagnostic opt-in. Original `legacy_*` fields preserve the failed
historical attempt; separate recovery fields record the successful rerun.
On the current machine its local weights, immutable revision/hash provenance and
Qwen worker environment pass preflight. No weights are downloaded automatically.

The earlier decision to use Qwen for live and Whisper large-v3 for final output
has been withdrawn. No replacement winner or one-model/two-model architecture
has been decided.

Next: [focused testing introduction](03-focused-testing-introduction.md).
