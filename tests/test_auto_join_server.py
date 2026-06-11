import unittest
from unittest.mock import Mock, patch

from source.join_sim.source.auto_join import normalize_server_number, run_auto_join_server


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
        statuses = []
        calls = []
        clock = FakeClock()

        result = run_auto_join_server(
            "5147",
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
        clock = FakeClock()
        outcomes = [False, False, True]
        calls = []

        result = run_auto_join_server(
            "5147",
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

    def test_default_join_round_uses_join_sim_main_flow(self):
        clock = FakeClock()
        join_main = Mock()
        join_main.is_menu.return_value = False
        join_main.join_round.return_value = True

        with patch.dict("sys.modules", {"source.join_sim.source.main": join_main}):
            result = run_auto_join_server(
                "5147",
                detect_crash=lambda: False,
                re_open_game=lambda: None,
                sleep=clock.sleep,
                now=clock.now,
            )

        self.assertTrue(result)
        join_main.join_round.assert_called_once_with("5147")

    def test_triggers_crash_reopen_before_retrying(self):
        clock = FakeClock()
        crash_checks = [True, False]
        reopened = []
        calls = []

        result = run_auto_join_server(
            "5147",
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
        clock = FakeClock()
        reopened = []
        calls = []
        outcomes = [False, True]

        result = run_auto_join_server(
            "5147",
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
