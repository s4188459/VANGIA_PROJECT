import os
import tempfile
import unittest

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "facial-cue-prototype-mpl"))
import mediapipe as mp
from mss import MSS


class DependencyCompatibilityTests(unittest.TestCase):
    def test_mediapipe_exposes_face_landmarker_tasks_api(self) -> None:
        self.assertTrue(hasattr(mp, "tasks"))
        self.assertTrue(hasattr(mp.tasks.vision, "FaceLandmarker"))

    def test_mss_constructor_is_available(self) -> None:
        self.assertTrue(callable(MSS))


if __name__ == "__main__":
    unittest.main()
