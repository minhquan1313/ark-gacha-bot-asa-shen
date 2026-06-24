import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch

from source.join_sim.source.server_number import normalize_server_number


join_main = types.ModuleType("source.join_sim.source.main")
join_main.is_menu = Mock(return_value=False)
join_main.join_round = Mock(return_value=True)
crash = types.ModuleType("source.join_sim.source.crash.crash")
crash.detect_crash = Mock(return_value=False)
crash.re_open_game = Mock()

with patch.dict(
    sys.modules,
    {
        "source.join_sim.source.main": join_main,
        "source.join_sim.source.crash.crash": crash,
    },
):
    auto_join = importlib.import_module("source.join_sim.source.auto_join")


class FakeClock:
    def __init__(self) -> None:
        self.value = 0

    def now(self) -> int:
        return self.value

    def sleep(self, seconds: int | float) -> None:
        self.value += seconds


class AutoJoinServerTests(unittest.TestCase):
    def setUp(self) -> None:
        focus_patcher = patch.object(
            auto_join.deposit_helper_capture, "focus_game_window"
        )
        focus_patcher.start()
        self.addCleanup(focus_patcher.stop)
        join_main.is_menu.reset_mock(return_value=True, side_effect=True)
        join_main.is_menu.return_value = False
        join_main.join_round.reset_mock(return_value=True, side_effect=True)
        join_main.join_round.return_value = True
        crash.detect_crash.reset_mock(return_value=True, side_effect=True)
        crash.detect_crash.return_value = False
        crash.re_open_game.reset_mock(return_value=True, side_effect=True)

    def test_normalize_server_number_rejects_invalid_values(self):
        for value in ["", "0", "abc", "12a"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_server_number(value)

        self.assertEqual(normalize_server_number(" 5147 "), "5147")

    def test_exits_successfully_when_join_round_returns_true(self):
        statuses = []
        clock = FakeClock()

        with (
            patch.object(auto_join.time, "sleep", side_effect=clock.sleep),
            patch.object(auto_join.time, "monotonic", side_effect=clock.now),
        ):
            result = auto_join.run_auto_join_server("5147", statuses.append)

        self.assertTrue(result)
        join_main.join_round.assert_called_once_with("5147")
        self.assertEqual(statuses[-1], "Joined server 5147.")

    def test_keeps_retrying_until_join_round_succeeds(self):
        clock = FakeClock()
        join_main.join_round.side_effect = [False, False, True]

        with (
            patch.object(auto_join.time, "sleep", side_effect=clock.sleep),
            patch.object(auto_join.time, "monotonic", side_effect=clock.now),
        ):
            result = auto_join.run_auto_join_server("5147")

        self.assertTrue(result)
        self.assertEqual(join_main.join_round.call_count, 3)

    def test_triggers_crash_reopen_before_retrying(self):
        clock = FakeClock()
        crash.detect_crash.side_effect = [True, False]
        statuses = []

        with (
            patch.object(auto_join.time, "sleep", side_effect=clock.sleep),
            patch.object(auto_join.time, "monotonic", side_effect=clock.now),
        ):
            result = auto_join.run_auto_join_server("5147", statuses.append)

        self.assertTrue(result)
        crash.re_open_game.assert_called_once_with()
        join_main.join_round.assert_called_once_with("5147")
        self.assertGreaterEqual(clock.value, auto_join.REOPEN_PAUSE_SECONDS)

    def test_triggers_periodic_reopen_while_still_in_menu(self):
        clock = FakeClock()
        join_main.is_menu.return_value = True
        join_main.join_round.side_effect = [False, True]
        statuses = []

        with (
            patch.object(auto_join.time, "sleep", side_effect=clock.sleep),
            patch.object(
                auto_join.time,
                "monotonic",
                side_effect=[0, 901, 901, 901, 901],
            ),
            patch.object(auto_join, "REOPEN_PAUSE_SECONDS", 0),
        ):
            result = auto_join.run_auto_join_server("5147", statuses.append)

        self.assertTrue(result)
        crash.re_open_game.assert_called_once_with()
        self.assertEqual(join_main.join_round.call_count, 2)


if __name__ == "__main__":
    unittest.main()
