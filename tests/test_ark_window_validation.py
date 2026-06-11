import os
import threading
import types
import unittest
from unittest.mock import Mock, call, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from source.launcher.auto_join_server_helper import AutoJoinServerHelper
from source.launcher.deposit_helper_capture import focus_game_window
from source.launcher.fertilizer_refresh_helper import FertilizerRefreshHelper
from source.launcher.gui import SettingsGUI
from source.launcher import system
from source.launcher.system import focus_window_if_needed, validate_ark_window


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

    def test_focus_window_if_needed_returns_false_for_missing_window(self):
        user32 = Mock()
        user32.FindWindowW.return_value = 0
        windll = types.SimpleNamespace(user32=user32)

        with patch.object(system.ctypes, "windll", windll):
            self.assertFalse(focus_window_if_needed("ArkAscended"))

        user32.GetForegroundWindow.assert_not_called()

    def test_focus_window_if_needed_centers_cursor_before_switching_to_ark(self):
        user32 = Mock()
        user32.FindWindowW.return_value = 123
        user32.GetForegroundWindow.side_effect = [456, 123]
        user32.GetWindowThreadProcessId.return_value = 789
        user32.AttachThreadInput.return_value = True
        user32.SetCursorPos.return_value = True
        user32.SetForegroundWindow.return_value = True
        kernel32 = Mock()
        kernel32.GetCurrentThreadId.return_value = 321

        def set_window_rect(_hwnd, rect_pointer):
            rect_pointer._obj.left = 100
            rect_pointer._obj.top = 200
            rect_pointer._obj.right = 2020
            rect_pointer._obj.bottom = 1280
            return True

        user32.GetWindowRect.side_effect = set_window_rect
        windll = types.SimpleNamespace(user32=user32, kernel32=kernel32)

        with patch.object(system.ctypes, "windll", windll):
            self.assertTrue(
                focus_window_if_needed("ArkAscended", center_cursor_when_switching=True)
            )

        self.assertLess(
            user32.mock_calls.index(call.ShowWindow(123, 9)),
            user32.mock_calls.index(call.SetCursorPos(1060, 740)),
        )
        self.assertLess(
            user32.mock_calls.index(call.SetCursorPos(1060, 740)),
            user32.mock_calls.index(call.SetForegroundWindow(123)),
        )
        user32.AttachThreadInput.assert_has_calls(
            [call(321, 789, True), call(321, 789, False)]
        )

    def test_focus_window_if_needed_does_nothing_when_ark_is_foreground(self):
        user32 = Mock()
        user32.FindWindowW.return_value = 123
        user32.GetForegroundWindow.return_value = 123
        windll = types.SimpleNamespace(user32=user32)

        with patch.object(system.ctypes, "windll", windll):
            self.assertTrue(
                focus_window_if_needed("ArkAscended", center_cursor_when_switching=True)
            )

        user32.ShowWindow.assert_not_called()
        user32.GetWindowRect.assert_not_called()
        user32.SetCursorPos.assert_not_called()
        user32.SetForegroundWindow.assert_not_called()

    def test_focus_window_if_needed_default_does_not_move_cursor(self):
        user32 = Mock()
        user32.FindWindowW.return_value = 123
        user32.GetForegroundWindow.side_effect = [456, 123]
        user32.GetWindowThreadProcessId.return_value = 789
        user32.AttachThreadInput.return_value = True
        user32.SetForegroundWindow.return_value = True
        kernel32 = Mock()
        kernel32.GetCurrentThreadId.return_value = 321
        windll = types.SimpleNamespace(user32=user32, kernel32=kernel32)

        with patch.object(system.ctypes, "windll", windll):
            self.assertTrue(focus_window_if_needed("ArkAscended"))

        user32.ShowWindow.assert_called_once_with(123, 9)
        user32.BringWindowToTop.assert_called_once_with(123)
        user32.GetWindowRect.assert_not_called()
        user32.SetCursorPos.assert_not_called()
        user32.SetForegroundWindow.assert_called_once_with(123)
        user32.AttachThreadInput.assert_has_calls(
            [call(321, 789, True), call(321, 789, False)]
        )

    def test_focus_window_if_needed_reports_window_position_failure(self):
        user32 = Mock()
        user32.FindWindowW.return_value = 123
        user32.GetForegroundWindow.return_value = 456
        user32.GetWindowThreadProcessId.return_value = 789
        user32.AttachThreadInput.return_value = True
        user32.GetWindowRect.return_value = False
        kernel32 = Mock()
        kernel32.GetCurrentThreadId.return_value = 321
        windll = types.SimpleNamespace(user32=user32, kernel32=kernel32)

        with (
            patch.object(system.ctypes, "windll", windll),
            self.assertRaisesRegex(RuntimeError, "window position"),
        ):
            focus_window_if_needed("ArkAscended", center_cursor_when_switching=True)

        user32.SetCursorPos.assert_not_called()
        user32.SetForegroundWindow.assert_not_called()
        user32.AttachThreadInput.assert_has_calls(
            [call(321, 789, True), call(321, 789, False)]
        )

    def test_focus_window_if_needed_reports_cursor_position_failure(self):
        user32 = Mock()
        user32.FindWindowW.return_value = 123
        user32.GetForegroundWindow.return_value = 456
        user32.GetWindowThreadProcessId.return_value = 789
        user32.AttachThreadInput.return_value = True
        user32.SetCursorPos.return_value = False
        kernel32 = Mock()
        kernel32.GetCurrentThreadId.return_value = 321

        def set_window_rect(_hwnd, rect_pointer):
            rect_pointer._obj.left = 100
            rect_pointer._obj.top = 200
            rect_pointer._obj.right = 2020
            rect_pointer._obj.bottom = 1280
            return True

        user32.GetWindowRect.side_effect = set_window_rect
        windll = types.SimpleNamespace(user32=user32, kernel32=kernel32)

        with (
            patch.object(system.ctypes, "windll", windll),
            self.assertRaisesRegex(RuntimeError, "center the mouse cursor"),
        ):
            focus_window_if_needed("ArkAscended", center_cursor_when_switching=True)

        user32.SetForegroundWindow.assert_not_called()
        user32.AttachThreadInput.assert_has_calls(
            [call(321, 789, True), call(321, 789, False)]
        )

    def test_focus_window_if_needed_reports_rejected_activation(self):
        user32 = Mock()
        user32.FindWindowW.return_value = 123
        user32.GetForegroundWindow.return_value = 456
        user32.GetWindowThreadProcessId.return_value = 789
        user32.AttachThreadInput.return_value = True
        user32.SetForegroundWindow.return_value = False
        kernel32 = Mock()
        kernel32.GetCurrentThreadId.return_value = 321
        windll = types.SimpleNamespace(user32=user32, kernel32=kernel32)

        with (
            patch.object(system.ctypes, "windll", windll),
            self.assertRaisesRegex(RuntimeError, "Unable to focus ArkAscended"),
        ):
            focus_window_if_needed("ArkAscended")

        user32.AttachThreadInput.assert_has_calls(
            [call(321, 789, True), call(321, 789, False)]
        )

    def test_focus_window_if_needed_reports_thread_attachment_failure(self):
        user32 = Mock()
        user32.FindWindowW.return_value = 123
        user32.GetForegroundWindow.return_value = 456
        user32.GetWindowThreadProcessId.return_value = 789
        user32.AttachThreadInput.return_value = False
        kernel32 = Mock()
        kernel32.GetCurrentThreadId.return_value = 321
        windll = types.SimpleNamespace(user32=user32, kernel32=kernel32)

        with (
            patch.object(system.ctypes, "windll", windll),
            self.assertRaisesRegex(RuntimeError, "foreground thread"),
        ):
            focus_window_if_needed("ArkAscended")

        user32.ShowWindow.assert_not_called()
        user32.SetForegroundWindow.assert_not_called()
        user32.AttachThreadInput.assert_called_once_with(321, 789, True)

    @patch("source.launcher.system.time.sleep")
    @patch("source.launcher.system.time.monotonic", side_effect=[0.0, 0.1])
    def test_focus_window_if_needed_waits_for_delayed_foreground_switch(
        self, _monotonic, sleep
    ):
        user32 = Mock()
        user32.FindWindowW.return_value = 123
        user32.GetForegroundWindow.side_effect = [456, 456, 123]
        user32.GetWindowThreadProcessId.return_value = 789
        user32.AttachThreadInput.return_value = True
        user32.SetForegroundWindow.return_value = True
        kernel32 = Mock()
        kernel32.GetCurrentThreadId.return_value = 321
        windll = types.SimpleNamespace(user32=user32, kernel32=kernel32)

        with patch.object(system.ctypes, "windll", windll):
            self.assertTrue(focus_window_if_needed("ArkAscended"))

        sleep.assert_called_once_with(0.01)
        user32.AttachThreadInput.assert_has_calls(
            [call(321, 789, True), call(321, 789, False)]
        )

    @patch("source.launcher.system.time.sleep")
    @patch("source.launcher.system.time.monotonic", side_effect=[0.0, 0.25])
    def test_focus_window_if_needed_reports_foreground_mismatch(
        self, _monotonic, sleep
    ):
        user32 = Mock()
        user32.FindWindowW.return_value = 123
        user32.GetForegroundWindow.side_effect = [456, 456]
        user32.GetWindowThreadProcessId.return_value = 789
        user32.AttachThreadInput.return_value = True
        user32.SetForegroundWindow.return_value = True
        kernel32 = Mock()
        kernel32.GetCurrentThreadId.return_value = 321
        windll = types.SimpleNamespace(user32=user32, kernel32=kernel32)

        with (
            patch.object(system.ctypes, "windll", windll),
            self.assertRaisesRegex(RuntimeError, "did not become foreground"),
        ):
            focus_window_if_needed("ArkAscended")

        user32.AttachThreadInput.assert_has_calls(
            [call(321, 789, True), call(321, 789, False)]
        )
        sleep.assert_not_called()

    @patch(
        "source.launcher.deposit_helper_capture.focus_window_if_needed",
        return_value=False,
    )
    @patch("source.launcher.deposit_helper_capture.validate_ark_window")
    def test_focus_game_window_reports_missing_window(self, _validate, _focus):
        with self.assertRaisesRegex(RuntimeError, "window was not found"):
            focus_game_window()


