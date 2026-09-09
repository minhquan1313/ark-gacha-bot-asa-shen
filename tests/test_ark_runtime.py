import unittest
import weakref
from unittest.mock import patch

from source.utility import ark_runtime


class ArkRuntimeTests(unittest.TestCase):
    def setUp(self):
        ark_runtime._paused = False
        ark_runtime._pause_reason = ""
        ark_runtime._pause_started = 0.0
        ark_runtime._last_pause_check = 0.0
        for patcher in (
            patch.object(ark_runtime, "STARTED", float("-inf")),
            patch.object(ark_runtime.utils_simple, "_live_clocks", weakref.WeakSet()),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_focus_is_checked_before_pause_menu(self):
        with (
            patch.object(ark_runtime, "is_ark_window_open", return_value=True),
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
            patch.object(ark_runtime, "is_ark_window_open", return_value=True),
            patch.object(
                ark_runtime, "is_ark_foreground", side_effect=[False, True]
            ),
            patch.object(ark_runtime, "_pause_menu_is_visible", return_value=False),
            patch.object(ark_runtime.time, "sleep"),
            patch.object(ark_runtime, "emit_runner_state") as emit,
        ):
            ark_runtime.wait_until_ready()

        self.assertEqual([call.args[0] for call in emit.call_args_list], ["PAUSED", "RUNNING"])

    def test_missing_ark_window_does_not_pause_input(self):
        with (
            patch.object(ark_runtime, "is_ark_window_open", return_value=False),
            patch.object(ark_runtime, "is_ark_foreground") as foreground,
            patch.object(ark_runtime, "_pause_menu_is_visible") as pause_menu,
            patch.object(ark_runtime.time, "sleep") as sleep,
        ):
            ark_runtime.wait_until_ready()

        foreground.assert_not_called()
        pause_menu.assert_not_called()
        sleep.assert_not_called()

    def test_repeated_pause_state_does_not_emit_again(self):
        with patch.object(ark_runtime, "emit_runner_state") as emit:
            ark_runtime._set_paused("FOCUS")
            ark_runtime._set_paused("MENU")

        emit.assert_called_once_with("PAUSED")

    def test_clocks_adjust_once_per_resume_before_running_event(self):
        with (
            patch.object(ark_runtime.utils_simple, "adjust_clocks_after_pause") as adjust,
            patch.object(ark_runtime, "emit_runner_state") as emit,
        ):
            def check_adjustment(state: str):
                """Verify each running event follows its clock adjustment."""
                if state == "RUNNING":
                    self.assertEqual(adjust.call_count, count)

            emit.side_effect = check_adjustment
            ark_runtime._set_running()
            adjust.assert_not_called()
            for count in (1, 2):
                ark_runtime._set_paused("FOCUS")
                ark_runtime._set_paused("MENU")
                ark_runtime._set_running()
                ark_runtime._set_running()
                self.assertEqual(adjust.call_count, count)
                self.assertEqual(ark_runtime._pause_started, 0.0)

    def test_resume_preserves_remaining_time_across_pause_cycles(self):
        with (
            patch.object(ark_runtime.time, "monotonic", return_value=100) as now,
            patch.object(ark_runtime, "emit_runner_state"),
        ):
            clock = ark_runtime.utils_simple.TimedOutCounter(180)
            now.return_value = 220
            ark_runtime._set_paused("FOCUS")
            now.return_value = 250
            ark_runtime._set_paused("MENU")
            now.return_value = 520
            ark_runtime._set_running()
            self.assertEqual(clock.remain(), 60)
            self.assertEqual(clock.eslapsed(), 120)
            self.assertFalse(clock())

            now.return_value = 540
            ark_runtime._set_paused("MENU")
            now.return_value = 640
            ark_runtime._set_running()
            self.assertEqual(clock.remain(), 40)
            self.assertEqual(clock.eslapsed(), 140)
            now.return_value = 679
            self.assertFalse(clock())
            now.return_value = 680
            self.assertTrue(clock())

    def test_resume_adjusts_clocks_created_or_reset_during_pause(self):
        with (
            patch.object(ark_runtime.utils_simple.time, "monotonic", return_value=100) as now,
            patch.object(ark_runtime, "emit_runner_state"),
        ):
            before = ark_runtime.utils_simple.get_default_clock(10)
            reset_during = ark_runtime.utils_simple.get_default_clock(30)
            now.return_value = 105
            ark_runtime._set_paused("FOCUS")
            now.return_value = 120
            during = ark_runtime.utils_simple.get_default_clock(20)
            reset_during.reset()
            now.return_value = 200
            ark_runtime._set_running()
            self.assertEqual(before.remain(), 5)
            self.assertEqual(during.remain(), 20)
            self.assertEqual(reset_during.remain(), 30)
            self.assertEqual(before.eslapsed(), 5)
            self.assertEqual(during.eslapsed(), 0)
            self.assertEqual(reset_during.eslapsed(), 0)

    def test_temporary_disable_does_not_adjust_clocks(self):
        with patch.object(ark_runtime.utils_simple, "adjust_clocks_after_pause") as adjust:
            with ark_runtime.temporary_disable():
                ark_runtime.wait_until_ready()
            adjust.assert_not_called()


if __name__ == "__main__":
    unittest.main()
