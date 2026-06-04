import threading
import unittest
from unittest.mock import patch

from source.join_sim.source.auto_join import (
    join_round_cancellable,
    normalize_server_number,
    run_auto_join_server,
)


class FakeClock:
    def __init__(self):
        self.value = 0

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class AutoJoinServerTests(unittest.TestCase):
    def test_normalize_server_number_rejects_invalid_values(self):
        for value in ["", "0", "abc", "12a"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_server_number(value)

        self.assertEqual(normalize_server_number(" 5147 "), "5147")

    def test_exits_successfully_when_join_round_returns_true(self):
        stop_event = threading.Event()
        statuses = []
        calls = []
        clock = FakeClock()

        result = run_auto_join_server(
            "5147",
            stop_event,
            status_callback=statuses.append,
            join_round=lambda server: calls.append(server) or True,
            is_menu=lambda: False,
            detect_crash=lambda: False,
            re_open_game=lambda: None,
            sleep=clock.sleep,
            now=clock.now,
        )

        self.assertTrue(result)
        self.assertEqual(calls, ["5147"])
        self.assertEqual(statuses[-1], "Joined server 5147.")

    def test_keeps_retrying_until_join_round_succeeds(self):
        stop_event = threading.Event()
        clock = FakeClock()
        outcomes = [False, False, True]
        calls = []

        result = run_auto_join_server(
            "5147",
            stop_event,
            join_round=lambda server: calls.append(server) or outcomes.pop(0),
            is_menu=lambda: False,
            detect_crash=lambda: False,
            re_open_game=lambda: None,
            sleep=clock.sleep,
            now=clock.now,
            retry_delay=2,
        )

        self.assertTrue(result)
        self.assertEqual(calls, ["5147", "5147", "5147"])
        self.assertGreaterEqual(clock.value, 4)

    def test_stops_when_stop_event_is_set(self):
        stop_event = threading.Event()
        clock = FakeClock()
        calls = []

        def join_round(server):
            calls.append(server)
            stop_event.set()
            return False

        result = run_auto_join_server(
            "5147",
            stop_event,
            join_round=join_round,
            is_menu=lambda: False,
            detect_crash=lambda: False,
            re_open_game=lambda: None,
            sleep=clock.sleep,
            now=clock.now,
        )

        self.assertFalse(result)
        self.assertEqual(calls, ["5147"])

    def test_default_join_round_receives_stop_event(self):
        stop_event = threading.Event()
        clock = FakeClock()
        calls = []

        def join_round(server, received_stop_event):
            calls.append((server, received_stop_event))
            received_stop_event.set()
            return False

        with patch(
            "source.join_sim.source.auto_join.join_round_cancellable",
            side_effect=join_round,
        ):
            result = run_auto_join_server(
                "5147",
                stop_event,
                is_menu=lambda: False,
                detect_crash=lambda: False,
                re_open_game=lambda: None,
                sleep=clock.sleep,
                now=clock.now,
            )

        self.assertFalse(result)
        self.assertEqual(calls, [("5147", stop_event)])

    def test_cancellable_join_round_stops_before_first_action(self):
        stop_event = threading.Event()
        stop_event.set()

        with (
            patch("source.join_sim.source.auto_join._is_menu_cancellable", return_value=True),
            patch("source.join_sim.source.auto_join._click_start_cancellable") as click_start,
            patch("source.join_sim.source.auto_join._click_join_game_cancellable") as click_join_game,
            patch("source.join_sim.source.auto_join._join_server_cancellable") as join_server,
            patch("source.join_sim.source.auto_join._mod_menu_join_cancellable") as mod_menu_join,
            patch("source.join_sim.source.auto_join._has_failure_cancellable") as has_failure,
        ):
            result = join_round_cancellable("5147", stop_event)

        self.assertFalse(result)
        click_start.assert_not_called()
        click_join_game.assert_not_called()
        join_server.assert_not_called()
        mod_menu_join.assert_not_called()
        has_failure.assert_not_called()

    def test_cancellable_join_round_stops_during_wait_after_start(self):
        stop_event = threading.Event()

        def wait(_stop_event, _seconds):
            if wait.call_count == 1:
                stop_event.set()
                return True
            wait.call_count += 1
            return False

        wait.call_count = 0

        with (
            patch("source.join_sim.source.auto_join._is_menu_cancellable", return_value=True),
            patch("source.join_sim.source.auto_join._wait", side_effect=wait),
            patch("source.join_sim.source.auto_join._click_start_cancellable") as click_start,
            patch("source.join_sim.source.auto_join._click_join_game_cancellable") as click_join_game,
            patch("source.join_sim.source.auto_join._join_server_cancellable") as join_server,
            patch("source.join_sim.source.auto_join._mod_menu_join_cancellable") as mod_menu_join,
            patch("source.join_sim.source.auto_join._has_failure_cancellable") as has_failure,
        ):
            result = join_round_cancellable("5147", stop_event)

        self.assertFalse(result)
        click_start.assert_called_once_with(stop_event)
        click_join_game.assert_not_called()
        join_server.assert_not_called()
        mod_menu_join.assert_not_called()
        has_failure.assert_not_called()

    def test_cancellable_join_round_runs_expected_menu_sequence_without_stop(self):
        stop_event = threading.Event()
        actions = []

        with (
            patch("source.join_sim.source.auto_join._is_menu_cancellable", return_value=True),
            patch("source.join_sim.source.auto_join._wait", return_value=False),
            patch(
                "source.join_sim.source.auto_join._click_start_cancellable",
                side_effect=lambda _stop_event: actions.append("start"),
            ),
            patch(
                "source.join_sim.source.auto_join._click_join_game_cancellable",
                side_effect=lambda _stop_event: actions.append("join_game"),
            ),
            patch(
                "source.join_sim.source.auto_join._join_server_cancellable",
                side_effect=lambda server, _stop_event: actions.append(f"server:{server}"),
            ),
            patch(
                "source.join_sim.source.auto_join._mod_menu_join_cancellable",
                side_effect=lambda _stop_event: actions.append("mod_menu"),
            ),
            patch(
                "source.join_sim.source.auto_join._has_failure_cancellable",
                side_effect=lambda _stop_event: actions.append("failure"),
            ),
        ):
            result = join_round_cancellable("5147", stop_event)

        self.assertFalse(result)
        self.assertEqual(
            actions,
            ["start", "join_game", "server:5147", "mod_menu", "failure"],
        )

    def test_triggers_crash_reopen_before_retrying(self):
        stop_event = threading.Event()
        clock = FakeClock()
        crash_checks = [True, False]
        reopened = []
        calls = []

        result = run_auto_join_server(
            "5147",
            stop_event,
            join_round=lambda server: calls.append(server) or True,
            is_menu=lambda: False,
            detect_crash=lambda: crash_checks.pop(0),
            re_open_game=lambda: reopened.append("reopen"),
            sleep=clock.sleep,
            now=clock.now,
            reopen_pause=5,
        )

        self.assertTrue(result)
        self.assertEqual(reopened, ["reopen"])
        self.assertEqual(calls, ["5147"])
        self.assertGreaterEqual(clock.value, 5)

    def test_triggers_periodic_reopen_while_still_in_menu(self):
        stop_event = threading.Event()
        clock = FakeClock()
        reopened = []
        calls = []
        outcomes = [False, True]

        result = run_auto_join_server(
            "5147",
            stop_event,
            join_round=lambda server: calls.append(server) or outcomes.pop(0),
            is_menu=lambda: True,
            detect_crash=lambda: False,
            re_open_game=lambda: reopened.append("reopen"),
            sleep=clock.sleep,
            now=clock.now,
            retry_delay=901,
            reopen_interval=900,
            reopen_pause=0,
        )

        self.assertTrue(result)
        self.assertEqual(reopened, ["reopen"])
        self.assertEqual(calls, ["5147", "5147"])


if __name__ == "__main__":
    unittest.main()
