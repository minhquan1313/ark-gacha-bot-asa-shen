import threading
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, Mock, call, patch

from source.gacha_bot.server_transfer import (
    TransferConfigError,
    _ensure_steam_window_ready,
    _transfer_deposit_to_dedi,
    check_transfer_disconnected,
    deposit_to_transfer_dedis,
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

        dependencies.kill_ark.assert_called_once_with()
        dependencies.withdraw_resource.assert_called()

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
        kill.assert_called_once_with()
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
            patch("time.sleep"),
        ):
            self.assertTrue(
                _ensure_steam_window_ready(steam, threading.Event(), Mock())
            )

        self.assertEqual(focus.call_count, 2)
        steam_path.assert_called_once_with()
        popen.assert_called_once_with(["C:\\Steam\\steam.exe"])

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

    def test_ensure_ark_running_launches_url_and_waits_for_valid_window(self):
        with (
            patch(
                "source.gacha_bot.server_transfer._process_running",
                side_effect=[False, True],
            ),
            patch(
                "source.launcher.ark_game_setup.launch_ark_through_steam"
            ) as launch,
            patch("source.launcher.system.validate_ark_window") as validate,
        ):
            self.assertTrue(ensure_ark_running(threading.Event()))

        launch.assert_called_once_with()
        validate.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
