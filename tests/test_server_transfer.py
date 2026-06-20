import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from source.gacha_bot.server_transfer import (
    STEAM_DIALOG_BUTTONS,
    TransferConfigError,
    close_ark_with_console_exit,
    _focus_visible_steam_window,
    _refresh_join_sim_ark_handle,
    _template_item,
    check_transfer_player_state,
    join_server,
    run_transfer_helper,
    steam_has_failure,
    switch_steam_account,
    transfer_to_server,
)
from source.launcher.transfer_helper_config import default_transfer_ui_coords


def ready_config():
    return {
        "settings": {
            "lag_offset": 1,
            "resource_station_yaw": 0,
            "destination_station_yaw": 0,
            "transmitter_teleport": "TX",
            "resource_server": "1111",
            "destination_server": "2222",
            "loop_count": 1,
            "structure_load_delay": 0,
            "transfer_retry_delay": 0,
        },
        "dedis": {
            "resource": {"teleport": "RESOURCE", "items": [{"location": {}}]},
            "destination": {"teleport": "DEST", "items": [{"location": {}}]},
        },
        "ui_coords": default_transfer_ui_coords(),
        "players": {"players": [{"bed_name": "Bed1", "steam_account": "alpha"}]},
        "steam_accounts": [
            {"account_name": "alpha", "most_recent": True, "timestamp": 1}
        ],
    }


