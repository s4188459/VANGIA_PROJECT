from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


class ComponentState(str, Enum):
    OFF = "off"
    STARTING = "starting"
    RECORDING = "recording"
    PAUSED = "paused"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass(frozen=True)
class ComponentStatus:
    component: str
    state: ComponentState
    message: str = ""


@dataclass(frozen=True)
class SessionOptions:
    video: bool = False
    system_audio: bool = False
    microphone: bool = False
    transcript: bool = False
    consent_confirmed: bool = False
    participant_id: str = ""

    def __post_init__(self) -> None:
        participant_id = self.participant_id.strip()
        if len(participant_id) > 64 or ".." in participant_id or not re.fullmatch(
            r"[A-Za-z0-9 _-]*", participant_id
        ):
            raise ValueError("Participant ID may contain letters, numbers, spaces, _ and -")
        object.__setattr__(self, "participant_id", participant_id)

    @property
    def persistent_capture_enabled(self) -> bool:
        return True

    def validation_error(self) -> str | None:
        if not self.consent_confirmed:
            return "Confirm participant consent"
        if self.transcript and not (self.system_audio or self.microphone):
            return "Transcript requires meeting audio or microphone"
        return None
