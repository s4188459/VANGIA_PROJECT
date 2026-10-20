# Verified historical baseline facts (NOT live validation)

Original JSON experiment ID `e634c257ef69434383d580442820821e`, mode `final`, protocol `full-file-v1`.

Audio duration 3111.93575 seconds (51.865596 minutes), 100 English samples, 5024 normalized reference words as reported by the original scoring system. Whole-file inference; historical `chunk_seconds` option is not evidence of live splitting.

**Warning:** Below scores come from different CPU inference setups; they compare deployable *configurations*, not isolated checkpoint properties. Live latency, native streaming and per-word display lag were NOT measured. **Two errors have no valid WER.**

| Role | Exact candidate checkpoint | Legacy label | WER | RTF (whole-file) | Backend / precision / VAD | Status |
|---|---|---|---:|---:|---|---|
| live | `nvidia/parakeet-tdt-0.6b-v2` | `parakeet-tdt-0.6b-v2` | 11.2858% | 0.2534 | nemo / float32 / off | completed |
| live | `nvidia/parakeet-tdt-0.6b-v3` | `parakeet-tdt-0.6b-v3 [catalog]` | 12.6791% | 0.2655 | nemo / float32 / off | completed |
| live/offline | `Qwen/Qwen3-ASR-0.6B` | `Qwen3-ASR-0.6B` | 10.0717% | 0.7424 | qwen-asr / float32 / off | completed |
| live | `openai/whisper-small.en` | `small.en` | 15.1871% | 0.2002 | faster-whisper / int8 / on | completed |
| live | `openai/whisper-small` | `small [catalog]` | 15.4260% | 0.2752 | faster-whisper / int8 / on | completed |
| offline | `openai/whisper-large-v3` | `large-v3 [catalog]` | 9.1361% | 1.4236 | faster-whisper / int8 / on | completed |
| offline | `openai/whisper-large-v2` | `large-v2 [catalog]` | 9.8129% | 1.5071 | faster-whisper / int8 / on | completed |
| offline | `nvidia/canary-1b-v2` | `canary-1b-v2 [catalog]` | 10.1513% | 1.0691 | nemo / float32 / off | completed |
| offline | `openai/whisper-large-v3-turbo` | `turbo [catalog]` | 10.6887% | 1.0051 | faster-whisper / int8 / on | completed |
| diagnostic_retry | `Qwen/Qwen3-ASR-1.7B` | `Qwen3-ASR-1.7B [catalog]` | N/A | N/A | qwen-asr / float32 / off | error |
| diagnostic_retry | `facebook/mms-1b-all` | `mms-1b-all [catalog]` | N/A | N/A | transformers-ctc / float32 / off | error |

## Historical validity notes

- **Parakeet v2** 0.11285828 WER, 0.25339245 RTF; 100/100. **Whisper large-v3** 0.09136146 WER, 1.42361544 RTF; 100/100. These are whole-file scores only.
- **Whisper small.en** 15.1871% and **Whisper small** 15.4260% are ABOVE the provisional 15% threshold, and no result currently establishes that either meets live criteria.
- **Qwen3-ASR-1.7B:** Windows `[WinError 1314]` privilege error; **MMS-1B-all:** load/backend timeout. These are system/tool failures, NOT accuracy failures.
- Historic `faster-whisper` labels (`small.en`, `small`, `large-v2`, `large-v3`, `turbo`) must be resolved to weight hashes/revisions before claims of exact source checkpoint parity; other models have string model IDs recorded but no pinned revision.
- The historical JSON contains references, hypotheses and audio filenames/hashes, but not playable waveform data. Original EN001–EN100 recordings are required for replay and human review.
- Current default acceptance gates are design hypotheses, not peer-reviewed acceptance standards; user validation and new held-out English sessions are required for proof.