def deps(**overrides):
    defaults = {
        "switch_account": Mock(side_effect=lambda target, _current: target),
        "ensure_ark_running": Mock(return_value=True),
        "is_menu": Mock(return_value=False),
        "join_server": Mock(return_value=True),
        "verify_tribelog": Mock(return_value=True),
        "check_state": Mock(),
        "wait_structure": Mock(),
        "withdraw_resource": Mock(return_value=True),
        "fast_travel_to_bed": Mock(),
        "enter_tekpod": Mock(),
        "leave_tekpod": Mock(),
        "transfer_to_server": Mock(),
        "wait_for_bed_screen": Mock(),
        "spawn_bed": Mock(),
        "stabilize_bed_position": Mock(),
        "deposit_resource": Mock(return_value=True),
        "kill_ark": Mock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class ServerTransferRunnerTests(unittest.TestCase):
    def test_missing_inputs_raise_config_error(self):
        config = ready_config()
        config["settings"]["resource_server"] = "0"

        with self.assertRaises(TransferConfigError):
            run_transfer_helper(config, dependencies=deps())

    def test_single_account_flow_uses_saved_servers_and_player_bed(self):
        status = []
        dependencies = deps()

        self.assertTrue(
            run_transfer_helper(
                ready_config(),
                status_callback=status.append,
                dependencies=dependencies,
            )
        )

        dependencies.join_server.assert_any_call("1111")
        dependencies.transfer_to_server.assert_any_call("2222", 1)
        dependencies.transfer_to_server.assert_any_call("1111", 1)
        dependencies.fast_travel_to_bed.assert_called_once_with("Bed1")
        dependencies.spawn_bed.assert_any_call("Bed1")
        self.assertEqual(status[-1], "Server transfer helper finished.")

    def test_join_failure_returns_false_without_killing_ark(self):
        dependencies = deps(join_server=Mock(return_value=False))

        self.assertFalse(run_transfer_helper(ready_config(), dependencies=dependencies))
        dependencies.kill_ark.assert_not_called()

    def test_template_item_uses_template_filename_stem(self):
        self.assertEqual(
            _template_item("assets/icons1080/steam_launch_option.png"),
            "steam_launch_option",
        )

    def test_steam_has_failure_skips_templates_when_steam_window_is_not_visible(self):
        steam = default_transfer_ui_coords()["steam"]
        template = SimpleNamespace(check_template_no_bounds=Mock())
        pyautogui = SimpleNamespace(click=Mock())

        with (
            patch.dict(
                "sys.modules",
                {"source.utility.template": template, "pyautogui": pyautogui},
            ),
            patch(
                "source.gacha_bot.server_transfer._focus_visible_steam_window",
                return_value=False,
            ) as focus_steam,
        ):
            self.assertFalse(steam_has_failure(steam))

        focus_steam.assert_called_once()
        template.check_template_no_bounds.assert_not_called()
        pyautogui.click.assert_not_called()

    def test_focus_visible_steam_window_requires_visible_window_before_maximize(self):
        steam = {"window_title": "Steam"}
        user32 = SimpleNamespace(
            FindWindowW=Mock(return_value=123),
            IsWindowVisible=Mock(return_value=True),
        )

        with (
            patch("ctypes.windll", SimpleNamespace(user32=user32), create=True),
            patch(
                "source.gacha_bot.server_transfer._focus_steam_window_maximized",
                return_value=True,
            ) as maximize,
        ):
            self.assertTrue(_focus_visible_steam_window(steam))

        user32.FindWindowW.assert_called_once_with(None, "Steam")
        user32.IsWindowVisible.assert_called_once_with(123)
        maximize.assert_called_once_with("Steam")

        user32.FindWindowW.reset_mock()
        user32.IsWindowVisible.reset_mock()
        user32.IsWindowVisible.return_value = False
        with (
            patch("ctypes.windll", SimpleNamespace(user32=user32), create=True),
            patch(
                "source.gacha_bot.server_transfer._focus_steam_window_maximized"
            ) as maximize,
        ):
            self.assertFalse(_focus_visible_steam_window(steam))

        user32.FindWindowW.assert_called_once_with(None, "Steam")
        user32.IsWindowVisible.assert_called_once_with(123)
        maximize.assert_not_called()

    def test_steam_has_failure_handles_launch_option_dialog(self):
        steam = default_transfer_ui_coords()["steam"]
        status = []
        events = []
        template = SimpleNamespace(
            check_template_no_bounds=Mock(
                side_effect=lambda item, _threshold: events.append(
                    ("template", item)
                )
                or item == "steam_launch_option"
            )
        )
        pyautogui = SimpleNamespace(click=Mock())

        with (
            patch.dict(
                "sys.modules",
                {"source.utility.template": template, "pyautogui": pyautogui},
            ),
            patch(
                "source.gacha_bot.server_transfer._focus_visible_steam_window",
                side_effect=lambda _steam, _emit: events.append("focus") or True,
            ) as focus_steam,
            patch("time.sleep"),
        ):
            self.assertTrue(steam_has_failure(steam, status.append))

        focus_steam.assert_called_once()
        self.assertEqual(events[0], "focus")
        template.check_template_no_bounds.assert_called_once_with(
            "steam_launch_option", 0.8
        )
        pyautogui.click.assert_has_calls(
            [
                call(
                    STEAM_DIALOG_BUTTONS["launch_option_select"]["x"],
                    STEAM_DIALOG_BUTTONS["launch_option_select"]["y"],
                ),
                call(
                    STEAM_DIALOG_BUTTONS["launch_option_checkbox"]["x"],
                    STEAM_DIALOG_BUTTONS["launch_option_checkbox"]["y"],
                ),
                call(
                    STEAM_DIALOG_BUTTONS["launch_option_play"]["x"],
                    STEAM_DIALOG_BUTTONS["launch_option_play"]["y"],
                ),
            ]
        )
        self.assertEqual(status[-1], "Detected Steam launch option dialog.")

    def test_steam_has_failure_handles_cloud_sync_conflict_dialog(self):
        steam = default_transfer_ui_coords()["steam"]
        status = []
        events = []
        template = SimpleNamespace(
            check_template_no_bounds=Mock(
                side_effect=lambda item, _threshold: events.append(
                    ("template", item)
                )
                or item == "steam_cloud_sync_conflic"
            )
        )
        pyautogui = SimpleNamespace(click=Mock())

        with (
            patch.dict(
                "sys.modules",
                {"source.utility.template": template, "pyautogui": pyautogui},
            ),
            patch(
                "source.gacha_bot.server_transfer._focus_visible_steam_window",
                side_effect=lambda _steam, _emit: events.append("focus") or True,
            ) as focus_steam,
            patch("time.sleep"),
        ):
            self.assertTrue(steam_has_failure(steam, status.append))

        focus_steam.assert_called_once()
        self.assertEqual(events[0], "focus")
        pyautogui.click.assert_called_once_with(
            STEAM_DIALOG_BUTTONS["cloud_sync_conflict_play"]["x"],
            STEAM_DIALOG_BUTTONS["cloud_sync_conflict_play"]["y"],
        )
        self.assertEqual(status[-1], "Detected Steam cloud sync conflict dialog.")

    def test_refresh_ark_handle_returns_live_handle_without_cached_assignment(self):
        with patch(
            "source.gacha_bot.server_transfer._ark_window_handle", return_value=123
        ):
            self.assertEqual(_refresh_join_sim_ark_handle(), 123)

    def test_join_server_focuses_ark_then_reuses_auto_join(self):
        system = SimpleNamespace(validate_ark_window=Mock(return_value=(1920, 1080)))
        auto_join_module = SimpleNamespace(run_auto_join_server=Mock(return_value=True))
        with (
            patch.dict(
                "sys.modules",
                {
                    "source.launcher.system": system,
                    "source.join_sim.source.auto_join": auto_join_module,
                },
            ),
            patch("source.gacha_bot.server_transfer._focus_ark_window_for_join") as focus,
        ):
            self.assertTrue(join_server("5147", Mock()))

        focus.assert_called_once_with((1920, 1080))
        auto_join_module.run_auto_join_server.assert_called_once()
        self.assertEqual(auto_join_module.run_auto_join_server.call_args.args[0], "5147")

    def test_check_transfer_player_state_uses_normal_teleporter_flow(self):
        buff_checker = SimpleNamespace(check_buffs=Mock(return_value=2))
        buffs = SimpleNamespace(check_buffs=Mock(return_value=buff_checker))
        render = SimpleNamespace(
            render_flag=False, enter_tekpod=Mock(), leave_tekpod=Mock()
        )
        teleporter = SimpleNamespace(teleport_not_default=Mock())
        config = ready_config()

        with (
            patch.dict(
                "sys.modules",
                {
                    "source.ASA.player.buffs": buffs,
                    "source.ASA.strucutres.teleporter": teleporter,
                    "source.gacha_bot.render": render,
                },
            ),
            patch("source.gacha_bot.server_transfer.check_transfer_disconnected"),
            patch("source.gacha_bot.server_transfer.reset_transfer_state"),
            patch("time.sleep"),
        ):
            check_transfer_player_state(
                config["settings"], config["players"], 1, "1111"
            )

        teleporter.teleport_not_default.assert_called_once_with(
            "Bed1", fallback_bed_name="Bed1"
        )

    def test_multi_account_flow_groups_withdraws_before_destination_phase(self):
        config = ready_config()
        config["players"] = {
            "players": [
                {"bed_name": "Bed1", "steam_account": "alpha"},
                {"bed_name": "Bed2", "steam_account": "beta"},
            ]
        }
        config["steam_accounts"] = [
            {"account_name": "alpha", "most_recent": True, "timestamp": 2},
            {"account_name": "beta", "most_recent": False, "timestamp": 1},
        ]
        events = []
        dependencies = deps(
            withdraw_resource=Mock(side_effect=lambda account: events.append(("withdraw", account)) or True),
            deposit_resource=Mock(side_effect=lambda account: events.append(("deposit", account)) or True),
            transfer_to_server=Mock(side_effect=lambda server, account: events.append(("transfer", server, account))),
        )

        self.assertTrue(run_transfer_helper(config, dependencies=dependencies))

        self.assertEqual(events[:2], [("withdraw", 1), ("withdraw", 2)])
        self.assertIn(("deposit", 1), events[2:])
        self.assertIn(("deposit", 2), events[2:])

    def test_switch_steam_account_uses_assigned_account_name(self):
        players = {
            "players": [
                {"bed_name": "Bed1", "steam_account": "alpha"},
                {"bed_name": "Bed2", "steam_account": "beta"},
            ]
        }
        steam_accounts = SimpleNamespace(
            select_auto_login_account=Mock(),
            close_steam=Mock(),
            launch_ark_with_steam=Mock(),
        )

        with (
            patch("source.gacha_bot.server_transfer.kill_ark") as kill,
            patch(
                "source.launcher.steam_accounts.select_auto_login_account",
                steam_accounts.select_auto_login_account,
            ),
            patch("source.launcher.steam_accounts.close_steam", steam_accounts.close_steam),
            patch(
                "source.launcher.steam_accounts.launch_ark_with_steam",
                steam_accounts.launch_ark_with_steam,
            ),
            patch("time.sleep"),
        ):
            result = switch_steam_account(2, "alpha", players, default_transfer_ui_coords())

        self.assertEqual(result, "beta")
        kill.assert_called_once()
        steam_accounts.select_auto_login_account.assert_called_once_with("beta")

    def test_close_ark_with_console_exit_retries_until_window_disappears(self):
        player_state = SimpleNamespace(reset_state=Mock())
        console = SimpleNamespace(console_write=Mock())
        capture = SimpleNamespace(focus_game_window=Mock())
        utils = SimpleNamespace(timed_out_counter=Mock(return_value=lambda: False))

        with (
            patch.dict(
                "sys.modules",
                {
                    "source.ASA.player.player_state": player_state,
                    "source.ASA.player.console": console,
                    "source.launcher.deposit_helper_capture": capture,
                    "source.utility.utils": utils,
                },
            ),
            patch(
                "source.gacha_bot.server_transfer._ark_window_exists",
                side_effect=[True, False],
            ),
            patch("time.sleep"),
        ):
            self.assertTrue(close_ark_with_console_exit())

        capture.focus_game_window.assert_called_once_with(center_cursor_when_switching=True)
        console.console_write.assert_called_once_with("exit")

    def test_transfer_to_server_uses_transmitter_helper_after_teleport_and_yaw(self):
        config = ready_config()
        status = []
        teleporter = SimpleNamespace(teleport_not_default=Mock())
        utils = SimpleNamespace(set_yaw=Mock())
        transmitter = SimpleNamespace(open_and_transfer=Mock(return_value=True))
        with (
            patch.dict(
                "sys.modules",
                {
                    "source.ASA.strucutres.teleporter": teleporter,
                    "source.utility.utils": utils,
                    "source.utility.structures.transmitter.transmitter": transmitter,
                },
            ),
        ):
            self.assertTrue(
                transfer_to_server(
                    "2222",
                    config["settings"],
                    config["ui_coords"],
                    status.append,
                    config["players"],
                    1,
                )
            )

        teleporter.teleport_not_default.assert_called_once_with(
            "TX", fallback_bed_name="Bed1"
        )
        utils.set_yaw.assert_called_once_with(0.0)
        transmitter.open_and_transfer.assert_called_once_with("2222")
        self.assertEqual(status[-1], "Transfer to server 2222 requested.")

    def test_transfer_to_server_recovers_after_failed_transmitter_attempt(self):
        config = ready_config()
        teleporter = SimpleNamespace(teleport_not_default=Mock())
        utils = SimpleNamespace(set_yaw=Mock())
        transmitter = SimpleNamespace(open_and_transfer=Mock(side_effect=[False, True]))
        with (
            patch.dict(
                "sys.modules",
                {
                    "source.ASA.strucutres.teleporter": teleporter,
                    "source.utility.utils": utils,
                    "source.utility.structures.transmitter.transmitter": transmitter,
                },
            ),
            patch("source.gacha_bot.server_transfer.check_transfer_player_state") as check_state,
            patch("time.sleep"),
        ):
            self.assertTrue(
                transfer_to_server(
                    "2222",
                    config["settings"],
                    config["ui_coords"],
                    players=config["players"],
                    account=1,
                )
            )

        self.assertEqual(transmitter.open_and_transfer.call_count, 2)
        check_state.assert_called_once_with(
            config["settings"], config["players"], 1, "2222"
        )


if __name__ == "__main__":
    unittest.main()
