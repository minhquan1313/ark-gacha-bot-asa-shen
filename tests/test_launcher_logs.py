import ctypes
import json
import os
import tempfile
import threading
import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QWidget

from source.launcher.components.widgets import AnimatedButton
from source.launcher.config.constants import (
    APP_NAME,
    GACHA_LOG_FILE,
    MAX_LAUNCHER_LOG_LINES,
)
from source.launcher.gui import START_GAME_DISABLE_DELAY, SettingsGUI
from source.launcher.runner_overlay import format_runner_logs, format_runner_overlay
from source.launcher.utils.native_window import WM_HOTKEY, WindowsMSG


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
            _sync_runner_overlay=lambda: None,
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

    @patch("source.launcher.gui_parts.runtime.time.time", return_value=100)
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

    def test_queue_snapshot_update_refreshes_runner_overlay(self):
        self.launcher._sync_runner_overlay = Mock()
        snapshot = {
            "running": [{"name": "gacha"}],
            "active": [],
            "waiting": [],
        }

        self.launcher._update_queue_snapshot(snapshot)

        self.launcher._sync_runner_overlay.assert_called_once_with()

    def test_live_log_refreshes_runner_overlay_immediately(self):
        self.launcher._sync_runner_overlay = Mock()

        SettingsGUI.append_log(self.launcher, "[INFO] live log message\n")

        self.launcher._sync_runner_overlay.assert_called_once_with()

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
        self.addCleanup(
            lambda: os.path.exists(temp_log_path) and os.remove(temp_log_path)
        )

        with patch("source.launcher.gui_parts.logs.GACHA_LOG_FILE", temp_log_path):
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

    def test_open_logs_uses_default_os_application(self):
        log_path = os.path.join("source", "logs", "logs.txt")
        launcher = SimpleNamespace(dialog=Mock())

        with (
            patch("source.launcher.gui_parts.logs.GACHA_LOG_FILE", log_path),
            patch(
                "source.launcher.gui_parts.logs.QDesktopServices.openUrl",
                return_value=True,
            ) as open_url,
        ):
            SettingsGUI.open_logs(launcher)

        opened_url = open_url.call_args.args[0]
        self.assertEqual(
            os.path.normpath(opened_url.toLocalFile()),
            os.path.abspath(log_path),
        )
        launcher.dialog.assert_not_called()

    def test_open_logs_reports_os_open_failure(self):
        launcher = SimpleNamespace(dialog=Mock())

        with patch("source.launcher.gui_parts.logs.QDesktopServices.openUrl", return_value=False):
            SettingsGUI.open_logs(launcher)

        launcher.dialog.assert_called_once_with(
            "Open Logs Failed",
            f"Unable to open the log file:\n{GACHA_LOG_FILE}",
            "error",
        )

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
        self.launcher._hide_runner_overlay = Mock()

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
        self.launcher._hide_runner_overlay.assert_called_once_with()

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
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False
        ) as temp_log:
            for line_number in range(MAX_LAUNCHER_LOG_LINES + 1):
                temp_log.write(f"12:00:00 - INFO - test - line {line_number}\n")
            temp_log_path = temp_log.name
        self.addCleanup(
            lambda: os.path.exists(temp_log_path) and os.remove(temp_log_path)
        )

        with patch("source.launcher.gui_parts.logs.GACHA_LOG_FILE", temp_log_path):
            SettingsGUI.load_previous_logs(self.launcher)

        self.assertEqual(len(self.launcher.log_lines), MAX_LAUNCHER_LOG_LINES)
        self.assertIn("line 1", self.launcher.log_lines[0])
        self.assertIn(f"line {MAX_LAUNCHER_LOG_LINES}", self.launcher.log_lines[-1])


class LauncherDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_gacha_render_launcher(self):
        launcher = SimpleNamespace(
            gacha_group_expanded={},
            copy_text=Mock(),
            auto_fill_gacha_group=Mock(),
            remove_gacha_group=Mock(),
            add_gacha_to_group=Mock(),
        )
        launcher._button = lambda text, _variant: QPushButton(text)
        launcher._icon_button = MethodType(SettingsGUI._icon_button, launcher)
        launcher._deposit_line_edit = lambda value: QLineEdit(str(value))
        launcher.update_gacha_group_teleporter = Mock()
        launcher._gacha_row_card = lambda _index, _entry: QWidget()
        launcher._gacha_group_card = MethodType(SettingsGUI._gacha_group_card, launcher)
        return launcher

    def test_full_gacha_group_hides_add_gacha_button(self):
        launcher = self.make_gacha_render_launcher()
        group = [
            (0, {"name": "left", "teleporter": "GACHAPAIR_1", "side": "left"}),
            (1, {"name": "right", "teleporter": "GACHAPAIR_1", "side": "right"}),
        ]

        card = launcher._gacha_group_card("GACHAPAIR_1", group, set())

        self.assertNotIn(
            "ADD GACHA", [button.text() for button in card.findChildren(QPushButton)]
        )

    def test_partial_gacha_group_shows_add_gacha_button(self):
        launcher = self.make_gacha_render_launcher()
        group = [(0, {"name": "left", "teleporter": "GACHAPAIR_1", "side": "left"})]

        card = launcher._gacha_group_card("GACHAPAIR_1", group, set())

        self.assertIn(
            "ADD GACHA", [button.text() for button in card.findChildren(QPushButton)]
        )

    def test_success_toast_is_modeless_and_auto_closes(self):
        launcher = SimpleNamespace()
        dialog = Mock()
        dialog.finished.connect = Mock()

        with (
            patch(
                "source.launcher.gui_parts.dialogs.CyberDialog", return_value=dialog
            ) as cyber,
            patch("source.launcher.gui_parts.dialogs.QTimer.singleShot") as single_shot,
        ):
            SettingsGUI.toast(launcher, "Copied", "success")

        cyber.assert_called_once()
        dialog.setModal.assert_called_once_with(False)
        dialog.show.assert_called_once_with()
        dialog.exec.assert_not_called()
        single_shot.assert_called_once_with(3000, dialog.accept)
        self.assertEqual(launcher._toast_dialogs, [dialog])

    def test_non_success_toast_uses_modal_dialog_path(self):
        launcher = SimpleNamespace(dialog=Mock())

        SettingsGUI.toast(launcher, "Needs attention", "warning")

        launcher.dialog.assert_called_once_with(APP_NAME, "Needs attention", "warning")

    def test_start_program_button_tooltip_mentions_hotkey(self):
        buttons = [Mock(), Mock(), Mock(), Mock()]
        restore_button = Mock()
        launcher = SimpleNamespace(
            _page=Mock(return_value=(Mock(), Mock())),
            _stat_card=Mock(return_value=Mock()),
            _panel=Mock(return_value=(Mock(), Mock())),
            _button=Mock(side_effect=buttons),
            _icon_button=Mock(return_value=restore_button),
            toggle_program=Mock(),
            start_game=Mock(),
            restore_game_settings=Mock(),
            clear_game_restore_settings=Mock(),
            toggle_auto_start_program=Mock(),
            _update_auto_start_switch=Mock(),
            _update_start_stop_button=Mock(),
            _update_start_game_button_visibility=Mock(),
            _update_game_restore_button_visibility=Mock(),
            _console_widget=Mock(return_value=Mock()),
            set_log_filter=Mock(),
            show_page=Mock(),
            _footer_stat=Mock(
                side_effect=[(Mock(), Mock()), (Mock(), Mock()), Mock(), Mock(), Mock()]
            ),
            _sync_dashboard_actions_width=Mock(),
        )

        with (
            patch("source.launcher.pages.home.HeroBanner"),
            patch("source.launcher.pages.home.QGridLayout") as grid,
            patch("source.launcher.pages.home.QHBoxLayout"),
            patch("source.launcher.pages.home.QFrame"),
            patch("source.launcher.pages.home.QVBoxLayout"),
            patch("source.launcher.pages.home.CyberSwitch") as switch,
            patch("source.launcher.pages.home.QLabel"),
            patch("source.launcher.pages.home.QTimer"),
        ):
            grid.return_value.itemAtPosition.return_value.widget.return_value = Mock()
            switch.return_value.toggled.connect = Mock()
            SettingsGUI._dashboard_page(launcher)

        launcher.start_stop_button.setToolTip.assert_called_once_with(
            "Hotkey: Shift + Alt + N"
        )
        launcher.start_game_button.setToolTip.assert_called_once_with(
            "Set display to 1920x1080 and start ARK through Steam."
        )
        launcher._icon_button.assert_called_once_with(
            "icon.restore_settings",
            "Restore the original display mode and ARK config. "
            "Right-click to clear saved restore data.",
            "danger",
        )
        self.assertIs(launcher.restore_game_settings_button, restore_button)
        launcher._update_start_game_button_visibility.assert_called_once_with()

    def test_icon_button_sets_icon_and_width_without_fixed_size(self):
        button = Mock()
        launcher = SimpleNamespace(_button=Mock(return_value=button))
        icon = Mock()

        with patch("source.launcher.pages.base.QIcon", return_value=icon) as qicon:
            result = SettingsGUI._icon_button(
                launcher, "icon.trash_junk", "Remove item", "danger"
            )

        self.assertIs(result, button)
        launcher._button.assert_called_once_with("", "danger")
        button.setObjectName.assert_called_once_with("HelperIconButton")
        qicon.assert_called_once()
        button.setIcon.assert_called_once_with(icon)
        button.setIconSize.assert_called_once_with(QSize(32, 32))
        button.setMinimumWidth.assert_called_once_with(36)
        button.setFixedSize.assert_not_called()
        button.setToolTip.assert_called_once_with("Remove item")

    @patch("source.launcher.gui_parts.settings_state.QTimer.singleShot")
    @patch(
        "source.launcher.gui_parts.settings_state.ark_game_setup.prepare_and_launch_game",
        return_value="GameUserSettings.ini",
    )
    def test_start_game_disables_button_and_schedules_unlock(
        self, _prepare_game, single_shot
    ):
        launcher = SimpleNamespace(
            start_game_button=Mock(),
            restore_game_settings_button=Mock(),
            _set_start_game_enabled=Mock(),
            _unlock_start_game_button=Mock(),
            _unlock_restore_game_button=Mock(),
            append_log=Mock(),
            _update_game_restore_button_visibility=Mock(),
        )

        SettingsGUI.start_game(launcher)

        launcher._set_start_game_enabled.assert_called_once_with(False)
        single_shot.assert_any_call(
            START_GAME_DISABLE_DELAY, launcher._unlock_start_game_button
        )
        single_shot.assert_any_call(
            START_GAME_DISABLE_DELAY, launcher._unlock_restore_game_button
        )
        self.assertEqual(single_shot.call_count, 2)
        launcher.restore_game_settings_button.setEnabled.assert_called_once_with(False)
        launcher._update_game_restore_button_visibility.assert_called_once_with()

    def test_unlock_start_game_button_enables_and_refreshes_visibility(self):
        launcher = SimpleNamespace(
            start_game_button=Mock(),
            _set_start_game_enabled=Mock(),
            _update_start_game_button_visibility=Mock(),
        )

        SettingsGUI._unlock_start_game_button(launcher)

        launcher._set_start_game_enabled.assert_called_once_with(True)
        launcher._update_start_game_button_visibility.assert_called_once_with()

    def test_set_start_game_enabled_updates_button_and_emits(self):
        launcher = SimpleNamespace(
            start_game_button=Mock(),
            start_game_enabled_changed=SimpleNamespace(emit=Mock()),
        )

        SettingsGUI._set_start_game_enabled(launcher, False)

        launcher.start_game_button.setEnabled.assert_called_once_with(False)
        launcher.start_game_enabled_changed.emit.assert_called_once_with(False)

    @patch("source.launcher.gui_parts.settings_state.find_window_size", return_value=None)
    def test_start_game_button_visible_when_ark_window_is_missing(self, _find_window):
        launcher = SimpleNamespace(start_game_button=Mock())

        SettingsGUI._update_start_game_button_visibility(launcher)

        launcher.start_game_button.setVisible.assert_called_once_with(True)

    @patch("source.launcher.gui_parts.settings_state.find_window_size", return_value=(1920, 1080))
    def test_start_game_button_hidden_when_ark_is_supported_size(self, _find_window):
        launcher = SimpleNamespace(start_game_button=Mock())

        SettingsGUI._update_start_game_button_visibility(launcher)

        launcher.start_game_button.setVisible.assert_called_once_with(False)

    @patch("source.launcher.gui_parts.settings_state.find_window_size", return_value=(2560, 1440))
    def test_start_game_button_visible_when_ark_size_is_unsupported(self, _find_window):
        launcher = SimpleNamespace(start_game_button=Mock())

        SettingsGUI._update_start_game_button_visibility(launcher)

        launcher.start_game_button.setVisible.assert_called_once_with(True)

    def test_tick_updates_start_game_button_visibility_on_dashboard(self):
        memory = SimpleNamespace(used=4 * 1024**3, total=8 * 1024**3)
        fake_psutil = SimpleNamespace(
            virtual_memory=Mock(return_value=memory),
            cpu_percent=Mock(return_value=12),
        )
        launcher = SimpleNamespace(
            shutdown_started=False,
            _poll_program_stop=Mock(),
            _sync_runner_overlay=Mock(),
            current_filter="ALL",
            _render_logs=Mock(),
            server_value=Mock(),
            _update_start_stop_button=Mock(),
            _update_start_game_button_visibility=Mock(),
            form_values={},
            settings={"server_number": "0"},
            fields={},
            active_value=Mock(),
            waiting_value=Mock(),
            queue_snapshot={"running": [], "active": [], "waiting": []},
            start_time=None,
            process=None,
            uptime_value=Mock(),
            memory_value=Mock(),
            memory_meter=Mock(),
            cpu_value=Mock(),
            cpu_meter=Mock(),
            runner_value=Mock(),
            activity_value=Mock(),
            clock_value=Mock(),
            last_activity="--:--:--",
        )

        with patch("source.launcher.gui_parts.runtime.psutil", fake_psutil):
            SettingsGUI._tick(launcher)

        launcher._update_start_game_button_visibility.assert_called_once_with()


