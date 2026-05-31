import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from source.launcher.deposit_helper_capture import focus_game_window
from source.launcher.fertilizer_refresh_helper import FertilizerRefreshHelper
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

    def styleSheet(self):
        return ""

    def screen(self):
        return None

    def is_program_running(self):
        return False

    def require_ark_window(self, _action):
        return False


class FertilizerStartValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch(
        "source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey",
        return_value=False,
    )
    def test_invalid_ark_window_does_not_start_worker(self, _register_hotkey):
        helper = FertilizerRefreshHelper(_RejectedOwner())
        try:
            helper.start()
            self.assertIsNone(helper.worker_thread)
            self.assertEqual(helper.start_stop_button.text(), "START")
            self.assertIn("window was not found", helper.status.text())
        finally:
            helper.close()


if __name__ == "__main__":
    unittest.main()
