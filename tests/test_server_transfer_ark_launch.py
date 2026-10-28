import unittest
from unittest.mock import Mock, patch

from source.gacha_bot import server_transfer


class EnsureArkRunningTests(unittest.TestCase):
    def test_launches_after_stale_process_cleanup_timeout(self):
        logger = Mock()
        launch = Mock()
        kill = Mock(return_value=False)

        with (
            patch.object(server_transfer, "_process_running", side_effect=[True, True]),
            patch.object(server_transfer, "validate_ark_window", side_effect=[RuntimeError("missing window"), (1920, 1080)]),
            patch.object(server_transfer, "kill_running_ark", kill),
            patch.object(server_transfer, "_wait_for_ark_process_exit", return_value=False),
            patch.object(server_transfer, "launch_ark_through_steam", launch),
            patch.object(server_transfer, "_prepare_ark_window_for_join", return_value=True),
            patch.object(server_transfer.utils_simple, "get_default_clock", return_value=lambda: False),
            patch.object(server_transfer, "steam_has_failure"),
            patch.object(server_transfer.logs, "logger", logger),
        ):
            self.assertTrue(
                server_transfer.ensure_ark_running(
                    {"ark_launch_attempts": 1, "ark_window_ready_timeout": 1},
                    {"steam": {}},
                )
            )

        kill.assert_called_once_with(server_transfer.STALE_ARK_PROCESS_EXIT_TIMEOUT_SECONDS)
        launch.assert_called_once()

    def test_launches_after_stale_process_exits(self):
        launch = Mock()

        with (
            patch.object(server_transfer, "_process_running", side_effect=[True, True]),
            patch.object(server_transfer, "validate_ark_window", side_effect=[RuntimeError("missing window"), (1920, 1080)]),
            patch.object(server_transfer, "kill_running_ark", return_value=True),
            patch.object(server_transfer, "_wait_for_ark_process_exit", return_value=True),
            patch.object(server_transfer, "launch_ark_through_steam", launch),
            patch.object(server_transfer, "_prepare_ark_window_for_join", return_value=True),
            patch.object(server_transfer.utils_simple, "get_default_clock", return_value=lambda: False),
            patch.object(server_transfer, "steam_has_failure"),
            patch.object(server_transfer.logs, "logger", Mock()),
        ):
            self.assertTrue(
                server_transfer.ensure_ark_running(
                    {"ark_launch_attempts": 1, "ark_window_ready_timeout": 1},
                    {"steam": {}},
                )
            )

        launch.assert_called_once()

    def test_reuses_valid_ark_window_without_relaunching(self):
        launch = Mock()
        kill = Mock()

        with (
            patch.object(server_transfer, "_process_running", return_value=True),
            patch.object(server_transfer, "validate_ark_window", return_value=(1920, 1080)),
            patch.object(server_transfer, "kill_running_ark", kill),
            patch.object(server_transfer, "launch_ark_through_steam", launch),
        ):
            self.assertTrue(server_transfer.ensure_ark_running({"ark_launch_attempts": 1}, {"steam": {}}))

        kill.assert_not_called()
        launch.assert_not_called()

    def test_retries_when_launched_ark_never_creates_a_window(self):
        launch = Mock()
        restart = Mock()

        with (
            patch.object(server_transfer, "_process_running", return_value=False),
            patch.object(server_transfer, "launch_ark_through_steam", launch),
            patch.object(server_transfer, "_restart_steam_before_ark_retry", restart),
            patch.object(server_transfer.utils_simple, "get_default_clock", return_value=lambda: True),
            patch.object(server_transfer.logs, "logger", Mock()),
        ):
            with self.assertRaisesRegex(RuntimeError, "ARK did not start after 2"):
                server_transfer.ensure_ark_running(
                    {"ark_launch_attempts": 2, "ark_window_ready_timeout": 1, "steam_restart_interval": 1},
                    {"steam": {}},
                )

        self.assertEqual(launch.call_count, 2)
        restart.assert_called_once_with({}, 1)
