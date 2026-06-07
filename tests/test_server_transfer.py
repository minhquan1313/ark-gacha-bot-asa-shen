import threading
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, Mock, call, patch

from source.gacha_bot.server_transfer import (
    TransferConfigError,
    _ensure_steam_window_ready,
    _logout_before_kill_ark,
    _open_main_menu_until_safe_to_kill,
    _reset_open_main_menu_console,
    _safe_check_join_template_no_bounds,
    _safe_is_ark_main_menu,
    _send_open_main_menu,
    _transfer_deposit_to_dedi,
    _wait_for_ark_loading_screen,
    check_transfer_disconnected,
    check_transfer_player_state,
    deposit_to_transfer_dedis,
    join_server,
    kill_ark,
    reset_transfer_state,
    ensure_ark_running,
    run_transfer_helper,
    switch_steam_account,
    transfer_to_server,
    withdraw_from_transfer_dedis,
)
from source.launcher.transfer_helper_config import (
    default_transfer_ui_coords,
    normalize_transfer_dedis,
    normalize_transfer_settings,
)


def ready_config(account_count=2, loop_count=1):
    settings = normalize_transfer_settings(
        {
            "resource_server": "1111",
            "destination_server": "2222",
            "transmitter_teleport": "TX",
            "loop_count": loop_count,
        }
    )
    dedis = normalize_transfer_dedis(
        {
            "resource": {
                "teleport": "RESOURCE_DEDI",
                "items": [
                    {
                        "location": {"yaw": 0, "pitch": 0},
                        "crouched": False,
                    }
                ],
            },
            "destination": {
                "teleport": "DEST_DEDI",
                "items": [
                    {
                        "location": {"yaw": 10, "pitch": 1},
                        "crouched": True,
                    }
                ],
            },
        }
    )
    players = {
        "players": [
            {"bed_name": f"Bed{index}"} for index in range(1, account_count + 1)
        ]
    }
    coords = default_transfer_ui_coords()
    for key in ("menu", "change_account", "continue"):
        coords["steam"][key] = {"x": 1, "y": 1}
    for key in (
        "transfer_button",
        "server_search",
        "first_server",
        "join_button",
        "transfer_not_ready_cancel",
    ):
        coords["transfer"][key] = {"x": 1, "y": 1}
    coords["transfer"]["transmitter_title_template"] = "README.md"
    coords["transfer"]["not_ready_template"] = "README.md"
    coords["transfer"]["dedi_deposit_ready_template"] = "README.md"
    coords["transfer"]["dedi_init_click"] = {"x": 1, "y": 1}
    return {
        "settings": settings,
        "dedis": dedis,
        "ui_coords": coords,
        "players": players,
    }


def deps():
    current = {"account": 1}

    def switch(target, _current):
        current["account"] = target
        return target

    return SimpleNamespace(
        switch_account=Mock(side_effect=switch),
        ensure_ark_running=Mock(),
        is_menu=Mock(return_value=False),
        join_server=Mock(return_value=True),
        verify_tribelog=Mock(return_value=True),
        check_state=Mock(),
        wait_structure=Mock(),
        withdraw_resource=Mock(),
        fast_travel_to_bed=Mock(),
        enter_tekpod=Mock(),
        leave_tekpod=Mock(),
        transfer_to_server=Mock(),
        wait_for_bed_screen=Mock(),
        spawn_bed=Mock(),
        stabilize_bed_position=Mock(),
        deposit_resource=Mock(),
        kill_ark=Mock(),
    )


