import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from source.launcher.auto_fishing_helper import AutoFishingHelper
from source.launcher.gui import SettingsGUI


class AutoFishingHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _owner():
        return SimpleNamespace(
            styleSheet=Mock(return_value=""),
            screen=Mock(return_value=None),
            settings={"helper_inactive_opacity": 0.3},
            isActiveWindow=Mock(return_value=False),
            is_program_running=Mock(return_value=False),
            program_stopping=False,
            require_ark_window=Mock(return_value=True),
            last_ark_window_error="",
            dialog=Mock(),
            forget_deposit_helper=Mock(),
        )

    def test_defaults_to_single_run_and_starts_without_infinite_flag(self):
        with patch(
            "source.launcher.auto_fishing_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            helper = AutoFishingHelper(self._owner())
        try:
            self.assertEqual(helper.description.text(), "...")
            self.assertFalse(helper.infinite_switch.isChecked())
            with (
                patch("source.launcher.auto_fishing_helper.focus_game_window"),
                patch.object(helper, "_start_worker") as start_worker,
            ):
                helper.start()
            start_worker.assert_called_once_with("auto_fishing")
        finally:
            helper.close()

    def test_infinite_switch_passes_runner_flag(self):
        with patch(
            "source.launcher.auto_fishing_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            helper = AutoFishingHelper(self._owner())
        try:
            helper.infinite_switch.setChecked(True)
            with (
                patch("source.launcher.auto_fishing_helper.focus_game_window"),
                patch.object(helper, "_start_worker") as start_worker,
            ):
                helper.start()
            start_worker.assert_called_once_with("auto_fishing", "--infinite")
        finally:
            helper.close()

    def test_tools_page_opens_auto_fishing_helper(self):
        helper = Mock()
        launcher = SimpleNamespace(
            _can_open_setup_helper=Mock(return_value=True),
            find_deposit_helper=Mock(return_value=None),
            close_external_helpers=Mock(),
            register_deposit_helper=Mock(),
        )

        with patch(
            "source.launcher.pages.helpers.AutoFishingHelper",
            return_value=helper,
        ):
            SettingsGUI.open_auto_fishing_helper(launcher)

        launcher.close_external_helpers.assert_called_once_with()
        launcher.register_deposit_helper.assert_called_once_with(helper)
        helper.show.assert_called_once_with()
        helper.raise_.assert_called_once_with()
        helper.activateWindow.assert_called_once_with()

    def test_tools_page_reuses_existing_auto_fishing_helper(self):
        helper = Mock()
        launcher = SimpleNamespace(
            _can_open_setup_helper=Mock(return_value=True),
            find_deposit_helper=Mock(return_value=helper),
            close_external_helpers=Mock(),
            register_deposit_helper=Mock(),
        )

        SettingsGUI.open_auto_fishing_helper(launcher)

        launcher.close_external_helpers.assert_not_called()
        launcher.register_deposit_helper.assert_not_called()
        helper.show.assert_called_once_with()
        helper.raise_.assert_called_once_with()
        helper.activateWindow.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
