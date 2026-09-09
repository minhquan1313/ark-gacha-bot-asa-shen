import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from source.launcher.gui import SettingsGUI
from source.launcher.components.helper_window import WorkerHelperWindow


class LauncherStartupTests(unittest.TestCase):
    def test_page_construction_yields_before_next_page_and_finalization(self):
        first, second = Mock(return_value=object()), Mock(return_value=object())
        launcher = SimpleNamespace(
            shutdown_started=False,
            _page_builders=iter((("first", first), ("second", second))),
            startup_progress=Mock(), startup_failed=Mock(), stack=Mock(), pages={},
            _finish_startup=Mock(), _initialize_next_page=Mock(),
        )
        with patch("source.launcher.gui.QTimer.singleShot") as schedule:
            SettingsGUI._initialize_next_page(launcher)
            first.assert_called_once()
            second.assert_not_called()
            launcher._finish_startup.assert_not_called()
            schedule.assert_called_once_with(0, launcher._initialize_next_page)
            SettingsGUI._initialize_next_page(launcher)
            second.assert_called_once()
            SettingsGUI._initialize_next_page(launcher)
            launcher._finish_startup.assert_called_once()

    def test_initialization_failure_reports_error_and_stops_scheduling(self):
        launcher = SimpleNamespace(
            shutdown_started=False,
            _page_builders=iter((("settings", Mock(side_effect=ValueError("bad config"))),)),
            startup_progress=Mock(), startup_failed=Mock(), pages={},
        )
        with patch("source.launcher.gui.QTimer.singleShot") as schedule:
            SettingsGUI._initialize_next_page(launcher)
        launcher.startup_failed.emit.assert_called_once_with("bad config")
        schedule.assert_not_called()

    def test_background_services_do_not_run_after_shutdown(self):
        launcher = SimpleNamespace(shutdown_started=True, auto_keys_runtime=Mock())
        SettingsGUI._start_background_services(launcher)
        launcher.auto_keys_runtime.configure.assert_not_called()

    def test_runner_waits_for_input_cleanup_and_cancel_releases_suspension(self):
        launcher = SimpleNamespace(
            shutdown_started=False, program_stopping=False,
            runner_launch_pending=True, runner_loading=True, process=None,
            auto_keys_runtime=SimpleNamespace(cleanup_pending=True),
            _suspend_auto_keys_for_automation=Mock(),
            _resume_auto_keys_after_automation=Mock(),
            _launch_program_process=Mock(), append_log=Mock(),
            _update_start_stop_button=Mock(), _hide_runner_overlay=Mock(),
        )
        with patch("source.launcher.gui_parts.runtime.QTimer.singleShot") as timer, \
                patch("source.launcher.gui_parts.runtime.start_subprocess") as launch:
            SettingsGUI._launch_program_process(launcher)
        timer.assert_called_once_with(20, launcher._launch_program_process)
        launch.assert_not_called()
        SettingsGUI.stop_program(launcher)
        launcher._resume_auto_keys_after_automation.assert_called_once_with("main-runner")
        self.assertFalse(launcher.runner_launch_pending)

    def test_helper_waits_for_input_cleanup_and_cancel_invalidates_retry(self):
        helper = SimpleNamespace(
            closing=False,
            owner=SimpleNamespace(
                shutdown_started=False,
                auto_keys_runtime=SimpleNamespace(cleanup_pending=True),
                _suspend_auto_keys_for_automation=Mock(),
            ),
            auto_keys_suspension_active=False,
            _set_running_ui=Mock(), _start_worker=Mock(),
            _release_auto_keys_suspension=Mock(),
        )
        with patch("source.launcher.components.helper_window.QTimer.singleShot") as timer, \
                patch("source.launcher.components.helper_window.start_subprocess") as launch:
            WorkerHelperWindow._start_worker(helper, "auto-feed")
        self.assertTrue(helper.worker_launch_pending)
        launch.assert_not_called()
        retry = timer.call_args.args[2]
        WorkerHelperWindow.stop(helper)
        retry()
        helper._start_worker.assert_not_called()
        helper._release_auto_keys_suspension.assert_called_once()