class _RejectedOwner:
    program_stopping = False
    last_ark_window_error = "ArkAscended window was not found."
    settings = {"helper_inactive_opacity": 0.3}

    def __init__(self):
        self.program_running = False
        self.required_dialog_parent = None
        self.dialog_calls = []
        self.stop_program = Mock()

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


class AutoJoinStopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.processEvents()

    def _running_process(self):
        process = Mock()
        process.poll.return_value = None
        process.stdout = None
        return process

    def _make_running_helper(self, cls, owner=None):
        with patch.object(cls, "_position_middle_right"):
            helper = cls(owner or _RejectedOwner())
        helper.worker_process = self._running_process()
        return helper

    @patch("source.launcher.auto_join_server_helper.register_alt_n_hotkey", return_value=False)
    def test_auto_join_stop_terminates_helper_process(self, _register_hotkey):
        helper = self._make_running_helper(AutoJoinServerHelper)
        process = helper.worker_process
        try:
            with patch("source.launcher.helper_window.terminate_process_tree") as terminate:
                helper.stop()
            terminate.assert_called_once_with(process)
            self.assertEqual(helper.status.text(), "Stopping...")
            self.assertEqual(helper.start_stop_button.text(), "START")
        finally:
            if helper.worker_process is not None:
                helper.worker_process.poll.return_value = 1
            helper.close()

    @patch("source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey", return_value=False)
    def test_invalid_ark_window_does_not_start_worker(self, _register_hotkey):
        owner = _RejectedOwner()
        helper = FertilizerRefreshHelper(owner)
        try:
            helper.start()
            self.assertIsNone(helper.worker_process)
            self.assertEqual(helper.start_stop_button.text(), "START")
            self.assertIn("window was not found", helper.status.text())
            self.assertIs(owner.required_dialog_parent, helper)
        finally:
            helper.close()

    @patch("source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey", return_value=False)
    def test_start_focuses_ark_before_launching_subprocess(self, _register_hotkey):
        helper = Mock()
        helper.is_running.return_value = False
        helper.closing = False
        helper.owner.is_program_running.return_value = False
        helper.owner.program_stopping = False
        helper._require_ark_window.return_value = True
        with patch("source.launcher.fertilizer_refresh_helper.focus_game_window") as focus:
            FertilizerRefreshHelper.start(helper)

        focus.assert_called_once_with(center_cursor_when_switching=True)
        helper._start_worker.assert_called_once_with("fertilizer_refresh")

    @patch("source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey", return_value=False)
    def test_fertilizer_stop_terminates_helper_process(self, _register_hotkey):
        helper = self._make_running_helper(FertilizerRefreshHelper)
        process = helper.worker_process
        try:
            with patch("source.launcher.helper_window.terminate_process_tree") as terminate:
                helper.stop()
            terminate.assert_called_once_with(process)
            self.assertEqual(helper.status.text(), "Stopped.")
        finally:
            if helper.worker_process is not None:
                helper.worker_process.poll.return_value = 1
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
