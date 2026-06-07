import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from source.launcher.deposit_helper_capture import capture_ccc_yaw_pitch


class DepositHelperCaptureTests(unittest.TestCase):
    def test_capture_ccc_yaw_pitch_preserves_character_state(self):
        console = SimpleNamespace(
            console_ccc=Mock(return_value=["X", "Y", "Z", "12.5", "-3.25"])
        )

        with (
            patch("source.launcher.deposit_helper_capture.focus_game_window"),
            patch.dict("sys.modules", {"source.ASA.player.console": console}),
        ):
            self.assertEqual(capture_ccc_yaw_pitch(), (12.5, -3.25))

        console.console_ccc.assert_called_once_with(reset_state_before_capture=False)


if __name__ == "__main__":
    unittest.main()
