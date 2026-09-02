import unittest
from unittest.mock import patch

from source.utility import ark_runtime


class ArkRuntimeTests(unittest.TestCase):
    def setUp(self):
        ark_runtime._paused = False
        ark_runtime._pause_reason = ""
        ark_runtime._last_pause_check = 0.0

    def test_focus_is_checked_before_pause_menu(self):
        with (
            patch.object(
                ark_runtime, "is_ark_foreground", side_effect=[False, True, True]
            ),
            patch.object(ark_runtime, "_pause_menu_is_visible") as pause_menu,
            patch.object(ark_runtime.time, "sleep"),
        ):
            ark_runtime.wait_until_ready()

        self.assertEqual(pause_menu.call_count, 1)

    def test_focus_pause_emits_once_and_resumes_once(self):
        with (
            patch.object(
                ark_runtime, "is_ark_foreground", side_effect=[False, True]
            ),
            patch.object(ark_runtime, "_pause_menu_is_visible", return_value=False),
            patch.object(ark_runtime.time, "sleep"),
            patch.object(ark_runtime, "emit_runner_state") as emit,
        ):
            ark_runtime.wait_until_ready()

        self.assertEqual([call.args[0] for call in emit.call_args_list], ["PAUSED", "RUNNING"])

    def test_repeated_pause_state_does_not_emit_again(self):
        with patch.object(ark_runtime, "emit_runner_state") as emit:
            ark_runtime._set_paused("FOCUS")
            ark_runtime._set_paused("MENU")

        emit.assert_called_once_with("PAUSED")


if __name__ == "__main__":
    unittest.main()
