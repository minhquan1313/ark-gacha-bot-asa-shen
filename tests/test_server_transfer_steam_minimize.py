import types
import unittest
from unittest.mock import Mock, patch

from source.gacha_bot import server_transfer


class ServerTransferSteamMinimizeTests(unittest.TestCase):
    def test_minimizes_visible_configured_steam_window(self):
        user32 = types.SimpleNamespace(
            FindWindowW=Mock(return_value=123),
            IsWindowVisible=Mock(return_value=True),
            IsIconic=Mock(return_value=False),
            ShowWindow=Mock(),
        )

        with patch.object(
            server_transfer.ctypes,
            "windll",
            types.SimpleNamespace(user32=user32),
            create=True,
        ):
            self.assertTrue(
                server_transfer._minimize_steam_window({"window_title": "Steam"})
            )

        user32.FindWindowW.assert_called_once_with(None, "Steam")
        user32.ShowWindow.assert_called_once_with(123, 6)

    def test_missing_or_minimized_steam_window_is_a_safe_no_op(self):
        missing_user32 = types.SimpleNamespace(FindWindowW=Mock(return_value=0))
        minimized_user32 = types.SimpleNamespace(
            FindWindowW=Mock(return_value=123),
            IsWindowVisible=Mock(return_value=True),
            IsIconic=Mock(return_value=True),
            ShowWindow=Mock(),
        )

        with patch.object(
            server_transfer.ctypes,
            "windll",
            types.SimpleNamespace(user32=missing_user32),
            create=True,
        ):
            self.assertFalse(server_transfer._minimize_steam_window({"window_title": "Steam"}))

        with patch.object(
            server_transfer.ctypes,
            "windll",
            types.SimpleNamespace(user32=minimized_user32),
            create=True,
        ):
            self.assertTrue(server_transfer._minimize_steam_window({"window_title": "Steam"}))

        minimized_user32.ShowWindow.assert_not_called()

    def test_minimize_failure_does_not_block_ark_focus(self):
        events = []

        with (
            patch.object(
                server_transfer,
                "_minimize_steam_window",
                side_effect=lambda _steam: events.append("minimize") or False,
            ),
            patch.object(
                server_transfer,
                "focus_game_window",
                side_effect=lambda **_kwargs: events.append("focus"),
            ),
            patch.object(server_transfer.time, "sleep"),
        ):
            self.assertTrue(
                server_transfer._prepare_ark_window_for_join(
                    steam={"window_title": "Steam"}
                )
            )

        self.assertEqual(events, ["minimize", "focus"])

    def test_prepare_minimizes_steam_before_focusing_ark(self):
        events = []

        with (
            patch.object(
                server_transfer,
                "_minimize_steam_window",
                side_effect=lambda _steam: events.append("minimize") or True,
            ),
            patch.object(
                server_transfer,
                "focus_game_window",
                side_effect=lambda **_kwargs: events.append("focus"),
            ),
            patch.object(server_transfer.time, "sleep"),
        ):
            server_transfer._prepare_ark_window_for_join(
                steam={"window_title": "Steam"}
            )

        self.assertEqual(events, ["minimize", "focus"])


if __name__ == "__main__":
    unittest.main()
