from pathlib import Path
import tempfile
import unittest

from src.face_landmarker import (
    FaceLandmarkerConfigurationError,
    create_face_landmarker,
)


class FakeOptions:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeLandmarkerType:
    options = None
    result = object()
    error = None

    @classmethod
    def create_from_options(cls, options):
        cls.options = options
        if cls.error:
            raise cls.error
        return cls.result


class FakeVision:
    class RunningMode:
        VIDEO = "video"

    FaceLandmarkerOptions = FakeOptions
    FaceLandmarker = FakeLandmarkerType


class FakeTasks:
    vision = FakeVision
    BaseOptions = FakeOptions


class FaceLandmarkerFactoryTests(unittest.TestCase):
    def setUp(self):
        FakeLandmarkerType.error = None
        FakeLandmarkerType.options = None

    def test_configures_video_blendshapes_matrix_and_one_face(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "face_landmarker.task"
            model.write_bytes(b"model")

            result = create_face_landmarker(model, tasks=FakeTasks)

            options = FakeLandmarkerType.options
            self.assertIs(result, FakeLandmarkerType.result)
            self.assertEqual(options.running_mode, "video")
            self.assertEqual(options.num_faces, 1)
            self.assertTrue(options.output_face_blendshapes)
            self.assertTrue(options.output_facial_transformation_matrixes)
            self.assertEqual(options.min_face_detection_confidence, 0.5)
            self.assertEqual(options.min_face_presence_confidence, 0.5)
            self.assertEqual(options.min_tracking_confidence, 0.5)
            self.assertEqual(options.base_options.model_asset_path, str(model))

    def test_missing_model_error_contains_setup_command(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "face_landmarker.task"

            with self.assertRaises(FaceLandmarkerConfigurationError) as context:
                create_face_landmarker(missing, tasks=FakeTasks)

            message = str(context.exception)
            self.assertIn("face_landmarker.task", message)
            self.assertIn("download_face_landmarker_model.py", message)

    def test_invalid_model_error_is_wrapped(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "face_landmarker.task"
            model.write_bytes(b"invalid")
            FakeLandmarkerType.error = RuntimeError("bad bundle")

            with self.assertRaisesRegex(
                FaceLandmarkerConfigurationError, "invalid.*bad bundle"
            ):
                create_face_landmarker(model, tasks=FakeTasks)


if __name__ == "__main__":
    unittest.main()
