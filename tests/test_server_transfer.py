import threading
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, Mock, call, patch

from source.gacha_bot.server_transfer import (
    TransferConfigError,
    _ensure_steam_window_ready,
    ensure_ark_running,
    run_transfer_helper,
    switch_steam_account,
    transfer_to_server,
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
            "teleport": "DEDI",
            "items": [
                {
                    "location": {"yaw": 0, "pitch": 0},
                    "crouched": False,
                }
            ],
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
            [call("2222"), call("1111"), call("2222"), call("1111")]
        )
        dependencies.spawn_bed.assert_has_calls(
            [
                call("Bed1"),
                call("Bed1"),
                call("Bed2"),
                call("Bed2"),
            ]
        )

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
            with self.assertRaisesRegex(
                RuntimeError, "change-account continue button"
            ):
                switch_steam_account(
                    2, 1, 2, coords, threading.Event(), Mock()
                )

        self.assertEqual(
            pyautogui.click.call_args_list,
            [
                call(10, 20),
                call(10, 20),
            ],
        )

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
        teleporter = SimpleNamespace(teleport_not_default=Mock())
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
        self.assertEqual(clicks[0], config["ui_coords"]["transfer"]["transfer_button"])

    def test_transfer_to_server_blocks_when_transmitter_title_missing(self):
        pyautogui = SimpleNamespace(hotkey=Mock(), write=Mock())
        inventory = SimpleNamespace(open=Mock())
        teleporter = SimpleNamespace(teleport_not_default=Mock())
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
