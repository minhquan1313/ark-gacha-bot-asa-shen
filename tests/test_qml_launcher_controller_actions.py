import os
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from source.launcher.controllers.launcher_controller import LauncherController
from source.launcher.controllers.log_controller import LogController
from source.launcher.controllers.queue_controller import QueueController
from source.launcher.controllers.settings_controller import SettingsController
from source.launcher.controllers.tools_controller import ToolsController


class QmlLauncherControllerActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle("Basic")
        cls.app = QApplication.instance() or QApplication([])

    def make_controller(self):
        settings = SettingsController()
        logs = LogController()
        queue = QueueController()
        controller = LauncherController(settings, logs, queue)
        self.addCleanup(controller.shutdown)
        return controller, logs, settings

    def test_check_colours_appends_average_colour_log(self):
        controller, logs, _settings = self.make_controller()
        colour_module = types.SimpleNamespace(
            console_output=types.SimpleNamespace(
                output_mean_colour=Mock(return_value=(10, 20, 30))
            )
        )

        with (
            patch.object(controller, "require_ark_window", return_value=True),
            patch.dict(sys.modules, {"source.utility.colour_checks": colour_module}),
        ):
            controller.checkColours()

        self.assertIn("Average console colour", "".join(logs.lines))

    def test_check_colours_reports_missing_dependency(self):
        controller, _logs, _settings = self.make_controller()
        dialogs = []
        controller.dialogRequested.connect(
            lambda title, message, variant: dialogs.append((title, message, variant))
        )

        with (
            patch.object(controller, "require_ark_window", return_value=True),
            patch.dict(sys.modules, {"source.utility.colour_checks": None}),
        ):
            controller.checkColours()

        self.assertEqual(dialogs[0][0], "Missing Dependency")
        self.assertEqual(dialogs[0][2], "error")

    def test_dashboard_start_game_visibility_matches_window_size(self):
        controller, _logs, _settings = self.make_controller()

        with patch(
            "source.launcher.controllers.launcher_controller.find_window_size",
            return_value=(1920, 1080),
        ):
            self.assertFalse(controller.showStartGame)

        with patch(
            "source.launcher.controllers.launcher_controller.find_window_size",
            return_value=None,
        ):
            self.assertTrue(controller.showStartGame)

    def test_dashboard_restore_visibility_matches_restore_state(self):
        controller, _logs, _settings = self.make_controller()

        with patch(
            "source.launcher.controllers.launcher_controller.ark_game_setup.restore_state_exists",
            return_value=True,
        ):
            self.assertTrue(controller.showRestoreGameSettings)

        with patch(
            "source.launcher.controllers.launcher_controller.ark_game_setup.restore_state_exists",
            return_value=False,
        ):
            self.assertFalse(controller.showRestoreGameSettings)

    def test_start_game_locks_button_and_ignores_repeat_click(self):
        controller, _logs, _settings = self.make_controller()

        with (
            patch(
                "source.launcher.controllers.launcher_controller.QTimer.singleShot"
            ),
            patch(
                "source.launcher.controllers.launcher_controller.ark_game_setup.prepare_and_launch_game",
                return_value="GameUserSettings.ini",
            ) as launch,
        ):
            controller.startGame()
            controller.startGame()

        self.assertFalse(controller.startGameEnabled)
        launch.assert_called_once()

    def test_auto_start_allowed_requires_server_number(self):
        controller, _logs, settings = self.make_controller()

        settings._settings["server_number"] = "0"
        self.assertFalse(controller.autoStartAllowed)
        self.assertEqual(controller.autoStartHint, "Set server number first")

        settings._settings["server_number"] = "5147"
        self.assertTrue(controller.autoStartAllowed)

    def test_show_page_ignores_unknown_page_name(self):
        controller, _logs, _settings = self.make_controller()

        controller.showPage("logs")
        controller.showPage("missing")

        self.assertEqual(controller.currentPage, "logs")
        self.assertEqual(
            controller.autoStartHint,
            "Start program when launcher opens",
        )

    def test_settings_controller_exposes_helper_inactive_opacity(self):
        settings = SettingsController()
        settings._settings["helper_inactive_opacity"] = 0.42

        self.assertEqual(settings.helperInactiveOpacity, 0.42)

    def test_schedule_auto_start_logs_blocked_when_server_missing(self):
        controller, logs, settings = self.make_controller()
        settings._settings["auto_start_program"] = True
        settings._settings["server_number"] = "0"

        with patch(
            "source.launcher.controllers.launcher_controller.QTimer.singleShot"
        ) as single_shot:
            controller.scheduleAutoStart()

        single_shot.assert_not_called()
        self.assertIn("server number is not set", "".join(logs.lines))

    def test_schedule_auto_start_uses_timer_when_allowed(self):
        controller, logs, settings = self.make_controller()
        settings._settings["auto_start_program"] = True
        settings._settings["server_number"] = "5147"

        with patch(
            "source.launcher.controllers.launcher_controller.QTimer.singleShot"
        ) as single_shot:
            controller.scheduleAutoStart()

        single_shot.assert_called_once_with(1000, controller.startProgram)
        self.assertIn("Auto start enabled", "".join(logs.lines))

    def test_clear_game_restore_settings_logs_success(self):
        controller, logs, _settings = self.make_controller()

        with patch(
            "source.launcher.controllers.launcher_controller.ark_game_setup.clear_restore_state"
        ) as clear_restore:
            controller.clearGameRestoreSettings()

        clear_restore.assert_called_once_with()
        self.assertIn("Cleared saved ARK restore settings", "".join(logs.lines))

    def test_clear_game_restore_settings_reports_failure(self):
        controller, logs, _settings = self.make_controller()
        dialogs = []
        controller.dialogRequested.connect(
            lambda title, message, variant: dialogs.append((title, message, variant))
        )

        with patch(
            "source.launcher.controllers.launcher_controller.ark_game_setup.clear_restore_state",
            side_effect=RuntimeError("missing backup"),
        ):
            controller.clearGameRestoreSettings()

        self.assertIn("Clear game restore settings failed", "".join(logs.lines))
        self.assertEqual(dialogs[0], ("Clear Restore Settings Failed", "missing backup", "error"))

    def test_system_stats_expose_numeric_meter_values(self):
        controller, _logs, _settings = self.make_controller()
        memory = types.SimpleNamespace(
            used=4 * 1024**3,
            total=8 * 1024**3,
            percent=50,
        )
        psutil_module = types.SimpleNamespace(
            virtual_memory=Mock(return_value=memory),
            cpu_percent=Mock(return_value=37.4),
        )

        with patch(
            "source.launcher.controllers.launcher_controller.psutil",
            psutil_module,
        ):
            controller._sync_system_stats()

        self.assertEqual(controller.memoryUsage, "4.0G / 8.0G")
        self.assertEqual(controller.memoryPercent, 50)
        self.assertEqual(controller.cpuUsage, "37%")
        self.assertEqual(controller.cpuPercent, 37)

    def test_queue_controller_runner_overlay_format_matches_legacy_overlay(self):
        queue = QueueController()
        snapshot = {
            "running": [{"name": "current"}],
            "active": [{"name": "ready", "execution_time": 90, "state": "READY"}],
            "waiting": [
                {"name": "later", "execution_time": 130, "state": "WAITING"},
                {"name": "sooner", "execution_time": 110, "state": "WAITING"},
            ],
        }

        with patch(
            "source.launcher.controllers.queue_controller.time.time",
            return_value=100,
        ):
            queue.updateSnapshot(snapshot)
            self.assertEqual(
                queue.runnerUpcomingTasks,
                [
                    "READY    ready",
                    "00:00:10 sooner",
                    "00:00:30 later",
                ],
            )
            self.assertEqual(queue.currentTask, "current")

    def test_log_controller_appends_visible_logs_to_persistent_log_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "log.txt")
            gacha_log_path = os.path.join(temp_dir, "logs.txt")
            logs = LogController(log_path)

            with patch(
                "source.launcher.controllers.log_controller.GACHA_LOG_FILE",
                gacha_log_path,
            ):
                logs.append("[INFO] first\n")
                logs.clearLogs()
                logs.append("[WARN] second\n")

            with open(log_path, "r", encoding="utf-8") as log_file:
                self.assertEqual(log_file.read(), "[INFO] first\n[WARN] second\n")

    def test_log_controller_queue_and_running_filters_use_queue_snapshot(self):
        queue = QueueController()
        logs = LogController()
        logs.setQueueController(queue)
        snapshot = {
            "running": [{"name": "current"}],
            "active": [{"name": "later", "execution_time": 130, "state": "WAITING"}],
            "waiting": [{"name": "sooner", "execution_time": 110, "state": "WAITING"}],
        }

        with patch(
            "source.launcher.controllers.queue_controller.time.time",
            return_value=100,
        ):
            queue.updateSnapshot(snapshot)
            logs.setFilter("QUEUE")
            self.assertEqual(
                logs.lines,
                [
                    "[QUEUE] 00:00:30  later",
                    "[QUEUE] 00:00:10  sooner",
                    "[QUEUE] RUNNING   current",
                ],
            )
            logs.setFilter("RUNNING")
            self.assertEqual(
                logs.lines,
                [
                    "[RUNNING] STARTED   current",
                    "[RUNNING] CURRENT   current",
                ],
            )

    def test_log_controller_ignores_unknown_filter(self):
        logs = LogController()

        logs.setFilter("INFO")
        logs.setFilter("missing")

        self.assertEqual(logs.currentFilter, "INFO")

    def test_queue_controller_tolerates_malformed_task_snapshot(self):
        queue = QueueController()
        snapshot = {
            "running": ["bad-running"],
            "active": [{"name": "", "execution_time": "bad", "state": "WAITING"}],
            "waiting": ["bad-waiting"],
        }

        with patch(
            "source.launcher.controllers.queue_controller.time.time",
            return_value=100,
        ):
            queue.updateSnapshot(snapshot)

            self.assertEqual(queue.currentTask, "unknown")
            self.assertEqual(
                queue.upcomingTasks,
                [
                    "[QUEUE] READY     unknown",
                    "[QUEUE] READY     unknown",
                    "[QUEUE] RUNNING   unknown",
                ],
            )
            self.assertEqual(
                queue.runnerUpcomingTasks,
                [
                    "READY    unknown",
                    "READY    unknown",
                ],
            )
            self.assertEqual(
                queue.runningLines,
                [
                    "[RUNNING] STARTED   unknown",
                    "[RUNNING] CURRENT   unknown",
                ],
            )

    def test_tools_controller_exposes_update_and_download_messages(self):
        tools = ToolsController()
        messages = []
        tools.messageRequested.connect(
            lambda title, message, variant: messages.append((title, message, variant))
        )

        tools.checkUpdates()
        tools.openDownloadPage()

        self.assertEqual(messages[0][0], "CHECK UPDATE")
        self.assertIn("update endpoint", messages[0][1])
        self.assertEqual(tools.latestVersion, "v1.0.0")
        self.assertEqual(tools.updateStatus, "Manual check required")
        self.assertFalse(tools.updateAvailable)
        self.assertEqual(messages[1][0], "DOWNLOAD")
        self.assertIn("not configured", messages[1][1])


if __name__ == "__main__":
    unittest.main()
