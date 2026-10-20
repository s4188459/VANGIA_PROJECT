# 1. Preliminary STT results ? old web tool

This is the complete historical screening run, not a final model decision.
The old tool (`stt-benchmark/`) evaluated **27 configurations** on the same
100 English recordings: **25 completed and 2 failed**. Total audio duration was
3,111.94 seconds (51.87 minutes), with 5,024 normalized reference words.
Run ID: `e634c257ef69434383d580442820821e`; mode: `final`; protocol: `full-file-v1`.

Source: [original summary CSV](../../stt-benchmark/Testing_STT_Model_English_Version.csv).
[Original per-sample JSON](../../Vangia_ASR_Selection_Codex_Package/data/legacy/STT-EN(1).json)
is retained for traceability and the new tool's historical importer.

## All tested configurations

WER/CER below are percentages. RTF is inference time divided by audio duration;
loading is reported separately in the source CSV. A dash means no valid result.

| Configuration | Backend | Completed / 100 | WER (%) | CER (%) | RTF | Status |
|---|---|---:|---:|---:|---:|---|
| base.en | faster-whisper | 100 | 22.1537 | 11.4818 | 0.0663 | completed |
| small.en | faster-whisper | 100 | 15.1871 | 7.6860 | 0.2002 | completed |
| Vosk small EN | vosk | 100 | 55.3344 | 27.6506 | 0.1282 | completed |
| Qwen3-ASR-0.6B | qwen-asr | 100 | 10.0717 | 4.5535 | 0.7424 | completed |
| parakeet-tdt-0.6b-v2 | nemo | 100 | 11.2858 | 5.8449 | 0.2534 | completed |
| SenseVoiceSmall | sensevoice | 100 | 21.1584 | 10.1433 | 0.1358 | completed |
| tiny.en [catalog] | faster-whisper | 100 | 33.7381 | 18.4259 | 0.0582 | completed |
| medium.en [catalog] | faster-whisper | 100 | 12.0223 | 5.8175 | 0.7675 | completed |
| tiny [catalog] | faster-whisper | 100 | 29.7373 | 15.0815 | 0.0573 | completed |
| base [catalog] | faster-whisper | 100 | 22.9498 | 11.5407 | 0.0961 | completed |
| small [catalog] | faster-whisper | 100 | 15.4260 | 7.7527 | 0.2752 | completed |
| medium [catalog] | faster-whisper | 100 | 11.3256 | 5.5741 | 0.7755 | completed |
| large-v1 [catalog] | faster-whisper | 100 | 10.8081 | 5.7193 | 1.3830 | completed |
| large-v2 [catalog] | faster-whisper | 100 | 9.8129 | 5.1973 | 1.5071 | completed |
| large-v3 [catalog] | faster-whisper | 100 | 9.1361 | 4.5613 | 1.4236 | completed |
| turbo [catalog] | faster-whisper | 100 | 10.6887 | 5.2090 | 1.0051 | completed |
| distil-small.en [catalog] | faster-whisper | 100 | 20.6608 | 11.4033 | 0.2198 | completed |
| distil-medium.en [catalog] | faster-whisper | 100 | 24.2038 | 15.7959 | 0.5505 | completed |
| distil-large-v2 [catalog] | faster-whisper | 100 | 15.1672 | 7.8665 | 0.9410 | completed |
| distil-large-v3 [catalog] | faster-whisper | 100 | 15.2866 | 8.1256 | 1.0434 | completed |
| distil-large-v3.5-ct2 [catalog] | faster-whisper | 100 | 12.1019 | 5.9823 | 0.9329 | completed |
| Qwen3-ASR-1.7B [catalog] | qwen-asr | 0 | ? | ? | ? | error |
| parakeet-tdt-0.6b-v3 [catalog] | nemo | 100 | 12.6791 | 5.8999 | 0.2655 | completed |
| canary-1b-v2 [catalog] | nemo | 100 | 10.1513 | 4.8911 | 1.0691 | completed |
| wav2vec2-large-960h-lv60-self [catalog] | transformers-ctc | 100 | 35.9076 | 13.5388 | 0.5281 | completed |
| mms-1b-all [catalog] | transformers-ctc | 0 | ? | ? | ? | error |
| vosk-model-en-us-0.22 [catalog] | vosk | 100 | 39.6696 | 20.2787 | 0.6485 | completed |

## Interpretation and limits

These are deployment-configuration comparisons on CPU, configured with four
threads. Backends, precision, beam and VAD differ (for example faster-whisper
INT8 versus NeMo/Qwen float32). The run was interrupted and resumed. Timing is
historical whole-file evidence, not a controlled repeated latency study.

Qwen3-ASR-1.7B failed with a Windows privilege error; MMS-1B-all hit a backend
timeout. Neither has a valid accuracy score. Their failure is not evidence of
poor recognition quality. The CSV's common-sample intersection is zero because
it includes these failed configurations; each successful configuration completed
100 samples.

No live word-display delay was established. RTF below 1 does not prove that
captions meet a latency target, and 100% minus WER is not comprehension accuracy.
These recordings were used for screening and cannot become an untouched final
test set. Local checkpoint aliases still require revision/hash verification.

Next: [candidate shortlist](02-candidate-shortlist.md).
