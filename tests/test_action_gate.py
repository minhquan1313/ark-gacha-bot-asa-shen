import unittest
from unittest.mock import patch

from source.utility import action_gate


class ActionGateTests(unittest.TestCase):
    def test_before_action_waits_until_pause_conditions_clear(self):
        with patch.object(
            action_gate.ark_runtime, "wait_until_ready"
        ) as wait_until_ready:
            action_gate.before_ark_action()
            action_gate.before_ark_action()

        self.assertEqual(wait_until_ready.call_count, 2)

    def test_input_helpers_wait_before_sending_by_default(self):
        """Automation cannot send input until its pause gate returns."""
        from source.utility import utils

        for helper in (utils.action_down, utils.key_hold_down):
            with (
                self.subTest(helper=helper.__name__),
                patch.object(action_gate, "before_ark_action", side_effect=RuntimeError("paused")),
                patch.object(utils.ctypes, "windll") as windll,
            ):
                with self.assertRaisesRegex(RuntimeError, "paused"):
                    helper("Use")
                windll.user32.PostMessageW.assert_not_called()
                windll.user32.keybd_event.assert_not_called()
                windll.user32.SendInput.assert_not_called()

    def test_input_helpers_can_send_without_entering_pause_gate(self):
        """Auto Keys can send input without waiting for automation pause conditions."""
        from source.utility import utils

        for helper in (utils.action_down, utils.key_hold_down):
            with (
                self.subTest(helper=helper.__name__),
                patch.object(action_gate, "before_ark_action", side_effect=AssertionError("unexpected pause")),
                patch.object(utils.local_player, "get_input_settings", return_value="e"),
                patch.object(utils.windows, "ark_hwnd", return_value=123),
                patch.object(utils, "keymap_return", return_value=0x45),
                patch.object(utils.ctypes, "windll") as windll,
            ):
                windll.user32.MapVirtualKeyW.return_value = 0x12
                windll.user32.SendInput.return_value = 1
                helper("Use", should_pause=False)

                if helper is utils.action_down:
                    windll.user32.PostMessageW.assert_called_once_with(123, utils.WM_KEYDOWN, 0x45, 0)
                else:
                    windll.user32.SendInput.assert_called_once()


if __name__ == "__main__":
    unittest.main()
