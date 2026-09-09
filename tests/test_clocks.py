import gc
import unittest
import weakref
from unittest.mock import patch

from source.utility import utils_simple


class ClockTests(unittest.TestCase):
    def setUp(self):
        registry = patch.object(utils_simple, "_live_clocks", weakref.WeakSet())
        registry.start()
        self.addCleanup(registry.stop)

    def test_reset_all_restarts_expired_and_long_clocks(self):
        with patch.object(utils_simple.time, "monotonic", return_value=100) as now:
            short = utils_simple.get_default_clock(3, multiplier=2)
            long = utils_simple.TimedOutCounter(900)
            now.return_value = 120
            self.assertTrue(short())
            self.assertFalse(long())

            utils_simple.reset_all_clocks()

            for clock, duration in ((short, 6), (long, 900)):
                self.assertEqual(clock.eslapsed(), 0)
                self.assertEqual(clock.remain(), duration)
                self.assertFalse(clock())
            now.return_value = 126
            self.assertTrue(short())
            self.assertEqual(long.eslapsed(), 6)

    def test_pause_adjustment_preserves_expired_and_active_clocks(self):
        with patch.object(utils_simple.time, "monotonic", return_value=100) as now:
            expired = utils_simple.TimedOutCounter(10)
            active = utils_simple.TimedOutCounter(180)
            now.return_value = 520
            utils_simple.adjust_clocks_after_pause(220, 520)
            self.assertTrue(expired())
            self.assertEqual(expired.remain(), -110)
            self.assertEqual(expired.eslapsed(), 120)
            self.assertFalse(active())
            self.assertEqual(active.remain(), 60)
            self.assertEqual(active.eslapsed(), 120)
            now.return_value = 579
            self.assertFalse(active())
            now.return_value = 580
            self.assertTrue(active())

    def test_registry_does_not_retain_discarded_clocks(self):
        clock = utils_simple.get_default_clock()
        reference = weakref.ref(clock)
        del clock
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(len(utils_simple._live_clocks), 0)
        utils_simple.reset_all_clocks()
        utils_simple.adjust_clocks_after_pause(100, 200)