class LauncherStartProgramTests(unittest.TestCase):
    def make_launcher(self, ark_window_ok=True):
        return SimpleNamespace(
            shutdown_started=False,
            program_stopping=False,
            runner_loading=False,
            process=None,
            require_ark_window=Mock(return_value=ark_window_ok),
            close_external_helpers=Mock(),
            append_log=Mock(),
            _update_start_stop_button=Mock(),
            start_log_tail=Mock(),
            read_output=Mock(),
            dialog=Mock(),
            _show_runner_overlay=Mock(),
            _hide_runner_overlay=Mock(),
            output_reader_stop=None,
            output_reader_thread=None,
            log_lines=[],
            queue_snapshot={"running": [], "active": [], "waiting": []},
            running_task_name=None,
        )

    def test_start_program_shows_loading_overlay_before_launching_process(self):
        launcher = self.make_launcher()
        events = []
        launcher._show_runner_overlay.side_effect = lambda: events.append("overlay")
        process = Mock()
        thread = Mock()

        def cleanup():
            events.append("cleanup")

        def popen(*_args, **_kwargs):
            events.append("popen")
            return process

        with (
            patch(
                "source.launcher.gui_parts.runtime.cleanup_debug_screenshots_on_program_start",
                side_effect=cleanup,
            ) as cleanup_mock,
            patch("source.launcher.gui_parts.runtime.subprocess.Popen", side_effect=popen),
            patch("source.launcher.gui_parts.runtime.threading.Thread", return_value=thread),
        ):
            SettingsGUI.start_program(launcher)

        cleanup_mock.assert_called_once_with()
        self.assertEqual(events, ["overlay", "cleanup", "popen", "overlay"])
        launcher.close_external_helpers.assert_called_once_with()
        thread.start.assert_called_once_with()
        self.assertTrue(launcher.runner_loading)
        self.assertEqual(launcher._show_runner_overlay.call_count, 2)

    def test_start_program_does_not_clean_when_ark_window_validation_fails(self):
        launcher = self.make_launcher(ark_window_ok=False)

        with (
            patch(
                "source.launcher.gui_parts.runtime.cleanup_debug_screenshots_on_program_start"
            ) as cleanup,
            patch("source.launcher.gui_parts.runtime.subprocess.Popen") as popen,
        ):
            SettingsGUI.start_program(launcher)

        cleanup.assert_not_called()
        popen.assert_not_called()
        launcher._show_runner_overlay.assert_not_called()

    def test_start_stop_button_update_is_noop_when_state_is_current(self):
        button = Mock()
        button.text.return_value = "START PROGRAM"
        button.variant = "primary"
        button.isEnabled.return_value = True
        launcher = SimpleNamespace(
            start_stop_button=button,
            program_stopping=False,
            is_program_running=Mock(return_value=False),
        )

        SettingsGUI._update_start_stop_button(launcher)

        button.setText.assert_not_called()
        button.set_variant.assert_not_called()
        button.setEnabled.assert_not_called()

    def test_start_stop_button_update_applies_real_state_changes(self):
        button = Mock()
        button.text.return_value = "START PROGRAM"
        button.variant = "primary"
        button.isEnabled.return_value = True
        launcher = SimpleNamespace(
            start_stop_button=button,
            program_stopping=True,
            is_program_running=Mock(return_value=True),
        )

        SettingsGUI._update_start_stop_button(launcher)

        button.setText.assert_called_once_with("STOPPING...")
        button.set_variant.assert_called_once_with("secondary")
        button.setEnabled.assert_called_once_with(False)

    def test_stop_program_hides_runner_overlay(self):
        launcher = self.make_launcher()
        launcher.process = Mock()
        launcher.process.poll.return_value = None

        with patch("source.launcher.gui_parts.runtime.time.time", return_value=100):
            SettingsGUI.stop_program(launcher)

        launcher.process.terminate.assert_called_once_with()
        launcher._hide_runner_overlay.assert_called_once_with()

    def test_show_runner_overlay_creates_and_refreshes_overlay(self) -> None:
        launcher = SimpleNamespace(
            process=Mock(),
            program_stopping=False,
            runner_loading=False,
            runner_overlay=None,
            queue_snapshot={"running": [{"name": "gacha"}]},
            log_lines=["[DEBUG] 09:03:45 - DEBUG - open - inventory opened"],
            is_program_running=Mock(return_value=True),
        )
        overlay = Mock()

        with patch("source.launcher.gui_parts.runtime.RunnerOverlay", return_value=overlay):
            SettingsGUI._show_runner_overlay(launcher)

        self.assertIs(launcher.runner_overlay, overlay)
        overlay.refresh.assert_called_once_with(
            launcher.queue_snapshot, launcher.log_lines
        )
        overlay.show.assert_called_once_with()
        overlay.raise_.assert_called_once_with()

    def test_show_runner_overlay_displays_loading_state(self) -> None:
        launcher = SimpleNamespace(
            process=None,
            program_stopping=False,
            runner_loading=True,
            runner_overlay=None,
            queue_snapshot={"running": [{"name": "stale task"}]},
            log_lines=["[INFO] stale log"],
            is_program_running=Mock(return_value=True),
        )
        overlay = Mock()

        with patch("source.launcher.gui_parts.runtime.RunnerOverlay", return_value=overlay):
            SettingsGUI._show_runner_overlay(launcher)

        overlay.refresh.assert_called_once_with(
            {
                "running": [{"name": "Loading runner..."}],
            },
            [],
        )
        overlay.stop_button.set_loading.assert_called_once_with(True)

    def test_runner_ready_reveals_collected_overlay_content(self) -> None:
        launcher = SimpleNamespace(
            runner_loading=True,
            process=Mock(),
            queue_snapshot={"running": [{"name": "pego 1"}]},
            log_lines=["[DEBUG] 09:03:45 - DEBUG - open - inventory opened"],
            is_program_running=Mock(return_value=True),
            _show_runner_overlay=Mock(),
        )

        SettingsGUI._on_runner_ready(launcher)

        self.assertFalse(launcher.runner_loading)
        launcher._show_runner_overlay.assert_called_once_with()

    def test_output_reader_emits_runner_ready_for_ready_marker(self) -> None:
        launcher = SimpleNamespace(
            output_reader_stop=threading.Event(),
            runner_ready=Mock(),
            stop_log_tail=Mock(),
            _emit_log_line=Mock(),
        )
        process = SimpleNamespace(stdout=iter(["__RUNNER_READY__\n"]))

        SettingsGUI.read_output(launcher, process)

        launcher.runner_ready.emit.assert_called_once_with()

    def test_shutdown_hides_overlay_and_unregisters_hotkey(self):
        process = Mock()
        process.poll.return_value = 1
        stop_event = Mock()
        launcher = SimpleNamespace(
            shutdown_started=False,
            timer=Mock(),
            auto_start_timer=Mock(),
            close_external_helpers=Mock(),
            output_reader_stop=stop_event,
            stop_log_tail=Mock(),
            process=process,
            program_stopping=False,
            stop_deadline=100,
            queue_snapshot={"running": [{"name": "gacha"}]},
            running_task_name="gacha",
            _close_output_reader=Mock(),
            _hide_runner_overlay=Mock(),
            _unregister_start_stop_hotkey=Mock(),
        )

        SettingsGUI._shutdown_resources(launcher)

        launcher._unregister_start_stop_hotkey.assert_called_once_with()
        launcher._hide_runner_overlay.assert_called_once_with()
        self.assertEqual(
            launcher.queue_snapshot, {"running": [], "active": [], "waiting": []}
        )
        self.assertIsNone(launcher.running_task_name)


