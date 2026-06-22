import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from source.launcher.config.transfer_helper_config import default_transfer_ui_coords
from source.launcher.utils import steam_switch


class SteamSwitchTests(unittest.TestCase):
    def test_window_ready_requires_visible_and_maximized(self) -> None:
        user32 = SimpleNamespace(
            FindWindowW=Mock(return_value=123),
            ShowWindow=Mock(),
            BringWindowToTop=Mock(),
            IsWindowVisible=Mock(return_value=True),
            IsZoomed=Mock(return_value=False),
        )

        with patch(
            "source.launcher.utils.steam_switch.ctypes.windll",
            SimpleNamespace(user32=user32),
            create=True,
        ):
            self.assertFalse(steam_switch._show_and_confirm_maximized("Steam"))
            user32.IsWindowVisible.return_value = False
            user32.IsZoomed.return_value = True
            self.assertFalse(steam_switch._show_and_confirm_maximized("Steam"))
            user32.FindWindowW.return_value = 0
            self.assertFalse(steam_switch._show_and_confirm_maximized("Steam"))
            user32.FindWindowW.return_value = 123
            user32.IsWindowVisible.return_value = True
            user32.IsZoomed.return_value = True
            self.assertTrue(steam_switch._show_and_confirm_maximized("Steam"))

        user32.ShowWindow.assert_called_with(123, 3)
        user32.BringWindowToTop.assert_called_with(123)

    def test_switch_retries_forever_shape_until_window_is_ready(self) -> None:
        players = {"players": [{"bed_name": "Bed1", "steam_account": "beta"}]}
        accounts = SimpleNamespace(
            select_auto_login_account=Mock(),
            close_steam=Mock(),
            launch_steam=Mock(),
        )
        ark_setup = SimpleNamespace(kill_running_ark=Mock())
        statuses = []

        with (
            patch.object(steam_switch, "steam_accounts", accounts),
            patch.object(steam_switch, "ark_game_setup", ark_setup),
            patch.object(
                steam_switch,
                "_wait_for_steam_window",
                side_effect=[False, False, True],
            ) as wait_ready,
            patch.object(steam_switch.time, "sleep"),
        ):
            result = steam_switch.switch_steam_account(
                1,
                "alpha",
                players,
                default_transfer_ui_coords(),
                statuses.append,
                loginusers=Path("loginusers.vdf"),
                steam_restart_interval=30,
            )

        self.assertEqual(result, "beta")
        self.assertEqual(accounts.launch_steam.call_count, 3)
        self.assertEqual(accounts.close_steam.call_count, 3)
        self.assertEqual(ark_setup.kill_running_ark.call_count, 3)
        self.assertEqual(wait_ready.call_count, 3)
        self.assertIn("Launching Steam (attempt 3).", statuses)
        self.assertEqual(statuses[-1], "Steam is visible and maximized for beta.")

    def test_same_account_remains_noop_without_force_restart(self) -> None:
        players = {"players": [{"bed_name": "Bed1", "steam_account": "alpha"}]}
        with patch.object(steam_switch.ark_game_setup, "kill_running_ark") as kill:
            result = steam_switch.switch_steam_account(
                1,
                "alpha",
                players,
                default_transfer_ui_coords(),
            )

        self.assertEqual(result, "alpha")
        kill.assert_not_called()
