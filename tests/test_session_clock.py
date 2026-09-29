import unittest

from src.session_clock import SessionClock


class FakeClock:
    def __init__(self, values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


class SessionClockTests(unittest.TestCase):
    def test_clock_uses_one_origin_and_keeps_advancing(self):
        clock = SessionClock(clock=FakeClock([100.0, 101.25, 104.0]))
        clock.start()
        self.assertEqual(clock.elapsed_s(), 1.25)
        self.assertEqual(clock.elapsed_s(), 4.0)

    def test_start_is_single_use(self):
        clock = SessionClock(clock=FakeClock([10.0]))
        clock.start()
        with self.assertRaises(RuntimeError):
            clock.start()


if __name__ == "__main__":
    unittest.main()
