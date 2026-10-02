from enum import Enum, auto


EXIT_KEYS = {ord("q"), ord("Q"), 27}


class PreviewAction(Enum):
    NONE = auto()
    TOGGLE_PAUSE = auto()
    RESELECT = auto()
    QUIT = auto()


def face_status_text(face_detected: bool) -> str:
    return "Face detected" if face_detected else "Face not detected"


def format_fps(fps: float) -> str:
    return f"FPS: {fps:05.1f}"


def should_exit(key_code: int) -> bool:
    return key_code in EXIT_KEYS


def preview_action(key_code: int) -> PreviewAction:
    if key_code in {ord("s"), ord("S")}:
        return PreviewAction.TOGGLE_PAUSE
    if key_code in {ord("r"), ord("R")}:
        return PreviewAction.RESELECT
    if key_code in EXIT_KEYS:
        return PreviewAction.QUIT
    return PreviewAction.NONE
