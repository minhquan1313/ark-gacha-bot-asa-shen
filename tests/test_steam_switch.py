import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from source.launcher.config.transfer_helper_config import default_transfer_ui_coords
from source.launcher.utils import steam_switch


class SteamSwitchTests(unittest.TestCase):
    def test_wait_ignores_main_window_until_sign_in_disappears(self) -> None:
        with (
            patch.object(steam_switch.time, "monotonic", return_value=0.0),
            patch.object(steam_switch.time, "sleep") as sleep,
            patch.object(
                steam_switch,
                "_is_window_visible",
                side_effect=[False, True, False],
            ) as sign_in_visible,
            patch.object(
                steam_switch, "_show_and_confirm_maximized", return_value=True
            ) as show_main,
        ):
            self.assertTrue(steam_switch._wait_for_steam_window("Steam", 30))

        self.assertEqual(sign_in_visible.call_count, 3)
        show_main.assert_called_once_with("Steam")
        self.assertEqual(sleep.call_count, 2)
        sleep.assert_called_with(0.1)

    def test_wait_times_out_when_sign_in_never_appears(self) -> None:
        with (
            patch.object(steam_switch.time, "monotonic", side_effect=[0.0, 0.0, 1.0]),
            patch.object(steam_switch.time, "sleep"),
            patch.object(
                steam_switch, "_is_window_visible", return_value=False
            ) as sign_in_visible,
            patch.object(steam_switch, "_show_and_confirm_maximized") as show_main,
        ):
            self.assertFalse(steam_switch._wait_for_steam_window("Steam", 1))

        sign_in_visible.assert_called_once_with("Sign in to Steam")
        show_main.assert_not_called()

    def test_wait_times_out_while_sign_in_remains_visible(self) -> None:
        with (
            patch.object(steam_switch.time, "monotonic", side_effect=[0.0, 0.0, 1.0]),
            patch.object(steam_switch.time, "sleep"),
            patch.object(steam_switch, "_is_window_visible", return_value=True),
            patch.object(steam_switch, "_show_and_confirm_maximized") as show_main,
        ):
            self.assertFalse(steam_switch._wait_for_steam_window("Steam", 1))

        show_main.assert_not_called()

    def test_window_ready_requires_visible_and_maximized(self) -> None:
        user32 = SimpleNamespace(
            FindWindowW=Mock(return_value=123),
            ShowWindow=Mock(),
            BringWindowToTop=Mock(),
            IsWindowVisible=Mock(return_value=True),
            IsZoomed=Mock(side_effect=[False, False, True, True, True]),
        )

        with patch(
            "source.launcher.utils.steam_switch.ctypes.windll",
            SimpleNamespace(user32=user32),
            create=True,
        ):
            self.assertFalse(steam_switch._show_and_confirm_maximized("Steam"))
            user32.IsWindowVisible.return_value = False
            self.assertFalse(steam_switch._show_and_confirm_maximized("Steam"))
            user32.FindWindowW.return_value = 0
            self.assertFalse(steam_switch._show_and_confirm_maximized("Steam"))
            user32.FindWindowW.return_value = 123
            user32.IsWindowVisible.return_value = True
            self.assertTrue(steam_switch._show_and_confirm_maximized("Steam"))

        user32.ShowWindow.assert_called_once_with(123, 3)
        user32.BringWindowToTop.assert_called_with(123)

    def test_window_ready_does_not_remaximize_maximized_window(self) -> None:
        user32 = SimpleNamespace(
            FindWindowW=Mock(return_value=123),
            ShowWindow=Mock(),
            BringWindowToTop=Mock(),
            IsWindowVisible=Mock(return_value=True),
            IsZoomed=Mock(return_value=True),
        )

        with patch(
            "source.launcher.utils.steam_switch.ctypes.windll",
            SimpleNamespace(user32=user32),
            create=True,
        ):
            self.assertTrue(steam_switch._show_and_confirm_maximized("Steam"))

        user32.ShowWindow.assert_not_called()
        user32.BringWindowToTop.assert_called_once_with(123)

    def test_switch_retries_forever_shape_until_window_is_ready(self) -> None:
        players = {"players": [{"bed_name": "Bed1", "steam_account": "beta"}]}
        accounts = SimpleNamespace(
            select_auto_login_account=Mock(),
            close_steam=Mock(),
            launch_steam=Mock(),
        )
        ark_setup = SimpleNamespace(kill_running_ark=Mock())
        with (
            patch.object(steam_switch, "steam_accounts", accounts),
            patch.object(steam_switch, "ark_game_setup", ark_setup),
            patch.object(
                steam_switch.utils, "close_ark_with_console_exit", return_value=True
            ) as graceful_close,
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
                loginusers=Path("loginusers.vdf"),
                steam_restart_interval=30,
            )

        self.assertEqual(result, "beta")
        self.assertEqual(accounts.launch_steam.call_count, 3)
        self.assertEqual(accounts.close_steam.call_count, 3)
        self.assertEqual(ark_setup.kill_running_ark.call_count, 3)
        graceful_close.assert_called_once_with()
        self.assertEqual(wait_ready.call_count, 3)

    def test_instant_switch_retries_without_touching_ark(self) -> None:
        players = {"players": [{"bed_name": "Bed1", "steam_account": "beta"}]}
        accounts = SimpleNamespace(
            select_auto_login_account=Mock(),
            close_steam=Mock(),
            launch_steam=Mock(),
        )
        ark_setup = SimpleNamespace(kill_running_ark=Mock())
        with (
            patch.object(steam_switch, "steam_accounts", accounts),
            patch.object(steam_switch, "ark_game_setup", ark_setup),
            patch.object(
                steam_switch.utils, "close_ark_with_console_exit"
            ) as graceful_close,
            patch.object(
                steam_switch,
                "_wait_for_steam_window",
                side_effect=[False, True],
            ),
            patch.object(steam_switch.time, "sleep"),
        ):
            result = steam_switch.switch_steam_account(
                1,
                "alpha",
                players,
                default_transfer_ui_coords(),
                close_ark=False,
                loginusers=Path("loginusers.vdf"),
                steam_restart_interval=30,
            )

        self.assertEqual(result, "beta")
        accounts.select_auto_login_account.assert_called_once()
        self.assertEqual(accounts.launch_steam.call_count, 2)
        self.assertEqual(accounts.close_steam.call_count, 2)
        graceful_close.assert_not_called()
        ark_setup.kill_running_ark.assert_not_called()

    def test_same_account_remains_noop_without_force_restart(self) -> None:
        players = {"players": [{"bed_name": "Bed1", "steam_account": "alpha"}]}
        with (
            patch.object(
                steam_switch.utils, "close_ark_with_console_exit"
            ) as graceful_close,
            patch.object(steam_switch.ark_game_setup, "kill_running_ark") as kill,
        ):
            result = steam_switch.switch_steam_account(
                1,
                "alpha",
                players,
                default_transfer_ui_coords(),
            )

        self.assertEqual(result, "alpha")
        graceful_close.assert_not_called()
        kill.assert_not_called()

    def test_graceful_and_force_close_precede_account_and_steam_changes(self) -> None:
        players = {"players": [{"bed_name": "Bed1", "steam_account": "beta"}]}
        events = []
        accounts = SimpleNamespace(
            select_auto_login_account=Mock(
                side_effect=lambda *_args: events.append("select_account")
            ),
            close_steam=Mock(side_effect=lambda: events.append("close_steam")),
            launch_steam=Mock(side_effect=lambda: events.append("launch_steam")),
        )
        ark_setup = SimpleNamespace(
            kill_running_ark=Mock(side_effect=lambda: events.append("force_close"))
        )

        with (
            patch.object(steam_switch, "steam_accounts", accounts),
            patch.object(steam_switch, "ark_game_setup", ark_setup),
            patch.object(
                steam_switch.utils,
                "close_ark_with_console_exit",
                side_effect=lambda: events.append("graceful_close"),
            ),
            patch.object(steam_switch, "_wait_for_steam_window", return_value=True),
            patch.object(steam_switch.time, "sleep"),
        ):
            steam_switch.switch_steam_account(
                1,
                "alpha",
                players,
                default_transfer_ui_coords(),
                loginusers=Path("loginusers.vdf"),
            )

        self.assertEqual(
            events[:4],
            ["graceful_close", "force_close", "select_account", "close_steam"],
        )