class ServerTransferRunnerTests(unittest.TestCase):
    def test_missing_runtime_inputs_block_before_dependencies_run(self):
        config = ready_config()
        config["ui_coords"]["steam"].pop("account_slots")

        with self.assertRaises(TransferConfigError):
            run_transfer_helper(config, threading.Event(), dependencies=deps())

    def test_resource_fill_skips_account_when_tribelog_unavailable(self):
        dependencies = deps()
        dependencies.verify_tribelog.side_effect = [False, True]

        self.assertTrue(
            run_transfer_helper(ready_config(), threading.Event(), dependencies=dependencies)
        )

        dependencies.kill_ark.assert_not_called()
        dependencies.withdraw_resource.assert_called()

    def test_resource_fill_stop_during_join_does_not_kill_ark(self):
        stop_event = threading.Event()
        dependencies = deps()

        def stop_join(_server):
            stop_event.set()
            return False

        dependencies.join_server.side_effect = stop_join

        self.assertFalse(
            run_transfer_helper(ready_config(), stop_event, dependencies=dependencies)
        )

        dependencies.kill_ark.assert_not_called()

    def test_flow_uses_saved_player_bed_names_and_transfer_servers(self):
        dependencies = deps()

        self.assertTrue(
            run_transfer_helper(ready_config(), threading.Event(), dependencies=dependencies)
        )

        dependencies.fast_travel_to_bed.assert_has_calls(
            [call("Bed1"), call("Bed2")]
        )
        dependencies.transfer_to_server.assert_has_calls(
            [call("2222", 1), call("1111", 1), call("2222", 2), call("1111", 2)]
        )
        dependencies.spawn_bed.assert_has_calls(
            [
                call("Bed1"),
                call("Bed1"),
                call("Bed2"),
                call("Bed2"),
            ]
        )
        dependencies.withdraw_resource.assert_has_calls(
            [call(1), call(2), call(1), call(2)]
        )
        dependencies.deposit_resource.assert_has_calls([call(1), call(2)])

    def test_runtime_processes_only_first_four_configured_accounts(self):
        dependencies = deps()
        config = ready_config(account_count=12)
        config["ui_coords"]["steam"]["account_slots"]["4"] = [
            {"x": 1, "y": 1},
            {"x": 2, "y": 1},
            {"x": 3, "y": 1},
            {"x": 4, "y": 1},
        ]

        self.assertTrue(
            run_transfer_helper(config, threading.Event(), dependencies=dependencies)
        )

        dependencies.switch_account.assert_has_calls(
            [call(1, 1), call(2, 1), call(3, 2), call(4, 3)]
        )
        self.assertEqual(dependencies.switch_account.call_count, 8)
        dependencies.fast_travel_to_bed.assert_has_calls(
            [call("Bed1"), call("Bed2"), call("Bed3"), call("Bed4")]
        )

    def test_single_account_flow_does_not_switch_accounts(self):
        dependencies = deps()

        self.assertTrue(
            run_transfer_helper(
                ready_config(account_count=1),
                threading.Event(),
                dependencies=dependencies,
            )
        )

        dependencies.switch_account.assert_not_called()
        dependencies.kill_ark.assert_not_called()

    def test_resource_fill_checks_tekpod_then_waits_before_withdraw_after_menu_join(self):
        dependencies = deps()
        dependencies.is_menu.return_value = True
        order = []
        dependencies.verify_tribelog.side_effect = lambda: order.append(
            "verify_tribelog"
        ) or True
        dependencies.wait_structure.side_effect = lambda: order.append(
            "wait_structure"
        )
        dependencies.check_state.side_effect = lambda _account: order.append(
            "check_state"
        )

        self.assertTrue(
            run_transfer_helper(
                ready_config(account_count=1),
                threading.Event(),
                dependencies=dependencies,
            )
        )

        self.assertEqual(
            order[:3],
            ["verify_tribelog", "check_state", "wait_structure"],
        )

    def test_resource_fill_skips_structure_wait_when_already_in_game(self):
        dependencies = deps()
        dependencies.is_menu.return_value = False
        order = []
        dependencies.verify_tribelog.side_effect = lambda: order.append(
            "verify_tribelog"
        ) or True
        dependencies.wait_structure.side_effect = lambda: order.append(
            "wait_structure"
        )
        dependencies.check_state.side_effect = lambda _account: order.append(
            "check_state"
        )
        dependencies.withdraw_resource.side_effect = lambda _account: order.append(
            "withdraw_resource"
        )

        self.assertTrue(
            run_transfer_helper(
                ready_config(account_count=1),
                threading.Event(),
                dependencies=dependencies,
            )
        )

        self.assertEqual(
            order[:3],
            ["verify_tribelog", "check_state", "withdraw_resource"],
        )
        dependencies.wait_structure.assert_has_calls([call(), call(), call()])

    def test_single_account_tribelog_failure_stops_without_killing_ark(self):
        dependencies = deps()
        dependencies.verify_tribelog.return_value = False

        self.assertFalse(
            run_transfer_helper(
                ready_config(account_count=1),
                threading.Event(),
                dependencies=dependencies,
            )
        )

        dependencies.kill_ark.assert_not_called()
        dependencies.withdraw_resource.assert_not_called()

    def test_single_account_join_failure_stops_without_killing_ark(self):
        dependencies = deps()
        dependencies.join_server.return_value = False

        self.assertFalse(
            run_transfer_helper(
                ready_config(account_count=1),
                threading.Event(),
                dependencies=dependencies,
            )
        )

        dependencies.kill_ark.assert_not_called()
        dependencies.verify_tribelog.assert_not_called()

    def test_stop_event_exits_before_first_account(self):
        stop_event = threading.Event()
        stop_event.set()
        dependencies = deps()

        self.assertFalse(
            run_transfer_helper(ready_config(), stop_event, dependencies=dependencies)
        )

        dependencies.switch_account.assert_not_called()

    def test_switch_account_kills_waits_for_picker_then_clicks_slot(self):
        pyautogui = SimpleNamespace(click=Mock())
        coords = default_transfer_ui_coords()
        for key in ("menu", "change_account", "continue"):
            coords["steam"][key] = {"x": 10, "y": 20}
        template = SimpleNamespace(
            roi_regions={},
            check_template=Mock(),
            check_template_no_bounds=Mock(),
        )

        with (
            patch.dict(
                "sys.modules",
                {
                    "pyautogui": pyautogui,
                    "source.utility.template": template,
                },
            ),
            patch("source.gacha_bot.server_transfer.kill_ark") as kill,
            patch("source.gacha_bot.server_transfer.stop_wait", return_value=False) as wait,
            patch(
                "source.gacha_bot.server_transfer._ensure_steam_window_ready",
                return_value=True,
            ) as ready,
            patch(
                "source.gacha_bot.server_transfer._wait_for_template_visible",
                side_effect=[True, True],
            ) as wait_template,
        ):
            account = switch_steam_account(
                2, 1, 2, coords, threading.Event(), Mock()
            )

        self.assertEqual(account, 2)
        kill.assert_called_once()
        self.assertIs(kill.call_args.args[1], coords)
        self.assertEqual(wait.call_args_list[0], call(ANY, 5))
        self.assertEqual(ready.call_count, 2)
        self.assertTrue(ready.call_args_list[0].kwargs["launch_if_missing"])
        self.assertFalse(ready.call_args_list[1].kwargs["launch_if_missing"])
        self.assertEqual(
            wait_template.call_args_list,
            [
                call(
                    template.check_template_no_bounds,
                    60.0,
                    ANY,
                    "steam_change_acc_ready",
                    0.75,
                ),
                call(
                    template.check_template_no_bounds,
                    60.0,
                    ANY,
                    "steam_switch_account",
                    0.75,
                ),
            ],
        )
        self.assertEqual(
            pyautogui.click.call_args_list,
            [
                call(10, 20),
                call(10, 20),
                call(10, 20),
                call(990, 550),
            ],
        )
        self.assertEqual(pyautogui.click.call_args_list[-1], call(990, 550))

    def test_switch_account_blocks_continue_until_steam_ready_template(self):
        pyautogui = SimpleNamespace(click=Mock())
        coords = default_transfer_ui_coords()
        for key in ("menu", "change_account", "continue"):
            coords["steam"][key] = {"x": 10, "y": 20}
        template = SimpleNamespace(
            roi_regions={},
            check_template=Mock(),
            check_template_no_bounds=Mock(),
        )

        with (
            patch.dict(
                "sys.modules",
                {
                    "pyautogui": pyautogui,
                    "source.utility.template": template,
                },
            ),
            patch("source.gacha_bot.server_transfer.kill_ark"),
            patch("source.gacha_bot.server_transfer.stop_wait", return_value=False),
            patch(
                "source.gacha_bot.server_transfer._ensure_steam_window_ready",
                return_value=True,
            ),
            patch(
                "source.gacha_bot.server_transfer._wait_for_template_visible",
                return_value=False,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "account switch UI"):
                switch_steam_account(
                    2, 1, 2, coords, threading.Event(), Mock()
                )

        self.assertEqual(
            pyautogui.click.call_args_list,
            [
                call(10, 20),
                call(10, 20),
                call(10, 20),
                call(10, 20),
                call(10, 20),
                call(10, 20),
            ],
        )

    def test_switch_account_retries_until_steam_ready_template(self):
        pyautogui = SimpleNamespace(click=Mock())
        coords = default_transfer_ui_coords()
        for key in ("menu", "change_account", "continue"):
            coords["steam"][key] = {"x": 10, "y": 20}
        template = SimpleNamespace(
            roi_regions={},
            check_template=Mock(),
            check_template_no_bounds=Mock(),
        )

        with (
            patch.dict(
                "sys.modules",
                {
                    "pyautogui": pyautogui,
                    "source.utility.template": template,
                },
            ),
            patch("source.gacha_bot.server_transfer.kill_ark"),
            patch("source.gacha_bot.server_transfer.stop_wait", return_value=False),
            patch(
                "source.gacha_bot.server_transfer._ensure_steam_window_ready",
                return_value=True,
            ),
            patch(
                "source.gacha_bot.server_transfer._wait_for_template_visible",
                side_effect=[False, False, True, True],
            ) as wait_template,
        ):
            self.assertEqual(
                switch_steam_account(2, 1, 2, coords, threading.Event(), Mock()),
                2,
            )

        self.assertEqual(
            [args.args[3] for args in wait_template.call_args_list],
            [
                "steam_change_acc_ready",
                "steam_change_acc_ready",
                "steam_change_acc_ready",
                "steam_switch_account",
            ],
        )
        self.assertEqual(pyautogui.click.call_args_list[-1], call(990, 550))

    def test_switch_account_retries_until_account_picker_template(self):
        pyautogui = SimpleNamespace(click=Mock())
        coords = default_transfer_ui_coords()
        for key in ("menu", "change_account", "continue"):
            coords["steam"][key] = {"x": 10, "y": 20}
        template = SimpleNamespace(
            roi_regions={},
            check_template=Mock(),
            check_template_no_bounds=Mock(),
        )

        with (
            patch.dict(
                "sys.modules",
                {
                    "pyautogui": pyautogui,
                    "source.utility.template": template,
                },
            ),
            patch("source.gacha_bot.server_transfer.kill_ark"),
            patch("source.gacha_bot.server_transfer.stop_wait", return_value=False),
            patch(
                "source.gacha_bot.server_transfer._ensure_steam_window_ready",
                return_value=True,
            ),
            patch(
                "source.gacha_bot.server_transfer._wait_for_template_visible",
                side_effect=[True, False, True, False, True, True],
            ) as wait_template,
        ):
            self.assertEqual(
                switch_steam_account(2, 1, 2, coords, threading.Event(), Mock()),
                2,
            )

        self.assertEqual(
            [args.args[3] for args in wait_template.call_args_list],
            [
                "steam_change_acc_ready",
                "steam_switch_account",
                "steam_change_acc_ready",
                "steam_switch_account",
                "steam_change_acc_ready",
                "steam_switch_account",
            ],
        )
        self.assertEqual(pyautogui.click.call_args_list[-1], call(990, 550))

    def test_steam_window_ready_reopens_running_steam_when_window_missing(self):
        steam = default_transfer_ui_coords()["steam"]
        with (
            patch(
                "source.gacha_bot.server_transfer._focus_steam_window_maximized",
                side_effect=[False, True],
            ) as focus,
            patch(
                "source.gacha_bot.server_transfer._running_steam_exe_path",
                return_value="C:\\Steam\\steam.exe",
            ) as steam_path,
            patch("subprocess.Popen") as popen,
            patch("subprocess.run") as run,
            patch("time.sleep"),
        ):
            self.assertTrue(
                _ensure_steam_window_ready(steam, threading.Event(), Mock())
            )

        self.assertEqual(focus.call_count, 2)
        steam_path.assert_called_once_with()
        popen.assert_called_once_with(["C:\\Steam\\steam.exe"])
        run.assert_not_called()

    def test_steam_window_ready_restarts_steam_between_failed_attempts(self):
        steam = default_transfer_ui_coords()["steam"]
        steam["window_ready_timeout"] = 1
        status = Mock()
        with (
            patch(
                "source.gacha_bot.server_transfer._focus_steam_window_maximized",
                side_effect=[True],
            ) as focus,
            patch(
                "source.gacha_bot.server_transfer._running_steam_exe_path",
                return_value="C:\\Steam\\steam.exe",
            ),
            patch(
                "source.gacha_bot.server_transfer.time.monotonic",
                side_effect=[0, 2, 2, 2.1],
            ),
            patch("subprocess.Popen") as popen,
            patch("subprocess.run") as run,
            patch(
                "source.gacha_bot.server_transfer.stop_wait", return_value=False
            ) as wait,
        ):
            self.assertTrue(
                _ensure_steam_window_ready(steam, threading.Event(), status)
            )

        run.assert_called_once_with(
            ["taskkill", "/f", "/im", "steam.exe"], check=False
        )
        wait.assert_called_once_with(ANY, 1)
        self.assertEqual(
            popen.call_args_list,
            [
                call(["C:\\Steam\\steam.exe"]),
                call(["C:\\Steam\\steam.exe"]),
            ],
        )
        focus.assert_called_once_with("Steam")
        status.assert_any_call(
            "Steam window was not ready; restarting Steam (1/3)."
        )

    def test_join_server_focuses_ark_and_clicks_center_before_auto_join(self):
        pyautogui = SimpleNamespace(click=Mock())
        join_windows = SimpleNamespace(hwnd="old")
        with (
            patch.dict(
                "sys.modules",
                {
                    "pyautogui": pyautogui,
                    "source.join_sim.source.utility.windows": join_windows,
                },
            ),
            patch(
                "source.launcher.system.validate_ark_window",
                return_value=(1920, 1080),
            ) as validate,
            patch(
                "source.launcher.deposit_helper_capture.focus_game_window"
            ) as focus,
            patch(
                "source.gacha_bot.server_transfer._ark_window_handle",
                return_value=123,
            ) as handle,
            patch(
                "source.join_sim.source.auto_join.run_auto_join_server",
                return_value=True,
            ) as auto_join,
        ):
            stop_event = threading.Event()
            status = Mock()
            self.assertTrue(join_server("5147", stop_event, status))

        validate.assert_called_once_with()
        focus.assert_called_once_with(center_cursor_when_switching=True)
        handle.assert_called_once_with("ArkAscended")
        self.assertEqual(join_windows.hwnd, 123)
        pyautogui.click.assert_called_once_with(960, 540)
        auto_join.assert_called_once_with("5147", stop_event, status)

    def test_transfer_to_server_checks_transmitter_before_clicking_transfer(self):
        pyautogui = SimpleNamespace(hotkey=Mock(), write=Mock())
        inventory = SimpleNamespace(open=Mock())
        teleporter = SimpleNamespace(transfer_teleport_not_default=Mock())
        template = SimpleNamespace(
            roi_regions={},
            check_template=Mock(),
            check_template_no_bounds=Mock(),
        )
        utils = SimpleNamespace(set_yaw=Mock())
        config = ready_config(account_count=1)
        clicks = []

        with (
            patch.dict(
                "sys.modules",
                {
                    "pyautogui": pyautogui,
                    "source.ASA.strucutres.inventory": inventory,
                    "source.ASA.strucutres.teleporter": teleporter,
                    "source.utility.template": template,
                    "source.utility.utils": utils,
                },
            ),
            patch(
                "source.gacha_bot.server_transfer._wait_for_template_visible",
                side_effect=[True, False],
            ) as wait_template,
            patch(
                "source.gacha_bot.server_transfer._click_coord",
                side_effect=lambda coord: clicks.append(coord),
            ),
        ):
            self.assertTrue(
                transfer_to_server(
                    "2222",
                    config["settings"],
                    config["ui_coords"],
                    threading.Event(),
                )
            )

        self.assertEqual(wait_template.call_args_list[0], call(
            template.check_template,
            2,
            ANY,
            "README",
            0.7,
        ))
        self.assertEqual(wait_template.call_args_list[1], call(
            template.check_template_no_bounds,
            0,
            ANY,
            "README",
            0.75,
        ))
        self.assertEqual(clicks[0], config["ui_coords"]["transfer"]["transfer_button"])

    def test_transfer_to_server_recovers_state_before_transmitter_retry(self):
        pyautogui = SimpleNamespace(hotkey=Mock(), write=Mock())
        inventory = SimpleNamespace(open=Mock())
        teleporter = SimpleNamespace(transfer_teleport_not_default=Mock())
        template = SimpleNamespace(
            roi_regions={},
            check_template=Mock(),
            check_template_no_bounds=Mock(),
        )
        utils = SimpleNamespace(set_yaw=Mock())
        config = ready_config(account_count=1)
        clicks = []

        with (
            patch.dict(
                "sys.modules",
                {
                    "pyautogui": pyautogui,
                    "source.ASA.strucutres.inventory": inventory,
                    "source.ASA.strucutres.teleporter": teleporter,
                    "source.utility.template": template,
                    "source.utility.utils": utils,
                },
            ),
            patch(
                "source.gacha_bot.server_transfer._wait_for_template_visible",
                side_effect=[False, False, True, False],
            ),
            patch(
                "source.gacha_bot.server_transfer.check_transfer_player_state"
            ) as recover,
            patch(
                "source.gacha_bot.server_transfer._click_coord",
                side_effect=lambda coord: clicks.append(coord),
            ),
            patch("source.gacha_bot.server_transfer.stop_wait", return_value=False),
        ):
            self.assertTrue(
                transfer_to_server(
                    "2222",
                    config["settings"],
                    config["ui_coords"],
                    threading.Event(),
                    players=config["players"],
                    account=1,
                )
            )

        self.assertEqual(inventory.open.call_count, 3)
        self.assertEqual(teleporter.transfer_teleport_not_default.call_count, 3)
        teleporter.transfer_teleport_not_default.assert_has_calls(
            [
                call("TX", fallback_bed_name="Bed1", stop_event=ANY),
                call("TX", fallback_bed_name="Bed1", stop_event=ANY),
                call("TX", fallback_bed_name="Bed1", stop_event=ANY),
            ]
        )
        recover.assert_has_calls(
            [
                call(config["settings"], config["players"], 1, "2222"),
                call(config["settings"], config["players"], 1, "2222"),
            ]
        )
        self.assertEqual(clicks[0], config["ui_coords"]["transfer"]["transfer_button"])

    def test_transfer_to_server_blocks_when_transmitter_title_missing(self):
        pyautogui = SimpleNamespace(hotkey=Mock(), write=Mock())
        inventory = SimpleNamespace(open=Mock())
        teleporter = SimpleNamespace(transfer_teleport_not_default=Mock())
        template = SimpleNamespace(
            roi_regions={},
            check_template=Mock(),
            check_template_no_bounds=Mock(),
        )
        utils = SimpleNamespace(set_yaw=Mock())
        config = ready_config(account_count=1)

        with (
            patch.dict(
                "sys.modules",
                {
                    "pyautogui": pyautogui,
                    "source.ASA.strucutres.inventory": inventory,
                    "source.ASA.strucutres.teleporter": teleporter,
                    "source.utility.template": template,
                    "source.utility.utils": utils,
                },
            ),
            patch(
                "source.gacha_bot.server_transfer._wait_for_template_visible",
                return_value=False,
            ),
            patch("source.gacha_bot.server_transfer.check_transfer_player_state"),
            patch("source.gacha_bot.server_transfer._click_coord") as click_coord,
        ):
            with self.assertRaisesRegex(RuntimeError, "Transmitter inventory"):
                transfer_to_server(
                    "2222",
                    config["settings"],
                    config["ui_coords"],
                    threading.Event(),
                )

        click_coord.assert_not_called()

    def test_withdraw_uses_resource_dedi_route(self):
        config = ready_config(account_count=1)
        metadata = SimpleNamespace(yaw=1, name="RESOURCE_DEDI")
        custom_stations = SimpleNamespace(
            get_station_metadata=Mock(return_value=metadata)
        )
        teleporter = SimpleNamespace(transfer_teleport_not_default=Mock())
        deposit = SimpleNamespace(_restore_route_view=Mock())
        utils = SimpleNamespace(set_yaw=Mock())

        with (
            patch.dict(
                "sys.modules",
                {
                    "source.ASA.stations.custom_stations": custom_stations,
                    "source.ASA.strucutres.teleporter": teleporter,
                    "source.gacha_bot.deposit": deposit,
                    "source.utility.utils": utils,
                },
            ),
            patch(
                "source.gacha_bot.server_transfer._transfer_withdraw_from_dedi",
                return_value=True,
            ) as withdraw,
        ):
            self.assertTrue(
                withdraw_from_transfer_dedis(
                    config["dedis"],
                    config["settings"],
                    threading.Event(),
                    config["ui_coords"],
                    config["players"],
                    1,
                )
            )

        custom_stations.get_station_metadata.assert_called_once_with("RESOURCE_DEDI")
        teleporter.transfer_teleport_not_default.assert_called_once_with(
            metadata, fallback_bed_name="Bed1", stop_event=ANY
        )
        withdraw.assert_called_once()
        self.assertEqual(
            withdraw.call_args.args[1],
            config["dedis"]["resource"]["items"][0],
        )
        self.assertEqual(withdraw.call_args.args[6], "Bed1")

    def test_deposit_uses_destination_dedi_route(self):
        config = ready_config(account_count=1)
        metadata = SimpleNamespace(yaw=1, name="DEST_DEDI")
        custom_stations = SimpleNamespace(
            get_station_metadata=Mock(return_value=metadata)
        )

        with (
            patch.dict(
                "sys.modules",
                {"source.ASA.stations.custom_stations": custom_stations},
            ),
            patch(
                "source.gacha_bot.server_transfer._transfer_deposit_to_dedi",
                return_value=True,
            ) as deposit,
        ):
            self.assertTrue(
                deposit_to_transfer_dedis(
                    config["dedis"],
                    config["ui_coords"],
                    config["settings"],
                    threading.Event(),
                    config["players"],
                    1,
                )
            )

        custom_stations.get_station_metadata.assert_called_once_with("DEST_DEDI")
        deposit.assert_called_once()
        self.assertEqual(
            deposit.call_args.args[1],
            config["dedis"]["destination"]["items"][0],
        )
        self.assertEqual(deposit.call_args.args[6], "Bed1")

    def test_destination_deposit_stops_before_opening_dedi(self):
        config = ready_config(account_count=1)
        metadata = SimpleNamespace(yaw=1, name="DEST_DEDI")
        custom_stations = SimpleNamespace(
            get_station_metadata=Mock(return_value=metadata)
        )
        stop_event = threading.Event()
        stop_event.set()

        with (
            patch.dict(
                "sys.modules",
                {"source.ASA.stations.custom_stations": custom_stations},
            ),
            patch(
                "source.gacha_bot.server_transfer._transfer_deposit_to_dedi"
            ) as deposit,
        ):
            self.assertFalse(
                deposit_to_transfer_dedis(
                    config["dedis"],
                    config["ui_coords"],
                    config["settings"],
                    stop_event,
                    config["players"],
                    1,
                )
            )

        deposit.assert_not_called()

    def test_destination_dedi_init_runs_before_retrying_deposit_ready(self):
        config = ready_config(account_count=1)
        inventory = SimpleNamespace(close=Mock())
        template = SimpleNamespace(
            roi_regions={},
            check_template=Mock(),
            check_template_no_bounds=Mock(),
        )
        utils = SimpleNamespace(press_key=Mock())
        variables = SimpleNamespace(get_pixel_loc=Mock(return_value=967))
        windows = SimpleNamespace(click=Mock())
        logs = SimpleNamespace(
            logger=SimpleNamespace(debug=Mock(), warning=Mock(), error=Mock())
        )
        route_metadata = SimpleNamespace(yaw=1, name="DEST_DEDI")
        item = config["dedis"]["destination"]["items"][0]

        with (
            patch.dict(
                "sys.modules",
                {
                    "source.ASA.strucutres.inventory": inventory,
                    "source.utility.template": template,
                    "source.utility.utils": utils,
                    "source.logs.gachalogs": logs,
                },
            ),
            patch("source.utility.variables", variables, create=True),
            patch("source.utility.windows", windows, create=True),
            patch(
                "source.gacha_bot.server_transfer._open_transfer_dedi_inventory",
                return_value=True,
            ),
            patch(
                "source.gacha_bot.server_transfer._wait_for_template_visible",
                side_effect=[False, True],
            ),
            patch("source.gacha_bot.server_transfer._recover_transfer_dedi_position"),
        ):
            self.assertTrue(
                _transfer_deposit_to_dedi(
                    route_metadata,
                    item,
                    "Transfer dedi 1",
                    config["settings"],
                    config["ui_coords"],
                )
            )

        windows.click.assert_any_call(1, 1)
        utils.press_key.assert_called_once_with("T")
        windows.click.assert_any_call(967, 967)

    def test_destination_dedi_init_failure_returns_false(self):
        config = ready_config(account_count=1)
        inventory = SimpleNamespace(close=Mock())
        template = SimpleNamespace(
            roi_regions={},
            check_template=Mock(),
            check_template_no_bounds=Mock(),
        )
        utils = SimpleNamespace(press_key=Mock())
        windows = SimpleNamespace(click=Mock())
        logs = SimpleNamespace(
            logger=SimpleNamespace(debug=Mock(), warning=Mock(), error=Mock())
        )
        route_metadata = SimpleNamespace(yaw=1, name="DEST_DEDI")
        item = config["dedis"]["destination"]["items"][0]

        with (
            patch.dict(
                "sys.modules",
                {
                    "source.ASA.strucutres.inventory": inventory,
                    "source.utility.template": template,
                    "source.utility.utils": utils,
                    "source.logs.gachalogs": logs,
                },
            ),
            patch("source.utility.windows", windows, create=True),
            patch(
                "source.gacha_bot.server_transfer._open_transfer_dedi_inventory",
                return_value=True,
            ),
            patch(
                "source.gacha_bot.server_transfer._wait_for_template_visible",
                return_value=False,
            ),
            patch("source.gacha_bot.server_transfer._recover_transfer_dedi_position"),
        ):
            self.assertFalse(
                _transfer_deposit_to_dedi(
                    route_metadata,
                    item,
                    "Transfer dedi 1",
                    config["settings"],
                    config["ui_coords"],
                )
            )

        self.assertEqual(utils.press_key.call_count, 3)

    def test_transfer_disconnected_uses_transfer_server_and_yaw(self):
        main = SimpleNamespace(
            is_menu=Mock(return_value=True),
            is_crashed=Mock(return_value=False),
            main_loop=Mock(return_value="hwnd"),
        )
        tribelog = SimpleNamespace(close=Mock())
        utils = SimpleNamespace(set_yaw=Mock())
        windows = SimpleNamespace(hwnd=None)
        logs = SimpleNamespace(logger=SimpleNamespace(critical=Mock()))
        config = ready_config(account_count=1)

        with (
            patch.dict(
                "sys.modules",
                {
                    "source.join_sim.source.main": main,
                    "source.ASA.player.tribelog": tribelog,
                    "source.utility.utils": utils,
                    "source.utility.windows": windows,
                    "source.logs.gachalogs": logs,
                },
            ),
            patch("time.sleep"),
        ):
            check_transfer_disconnected(config["settings"], "2222")

        main.main_loop.assert_called_once_with("2222")
        utils.set_yaw.assert_called_once_with(
            float(config["settings"]["destination_station_yaw"])
        )
        self.assertEqual(windows.hwnd, "hwnd")

    def test_check_transfer_player_state_uses_buff_checker_for_tekpod(self):
        buff_checker = SimpleNamespace(check_buffs=Mock(return_value=1))
        buffs = SimpleNamespace(check_buffs=Mock(return_value=buff_checker))
        render = SimpleNamespace(render_flag=False, leave_tekpod=Mock())
        teleporter = SimpleNamespace(transfer_teleport_not_default=Mock())
        config = ready_config(account_count=1)

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
        ):
            check_transfer_player_state(
                config["settings"], config["players"], 1, "1111"
            )

        buffs.check_buffs.assert_called_once_with()
        buff_checker.check_buffs.assert_called_once_with()
        render.leave_tekpod.assert_called_once_with()
        teleporter.transfer_teleport_not_default.assert_not_called()

    def test_check_transfer_player_state_uses_player_bed_for_food_water_recovery(self):
        buff_checker = SimpleNamespace(check_buffs=Mock(return_value=2))
        buffs = SimpleNamespace(check_buffs=Mock(return_value=buff_checker))
        render = SimpleNamespace(
            render_flag=False, enter_tekpod=Mock(), leave_tekpod=Mock()
        )
        teleporter = SimpleNamespace(transfer_teleport_not_default=Mock())
        config = ready_config(account_count=1)

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

        teleporter.transfer_teleport_not_default.assert_called_once_with(
            "Bed1", fallback_bed_name="Bed1"
        )
        render.enter_tekpod.assert_called_once_with()
        render.leave_tekpod.assert_called_once_with()

    def test_reset_transfer_state_uses_player_bed_name(self):
        player_inventory = SimpleNamespace(close=Mock())
        tribelog = SimpleNamespace(close=Mock())
        teleporter = SimpleNamespace(close=Mock())
        bed = SimpleNamespace(is_open=Mock(return_value=True), spawn_in=Mock())
        utils = SimpleNamespace(press_key=Mock())
        config = ready_config(account_count=2)

        with patch.dict(
            "sys.modules",
            {
                "source.ASA.player.player_inventory": player_inventory,
                "source.ASA.player.tribelog": tribelog,
                "source.ASA.strucutres.bed": bed,
                "source.ASA.strucutres.teleporter": teleporter,
                "source.utility.utils": utils,
            },
        ):
            reset_transfer_state(config["settings"], config["players"], 2)

        bed.spawn_in.assert_called_once_with("Bed2")
        utils.press_key.assert_called_once_with("Run")

    def test_logout_before_kill_uses_console_main_menu_before_kill(self):
        with (
            patch("source.launcher.deposit_helper_capture.focus_game_window") as focus,
            patch("source.gacha_bot.server_transfer._refresh_join_sim_ark_handle") as refresh,
            patch(
                "source.gacha_bot.server_transfer._open_main_menu_until_safe_to_kill",
                return_value=True,
            ) as open_until_safe,
        ):
            stop_event = threading.Event()
            status = Mock()
            self.assertTrue(_logout_before_kill_ark(stop_event, None, status))

        focus.assert_called_once_with(center_cursor_when_switching=True)
        refresh.assert_called_once_with()
        status.assert_any_call("Returning ARK to main menu before closing.")
        open_until_safe.assert_called_once_with(stop_event, status)

    def test_kill_ark_skips_taskkill_when_main_menu_logout_fails(self):
        with (
            patch(
                "source.gacha_bot.server_transfer._logout_before_kill_ark",
                return_value=False,
            ),
            patch("source.launcher.ark_game_setup.kill_running_ark") as kill_running,
        ):
            self.assertFalse(kill_ark())

        kill_running.assert_not_called()

    def test_open_main_menu_retries_when_loading_screen_does_not_appear(self):
        stop_event = threading.Event()
        status = Mock()

        with (
            patch(
                "source.gacha_bot.server_transfer._send_open_main_menu",
                return_value=True,
            ) as send_menu,
            patch(
                "source.gacha_bot.server_transfer._wait_for_ark_loading_screen",
                side_effect=[False, True],
            ) as wait_loading,
            patch(
                "source.gacha_bot.server_transfer._wait_for_ark_main_menu",
                return_value=True,
            ) as wait_menu,
            patch(
                "source.gacha_bot.server_transfer._reset_open_main_menu_console",
                return_value=True,
            ) as reset_console,
        ):
            self.assertTrue(_open_main_menu_until_safe_to_kill(stop_event, status))

        self.assertEqual(send_menu.call_count, 2)
        wait_loading.assert_has_calls(
            [call(stop_event, timeout=3), call(stop_event, timeout=3)]
        )
        reset_console.assert_called_once_with(stop_event)
        wait_menu.assert_called_once_with(stop_event, timeout=30)
        status.assert_any_call("ARK loading screen did not appear; resetting console.")

    def test_send_open_main_menu_resets_console_on_exception(self):
        console = SimpleNamespace(console_write=Mock(side_effect=RuntimeError("bad")))
        player_state = SimpleNamespace(reset_state=Mock())
        stop_event = threading.Event()
        status = Mock()

        with (
            patch.dict(
                "sys.modules",
                {
                    "source.ASA.player.console": console,
                    "source.ASA.player.player_state": player_state,
                },
            ),
            patch(
                "source.gacha_bot.server_transfer._reset_open_main_menu_console",
                return_value=True,
            ) as reset_console,
        ):
            self.assertFalse(_send_open_main_menu(stop_event, status, attempt=4))

        player_state.reset_state.assert_called_once_with()
        console.console_write.assert_called_once_with("open MainMenu")
        reset_console.assert_called_once_with(stop_event)
        status.assert_any_call("Opening ARK main menu (attempt 4).")
        status.assert_any_call("open MainMenu failed: bad; resetting console.")

    def test_reset_open_main_menu_console_matches_ccc_clear_flow(self):
        utils = SimpleNamespace(press_key=Mock())
        stop_event = threading.Event()

        with (
            patch.dict("sys.modules", {"source.utility.utils": utils}),
            patch("source.gacha_bot.server_transfer.stop_wait", return_value=False) as wait,
        ):
            self.assertTrue(_reset_open_main_menu_console(stop_event))

        utils.press_key.assert_has_calls([call("ConsoleKeys"), call("Enter")])
        wait.assert_called_once_with(stop_event, 0.1)

    def test_wait_for_ark_loading_screen_uses_no_bounds_template(self):
        recon_utils = SimpleNamespace(
            check_template_no_bounds=Mock(side_effect=[False, True])
        )

        with (
            patch.dict(
                "sys.modules",
                {"source.join_sim.source.utility.recon_utils": recon_utils},
            ),
            patch("time.sleep"),
        ):
            self.assertTrue(_wait_for_ark_loading_screen(None, timeout=1))

        recon_utils.check_template_no_bounds.assert_has_calls(
            [call("loading_screen", 0.7), call("loading_screen", 0.7)]
        )

    def test_wait_for_ark_loading_screen_ignores_empty_frame_errors(self):
        recon_utils = SimpleNamespace(
            check_template_no_bounds=Mock(side_effect=[RuntimeError("empty"), True])
        )

        with (
            patch.dict(
                "sys.modules",
                {"source.join_sim.source.utility.recon_utils": recon_utils},
            ),
            patch("time.sleep"),
        ):
            self.assertTrue(_wait_for_ark_loading_screen(None, timeout=1))

    def test_safe_menu_check_ignores_empty_frame_errors(self):
        main = SimpleNamespace(is_menu=Mock(side_effect=RuntimeError("empty")))

        with patch.dict("sys.modules", {"source.join_sim.source.main": main}):
            self.assertFalse(_safe_is_ark_main_menu())

    def test_safe_template_check_ignores_empty_frame_errors(self):
        recon_utils = SimpleNamespace(
            check_template_no_bounds=Mock(side_effect=RuntimeError("empty"))
        )

        with patch.dict(
            "sys.modules",
            {"source.join_sim.source.utility.recon_utils": recon_utils},
        ):
            self.assertFalse(_safe_check_join_template_no_bounds("loading_screen", 0.7))

    def test_ensure_ark_running_launches_url_and_waits_for_valid_window(self):
        pyautogui = SimpleNamespace(click=Mock())
        join_windows = SimpleNamespace(hwnd="old")
        status = Mock()
        settings = {"ark_window_ready_timeout": 180, "ark_launch_attempts": 3}
        with (
            patch.dict(
                "sys.modules",
                {
                    "pyautogui": pyautogui,
                    "source.join_sim.source.utility.windows": join_windows,
                },
            ),
            patch(
                "source.gacha_bot.server_transfer._process_running",
                side_effect=[False, True],
            ),
            patch(
                "source.launcher.ark_game_setup.launch_ark_through_steam"
            ) as launch,
            patch(
                "source.launcher.system.validate_ark_window",
                return_value=(1920, 1080),
            ) as validate,
            patch(
                "source.gacha_bot.server_transfer.stop_wait", return_value=False
            ) as wait,
            patch(
                "source.launcher.deposit_helper_capture.focus_game_window"
            ) as focus,
            patch(
                "source.gacha_bot.server_transfer._ark_window_handle",
                return_value=123,
            ),
        ):
            stop_event = threading.Event()
            self.assertTrue(ensure_ark_running(stop_event, status, settings))

        launch.assert_called_once_with()
        validate.assert_called_once_with()
        status.assert_has_calls(
            [
                call("Launching ARK through Steam."),
                call("ARK detected. Focusing game before joining server."),
            ]
        )
        wait.assert_called_once_with(stop_event, 2)
        focus.assert_called_once_with(center_cursor_when_switching=True)
        self.assertEqual(join_windows.hwnd, 123)
        pyautogui.click.assert_called_once_with(960, 540)

    def test_ensure_ark_running_does_not_refocus_when_ark_already_running(self):
        pyautogui = SimpleNamespace(click=Mock())
        settings = {"ark_window_ready_timeout": 180, "ark_launch_attempts": 3}
        with (
            patch.dict("sys.modules", {"pyautogui": pyautogui}),
            patch(
                "source.gacha_bot.server_transfer._process_running",
                return_value=True,
            ),
            patch(
                "source.launcher.ark_game_setup.launch_ark_through_steam"
            ) as launch,
            patch(
                "source.launcher.system.validate_ark_window",
                return_value=(1920, 1080),
            ) as validate,
            patch(
                "source.launcher.deposit_helper_capture.focus_game_window"
            ) as focus,
        ):
            self.assertTrue(ensure_ark_running(threading.Event(), settings=settings))

        launch.assert_not_called()
        validate.assert_called_once_with()
        focus.assert_not_called()
        pyautogui.click.assert_not_called()

    def test_ensure_ark_running_waits_through_slow_window_validation(self):
        with (
            patch(
                "source.gacha_bot.server_transfer._process_running",
                return_value=True,
            ),
            patch(
                "source.launcher.system.validate_ark_window",
                side_effect=[RuntimeError("ArkAscended window was not found."), (1920, 1080)],
            ) as validate,
            patch(
                "source.gacha_bot.server_transfer.time.monotonic",
                side_effect=[0, 0, 0],
            ),
            patch("source.gacha_bot.server_transfer.time.sleep") as sleep,
        ):
            self.assertTrue(
                ensure_ark_running(
                    threading.Event(),
                    settings={"ark_window_ready_timeout": 10, "ark_launch_attempts": 3},
                )
            )

        self.assertEqual(validate.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_ensure_ark_running_relaunches_after_hung_attempt(self):
        pyautogui = SimpleNamespace(click=Mock())
        join_windows = SimpleNamespace(hwnd="old")
        status = Mock()
        with (
            patch.dict(
                "sys.modules",
                {
                    "pyautogui": pyautogui,
                    "source.join_sim.source.utility.windows": join_windows,
                },
            ),
            patch(
                "source.gacha_bot.server_transfer._process_running",
                side_effect=[False, True, False, True],
            ),
            patch(
                "source.launcher.ark_game_setup.launch_ark_through_steam"
            ) as launch,
            patch(
                "source.launcher.system.validate_ark_window",
                side_effect=[RuntimeError("ArkAscended window was not found."), (1920, 1080)],
            ),
            patch(
                "source.gacha_bot.server_transfer.time.monotonic",
                side_effect=[0, 0, 2, 2, 2],
            ),
            patch("source.gacha_bot.server_transfer.time.sleep"),
            patch("source.gacha_bot.server_transfer.kill_ark") as kill,
            patch(
                "source.gacha_bot.server_transfer.stop_wait", return_value=False
            ) as wait,
            patch(
                "source.launcher.deposit_helper_capture.focus_game_window"
            ) as focus,
            patch(
                "source.gacha_bot.server_transfer._ark_window_handle",
                return_value=123,
            ),
        ):
            self.assertTrue(
                ensure_ark_running(
                    threading.Event(),
                    status,
                    {"ark_window_ready_timeout": 1, "ark_launch_attempts": 2},
                )
            )

        self.assertEqual(launch.call_count, 2)
        kill.assert_called_once()
        wait.assert_has_calls([call(ANY, 2), call(ANY, 2)])
        status.assert_any_call(
            "ARK did not reach a usable window state; relaunching (1/2)."
        )
        focus.assert_called_once_with(center_cursor_when_switching=True)
        self.assertEqual(join_windows.hwnd, 123)
        pyautogui.click.assert_called_once_with(960, 540)

    def test_ensure_ark_running_raises_after_exhausted_launch_attempts(self):
        status = Mock()
        with (
            patch(
                "source.gacha_bot.server_transfer._process_running",
                side_effect=[False, True, False, True],
            ),
            patch("source.launcher.ark_game_setup.launch_ark_through_steam"),
            patch(
                "source.launcher.system.validate_ark_window",
                side_effect=RuntimeError("ArkAscended window was not found."),
            ),
            patch(
                "source.gacha_bot.server_transfer.time.monotonic",
                side_effect=[0, 0, 2, 2, 2, 4],
            ),
            patch("source.gacha_bot.server_transfer.time.sleep"),
            patch("source.gacha_bot.server_transfer.kill_ark"),
            patch("source.gacha_bot.server_transfer.stop_wait", return_value=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "after 2 attempt"):
                ensure_ark_running(
                    threading.Event(),
                    status,
                    {"ark_window_ready_timeout": 1, "ark_launch_attempts": 2},
                )

    def test_ensure_ark_running_stop_during_relaunch_delay_returns_false(self):
        stop_event = threading.Event()

        def stop_after_timeout(_event, _seconds):
            stop_event.set()
            return True

        with (
            patch(
                "source.gacha_bot.server_transfer._process_running",
                side_effect=[False, True],
            ),
            patch("source.launcher.ark_game_setup.launch_ark_through_steam") as launch,
            patch(
                "source.launcher.system.validate_ark_window",
                side_effect=RuntimeError("ArkAscended window was not found."),
            ),
            patch(
                "source.gacha_bot.server_transfer.time.monotonic",
                side_effect=[0, 0, 2],
            ),
            patch("source.gacha_bot.server_transfer.time.sleep"),
            patch("source.gacha_bot.server_transfer.kill_ark") as kill,
            patch(
                "source.gacha_bot.server_transfer.stop_wait",
                side_effect=stop_after_timeout,
            ),
        ):
            self.assertFalse(
                ensure_ark_running(
                    stop_event,
                    settings={"ark_window_ready_timeout": 1, "ark_launch_attempts": 3},
                )
            )

        launch.assert_called_once_with()
        kill.assert_called_once()


if __name__ == "__main__":
    unittest.main()
