import threading
import unittest

from src.control_panel import TkCallbackQueue


class FakeRoot:
    def __init__(self):
        self.after_calls = []

    def after(self, delay_ms, callback):
        self.after_calls.append((delay_ms, callback, threading.get_ident()))


class TkCallbackQueueTests(unittest.TestCase):
    def test_callback_burst_yields_to_overlay_without_losing_work(self):
        root = FakeRoot()
        scheduler = TkCallbackQueue(root)
        called = []
        for index in range(100):
            scheduler.schedule(lambda index=index: called.append(index))
        root.after_calls[0][1]()
        self.assertGreater(len(called), 0)
        self.assertLess(len(called), 100)
        for _ in range(100):
            if len(called) == 100:
                break
            root.after_calls[-1][1]()
        self.assertEqual(called, list(range(100)))

    def test_background_schedule_does_not_call_tkinter(self):
        root = FakeRoot()
        main_thread = threading.get_ident()
        scheduler = TkCallbackQueue(root)
        called = []

        thread = threading.Thread(target=lambda: scheduler.schedule(lambda: called.append("done")))
        thread.start()
        thread.join()

        self.assertEqual(len(root.after_calls), 1)
        self.assertEqual(root.after_calls[0][2], main_thread)
        root.after_calls[0][1]()
        self.assertEqual(called, ["done"])
        self.assertEqual(len(root.after_calls), 2)
        self.assertEqual(root.after_calls[1][2], main_thread)


if __name__ == "__main__":
    unittest.main()
