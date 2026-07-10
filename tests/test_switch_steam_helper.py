import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from source.launcher.components.custom_pyside_component import NoWheelComboBox
from source.launcher.gui import SettingsGUI
from source.launcher.switch_steam_helper import SwitchSteamHelper


ACCOUNTS = [
    {"account_name": "beta", "most_recent": True, "timestamp": 20},
    {"account_name": "alpha", "most_recent": False, "timestamp": 10},
]


class SwitchSteamHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _owner(self) -> SimpleNamespace:
        launcher_button = Mock()
        launcher_button.isEnabled.return_value = True
        return SimpleNamespace(
            styleSheet=Mock(return_value=""),
            screen=Mock(return_value=None),
            settings={"helper_inactive_opacity": 0.3},
            isActiveWindow=Mock(return_value=False),
            start_game=Mock(),
            start_game_button=launcher_button,
            start_game_enabled_changed=SimpleNamespace(connect=Mock()),
            forget_deposit_helper=Mock(),
        )

    def _helper(
        self, accounts: list[dict[str, object]] | None = None
    ) -> SwitchSteamHelper:
        loaded_accounts = ACCOUNTS if accounts is None else accounts
        with (
            patch(
                "source.launcher.switch_steam_helper.steam_accounts.loginusers_path",
                return_value=Path("C:/Steam/config/loginusers.vdf"),
            ),
            patch(
                "source.launcher.switch_steam_helper.steam_accounts.load_steam_accounts",
                return_value=loaded_accounts,
            ),
        ):
            return SwitchSteamHelper(self._owner())

    def test_selects_current_account_and_uses_no_wheel_combo(self) -> None:
        helper = self._helper()
        try:
            self.assertIsInstance(helper.account_combo, NoWheelComboBox)
            self.assertEqual(helper.account_combo.currentData(), "beta")
            self.assertEqual(helper.account_combo.currentText(), "beta (CURRENT)")
            self.assertTrue(helper.switch_button.isEnabled())
            self.assertTrue(helper.switch_instant_button.isEnabled())
            self.assertTrue(helper.start_game_button.isEnabled())
            self.assertIn("Current Steam account: beta", helper.status.text())
            actions = helper.content_layout.itemAt(4).layout()
            self.assertEqual(actions.itemAt(0).widget(), helper.switch_button)
            self.assertEqual(
                actions.itemAt(1).widget(),
                helper.switch_instant_button,
            )
            self.assertEqual(
                actions.itemAt(2).widget(),
                helper.start_game_button,
            )

            event = QWheelEvent(
                QPoint(1, 1),
                QPoint(1, 1),
                QPoint(0, 0),
                QPoint(0, 120),
                Qt.NoButton,
                Qt.NoModifier,
                Qt.ScrollUpdate,
                False,
            )
            QApplication.sendEvent(helper.account_combo, event)
            self.assertFalse(event.isAccepted())
        finally:
            helper.close()

    def test_noncurrent_selection_keeps_actions_enabled(self) -> None:
        helper = self._helper()
        try:
            helper.account_combo.setCurrentIndex(1)

            self.assertEqual(helper.account_combo.currentData(), "alpha")
            self.assertTrue(helper.switch_button.isEnabled())
            self.assertTrue(helper.switch_instant_button.isEnabled())
            self.assertTrue(helper.start_game_button.isEnabled())
            self.assertIn("beta to alpha", helper.status.text())
        finally:
            helper.close()

    def test_start_game_button_continuously_mirrors_launcher_state(self) -> None:
        helper = self._helper()
        try:
            sync = helper.owner.start_game_enabled_changed.connect.call_args.args[0]
            sync(False)
            self.assertTrue(helper.switch_instant_button.isEnabled())
            self.assertFalse(helper.start_game_button.isEnabled())

            helper.account_combo.setCurrentIndex(1)
            self.assertFalse(helper.start_game_button.isEnabled())

            sync(True)
            self.assertTrue(helper.switch_instant_button.isEnabled())
            self.assertTrue(helper.start_game_button.isEnabled())

            helper.switching = True
            sync(True)
            self.assertFalse(helper.switch_instant_button.isEnabled())
            self.assertFalse(helper.start_game_button.isEnabled())
        finally:
            helper.close()

    def test_current_start_game_delegates_without_worker(self) -> None:
        helper = self._helper()
        try:
            with (
                patch(
                    "source.launcher.switch_steam_helper.steam_accounts.load_steam_accounts",
                    return_value=ACCOUNTS,
                ),
                patch.object(helper, "_start_worker") as start_worker,
            ):
                helper.start_game()

            helper.owner.start_game.assert_called_once_with()
            start_worker.assert_not_called()
        finally:
            helper.close()

    def test_switch_and_start_game_flow_uses_status_spinner(self) -> None:
        helper = self._helper()
        try:
            helper.account_combo.setCurrentIndex(1)
            with (
                patch(
                    "source.launcher.switch_steam_helper.steam_accounts.load_steam_accounts",
                    return_value=ACCOUNTS,
                ),
                patch.object(helper, "_start_worker") as start_worker,
            ):
                helper.start_game()

            start_worker.assert_called_once_with(
                "switch_steam",
                "--account",
                "alpha",
                "--loginusers",
                str(Path("C:/Steam/config/loginusers.vdf").resolve()),
            )
            self.assertTrue(helper.status_spinner.timer.isActive())
            self.assertFalse(helper.switch_button.isEnabled())
            self.assertFalse(helper.switch_instant_button.isEnabled())
            self.assertFalse(helper.account_combo.isEnabled())

            helper._on_worker_finished("Steam restarted for alpha.")
            self.app.processEvents()

            self.assertFalse(helper.status_spinner.timer.isActive())
            self.assertTrue(helper.switch_button.isEnabled())
            self.assertTrue(helper.switch_instant_button.isEnabled())
            self.assertEqual(helper.current_account, "alpha")
            helper.owner.start_game.assert_called_once_with()
        finally:
            helper.close()

    def test_switch_instant_flow_adds_worker_flag(self) -> None:
        helper = self._helper()
        try:
            helper.account_combo.setCurrentIndex(1)
            with (
                patch(
                    "source.launcher.switch_steam_helper.steam_accounts.load_steam_accounts",
                    return_value=ACCOUNTS,
                ),
                patch.object(helper, "_start_worker") as start_worker,
            ):
                helper.switch_account_instant()

            start_worker.assert_called_once_with(
                "switch_steam",
                "--account",
                "alpha",
                "--loginusers",
                str(Path("C:/Steam/config/loginusers.vdf").resolve()),
                "--instant",
            )
            self.assertFalse(helper.switch_button.isEnabled())
            self.assertFalse(helper.switch_instant_button.isEnabled())
            self.assertFalse(helper.start_game_button.isEnabled())
            self.assertIs(helper._active_button(), helper.switch_instant_button)

            helper._on_worker_finished("Steam restarted for alpha.")

            self.assertTrue(helper.switch_button.isEnabled())
            self.assertTrue(helper.switch_instant_button.isEnabled())
            self.assertTrue(helper.start_game_button.isEnabled())
        finally:
            helper.close()

    def test_worker_failure_restores_controls_without_dialog(self) -> None:
        helper = self._helper()
        try:
            with (
                patch(
                    "source.launcher.switch_steam_helper.steam_accounts.load_steam_accounts",
                    return_value=ACCOUNTS,
                ),
                patch.object(helper, "_start_worker"),
            ):
                helper.switch_account()

            helper._on_worker_finished("Failed: restart failed")

            self.assertFalse(helper.status_spinner.timer.isActive())
            self.assertTrue(helper.account_combo.isEnabled())
            self.assertTrue(helper.switch_button.isEnabled())
            self.assertTrue(helper.switch_instant_button.isEnabled())
            self.assertEqual(helper.status.text(), "Failed: restart failed")
            self.assertFalse(hasattr(helper.owner, "dialog"))
        finally:
            helper.close()

    def test_ready_status_and_hotkey_only_focus(self) -> None:
        helper = self._helper()
        try:
            with (
                patch(
                    "source.launcher.switch_steam_helper.steam_accounts.load_steam_accounts",
                    return_value=ACCOUNTS,
                ),
                patch.object(helper, "_start_worker"),
            ):
                helper.switch_account()

            helper._on_worker_ready()
            self.assertEqual(helper.status.text(), "Restarting Steam as beta...")
            self.assertFalse(helper.status_spinner.timer.isActive())

            with patch.object(helper, "refocus_helper") as refocus:
                helper.handle_hotkey()

            refocus.assert_called_once_with()
            self.assertTrue(helper.switching)
        finally:
            helper.close()

    def test_tools_open_registers_helper_and_refocuses_duplicate(self) -> None:
        helper = Mock()
        launcher = SimpleNamespace(
            _can_open_setup_helper=Mock(return_value=True),
            find_deposit_helper=Mock(side_effect=[None, helper]),
            close_external_helpers=Mock(),
            register_deposit_helper=Mock(),
        )

        with patch("source.launcher.pages.helpers.SwitchSteamHelper", return_value=helper):
            SettingsGUI.open_switch_steam_helper(launcher)
            SettingsGUI.open_switch_steam_helper(launcher)

        launcher.register_deposit_helper.assert_called_once_with(helper)
        launcher.close_external_helpers.assert_called_once_with()
        self.assertEqual(helper.show.call_count, 2)
        self.assertEqual(helper.raise_.call_count, 2)
        self.assertEqual(helper.activateWindow.call_count, 2)

    def test_worker_uses_reorganized_runner_module(self) -> None:
        helper = self._helper()
        process = Mock()
        process.stdout = None
        try:
            with (
                patch(
                    "source.launcher.components.helper_window.subprocess.Popen",
                    return_value=process,
                ) as popen,
                patch(
                    "source.launcher.components.helper_window.threading.Thread"
                ) as thread,
            ):
                helper._start_worker("switch_steam", "--account", "beta")

            command = popen.call_args.args[0]
            self.assertEqual(
                command[:4],
                [
                    sys.executable,
                    "-u",
                    "-m",
                    "source.launcher.components.helper_runner",
                ],
            )
            thread.return_value.start.assert_called_once_with()
        finally:
            helper.worker_process = None
            helper.close()

    def test_failed_worker_output_is_logged_as_stack_trace(self) -> None:
        helper = self._helper()
        try:
            helper.worker_debug_lines = [
                "Traceback (most recent call last):",
                "RuntimeError: test failure",
            ]
            with patch(
                "source.launcher.components.helper_window.logs.logger.error"
            ) as log_error:
                helper._log_worker_debug_output("Failed: test failure")

            log_error.assert_called_once_with(
                "Helper worker failed: %s\n%s",
                "Failed: test failure",
                "Traceback (most recent call last):\nRuntimeError: test failure",
            )
        finally:
            helper.close()

    def test_worker_waits_for_real_exit_code_instead_of_reporting_none(self) -> None:
        helper = self._helper()
        process = Mock()
        process.stdout = ["Traceback: startup failure\n"]
        process.poll.return_value = None
        process.wait.return_value = 1
        try:
            with (
                patch.object(helper, "_emit_worker_finished") as finished,
                patch("source.launcher.components.helper_window.logs.logger.error"),
            ):
                helper._read_worker_output(process)

            process.wait.assert_called_once_with(timeout=1)
            finished.assert_called_once_with("Failed: helper exited with code 1.")
        finally:
            helper.close()
