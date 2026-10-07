# Session 014 technical review

Review date: 2026-10-06. Existing source and raw artifacts inspected; no application changes or new manual run.

## Stop outcome

The manifest records a clean closure: status `closed`, no errors, warnings or drops, transcript failure `null`, and all recorded components `stopped`. System audio and LIVE transcription were enabled; microphone and video were disabled. Execution was `spawn_process` with `cancel_without_flush`. Session duration was 51.3425579 s.

The previous Stop timeout is not recorded in this run. This supports successful closure under the intended policy, but the logs alone do not measure click-to-cleanup latency or establish visible UI responsiveness. `phase_at_stop=waiting_audio`: this session does not demonstrate cancellation during an active decode.

Manual feedback received on 2026-10-06: the user reported that the UI behaved normally. This supports satisfactory observed UI responsiveness in this run. The user did not separately confirm the absence of late transcript updates; that detail remains unobserved rather than a reported defect.

## Transcript coverage and quality

- Four committed LIVE segments were retained, ending at 40.4719133 s. Final transcription remains `not_started`.
- `coverage_complete=false`; the unprocessed system-audio interval is [40.611913333333035, 51.260579999999706], or 10.6486667 s. Decode coverage includes silence and differs from the last spoken-word timestamp. The interval may include speech and silence; it has not been listened to.
- Last completed-decode metrics: lag 6.0424315 s, RTF 0.4980981, queued system audio 5.9306667 s. These are one snapshot, not session averages or queue length at Stop. Pending audio can include buffering for a window/endpoint as well as queued work.
- Boundary repetition remains: segment 3 ends with "you are gonna read your", while segment 4 begins with "to read your line".
- The saved text includes "the second line". No accuracy judgment is made against the earlier reference excerpt because a verified reference covering this session is unavailable. WER was not calculated.

The incomplete tail is expected under cancellation without flushing; it is not by itself a transcription failure. A final transcript should only be generated on explicit user request.

## Audio and frame timing

The WAV is structurally readable: 48 kHz, stereo, 16-bit PCM, 2,460,508 frames, 51.2605833 s. Its frame count matches the manifest. This is not a listening-quality assessment or proof that all source samples were captured.

There are 858 feature rows and 859 timing rows: 783 rendered, 75 replaced, 1 stopped. The manifest records zero omitted and invalid-order frames. The final feature timestamp is 51.282 s, before the frozen Stop boundary. Capture dimensions are 1407 x 791, matching session 013.

| Metric | Session 014 |
|---|---:|
| Feature FPS | 16.8654 |
| Capture-to-post-action callback mean / p95 | 58.5416 / 75.2119 ms |
| Capture-to-render mean / p95 | 123.0004 / 164.5743 ms |

FPS = (feature rows - 1) / feature timestamp span. Callback latency uses `overlay_callback_s - capture_start_s` for 858 rows with the marker. Render latency uses `render_end_s - capture_start_s` for 783 rendered rows. Percentile 95 uses linear interpolation.

Callback latency measures computation through the post-action marker, not delay from actual gesture onset; smoothing and persistence need separate interpretation. Render latency ends when the Tk canvas call returns, not at physical display presentation. Session 013 had transcription disabled, so the two sessions are not a controlled attribution of performance differences to Whisper.

## Remaining work

The current Stop review can be closed based on clean session closure, the seven passing focused automated tests documented in `../immediate-stop-change-log.md`, and the user's normal-UI observation. No repeat manual run is requested. This is scoped acceptance of the reviewed Stop behavior, not exhaustive validation of every timing condition. Remaining LIVE transcript repetition, accuracy, and concurrent performance work are separate; this review does not declare the whole application complete.

## Raw SHA-256

- audio.wav: b9781db94ac002c2bae1879ebbe06eb5ade3860150c30d83b7660eb08e12dced
- features.csv: 819d979be7a79fc799daab287638e165de36a227a1ffbc9c24825aca2db98193
- landmark-timing.csv: 40daaac027bef54208cfe2de5a82f7a2a759e012c2971b9ff15957358ce4f319
- session.json: b1c6ae44bab81c17bb85839105311ea5a27457042e1ada516fd4d0c49ba45056
- transcript.jsonl: 142f2d119a654fd20c9058cd351f33c749aea2f0e106cae8e7e0036bc298cb8b
