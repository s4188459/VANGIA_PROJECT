import tempfile
import unittest
import threading
from pathlib import Path
import numpy as np

from src.video_recorder import CapturedVideoFrame, VideoRecorder


class FakeWriter:
    def __init__(self): self.frames = []; self.released = False
    def isOpened(self): return True
    def write(self, frame): self.frames.append(frame.copy())
    def release(self): self.released = True


class VideoRecorderTests(unittest.TestCase):
    def test_confirms_video_index_only_after_write(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = FakeWriter()
            mappings = []
            recorder = VideoRecorder(
                Path(directory) / "v.mp4", (4, 3), writer_factory=lambda *_: writer,
                mapping_callback=lambda *args: mappings.append(args),
            )
            recorder.start()
            self.assertIsNone(recorder.submit(CapturedVideoFrame(7, 1.25, np.zeros((3, 4, 3), np.uint8))))
            recorder.stop()
            self.assertEqual(len(writer.frames), 26)
            self.assertEqual(mappings, [(7, 25)])
            self.assertFalse((Path(directory) / "t.csv").exists())

    def test_irregular_capture_and_pause_preserve_session_duration(self):
        writer = FakeWriter(); mappings = []
        recorder = VideoRecorder(Path("unused.mp4"), (4, 3), fps=10,
                                 writer_factory=lambda *_: writer,
                                 mapping_callback=lambda *a: mappings.append(a))
        recorder.start()
        frame = np.ones((3, 4, 3), np.uint8)
        recorder.submit(CapturedVideoFrame(0, 0, frame))
        recorder.submit(CapturedVideoFrame(1, .02, frame))
        recorder.submit(CapturedVideoFrame(2, .3, frame * 2))
        recorder.pause(.5)
        recorder.resume(1.0)
        recorder.submit(CapturedVideoFrame(3, 1., frame * 3))
        stats = recorder.stop(timestamp_s=1.2)
        self.assertEqual(stats.written_frames, 12)
        self.assertEqual(mappings, [(0, 0), (2, 3), (3, 10)])
        self.assertTrue(all(not image.any() for image in writer.frames[5:10]))

    def test_stop_drains_full_queue_without_releasing_writer_early(self):
        entered = threading.Event(); release = threading.Event()
        class SlowWriter(FakeWriter):
            def write(self, frame):
                entered.set(); release.wait(2); super().write(frame)
        writer = SlowWriter(); mappings = []
        recorder = VideoRecorder(Path("unused.mp4"), (4, 3), queue_size=1,
                                 writer_factory=lambda *_: writer,
                                 mapping_callback=lambda *a: mappings.append(a))
        recorder.start()
        frame = np.zeros((3, 4, 3), np.uint8)
        recorder.submit(CapturedVideoFrame(0, 0., frame))
        self.assertTrue(entered.wait(1))
        recorder.submit(CapturedVideoFrame(1, .05, frame))
        recorder.submit(CapturedVideoFrame(2, .1, frame))
        stopper = threading.Thread(target=recorder.stop)
        stopper.start()
        self.assertFalse(writer.released)
        release.set(); stopper.join(3)
        self.assertFalse(stopper.is_alive())
        self.assertEqual(mappings, [(0, 0), (1, 1)])
        self.assertTrue(writer.released)

    def test_failed_write_never_confirms_source_frame(self):
        class BrokenWriter(FakeWriter):
            def write(self, frame): raise OSError("disk full")
        mappings = []
        recorder = VideoRecorder(Path("unused.mp4"), (4, 3), writer_factory=lambda *_: BrokenWriter(),
                                 mapping_callback=lambda *a: mappings.append(a))
        recorder.start()
        recorder.submit(CapturedVideoFrame(0, 0., np.zeros((3, 4, 3), np.uint8)))
        stats = recorder.stop()
        self.assertEqual(mappings, [])
        self.assertIn("disk full", stats.failure)


if __name__ == "__main__": unittest.main()
