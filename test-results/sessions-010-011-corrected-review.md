# Corrected review: sessions 010 and 011

Reviewed 2026-10-02. Authoritative data root: D:/@_Binh's document/AI Course/VANGIA_PROJECT/test-results.

## Folder/version correction

The earlier session 010 review used the separate VANGIAPROJECT workspace. Its 36.798 s / 781-frame session is not the current 65.163 s / 1427-frame session. All four raw-file hashes differ. Earlier report numbers and optimization attribution must not be transferred to this run.

Current source in the user-selected project has direct OpenCV BGRA conversion, but still allocates a full overlay background each frame and schedules an additional 16 ms after drawing. It lacks the background-cache and draw-budget optimizations made in the other workspace, and also lacks the recent transcript guards. Current source inspection does not independently establish capture-time source version. No code was changed or synchronized in this review. The 222-test pass from the other workspace does not validate this checkout.

## Session comparison

Same selected region: 1404 x 804 at (1443,288). System audio enabled; video/microphone disabled. Transcript disabled in 010 and enabled in 011. Both metadata files are closed with no reported errors or drops. Feature/timing frame IDs match throughout, with no timing capacity omissions or reported invalid timestamp orders.

| Metric | 010 | 011 |
| --- | ---: | ---: |
| Session duration (s) | 65.163 | 72.922 |
| Feature frames | 1427 | 1315 |
| Processing FPS | 22.239 | 20.458 |
| Mean processing_ms | 43.692 | 47.683 |
| Mean capture-to-action readiness (ms) | 44.294 | 48.247 |
| p95 capture-to-action readiness (ms) | 51.350 | 64.690 |
| Mean capture-to-render return (ms) | 94.210 | 105.289 |
| p95 capture-to-render return (ms) | 117.488 | 144.177 |
| Mean bitmap construction (ms) | 12.864 | 13.840 |
| Mean UI wait (ms) | 18.528 | 20.017 |
| Mean Tk image/canvas work (ms) | 18.386 | 22.541 |
| Rendered / replaced / pending at close | 1220 / 206 / 1 | 1105 / 209 / 1 |

Intervals are calculated per frame before aggregation; percentiles use NumPy default linear interpolation. Render metrics use rendered rows only. Differences show a modest computational slowdown during the transcript-enabled run, consistent with added load, but source/system load are uncontrolled and causality is not isolated. The user's observation of no noticeable landmark slowdown is compatible with these measurements. These are not physical display or gesture-onset latency measurements.

## Session 011 transcript comparison

Seven LIVE system-audio segments cover the provided reference passage. Concatenated transcript has 204 words against 198 reference words. Lowercase regex tokenization retains internal apostrophes and ignores punctuation. Word-level Levenshtein edit distance is 18, giving WER 9.09%. This includes going-to/gonna and contraction differences and must not be called a semantic error percentage.

Clear repeated boundary phrases are Well, other one, will be yours, and mutual friend. Those four neighboring segment pairs overlap in audio timestamps by 0.56, 0.65, 0.59 and 0.65 seconds. There is also an inserted of in go over of what. Main reference content is substantially retained; the supplied passage ends mid-sentence.

The configured maximum buffer is 12 s with 0.75 s overlap, minimum buffer 1.2 s, and speech-pause requirement 1.0 s. Decoding begins after endpoint confirmation or a forced maximum-length split. Existing publication checks only whether segment.end_s exceeds the previous cutoff, so a boundary-crossing segment can republish earlier words. Overlap/timestamp evidence and this code path support a boundary deduplication defect; generic low-confidence/repetition filters do not by themselves solve it.

Last metrics: buffer-end lag 3.379 s, RTF 0.446, queued duration zero, no transcript failure/dropped chunks. These describe only the last measured decode and cannot establish average/p95 live latency or absence of earlier backlog. No text-publication timestamp series exists to measure speech-end-to-visible-text delay.

## Manual feedback and decision

User reports improved/good landmark latency for 010. For 011, text appears after pauses and feels slow; landmarks do not feel slower, audio and Stop are good. Preserve these observations separately from measured timing.

Use this project and these sessions as the working reference. Next implementation should target overlapping-word publication and endpoint/buffer waiting, with accuracy and CPU-load checks. Do not blindly overwrite this project with the other copy. No additional recording is required just to repeat this comparison.

## Raw-file hashes

- session_010/audio.wav: `869ada89c8b540e598772e13a3c61393ce962ff8a113a1b28f425c3877f547db`
- session_010/features.csv: `b2ba8bb6a0830332e533f57fb52fa09f831e1264b277fe1c64a558f07eb32bbd`
- session_010/landmark-timing.csv: `5bc6b44a74474c9f72d0d8250292614726a3897071e85a0d6c522324ac6d6afa`
- session_010/session.json: `d3b9dd788cc25c6452df038b502a6476677c1db695a741c11e65b1776cb1b3df`
- session_011/audio.wav: `dbb292d23c6fa5d05a7962cba878050e6bcdd0b2428ac768489a5323cfb9de3b`
- session_011/features.csv: `5190931a37c235c5699caa73292f31495cba8dff901b747e45b023b2ebea38a4`
- session_011/landmark-timing.csv: `1ce0880f6795fa2e61a7bd955651d54fd749abbee76575270175be36bf76c567`
- session_011/session.json: `1c879d55f582bcfb20234d9d87af187750912c9d789f400bc91acd7ed7f7bd5d`
- session_011/transcript.jsonl: `d60585cce423c4ab7f5ffd707a7b0006b2d752d0f252a99859317135cb0c314a`
