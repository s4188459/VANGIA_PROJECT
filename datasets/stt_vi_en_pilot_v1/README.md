# Vietnamese-English recording pilot

This package contains 30 reading scripts and draft reference transcripts. It contains no recordings and is not yet a validated benchmark dataset.

## Files

- `RECORDING_SCRIPTS.md`: Vietnamese reading guide with all 30 passages.
- `transcripts/VI001.txt` through `VI030.txt`: UTF-8 draft references; edit after listening to the actual recordings.
- `audio/`: place your recordings here, using matching IDs, for example `VI001.wav` or `VI001.m4a`.
- `sample_metadata.json`: group labels and manually selected technical terms for review. These terms are not an automatic scoring configuration in the current tool.

## Recording procedure

1. Read each dialogue naturally, alternating the student (Con) and teacher (Thầy). Each dialogue has four turns, separated by blank lines. Aim roughly for 20–40 seconds, without padding silence or forcing the pace. Actual duration depends on the speaker; some passages may be shorter.
2. Use the microphone and speaking style expected in the application. Keep distance and room conditions reasonably consistent in the first pilot. Record natural English pronunciation within Vietnamese sentences; do not translate the English terms.
3. Read only the dialogue text, not its ID, heading, group, term list, or speaker labels. The TXT references omit speaker labels. Two speakers may record together; one speaker may also read both roles naturally. The first five passages have no English terms: for the technical smoke run, use VI001, VI011, VI018, VI026, and VI028 instead.
4. Say abbreviations naturally, preferably as letter names for this pilot. Preserve the spelling CPU, GPU, RAM, API, JSON, WER, and CER in the reference when those are the terms spoken. Record any spelling-equivalence decisions before comparing models. The current scorer does not automatically equate `GPU` with `G P U` or `JSON` with a phonetic spelling.
5. Listen to every recording and correct its TXT reference to match the actual words. Preserve genuine repetitions, corrections, and English terms. VI010 deliberately contains a spoken correction. If the recording is unusable, re-record it rather than treating the script as ground truth.
6. If you expand an abbreviation aloud, update the reference accordingly. Do not correct references to match a model's prediction. Spoken numbers here are written as words; the current scorer does not automatically normalize words and digits to the same form.
7. Keep original recordings. The tool normalizes imported audio for all models; avoid giving different preprocessing to different candidates.

## First technical run

Start with these five samples: **VI001, VI011, VI018, VI026, VI028**. This checks pure Vietnamese, mixed terminology, acronyms, sentence switching, and the live-latency topic. Create a ZIP containing only those five audio files and their five reviewed TXT files.

Import it as **Vietnamese / Vietnamese with English terms**. Use the Vietnamese-English Video set first to check that the models load and produce output. Five samples are not sufficient to rank model quality reliably.

## Full pilot

After the technical run works, import all 30 reviewed pairs. Run the Video set on whole files. Run the Live set twice, once with 1-second chunks and once with 2-second chunks. These are simulated chunk tests, not microphone-to-screen latency measurements.

Compare overall WER/CER and results for each group. Manually check whether the English terms were preserved, substituted, omitted, or translated. Predefine abbreviation equivalences; report the tool's raw score separately from any manually normalized term score. The term lists here are review targets, not a complete list of every English word in the passages.

This is a development pilot, not a final held-out test. After selecting candidates, record a new evaluation set with new wording and, where possible, additional speakers and accents. Do not claim broad Vietnamese-English performance from one speaker reading 30 scripts.

## ZIP layout

```text
audio/VI001.wav
...
audio/VI030.wav
transcripts/VI001.txt
...
transcripts/VI030.txt
```

WAV, MP3, M4A, FLAC, OGG, OPUS, AAC, and WebM are supported by the tool. Use exactly one recording per ID, with a matching TXT. The tool does not import an audio-free script pack as a dataset. No import-ready ZIP is supplied until recordings and reviewed references exist.

## Dialogue revision

Version 2 replaces the monologues with 30 teacher–student dialogues, each containing four turns. If you recorded the earlier scripts, those recordings do not match these revised draft references: record again or retain references matching the original audio. Do not replace the reference of an already recorded sample with this new wording.
