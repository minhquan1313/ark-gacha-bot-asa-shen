import os
import types
import unittest
from unittest.mock import Mock, call, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from source.launcher.deposit_helper_capture import focus_game_window
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


if __name__ == "__main__":
    unittest.main()
