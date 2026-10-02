# Documentation Guide

## Current system

| Document | Purpose |
| --- | --- |
| [Project overview](../README.md) | Scope, installation, and demonstration |
| [System handbook](system-understanding-guide.md) | Module map, pipelines, algorithms, parameters, limitations, and roadmap |
| [Dataset schema](dataset-schema.md) | Session files, fields, and timing semantics |
| [Transcription methodology](transcription-methodology.md) | Speech segmentation, parameter choices, and evaluation |
| [Testing guide](testing.md) | Automated checks and manual hardware validation |

For a code review, begin with `src/main.py`, then `src/app_controller.py`.
Use the handbook's module map to follow the face, audio, and recording pipelines.
Tests are grouped by the corresponding module under `tests/`.

## Historical material

These documents preserve earlier design decisions. They may describe superseded
behavior or proposed work and should not be treated as the current feature list.

- [Facial output catalog](system-outputs-and-observable-actions.md): earlier
  facial-only pipeline and CSV event layout.
- [Design specifications](superpowers/specs/): dated architectural proposals.
- [Implementation plans](superpowers/plans/): dated development instructions.

The current source code is authoritative when a historical plan differs from
the implementation. Measurement claims must retain their test conditions.