class RunnerOverlayFormattingTests(unittest.TestCase):
    def test_overlay_formats_running_and_next_three_tasks_soonest_first(self) -> None:
        snapshot = {
            "running": [{"name": "pego deposit"}],
            "active": [
                {"name": "ready task", "execution_time": 100, "state": "READY"},
                {"name": "feed gacha", "execution_time": 112},
            ],
            "waiting": [
                {"name": "task 5", "execution_time": 150},
                {"name": "task 4", "execution_time": 140},
                {"name": "task 3", "execution_time": 130},
                {"name": "task 6", "execution_time": 160},
                {"name": "task 2", "execution_time": 120},
            ],
        }

        current, upcoming = format_runner_overlay(snapshot, now=100)

        self.assertEqual(current, "pego deposit")
        self.assertEqual(
            upcoming,
            [
                "ready task",
                "00:00:12 feed gacha",
                "00:00:20 task 2",
            ],
        )

    def test_overlay_shows_waiting_state_without_running_snapshot(self):
        current, upcoming = format_runner_overlay(
            {"running": [], "active": [], "waiting": []}, now=100
        )

        self.assertEqual(current, "Waiting for running task...")
        self.assertEqual(upcoming, ["No upcoming tasks."])

    def test_overlay_logs_include_every_level_without_metadata(self) -> None:
        lines = [
            "09:03:40 - DEBUG - open - debug message",
            "09:03:41 - INFO - open - info message",
            "09:03:42 - WARNING - open - warning message",
            "[ERROR] 09:03:43 - ERROR - open - error message",
            "[CRITICAL] 09:03:44 - CRITICAL - open - critical message",
            "[TEMPLATE] 09:03:45 - TEMPLATE - open - template message",
        ]

        self.assertEqual(
            format_runner_logs(lines, limit=10),
            [
                "45 template message",
                "44 critical message",
                "43 error message",
                "42 warning message",
                "41 info message",
                "40 debug message",
            ],
        )

    def test_overlay_logs_keep_latest_three_timestamped_messages(self) -> None:
        lines = [
            "09:03:39 - DEBUG - open - older message",
            "[INFO] launcher message without a timestamp",
            "09:03:41 - DEBUG - open - open inventory 1/3",
            "09:03:43 - DEBUG - open - open inventory 2/3",
            "09:03:45 - DEBUG - open - open inventory - 3/3",
        ]

        self.assertEqual(
            format_runner_logs(lines),
            [
                "45 open inventory - 3/3",
                "43 open inventory 2/3",
                "41 open inventory 1/3",
            ],
        )
        self.assertEqual(format_runner_logs(lines, limit=0), [])


