import json
import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import patch

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

        SettingsGUI.clear_logs(self.launcher)

        self.assertEqual(self.launcher.log_lines, [])
        self.assertEqual(self.launcher.running_history, [])


if __name__ == "__main__":
    unittest.main()
