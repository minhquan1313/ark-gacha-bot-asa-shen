import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from source.launcher.utils.update_schedule import UpdateSchedule


class UpdateScheduleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "check.json"
        self.now = datetime(2026, 9, 7, 23, 59, 59)

    def test_attempt_survives_restart_until_local_midnight(self):
        schedule = UpdateSchedule(self.path)
        self.assertTrue(schedule.is_due(self.now))
        schedule.record_attempt(self.now)
        restored = UpdateSchedule(self.path)
        self.assertFalse(restored.is_due(self.now))
        self.assertTrue(restored.is_due(self.now + timedelta(seconds=1)))
        self.assertTrue(restored.is_due(self.now + timedelta(days=3)))
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_invalid_cache_and_deleted_cache_allow_attempt(self):
        for content in ("broken", "[]", "null", "{}", '{"date":"bad"}',
                        '{"date":"2026-09-07","timestamp":"2026-09-06T12:00:00"}'):
            with self.subTest(content=content):
                self.path.write_text(content)
                self.assertTrue(UpdateSchedule(self.path).is_due(self.now))
        self.path.unlink()
        self.assertTrue(UpdateSchedule(self.path).is_due(self.now))

    def test_failed_persistence_still_limits_this_session(self):
        schedule = UpdateSchedule(self.path)
        with patch.object(Path, "replace", side_effect=OSError("read only")):
            with self.assertRaises(OSError):
                schedule.record_attempt(self.now)
        self.assertFalse(schedule.is_due(self.now))
        self.assertTrue(schedule.is_due(self.now + timedelta(days=1)))
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])
