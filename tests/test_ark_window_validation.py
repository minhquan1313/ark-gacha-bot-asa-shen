import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from source.launcher.deposit_helper_capture import focus_game_window
from source.launcher.fertilizer_refresh_helper import FertilizerRefreshHelper
from source.launcher.gui import SettingsGUI
from source.launcher.system import validate_ark_window


class ArkWindowValidationTests(unittest.TestCase):
    @patch("source.launcher.system.find_window_size", return_value=(1920, 1080))
    def test_accepts_supported_resolution(self, _find_window_size):
        self.assertEqual(validate_ark_window(), (1920, 1080))

    @patch("source.launcher.system.find_window_size", return_value=None)
    def test_rejects_missing_window(self, _find_window_size):
        with self.assertRaisesRegex(RuntimeError, "window was not found"):
            validate_ark_window()

    @patch("source.launcher.system.find_window_size", return_value=(2560, 1440))
    def test_rejects_unsupported_resolution(self, _find_window_size):
        with self.assertRaisesRegex(RuntimeError, "2560x1440"):
            validate_ark_window()

    @patch(
        "source.launcher.deposit_helper_capture.validate_ark_window",
        side_effect=RuntimeError("invalid Ark window"),
    )
    def test_focus_game_window_revalidates_before_focusing(self, _validate):
        with self.assertRaisesRegex(RuntimeError, "invalid Ark window"):
            focus_game_window()


class _RejectedOwner:
    program_stopping = False
    last_ark_window_error = "ArkAscended window was not found."
    settings = {"helper_inactive_opacity": 0.3}

    def __init__(self):
        self.program_running = False
        self.required_dialog_parent = None
        self.dialog_calls = []

    def styleSheet(self):
        return ""

    def screen(self):
        return None

    def is_program_running(self):
        return self.program_running

    def require_ark_window(self, _action, dialog_parent=None):
        self.required_dialog_parent = dialog_parent
        return False

    def dialog(self, title, message, variant="info", parent=None):
        self.dialog_calls.append((title, message, variant, parent))


class FertilizerStartValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch(
        "source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey",
        return_value=False,
    )
    def test_invalid_ark_window_does_not_start_worker(self, _register_hotkey):
        owner = _RejectedOwner()
        helper = FertilizerRefreshHelper(owner)
        try:
            helper.start()
            self.assertIsNone(helper.worker_thread)
            self.assertEqual(helper.start_stop_button.text(), "START")
            self.assertIn("window was not found", helper.status.text())
            self.assertIs(owner.required_dialog_parent, helper)
        finally:
            helper.close()

    @patch(
        "source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey",
        return_value=False,
    )
    def test_running_program_warning_belongs_to_helper(self, _register_hotkey):
        owner = _RejectedOwner()
        owner.program_running = True
        helper = FertilizerRefreshHelper(owner)
        try:
            helper.start()
            self.assertEqual(len(owner.dialog_calls), 1)
            self.assertEqual(owner.dialog_calls[0][0], "Stop Program First")
            self.assertIs(owner.dialog_calls[0][3], helper)
        finally:
            helper.close()


class DialogOwnershipTests(unittest.TestCase):
    @patch(
        "source.launcher.gui.validate_ark_window",
        side_effect=RuntimeError("invalid Ark window"),
    )
    def test_window_validation_forwards_dialog_parent(self, _validate):
        launcher = Mock()
        helper = Mock()

        self.assertFalse(
            SettingsGUI.require_ark_window(
                launcher, "start fertilizer refresh", dialog_parent=helper
            )
        )
        launcher.dialog.assert_called_once_with(
            "ArkAscended Required",
            "invalid Ark window",
            "error",
            parent=helper,
        )

    def test_existing_parent_dialog_is_focused_instead_of_duplicated(self):
        parent = Mock()
        active_dialog = Mock()
        active_dialog.isVisible.return_value = True
        active_dialog.result.return_value = 7
        parent._active_cyber_dialog = active_dialog

        with patch("source.launcher.gui.CyberDialog") as cyber_dialog:
            result = SettingsGUI.dialog(
                Mock(), "ArkAscended Required", "Invalid resolution", parent=parent
            )

        self.assertEqual(result, 7)
        cyber_dialog.assert_not_called()
        active_dialog.show.assert_called_once_with()
        active_dialog.raise_.assert_called_once_with()
        active_dialog.activateWindow.assert_called_once_with()

    def test_new_parent_dialog_brings_helper_forward_and_clears_tracking(self):
        parent = Mock()
        parent._active_cyber_dialog = None

        with patch("source.launcher.gui.CyberDialog") as cyber_dialog:
            cyber_dialog.return_value.exec.return_value = 1
            result = SettingsGUI.dialog(
                Mock(), "ArkAscended Required", "Invalid resolution", parent=parent
            )

        self.assertEqual(result, 1)
        parent.show.assert_called_once_with()
        parent.raise_.assert_called_once_with()
        parent.activateWindow.assert_called_once_with()
        cyber_dialog.assert_called_once_with(
            parent, "ArkAscended Required", "Invalid resolution", "info"
        )
        self.assertIsNone(parent._active_cyber_dialog)


if __name__ == "__main__":
    unittest.main()
