import json
import os
import tempfile
import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import patch

from source.launcher.constants import MAX_LAUNCHER_LOG_LINES
from source.launcher.gui import SettingsGUI


class LauncherLogTests(unittest.TestCase):
    def setUp(self):
        self.launcher = SimpleNamespace(
            queue_snapshot={"running": [], "active": [], "waiting": []},
            running_history=[],
            running_task_name=None,
            log_lines=[],
            current_filter="ALL",
            active_count=0,
            waiting_count=0,
            log_file_position=50,
            _render_logs=lambda: None,
        )
        for method_name in [
            "_filtered_logs",
            "_format_queue_snapshot",
            "_format_running_snapshot",
            "_update_queue_snapshot",
        ]:
            method = getattr(SettingsGUI, method_name)
            setattr(self.launcher, method_name, MethodType(method, self.launcher))
        self.launcher._normalize_file_log_line = SettingsGUI._normalize_file_log_line

    def append_snapshot(self, snapshot):
        SettingsGUI.append_log(self.launcher, f"[QUEUE_STATE] {json.dumps(snapshot)}")

    @patch("source.launcher.gui.time.time", return_value=100)
    def test_queue_snapshot_lists_soonest_task_last_before_running_task(self, _):
        self.launcher.queue_snapshot = {
            "running": [{"name": "current"}],
            "active": [
                {"name": "ready", "execution_time": 90, "state": "READY"},
            ],
            "waiting": [
                {"name": "later", "execution_time": 130, "state": "WAITING"},
                {"name": "sooner", "execution_time": 110, "state": "WAITING"},
            ],
        }

        self.assertEqual(
            self.launcher._format_queue_snapshot(),
            [
                "[QUEUE] 00:00:30  later",
                "[QUEUE] 00:00:10  sooner",
                "[QUEUE] READY     ready",
                "[QUEUE] RUNNING   current",
            ],
        )

    def test_running_history_records_transitions_and_ignores_duplicate_snapshots(self):
        running = {
            "running": [{"name": "gacha"}],
            "active": [],
            "waiting": [],
        }
        idle = {"running": [], "active": [], "waiting": []}

        self.append_snapshot(running)
        self.append_snapshot(running)
        self.append_snapshot(idle)
        self.append_snapshot(running)

        self.assertEqual(
            self.launcher.running_history,
            ["[RUNNING] STARTED   gacha", "[RUNNING] STARTED   gacha"],
        )

    def test_running_filter_shows_history_and_current_task(self):
        self.launcher.running_history = ["[RUNNING] STARTED   gacha"]
        self.launcher.queue_snapshot["running"] = [{"name": "berry"}]
        self.launcher.current_filter = "RUNNING"

        self.assertEqual(
            self.launcher._filtered_logs(),
            ["[RUNNING] STARTED   gacha", "[RUNNING] CURRENT   berry"],
        )

    def test_running_filter_shows_idle_without_current_task(self):
        self.launcher.current_filter = "RUNNING"

        self.assertEqual(self.launcher._filtered_logs(), ["[RUNNING] IDLE"])

    def test_clear_logs_removes_running_history(self):
        self.launcher.log_lines = ["[INFO] retained log"]
        self.launcher.running_history = ["[RUNNING] STARTED   gacha"]
        self.launcher.queue_snapshot = {
            "running": [{"name": "gacha"}],
            "active": [{"name": "berry"}],
            "waiting": [{"name": "pego"}],
        }
        self.launcher.running_task_name = "gacha"

        with tempfile.NamedTemporaryFile(delete=False) as temp_log:
            temp_log.write(b"previous log")
            temp_log_path = temp_log.name
        self.addCleanup(lambda: os.path.exists(temp_log_path) and os.remove(temp_log_path))

        with patch("source.launcher.gui.GACHA_LOG_FILE", temp_log_path):
            SettingsGUI.clear_logs(self.launcher)

        self.assertEqual(self.launcher.log_lines, [])
        self.assertEqual(self.launcher.running_history, [])
        self.assertEqual(
            self.launcher.queue_snapshot, {"running": [], "active": [], "waiting": []}
        )
        self.assertIsNone(self.launcher.running_task_name)
        self.assertEqual(self.launcher.log_file_position, 0)
        with open(temp_log_path, "r", encoding="utf-8") as temp_log:
            self.assertEqual(temp_log.read(), "")

    def test_finalize_program_stop_preserves_queue_and_running_state(self):
        self.launcher.process = object()
        self.launcher.program_stopping = False
        self.launcher.stop_deadline = 100
        self.launcher.queue_snapshot = {
            "running": [{"name": "gacha"}],
            "active": [{"name": "berry"}],
            "waiting": [{"name": "pego"}],
        }
        self.launcher.running_task_name = "gacha"
        self.launcher.stop_log_tail = lambda: None
        self.launcher._close_output_reader = lambda process: None
        self.launcher._update_start_stop_button = lambda: None

        SettingsGUI._finalize_program_stop(self.launcher)

        self.assertIsNone(self.launcher.process)
        self.assertFalse(self.launcher.program_stopping)
        self.assertIsNone(self.launcher.stop_deadline)
        self.assertEqual(
            self.launcher.queue_snapshot,
            {
                "running": [{"name": "gacha"}],
                "active": [{"name": "berry"}],
                "waiting": [{"name": "pego"}],
            },
        )
        self.assertEqual(self.launcher.running_task_name, "gacha")

    def test_append_log_keeps_only_latest_configured_lines(self):
        for line_number in range(MAX_LAUNCHER_LOG_LINES + 1):
            SettingsGUI.append_log(self.launcher, f"[INFO] line {line_number}\n")

        self.assertEqual(len(self.launcher.log_lines), MAX_LAUNCHER_LOG_LINES)
        self.assertEqual(self.launcher.log_lines[0], "[INFO] line 1\n")
        self.assertEqual(
            self.launcher.log_lines[-1],
            f"[INFO] line {MAX_LAUNCHER_LOG_LINES}\n",
        )

    def test_load_previous_logs_keeps_only_latest_configured_lines(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as temp_log:
            for line_number in range(MAX_LAUNCHER_LOG_LINES + 1):
                temp_log.write(f"12:00:00 - INFO - test - line {line_number}\n")
            temp_log_path = temp_log.name
        self.addCleanup(lambda: os.path.exists(temp_log_path) and os.remove(temp_log_path))

        with patch("source.launcher.gui.GACHA_LOG_FILE", temp_log_path):
            SettingsGUI.load_previous_logs(self.launcher)

        self.assertEqual(len(self.launcher.log_lines), MAX_LAUNCHER_LOG_LINES)
        self.assertIn("line 1", self.launcher.log_lines[0])
        self.assertIn(f"line {MAX_LAUNCHER_LOG_LINES}", self.launcher.log_lines[-1])


if __name__ == "__main__":
    unittest.main()
