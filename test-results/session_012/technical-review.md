# Session 012 technical review

Reviewed 2026-10-03. Compared the six saved LIVE segments with the latest user-provided reference, starting at 'today' and ending at 'we know that'. No application code or raw recording was changed.

## Transcript comparison

- Reference: 192 words; hypothesis: 202 words.
- Word-level Levenshtein distance: 12; WER: 6.25%.
- Normalize to lowercase; extract `[a-z]+(?:'[a-z]+)?`; ignore punctuation, retain internal apostrophes. Contraction expansion can count as edits without changing meaning. WER is not semantic accuracy.
- One optimal alignment has 10 insertions, 2 substitutions and 0 deletions. This does not certify completeness of the recording.

| Location | Expected | Saved output / issue |
|---|---|---|
| Segments 1-2 | because you asked for it | because you asked for / as you asked for it: repeated boundary words and added 'as' |
| Segment 3 | you're going to | you are going to: equivalent contraction expansion |
| Segment 4 | the second mine | the second line: recognition substitution |
| Segments 4-5 | ready lines and answers | ready lines in / lines and answers: extra words |
| Segments 5-6 | go through a dialogue | go through a / go through a dialogue: repeated boundary phrase |

The timed overlap deduplication did not eliminate these boundary repetitions. Segment text alone does not establish why individual words escaped the matching rule; word-level decoder traces would be needed. Session 011 WER was 9.09% against its own longer reference; the different reference boundaries and uncontrolled runtime conditions prevent a controlled before/after claim.

## Stop and runtime findings

Session status is `incomplete`. Transcript component reported: `Live transcription timed out on Stop; use final transcription for remaining audio`. Audio components and transcript store report stopped. Final transcription was not started. No transcript runtime metrics are saved under media_stats, so queue size, decoding RTF and end-to-end text display delay cannot be quantified for this run.

The last saved transcript endpoint is 70.856 s; the recorded audio interval ends at 84.077 s. This gap alone does not establish missing speech: the supplied text and saved segment timestamps are insufficient to determine what the remaining audio contains.

| Session | Feature FPS | Capture-to-features mean / p95 ms | Capture-to-render mean / p95 ms |
|---|---:|---:|---:|
| session_011 | 20.46 | 47.72 / 64.01 | 105.29 / 144.18 |
| session_012 | 10.43 | 93.72 / 122.03 | 224.54 / 306.96 |

Timing definitions: subtract capture_start_s from features_end_s for computational feature/action readiness; subtract capture_start_s from render_end_s for rendered frames only. The former is not gesture-onset latency and does not measure smoothing/persistence delay. The render boundary is return from Tk canvas itemconfigure, not physical screen presentation. FPS is (feature row count - 1) / (last timestamp - first timestamp). Percentiles use linear interpolation.

Session 012 has 784 timing records: 577 rendered, 206 replaced and 1 not rendered at close; zero invalid-order or omitted records. Replacement is a latest-frame policy outcome, not proof of audio loss. Processing/rendering were slower than session 011. CPU contention is a possible explanation, not an established cause. Region size also differs slightly (1405x807 versus 1404x804).

The recording confirms endpoint_pause_s=0.6, max_window_s=12.0 and overlap_deduplication=timed_suffix_prefix_v1. Next priority is diagnosing the Stop timeout and concurrent workload before calling the live change successful. No new subjective latency, audio or Stop observations were provided with this reference.

## User reference

today we're making another video where we're going to be practicing your speaking and conversational skills by having a conversation you and me well because you asked for it and I'm very glad that you love this format so let's go over what it's going to look like I have prepared a dialogue one line is for me and the other one is for you you will see them on the screen I'm going to say my line and you're going to read your line out loud on the screen and that's going to be your response and then vice versa the first line will be yours and the second mine this exercise will give you already ready lines and answers to use in real life with other people and get you prepared to have conversations in addition you might pick up a phrase or two and for this video I thought it'd be useful to go through a dialogue of two people meeting each other for the first time and let's say a mutual friend introduced them I believe that we've all been in such a situation and we know that

## Saved hypothesis

Today we're making another video where we're going to be practicing your speaking and conversational skills by having a conversation You and me well because you asked for as you asked for it, and I'm very glad that you love this format. So let's go over what it's going to look like. I have prepared a dialogue. One line is for me and the other one is for you. You will see them on the screen. I'm going to say my line and you are going to read your... line out loud on the screen and that's going to be your response and then vice versa. The first line will be yours and the second line. This exercise will give you already ready lines in lines and answers to use in real life with other people and get you prepared to have conversations. In addition, you might pick up a phrase or two. And for this video, I thought it'd be useful to go through a- go through a dialogue of two people meeting each other for the first time and let's say a mutual friend introduced them. I believe that we've all been in such a situation and we know that

## Raw SHA-256 hashes

- `audio.wav`: `723a601d3dc8e47fedfbd52371d0012c0a5b2dcbccb733d1c2a1173bdf3c5695`
- `features.csv`: `b346c328ce796328675a45176a964937ee1ad0cc0874b829ae38544609a248ff`
- `landmark-timing.csv`: `f8495a7e4bd00f014d31f8af1a7b1994428327546abea4e42cc8a9874b45d3a9`
- `session.json`: `3384843b36adc33f7b4e329650b38c596f43c8a9bb4724cf6a2a982564e576b7`
- `transcript.jsonl`: `77bf07528d02bf913a739859cf16b02060ec85d4e45684f9c08f4a9758eff09c`

## Follow-up investigation

See cause-investigation.md. Offline model replay found additional tail speech absent from LIVE JSON; the supplied reference and its WER cover only an excerpt. Also, features_end_s is before detector.update, so capture-to-features must not be described as completed action readiness. Use overlay_callback_s for the post-action-update boundary. No raw data was modified.
