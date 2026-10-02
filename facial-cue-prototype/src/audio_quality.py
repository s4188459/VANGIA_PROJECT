from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class AudioLevelState(str, Enum):
    NO_SIGNAL = "No signal"
    TOO_QUIET = "Too quiet"
    GOOD = "Good"
    CLIPPING = "Clipping"


@dataclass(frozen=True)
class AudioLevelMetrics:
    rms: float
    peak: float
    state: AudioLevelState


def analyze_level(samples: np.ndarray) -> AudioLevelMetrics:
    audio = np.asarray(samples, dtype=np.float32)
    if audio.size == 0:
        return AudioLevelMetrics(0.0, 0.0, AudioLevelState.NO_SIGNAL)
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
    peak = float(np.max(np.abs(audio)))
    if peak >= 0.98:
        state = AudioLevelState.CLIPPING
    elif rms < 0.0005:
        state = AudioLevelState.NO_SIGNAL
    elif rms < 0.01:
        state = AudioLevelState.TOO_QUIET
    else:
        state = AudioLevelState.GOOD
    return AudioLevelMetrics(rms, peak, state)


def prepare_inference_audio(
    samples: np.ndarray,
    *,
    target_rms: float = 0.10,
    max_gain: float = 8.0,
    limit: float = 0.98,
) -> tuple[np.ndarray, float]:
    audio = np.asarray(samples, dtype=np.float32).copy()
    metrics = analyze_level(audio)
    if metrics.rms < 0.0005:
        return audio, 1.0
    gain = min(max_gain, max(1.0, target_rms / metrics.rms), limit / metrics.peak)
    return np.clip(audio * gain, -limit, limit).astype(np.float32), float(gain)
