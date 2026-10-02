# Multimodal Facial Dataset Collector

Local Windows prototype for collecting synchronized data for future AI research.
It tracks one face inside a selected Meet/Zoom region and always stores facial
features and observable events. With explicit participant consent, it can also
record the selected region, meeting audio, microphone audio, and a delayed local
English transcript.

The application does not detect confusion, emotion, attention, engagement,
cognitive load, understanding, or identity. Current observable-action rules are
not training labels or psychological conclusions.

## For Reviewers

This is the data-collection stage of **AI-Assisted Real-Time Confusion Signal
Detection and Teaching Support for Lecturers**. No confusion classifier has been
trained or validated on this project's dataset.

1. [System handbook](docs/system-understanding-guide.md): architecture, algorithms,
   parameters, limitations, and evaluation roadmap.
2. [Dataset schema](docs/dataset-schema.md): session files and field meanings.
3. [Transcription methodology](docs/transcription-methodology.md): segmentation,
   timing, engineering choices, and evaluation.
4. [Documentation index](docs/README.md): current documentation and historical designs.

The handbook distinguishes code facts, historical measurements, and untested
hypotheses. Historical plans are not the current feature specification.

## Repository Layout

```text
facial-cue-prototype/
|-- README.md             # Overview and quick start
|-- requirements.txt      # Pinned direct Python dependencies
|-- src/                  # Desktop application and processing modules
|-- scripts/              # Model download utilities
|-- tests/                # Automated tests
|-- docs/                 # Technical documentation and reading guide
|   `-- superpowers/      # Historical plans and specifications
`-- models/              # Local downloads; weights are excluded from Git
```

Start reading code at [src/main.py](src/main.py), then
[src/app_controller.py](src/app_controller.py) for session coordination.
The handbook maps the other modules to their responsibilities.

## Requirements

- Windows 10 version 2004 or newer, or Windows 11.
- Python 3.12, 64-bit recommended.
- A participant who has explicitly consented to the selected data collection.
- Internet only during dependency/model setup. Normal processing is local.

## Install

Download or clone this repository and open PowerShell in its root folder
(the folder containing `requirements.txt`).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\scripts\download_face_landmarker_model.py
.\.venv\Scripts\python.exe .\scripts\download_whisper_model.py --model small.en
.\.venv\Scripts\python.exe .\scripts\download_whisper_model.py --model medium.en
```

The Whisper downloads are needed only for transcription. For facial-only use,
skip both Whisper commands. Runtime never silently downloads a missing model.
Live transcription prefers `small.en`, then an installed `base.en`. The final
pass prefers `medium.en`, then `small.en`, then `base.en`. Downloaded weights,
virtual environments, and generated recordings are excluded from Git.

## Run

```powershell
.\.venv\Scripts\python.exe .\src\main.py
```

## Use

1. Open a one-on-one Meet/Zoom call or consented test video.
2. Click **Select Region** and drag around only the student's video tile.
3. Click **Choose Save Folder**.
4. Enable optional video, meeting audio, microphone, and/or English transcript.
5. Optionally enter a pseudonymous participant ID. Do not enter a real name.
6. Check **Consent confirmed**.
7. Click **Start** and hold a stable forward pose during calibration.
8. Use **Pause/Resume** or `S`. Pause creates a real timestamp gap.
9. Click **Stop** before inspecting files. Use `Q` or `Escape` to quit.

Transcript appears beside the selected region after several seconds with a
`LIVE` marker. `small.en` is preferred for live recognition; the installed
`base.en` model remains the lower-latency fallback. Native
44.1/48 kHz audio is downmixed and resampled to the 16 kHz rate expected by
Whisper. Ongoing speech can reach a 12-second forced split with 0.75 seconds
of overlap to preserve words near a window boundary. `Student`
means Windows loopback audio; `You` means microphone. These describe technical
sources, not verified identities. Loopback may include notifications and other
applications routed to the same output device.

## Output

Each Start creates a new directory without overwriting old data:

```text
session_001/
|-- session.json
|-- features.csv
|-- audio.wav                 # when audio is enabled; left=You, right=Student
|-- transcript.jsonl          # when transcript is enabled; LIVE and FINAL rows
`-- video.mp4                 # optional
```

See [docs/dataset-schema.md](docs/dataset-schema.md) for field details.

## Live Transcript Accuracy and Delay

Live English transcription retains `small.en`, beam size 5 and four CPU threads.
After at least 1.2 seconds of buffered audio, Silero VAD checks for a 1 second
pause every 100 ms of new audio.
Each check examines only the latest 2 seconds; Whisper still receives the full
buffered utterance. Landmark overlay publication precedes CSV recording, and
UI callback batches are bounded so pending updates do not monopolize redraws.
Ongoing speech can use up to 12 seconds of context before a forced split with
750 ms overlap. This improves the input context but is not a measured accuracy
guarantee. Long uninterrupted speech can take 12 seconds plus inference time
to appear. Final transcription still uses the recorded audio.

Both live and final transcripts group recognized words across decoder segments
until an estimated inter-word gap of at least 1 second. Each row uses the first
and last word timestamps, excluding the silence used to confirm the endpoint.
These are pause-delimited utterances, not guaranteed grammatical sentences.
See [the report methodology notes](docs/transcription-methodology.md) for
principles, sources, parameter choices, limitations and the evaluation protocol.

The live queue holds 4096 capture packets (about 43 seconds with two 48 kHz
sources using 1024-sample packets), replacing the previous 24-packet queue.
It remains bounded: sustained overload can still drop audio from the live path.
Missing packet indices break the transcript buffer rather than joining speech
across a missing interval. The separate audio recording path is unchanged.
Gain is peak-limited to avoid introducing clipped peaks before recognition.

For a quality check, use the same consented English recording with a written
reference and compare live and final output. Unit tests verify buffering and
timing, not recognition quality for a particular speaker or accent.

## Automated Checks

The 2026-09-29 preparation run recorded **204 passing tests and 4 outstanding
tests** (2 failures, 2 errors). Dependency and compilation checks passed.
See [current verification details](docs/testing.md) before evaluating readiness.

These checks use fake frames/devices and do not activate camera or microphone:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
```

## Manual Hardware Test

See the [testing guide](docs/testing.md) for validation and reporting boundaries.

Use yourself or a participant who has consented:

1. Run facial-only and confirm landmarks/FPS remain responsive.
2. Enable video and confirm the MP4 contains only the selected region and no app UI.
3. Record both audio sources and verify `audio.wav` has You on the left channel
   and Student on the right channel.
4. Speak English for 10 seconds from each source and confirm delayed `Student`
   and `You` transcript entries appear beside the region.
5. Pause for five seconds, resume, and compare all timestamps.
6. Disable one audio device and confirm remaining components continue.
7. Click **Generate Final Transcript** and compare FINAL text with LIVE text.
8. Confirm `session.json` ends with `closed` and records errors/drops.

Do not claim hardware acceptance until these checks pass on the target computer.
