from __future__ import annotations

from pathlib import Path

import mediapipe as mp


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "face_landmarker.task"
DOWNLOAD_COMMAND = (
    r".\.venv\Scripts\python.exe .\scripts\download_face_landmarker_model.py"
)


class FaceLandmarkerConfigurationError(RuntimeError):
    pass


def create_face_landmarker(
    model_path: Path = DEFAULT_MODEL_PATH,
    *,
    tasks=mp.tasks,
):
    path = Path(model_path)
    if not path.is_file():
        raise FaceLandmarkerConfigurationError(
            f"Missing MediaPipe model: {path}. Download face_landmarker.task with: "
            f"{DOWNLOAD_COMMAND}"
        )

    options = tasks.vision.FaceLandmarkerOptions(
        base_options=tasks.BaseOptions(model_asset_path=str(path)),
        running_mode=tasks.vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    )
    try:
        return tasks.vision.FaceLandmarker.create_from_options(options)
    except Exception as exc:
        raise FaceLandmarkerConfigurationError(
            f"Face Landmarker model is invalid or incompatible: {exc}"
        ) from exc