class LauncherHotkeyTests(unittest.TestCase):
    def test_register_start_stop_hotkey_uses_shift_alt_n_and_is_nonfatal(self):
        launcher = SimpleNamespace(
            start_stop_hotkey_id=44,
            start_stop_hotkey_registered=False,
            winId=Mock(return_value=123),
        )

        with (
            patch(
                "source.launcher.gui_parts.runtime.ctypes",
                SimpleNamespace(windll=object()),
            ),
            patch(
                "source.launcher.gui_parts.runtime.register_shift_alt_n_hotkey",
                return_value=True,
            ) as register,
        ):
            SettingsGUI._register_start_stop_hotkey(launcher)

        register.assert_called_once_with(123, 44)
        self.assertTrue(launcher.start_stop_hotkey_registered)

        launcher.start_stop_hotkey_registered = False
        with (
            patch(
                "source.launcher.gui_parts.runtime.ctypes",
                SimpleNamespace(windll=object()),
            ),
            patch(
                "source.launcher.gui_parts.runtime.register_shift_alt_n_hotkey",
                side_effect=RuntimeError("blocked"),
            ),
        ):
            SettingsGUI._register_start_stop_hotkey(launcher)

        self.assertFalse(launcher.start_stop_hotkey_registered)

    def test_unregister_start_stop_hotkey(self):
        launcher = SimpleNamespace(
            start_stop_hotkey_id=44,
            start_stop_hotkey_registered=True,
            winId=Mock(return_value=123),
        )

        with (
            patch(
                "source.launcher.gui_parts.runtime.ctypes",
                SimpleNamespace(windll=object()),
            ),
            patch("source.launcher.gui_parts.runtime.unregister_hotkey") as unregister,
        ):
            SettingsGUI._unregister_start_stop_hotkey(launcher)

        unregister.assert_called_once_with(123, 44)
        self.assertFalse(launcher.start_stop_hotkey_registered)

    def test_native_hotkey_message_toggles_program(self):
        launcher = SimpleNamespace(
            start_stop_hotkey_id=44,
            start_stop_hotkey_registered=True,
            toggle_program=Mock(),
        )
        message = WindowsMSG()
        message.message = WM_HOTKEY
        message.wParam = 44

        handled = SettingsGUI._handle_native_hotkey_message(
            launcher, ctypes.addressof(message)
        )

        self.assertTrue(handled)
        launcher.toggle_program.assert_called_once_with()


class AnimatedButtonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_repeated_set_enabled_true_does_not_reset_state(self):
        button = AnimatedButton("TEST", "primary")

        with patch.object(button, "set_state") as set_state:
            button.setEnabled(True)

        set_state.assert_not_called()

    def test_set_enabled_false_updates_disabled_state(self):
        button = AnimatedButton("TEST", "primary")

        with patch.object(button, "set_state") as set_state:
            button.setEnabled(False)

        set_state.assert_called_once_with("disabled")

    def test_mouse_release_ignores_deleted_qt_object_after_click_handler(self):
        button = AnimatedButton("TEST", "primary")
        event = Mock()

        with (
            patch.object(QPushButton, "mouseReleaseEvent") as release,
            patch.object(
                button,
                "isEnabled",
                side_effect=RuntimeError(
                    "Internal C++ object (AnimatedButton) already deleted."
                ),
            ),
        ):
            button.mouseReleaseEvent(event)

        release.assert_called_once_with(event)


if __name__ == "__main__":
    unittest.main()
