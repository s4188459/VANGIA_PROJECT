# Session 012 change log

## 2026-10-03 - Review only

- Saved the latest user reference and compared it with the six raw LIVE transcript segments in technical-review.md.
- Measured WER at 6.25% (12 edits / 192 reference words), identified boundary repetition and mine-to-line substitution.
- Recorded the transcript Stop timeout, incomplete status, and slower frame processing/rendering versus session 011.
- Documented latency measurement definitions and limits in technical-review.md.
- No source code changes or raw recording edits. No manual test observations inferred from logs.

## 2026-10-03 - Cause investigation

- Added cause-investigation.md with Stop control-flow analysis, per-stage timing comparison and a real-model offline replay of session 012 audio.
- Confirmed timeout cancellation and loss of persisted transcription metrics on the error path.
- Replay completed in 26.468 s and returned eight segments, including tail content absent from the six saved LIVE segments. Tail text is model output, not human ground truth.
- Identified concurrent resource contention as a hypothesis requiring measurements, not a proven root cause.
- Clarified that features_end_s precedes action detector.update; action readiness uses the later overlay_callback_s boundary.
- Ran the 21 existing transcription tests successfully. No production fixes or configuration changes in this investigation.
