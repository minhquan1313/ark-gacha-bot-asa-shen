import os
import threading
import types
import unittest
from unittest.mock import Mock, call, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

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
        user32.GetForegroundWindow.return_value = 456
        user32.SetCursorPos.return_value = True

        def set_window_rect(_hwnd, rect_pointer):
            rect_pointer._obj.left = 100
            rect_pointer._obj.top = 200
            rect_pointer._obj.right = 2020
            rect_pointer._obj.bottom = 1280
            return True

        user32.GetWindowRect.side_effect = set_window_rect
        windll = types.SimpleNamespace(user32=user32)

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
        user32.GetForegroundWindow.return_value = 456
        windll = types.SimpleNamespace(user32=user32)

        with patch.object(system.ctypes, "windll", windll):
            self.assertTrue(focus_window_if_needed("ArkAscended"))

        user32.ShowWindow.assert_called_once_with(123, 9)
        user32.GetWindowRect.assert_not_called()
        user32.SetCursorPos.assert_not_called()
        user32.SetForegroundWindow.assert_called_once_with(123)

    def test_focus_window_if_needed_reports_window_position_failure(self):
        user32 = Mock()
        user32.FindWindowW.return_value = 123
        user32.GetForegroundWindow.return_value = 456
        user32.GetWindowRect.return_value = False
        windll = types.SimpleNamespace(user32=user32)

        with (
            patch.object(system.ctypes, "windll", windll),
            self.assertRaisesRegex(RuntimeError, "window position"),
        ):
            focus_window_if_needed("ArkAscended", center_cursor_when_switching=True)

        user32.SetCursorPos.assert_not_called()
        user32.SetForegroundWindow.assert_not_called()

    def test_focus_window_if_needed_reports_cursor_position_failure(self):
        user32 = Mock()
        user32.FindWindowW.return_value = 123
        user32.GetForegroundWindow.return_value = 456
        user32.SetCursorPos.return_value = False

        def set_window_rect(_hwnd, rect_pointer):
            rect_pointer._obj.left = 100
            rect_pointer._obj.top = 200
            rect_pointer._obj.right = 2020
            rect_pointer._obj.bottom = 1280
            return True

        user32.GetWindowRect.side_effect = set_window_rect
        windll = types.SimpleNamespace(user32=user32)

        with (
            patch.object(system.ctypes, "windll", windll),
            self.assertRaisesRegex(RuntimeError, "center the mouse cursor"),
        ):
            focus_window_if_needed("ArkAscended", center_cursor_when_switching=True)

        user32.SetForegroundWindow.assert_not_called()

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

    def tearDown(self):
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.processEvents()

    def test_helper_starts_at_middle_right(self):
        helper = Mock()
        rect = Mock()
        rect.right.return_value = 1919
        rect.top.return_value = 0
        rect.height.return_value = 1080
        helper.screen.return_value.availableGeometry.return_value = rect
        helper.width.return_value = 440
        helper.height.return_value = 250

        FertilizerRefreshHelper._position_middle_right(helper)

        helper.move.assert_called_once_with(1461, 415)

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

    @patch(
        "source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey",
        return_value=False,
    )
    def test_start_focuses_ark_before_launching_worker(self, _register_hotkey):
        helper = Mock()
        helper.is_running.return_value = False
        helper.closing = False
        helper.owner.is_program_running.return_value = False
        helper.owner.program_stopping = False
        helper._require_ark_window.return_value = True
        worker = Mock()
        events = []
        fake_threading = types.SimpleNamespace(
            Event=threading.Event,
            Thread=lambda **_kwargs: events.append("thread") or worker,
        )
        with (
            patch(
                "source.launcher.fertilizer_refresh_helper.focus_game_window",
                side_effect=lambda **_kwargs: events.append("focus"),
            ) as focus,
            patch(
                "source.launcher.fertilizer_refresh_helper.threading",
                fake_threading,
            ),
        ):
            FertilizerRefreshHelper.start(helper)

        self.assertEqual(events, ["focus", "thread"])
        focus.assert_called_once_with(center_cursor_when_switching=True)
        self.assertIs(helper.worker_thread, worker)
        worker.start.assert_called_once_with()

    @patch(
        "source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey",
        return_value=False,
    )
    @patch(
        "source.launcher.fertilizer_refresh_helper.focus_game_window",
        side_effect=RuntimeError("unable to focus Ark"),
    )
    def test_focus_failure_does_not_start_worker(self, _focus, _register_hotkey):
        helper = Mock()
        helper.is_running.return_value = False
        helper.closing = False
        helper.owner.is_program_running.return_value = False
        helper.owner.program_stopping = False
        helper._require_ark_window.return_value = True
        helper.worker_thread = None

        FertilizerRefreshHelper.start(helper)

        self.assertIsNone(helper.worker_thread)
        helper.status.setText.assert_called_once_with(
            "Cannot start: unable to focus Ark"
        )

    @patch(
        "source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey",
        return_value=False,
    )
    def test_close_defers_without_joining_live_worker(self, _register_hotkey):
        with patch.object(FertilizerRefreshHelper, "_position_middle_right"):
            helper = FertilizerRefreshHelper(_RejectedOwner())
        worker = Mock()
        worker.is_alive.return_value = True
        helper.worker_thread = worker
        event = Mock()

        try:
            helper.closeEvent(event)

            self.assertTrue(helper.stop_event.is_set())
            self.assertEqual(helper.status.text(), "Stopping...")
            self.assertFalse(helper.start_stop_button.isEnabled())
            event.ignore.assert_called_once_with()
            worker.join.assert_not_called()
        finally:
            worker.is_alive.return_value = False
            helper.close()

    @patch(
        "source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey",
        return_value=False,
    )
    def test_worker_finish_finalizes_deferred_close(self, _register_hotkey):
        with patch.object(FertilizerRefreshHelper, "_position_middle_right"):
            helper = FertilizerRefreshHelper(_RejectedOwner())
        helper.closing = True

        with patch.object(helper, "close") as close:
            helper._on_worker_finished("")

        self.assertIsNone(helper.worker_thread)
        close.assert_called_once_with()

    @patch(
        "source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey",
        return_value=False,
    )
    def test_stop_reports_stopped_immediately_and_disables_restart(
        self, _register_hotkey
    ):
        with patch.object(FertilizerRefreshHelper, "_position_middle_right"):
            helper = FertilizerRefreshHelper(_RejectedOwner())
        worker = Mock()
        worker.is_alive.return_value = True
        helper.worker_thread = worker
        try:
            helper.stop()

            self.assertTrue(helper.stop_event.is_set())
            self.assertEqual(helper.status.text(), "Stopped.")
            self.assertEqual(helper.start_stop_button.text(), "START")
            self.assertFalse(helper.start_stop_button.isEnabled())
        finally:
            worker.is_alive.return_value = False
            helper.close()

    @patch(
        "source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey",
        return_value=False,
    )
    def test_worker_finish_reenables_restart(self, _register_hotkey):
        with patch.object(FertilizerRefreshHelper, "_position_middle_right"):
            helper = FertilizerRefreshHelper(_RejectedOwner())
        try:
            helper.start_stop_button.setEnabled(False)
            helper._on_worker_finished("")

            self.assertTrue(helper.start_stop_button.isEnabled())
            self.assertEqual(helper.status.text(), "Stopped.")
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
