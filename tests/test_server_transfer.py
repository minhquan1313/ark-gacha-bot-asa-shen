import importlib
import sys
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, call, patch


def _module(name: str, **attributes: object) -> ModuleType:
    module = ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


runtime_settings = _module("settings")
buffs_module = _module("source.ASA.player.buffs")
console_module = _module("source.ASA.player.console")
player_inventory_module = _module("source.ASA.player.player_inventory")
player_state_module = _module("source.ASA.player.player_state")
tribelog_module = _module("source.ASA.player.tribelog")
bed_module = _module("source.ASA.strucutres.bed")
teleporter_module = _module("source.ASA.strucutres.teleporter")
render_module = _module("source.gacha_bot.render", render_flag=False)
join_main_module = _module("source.join_sim.source.main")
auto_join_module = _module(
    "source.join_sim.source.auto_join", run_auto_join_server=Mock(return_value=True)
)
recon_utils_module = _module("source.join_sim.source.utility.recon_utils")
steam_accounts_module = _module("source.launcher.utils.steam_accounts")
ark_setup_module = _module(
    "source.launcher.ark_game_setup",
    ARK_PROCESS_NAME="ArkAscended.exe",
    find_running_steam_dir=Mock(),
    launch_ark_through_steam=Mock(),
)
constants_module = _module("source.launcher.constants", GAME_WINDOW_TITLE="ArkAscended")
capture_module = _module(
    "source.launcher.deposit_helper_capture", focus_game_window=Mock()
)
system_module = _module(
    "source.launcher.system",
    focus_window_if_needed=Mock(),
    validate_ark_window=Mock(),
)
logs_module = _module(
    "source.logs.gachalogs",
    logger=SimpleNamespace(debug=Mock(), error=Mock(), critical=Mock()),
)
template_module = _module("source.utility.template")
utils_module = _module("source.utility.utils", zero_center=Mock())
windows_module = _module("source.utility.windows")
dedi_module = _module("source.utility.structures.dedi.dedi")
transmitter_module = _module("source.utility.structures.transmitter.transmitter")
psutil_module = _module(
    "psutil",
    AccessDenied=type("AccessDenied", (Exception,), {}),
    NoSuchProcess=type("NoSuchProcess", (Exception,), {}),
    process_iter=Mock(return_value=[]),
)
pyautogui_module = _module("pyautogui", click=Mock())

with patch.dict(
    sys.modules,
    {
        "settings": runtime_settings,
        "psutil": psutil_module,
        "pyautogui": pyautogui_module,
        "source.ASA.player.buffs": buffs_module,
        "source.ASA.player.console": console_module,
        "source.ASA.player.player_inventory": player_inventory_module,
        "source.ASA.player.player_state": player_state_module,
        "source.ASA.player.tribelog": tribelog_module,
        "source.ASA.strucutres.bed": bed_module,
        "source.ASA.strucutres.teleporter": teleporter_module,
        "source.gacha_bot.render": render_module,
        "source.join_sim.source.main": join_main_module,
        "source.join_sim.source.auto_join": auto_join_module,
        "source.join_sim.source.utility.recon_utils": recon_utils_module,
        "source.launcher.utils.steam_accounts": steam_accounts_module,
        "source.launcher.ark_game_setup": ark_setup_module,
        "source.launcher.constants": constants_module,
        "source.launcher.deposit_helper_capture": capture_module,
        "source.launcher.system": system_module,
        "source.logs.gachalogs": logs_module,
        "source.utility.template": template_module,
        "source.utility.utils": utils_module,
        "source.utility.windows": windows_module,
        "source.utility.structures.dedi.dedi": dedi_module,
        "source.utility.structures.transmitter.transmitter": transmitter_module,
    },
):
    server_transfer = importlib.import_module("source.gacha_bot.server_transfer")

sys.modules["source.gacha_bot.server_transfer"] = server_transfer

STEAM_DIALOG_BUTTONS = server_transfer.STEAM_DIALOG_BUTTONS
TransferConfigError = server_transfer.TransferConfigError
_focus_visible_steam_window = server_transfer._focus_visible_steam_window
check_transfer_player_state = server_transfer.check_transfer_player_state
deposit_to_transfer_dedis = server_transfer.deposit_to_transfer_dedis
join_server = server_transfer.join_server
run_transfer_helper = server_transfer.run_transfer_helper
steam_has_failure = server_transfer.steam_has_failure
switch_steam_account = server_transfer.switch_steam_account
transfer_to_server = server_transfer.transfer_to_server
withdraw_from_transfer_dedis = server_transfer.withdraw_from_transfer_dedis
from source.launcher.config.transfer_helper_config import default_transfer_ui_coords


def ready_config():
    return {
        "settings": {
            "ping": 1,
            "resource_station_yaw": 0,
            "destination_station_yaw": 0,
            "resource_server": "1111",
            "destination_server": "2222",
            "loop_count": 1,
            "structure_load_delay": 0,
            "transfer_retry_delay": 0,
        },
        "dedis": {
            "resource": {
                "teleport": "RESOURCE",
                "transmitter_teleport": "RESOURCE_TX",
                "items": [{"location": {}}],
            },
            "destination": {
                "teleport": "DEST",
                "transmitter_teleport": "DEST_TX",
                "items": [{"location": {}}],
            },
        },
        "ui_coords": default_transfer_ui_coords(),
        "players": {"players": [{"bed_name": "Bed1", "steam_account": "alpha"}]},
        "steam_accounts": [
            {"account_name": "alpha", "most_recent": True, "timestamp": 1}
        ],
    }


@contextmanager
def runtime_dependencies(**overrides: object) -> Iterator[SimpleNamespace]:
    """Patch direct transfer operations for orchestration tests."""
    defaults = {
        "switch_steam_account": Mock(
            side_effect=lambda target, _current, *_args, **_kwargs: target
        ),
        "ensure_ark_running": Mock(return_value=True),
        "is_menu": Mock(return_value=False),
        "join_server": Mock(return_value=True),
        "verify_tribelog": Mock(return_value=True),
        "check_transfer_player_state": Mock(),
        "withdraw_from_transfer_dedis": Mock(return_value=True),
        "go_back_to_bed": Mock(),
        "enter_tekpod": Mock(),
        "leave_tekpod": Mock(),
        "transfer_to_server": Mock(),
        "wait_for_bed_screen": Mock(),
        "spawn_bed": Mock(),
        "deposit_to_transfer_dedis": Mock(return_value=True),
    }
    defaults.update(overrides)
    with (
        patch.multiple(server_transfer, **defaults),
        patch.object(server_transfer.time, "sleep") as sleep,
    ):
        dependencies = SimpleNamespace(**defaults)
        dependencies.wait_structure = sleep
        yield dependencies


class ServerTransferRunnerTests(unittest.TestCase):
    def test_missing_inputs_raise_config_error(self):
        config = ready_config()
        config["settings"]["resource_server"] = "0"

        with self.assertRaises(TransferConfigError):
            run_transfer_helper(config)

    def test_single_account_flow_uses_saved_servers_and_player_bed(self):
        with runtime_dependencies() as dependencies:
            self.assertTrue(
                run_transfer_helper(ready_config())
            )

        self.assertTrue(
            any(
                call_args.args[0] == "1111"
                for call_args in dependencies.join_server.call_args_list
            )
        )
        transferred_servers = [
            call_args.args[0]
            for call_args in dependencies.transfer_to_server.call_args_list
        ]
        self.assertIn("2222", transferred_servers)
        self.assertIn("1111", transferred_servers)
        transfer_sides = [
            call_args.args[6]
            for call_args in dependencies.transfer_to_server.call_args_list
        ]
        self.assertIn("resource", transfer_sides)
        self.assertIn("destination", transfer_sides)
        dependencies.go_back_to_bed.assert_called_once_with("Bed1")
        dependencies.spawn_bed.assert_any_call("Bed1")
        dependencies.switch_steam_account.assert_not_called()
        self.assertEqual(dependencies.ensure_ark_running.call_count, 2)
        self.assertEqual(dependencies.join_server.call_count, 2)

    def test_multi_account_flow_restores_player_one_on_resource_server(self):
        config = ready_config()
        config["players"]["players"].append(
            {"bed_name": "Bed2", "steam_account": "beta"}
        )
        config["steam_accounts"].append(
            {"account_name": "beta", "most_recent": False, "timestamp": 0}
        )

        snapshots = []
        with runtime_dependencies() as dependencies:
            self.assertTrue(run_transfer_helper(config, task_callback=snapshots.append))

        final_switch = dependencies.switch_steam_account.call_args_list[-1]
        self.assertEqual(final_switch.args[:2], (1, 2))
        self.assertEqual(final_switch.kwargs["steam_restart_interval"], 30)
        self.assertEqual(dependencies.ensure_ark_running.call_count, 5)
        self.assertEqual(dependencies.join_server.call_count, 5)
        self.assertEqual(dependencies.join_server.call_args.args[0], "1111")
        restore_steam = next(
            snapshot
            for snapshot in snapshots
            if snapshot["running"]
            and snapshot["running"][0]["name"] == "Acc 1 - Restore Steam - alpha"
        )
        self.assertEqual(
            [task["name"] for task in restore_steam["active"]],
            ["Acc 1 - Restore ARK", "Acc 1 - Restore Resource - 1111"],
        )

    def test_player_one_restore_ark_failure_returns_false(self):
        config = ready_config()
        config["players"]["players"].append(
            {"bed_name": "Bed2", "steam_account": "beta"}
        )
        config["steam_accounts"].append(
            {"account_name": "beta", "most_recent": False, "timestamp": 0}
        )
        with runtime_dependencies(
            ensure_ark_running=Mock(side_effect=[True, True, True, True, False])
        ) as dependencies:
            self.assertFalse(run_transfer_helper(config))

        self.assertEqual(dependencies.join_server.call_count, 4)

    def test_player_one_restore_join_failure_returns_false(self):
        config = ready_config()
        config["players"]["players"].append(
            {"bed_name": "Bed2", "steam_account": "beta"}
        )
        config["steam_accounts"].append(
            {"account_name": "beta", "most_recent": False, "timestamp": 0}
        )
        with runtime_dependencies(
            join_server=Mock(side_effect=[True, True, True, True, False])
        ):
            self.assertFalse(run_transfer_helper(config))

    def test_destinate_mode_starts_at_destination_loop(self):
        config = ready_config()
        config["settings"]["transfer_start_mode"] = "destinate"
        snapshots = []

        with runtime_dependencies() as dependencies:
            self.assertTrue(
                run_transfer_helper(
                    config,
                    task_callback=snapshots.append,
                )
            )

        dependencies.verify_tribelog.assert_not_called()
        dependencies.withdraw_from_transfer_dedis.assert_not_called()
        dependencies.go_back_to_bed.assert_not_called()
        dependencies.leave_tekpod.assert_called_once()
        dependencies.deposit_to_transfer_dedis.assert_called_once()
        dependencies.enter_tekpod.assert_called_once()
        self.assertEqual(dependencies.join_server.call_count, 1)
        self.assertEqual(
            [call_args.args[0] for call_args in dependencies.transfer_to_server.call_args_list],
            ["2222", "1111"],
        )
        self.assertEqual(
            snapshots[0]["running"][0]["name"], "Acc 1 L1 - Ensure ARK Ready"
        )

    def test_default_mode_start_account_skips_first_pass_accounts(self):
        config = ready_config()
        config["start_account"] = 3
        config["players"]["players"].extend(
            [
                {"bed_name": "Bed2", "steam_account": "beta"},
                {"bed_name": "Bed3", "steam_account": "gamma"},
            ]
        )
        config["steam_accounts"] = [
            {"account_name": "alpha", "most_recent": False, "timestamp": 1},
            {"account_name": "beta", "most_recent": False, "timestamp": 2},
            {"account_name": "gamma", "most_recent": True, "timestamp": 3},
        ]
        snapshots = []

        with runtime_dependencies() as dependencies:
            self.assertTrue(run_transfer_helper(config, task_callback=snapshots.append))

        self.assertEqual(
            [call_args.args[3] for call_args in dependencies.withdraw_from_transfer_dedis.call_args_list],
            [3],
        )
        self.assertEqual(
            [call_args.args[3] for call_args in dependencies.deposit_to_transfer_dedis.call_args_list],
            [3],
        )
        self.assertEqual(
            [call_args.args[0] for call_args in dependencies.switch_steam_account.call_args_list],
            [3, 3, 1],
        )
        self.assertEqual(
            snapshots[0]["running"][0]["name"], "Acc 3 - Switch Steam - gamma"
        )

    def test_default_mode_start_account_only_skips_first_loop(self):
        config = ready_config()
        config["start_account"] = 3
        config["settings"]["loop_count"] = 2
        config["players"]["players"].extend(
            [
                {"bed_name": "Bed2", "steam_account": "beta"},
                {"bed_name": "Bed3", "steam_account": "gamma"},
            ]
        )
        config["steam_accounts"] = [
            {"account_name": "alpha", "most_recent": False, "timestamp": 1},
            {"account_name": "beta", "most_recent": False, "timestamp": 2},
            {"account_name": "gamma", "most_recent": True, "timestamp": 3},
        ]

        with runtime_dependencies() as dependencies:
            self.assertTrue(run_transfer_helper(config))

        self.assertEqual(
            [call_args.args[3] for call_args in dependencies.withdraw_from_transfer_dedis.call_args_list],
            [3, 3],
        )
        self.assertEqual(
            [call_args.args[3] for call_args in dependencies.deposit_to_transfer_dedis.call_args_list],
            [3, 1, 2, 3],
        )

    def test_destinate_mode_start_account_skips_first_loop_accounts(self):
        config = ready_config()
        config["start_account"] = 3
        config["settings"]["transfer_start_mode"] = "destinate"
        config["players"]["players"].extend(
            [
                {"bed_name": "Bed2", "steam_account": "beta"},
                {"bed_name": "Bed3", "steam_account": "gamma"},
            ]
        )
        config["steam_accounts"] = [
            {"account_name": "alpha", "most_recent": False, "timestamp": 1},
            {"account_name": "beta", "most_recent": False, "timestamp": 2},
            {"account_name": "gamma", "most_recent": True, "timestamp": 3},
        ]
        snapshots = []

        with runtime_dependencies() as dependencies:
            self.assertTrue(run_transfer_helper(config, task_callback=snapshots.append))

        dependencies.verify_tribelog.assert_not_called()
        dependencies.withdraw_from_transfer_dedis.assert_not_called()
        self.assertEqual(
            [call_args.args[3] for call_args in dependencies.deposit_to_transfer_dedis.call_args_list],
            [3],
        )
        self.assertEqual(
            [call_args.args[4] for call_args in dependencies.transfer_to_server.call_args_list],
            [3, 3],
        )
        self.assertEqual(
            snapshots[0]["running"][0]["name"], "Acc 3 L1 - Switch Steam - gamma"
        )

    def test_task_snapshots_track_dependency_actions_and_next_three(self):
        config = ready_config()
        config["settings"]["loop_count"] = 2
        config["players"]["players"].append(
            {"bed_name": "Bed2", "steam_account": "beta"}
        )
        config["steam_accounts"].append(
            {"account_name": "beta", "most_recent": False, "timestamp": 0}
        )
        snapshots = []

        with runtime_dependencies():
            self.assertTrue(
                run_transfer_helper(
                    config,
                    task_callback=snapshots.append,
                )
            )

        self.assertEqual(
            snapshots[0],
            {
                "running": [{"name": "Acc 1 - Switch Steam - alpha"}],
                "active": [
                    {"name": "Acc 1 - Ensure ARK Ready", "state": "READY"},
                    {"name": "Acc 1 - Check Menu State", "state": "READY"},
                    {"name": "Acc 1 - Join Resource - 1111", "state": "READY"},
                ],
                "waiting": [],
            },
        )
        transfer_snapshot = next(
            snapshot
            for snapshot in snapshots
            if snapshot["running"]
            and snapshot["running"][0]["name"]
            == "Acc 1 L1 - Transfer Destination - 2222"
        )
        self.assertEqual(
            [task["name"] for task in transfer_snapshot["active"]],
            [
                "Acc 1 L1 - Wait Destination Bed",
                "Acc 1 L1 - Spawn Destination Bed - Bed1",
                "Acc 1 L1 - Wait Destination Structures",
            ],
        )
        self.assertTrue(
            any(
                snapshot["running"]
                and snapshot["running"][0]["name"] == "Acc 2 L2 - Deposit Resources"
                for snapshot in snapshots
            )
        )
        published_tasks = [
            snapshot["running"][0]["name"]
            for snapshot in snapshots
            if snapshot["running"]
        ]
        self.assertIn("Acc 1 - Join Resource - 1111", published_tasks)
        self.assertIn("Acc 1 L1 - Going back to Tekpod", published_tasks)
        self.assertIn("Acc 1 L1 - Enter Tekpod", published_tasks)
        self.assertIn("Acc 1 L2 - Enter Tekpod", published_tasks)
        self.assertFalse(
            any("Stabilize Bed" in task_name for task_name in published_tasks)
        )

    def test_task_snapshots_insert_confirmed_conditional_wait(self):
        snapshots = []

        with runtime_dependencies(is_menu=Mock(return_value=True)):
            self.assertTrue(
                run_transfer_helper(
                    ready_config(),
                    task_callback=snapshots.append,
                )
            )

        verify_snapshot = next(
            snapshot
            for snapshot in snapshots
            if snapshot["running"]
            and snapshot["running"][0]["name"] == "Acc 1 - Verify Tribe Log"
        )
        self.assertEqual(
            verify_snapshot["active"][0]["name"],
            "Acc 1 - Check Player State",
        )

    def test_task_snapshots_discard_skipped_account_actions(self):
        config = ready_config()
        config["players"]["players"].append(
            {"bed_name": "Bed2", "steam_account": "beta"}
        )
        config["steam_accounts"].append(
            {"account_name": "beta", "most_recent": False, "timestamp": 0}
        )
        snapshots = []

        with runtime_dependencies(verify_tribelog=Mock(side_effect=[False, True])):
            self.assertTrue(
                run_transfer_helper(
                    config,
                    task_callback=snapshots.append,
                )
            )

        account_two = next(
            snapshot
            for snapshot in snapshots
            if snapshot["running"]
            and snapshot["running"][0]["name"] == "Acc 2 - Switch Steam - beta"
        )
        self.assertEqual(
            [task["name"] for task in account_two["active"]],
            [
                "Acc 2 - Ensure ARK Ready",
                "Acc 2 - Check Menu State",
                "Acc 2 - Join Resource - 1111",
            ],
        )

    def test_join_failure_returns_false_without_killing_ark(self):
        with runtime_dependencies(join_server=Mock(return_value=False)):
            self.assertFalse(run_transfer_helper(ready_config()))

    def test_steam_has_failure_skips_templates_when_steam_window_is_not_visible(self):
        steam = default_transfer_ui_coords()["steam"]
        template = SimpleNamespace(check_template_no_bounds=Mock())
        pyautogui = SimpleNamespace(click=Mock())

        with (
            patch.object(server_transfer, "template", template),
            patch.object(server_transfer, "pyautogui", pyautogui),
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

    def test_focus_steam_window_only_maximizes_when_needed(self):
        user32 = SimpleNamespace(
            FindWindowW=Mock(return_value=123),
            IsZoomed=Mock(side_effect=[True, False]),
            ShowWindow=Mock(),
            BringWindowToTop=Mock(),
        )

        with (
            patch("ctypes.windll", SimpleNamespace(user32=user32), create=True),
            patch.object(server_transfer, "focus_window_if_needed", return_value=True),
        ):
            self.assertTrue(server_transfer._focus_steam_window_maximized("Steam"))
            user32.ShowWindow.assert_not_called()

            self.assertTrue(server_transfer._focus_steam_window_maximized("Steam"))

        user32.ShowWindow.assert_called_once_with(123, 3)
        self.assertEqual(user32.BringWindowToTop.call_count, 2)

    def test_steam_has_failure_handles_launch_option_dialog(self):
        steam = default_transfer_ui_coords()["steam"]
        status = []
        events = []
        template = SimpleNamespace(
            check_template_no_bounds=Mock(
                side_effect=lambda item, _threshold: (
                    events.append(("template", item)) or item == "steam_launch_option"
                )
            )
        )
        pyautogui = SimpleNamespace(click=Mock())

        with (
            patch.object(server_transfer, "template", template),
            patch.object(server_transfer, "pyautogui", pyautogui),
            patch(
                "source.gacha_bot.server_transfer._focus_visible_steam_window",
                side_effect=lambda _steam, _emit: events.append("focus") or True,
            ) as focus_steam,
            patch.object(server_transfer.time, "sleep"),
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
                side_effect=lambda item, _threshold: (
                    events.append(("template", item))
                    or item == "steam_cloud_sync_conflic"
                )
            )
        )
        pyautogui = SimpleNamespace(click=Mock())

        with (
            patch.object(server_transfer, "template", template),
            patch.object(server_transfer, "pyautogui", pyautogui),
            patch(
                "source.gacha_bot.server_transfer._focus_visible_steam_window",
                side_effect=lambda _steam, _emit: events.append("focus") or True,
            ) as focus_steam,
            patch.object(server_transfer.time, "sleep"),
        ):
            self.assertTrue(steam_has_failure(steam, status.append))

        focus_steam.assert_called_once()
        self.assertEqual(events[0], "focus")
        pyautogui.click.assert_called_once_with(
            STEAM_DIALOG_BUTTONS["cloud_sync_conflict_play"]["x"],
            STEAM_DIALOG_BUTTONS["cloud_sync_conflict_play"]["y"],
        )
        self.assertEqual(status[-1], "Detected Steam cloud sync conflict dialog.")

    def test_ensure_ark_running_restarts_steam_before_retry(self):
        status = []
        events = []
        steam = {"restart_delay": 3, "window_title": "Steam"}
        steam_accounts = SimpleNamespace(
            close_steam=Mock(side_effect=lambda: events.append("close_steam")),
            launch_steam=Mock(side_effect=lambda: events.append("launch_steam")),
        )
        ark_game_setup = SimpleNamespace(
            kill_running_ark=Mock(side_effect=lambda: events.append("kill_ark"))
        )
        launch_ark = Mock(side_effect=lambda: events.append("launch_ark"))

        with (
            patch.object(server_transfer, "steam_accounts", steam_accounts),
            patch.object(server_transfer, "ark_game_setup", ark_game_setup),
            patch.object(
                server_transfer,
                "launch_ark_through_steam",
                launch_ark,
            ),
            patch.object(server_transfer, "_process_running", return_value=False),
            patch.object(server_transfer, "steam_has_failure"),
            patch.object(
                server_transfer,
                "_focus_visible_steam_window",
                side_effect=lambda *_args: events.append("focus_steam") or True,
            ) as focus_steam,
            patch.object(
                server_transfer.utils_simple,
                "get_default_clock",
                side_effect=[lambda: True, lambda: False, lambda: True],
            ) as get_default_clock,
            patch.object(
                server_transfer.time,
                "sleep",
                side_effect=lambda seconds: events.append(f"sleep:{seconds}"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "ARK did not start after 2"):
                server_transfer.ensure_ark_running(
                    status.append,
                    {
                        "ark_launch_attempts": 2,
                        "ark_window_ready_timeout": 5,
                        "steam_restart_interval": 7,
                    },
                    {"steam": steam},
                )

        self.assertEqual(
            events,
            [
                "launch_ark",
                "kill_ark",
                "close_steam",
                "sleep:3.0",
                "launch_steam",
                "focus_steam",
                "launch_ark",
            ],
        )
        self.assertEqual(launch_ark.call_count, 2)
        focus_steam.assert_called_once()
        self.assertEqual(
            [call_args.args[0] for call_args in get_default_clock.call_args_list],
            [5, 7, 5],
        )
        self.assertIn("Restarting Steam before relaunching ARK.", status)

    def test_ensure_ark_running_does_not_restart_steam_after_final_attempt(self):
        steam_accounts = SimpleNamespace(close_steam=Mock(), launch_steam=Mock())
        ark_game_setup = SimpleNamespace(kill_running_ark=Mock())

        with (
            patch.object(server_transfer, "steam_accounts", steam_accounts),
            patch.object(server_transfer, "ark_game_setup", ark_game_setup),
            patch.object(server_transfer, "launch_ark_through_steam"),
            patch.object(server_transfer, "_process_running", return_value=False),
            patch.object(server_transfer, "steam_has_failure"),
            patch.object(
                server_transfer.utils_simple,
                "get_default_clock",
                return_value=lambda: True,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "ARK did not start after 1"):
                server_transfer.ensure_ark_running(
                    Mock(),
                    {
                        "ark_launch_attempts": 1,
                        "ark_window_ready_timeout": 5,
                        "steam_restart_interval": 7,
                    },
                    {"steam": default_transfer_ui_coords()["steam"]},
                )

        ark_game_setup.kill_running_ark.assert_not_called()
        steam_accounts.close_steam.assert_not_called()
        steam_accounts.launch_steam.assert_not_called()

    def test_join_server_focuses_ark_then_reuses_auto_join(self):
        run_auto_join = Mock(return_value=True)
        with (
            patch.object(
                server_transfer,
                "validate_ark_window",
                return_value=(1920, 1080),
            ),
            patch.object(server_transfer, "run_auto_join_server", run_auto_join),
            patch(
                "source.gacha_bot.server_transfer._focus_ark_window_for_join"
            ) as focus,
        ):
            self.assertTrue(join_server("5147", Mock()))

        focus.assert_called_once_with((1920, 1080))
        run_auto_join.assert_called_once()
        self.assertEqual(run_auto_join.call_args.args[0], "5147")

    def test_check_transfer_player_state_uses_normal_teleporter_flow(self):
        player_state = SimpleNamespace(check_state=Mock())
        config = ready_config()
        runtime_settings = SimpleNamespace()

        with (
            patch.object(server_transfer, "global_settings", runtime_settings),
            patch.object(server_transfer, "player_state", player_state),
        ):
            check_transfer_player_state(
                config["settings"], config["players"], 1, "1111"
            )

        self.assertEqual(runtime_settings.server_number, "1111")
        self.assertEqual(runtime_settings.bed_spawn, "Bed1")
        player_state.check_state.assert_called_once_with()

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
        with runtime_dependencies(
            withdraw_from_transfer_dedis=Mock(
                side_effect=lambda _dedis, _settings, _players, account: (
                    events.append(("withdraw", account)) or True
                )
            ),
            deposit_to_transfer_dedis=Mock(
                side_effect=lambda _dedis, _settings, _players, account: (
                    events.append(("deposit", account)) or True
                )
            ),
            transfer_to_server=Mock(
                side_effect=lambda server, *_args: events.append(
                    ("transfer", server, _args[-1])
                )
            ),
        ) as dependencies:
            self.assertTrue(run_transfer_helper(config))

        for switch_call in dependencies.switch_steam_account.call_args_list:
            self.assertEqual(switch_call.kwargs["steam_restart_interval"], 30)

        self.assertEqual(events[:2], [("withdraw", 1), ("withdraw", 2)])
        self.assertIn(("deposit", 1), events[2:])
        self.assertIn(("deposit", 2), events[2:])

    def test_resource_dedi_sweep_delegates_and_sets_account_runtime_settings(self):
        config = ready_config()
        config["dedis"]["resource"]["items"] *= 2
        runtime_settings = SimpleNamespace()
        teleporter = SimpleNamespace(teleport_not_default=Mock())
        utils = SimpleNamespace(zero_center=Mock())
        dedi = ModuleType("source.utility.structures.dedi.dedi")
        dedi.open_withdraw_all = Mock(return_value=True)
        with (
            patch.object(server_transfer, "global_settings", runtime_settings),
            patch.object(server_transfer, "teleporter", teleporter),
            patch.object(server_transfer, "utils", utils),
            patch.object(server_transfer, "dedi", dedi),
        ):
            result = withdraw_from_transfer_dedis(
                config["dedis"], config["settings"], config["players"], 1
            )

        self.assertTrue(result)
        self.assertEqual(runtime_settings.ping, 1)
        self.assertEqual(runtime_settings.station_yaw, 0.0)
        self.assertEqual(runtime_settings.bed_spawn, "Bed1")
        teleporter.teleport_not_default.assert_called_once_with(
            "RESOURCE", fallback_bed_name="Bed1"
        )
        utils.zero_center.assert_called_once_with()
        self.assertEqual(dedi.open_withdraw_all.call_count, 2)
        for call_args in dedi.open_withdraw_all.call_args_list:
            self.assertEqual(call_args.args[0], "RESOURCE")

    def test_destination_dedi_sweep_delegates_and_sets_account_runtime_settings(self):
        config = ready_config()
        config["settings"]["ping"] = 150
        config["settings"]["destination_station_yaw"] = 45
        config["dedis"]["destination"]["items"] *= 2
        runtime_settings = SimpleNamespace()
        teleporter = SimpleNamespace(teleport_not_default=Mock())
        utils = SimpleNamespace(zero_center=Mock())
        dedi = ModuleType("source.utility.structures.dedi.dedi")
        dedi.open_deposit_all = Mock(return_value=True)
        with (
            patch.object(server_transfer, "global_settings", runtime_settings),
            patch.object(server_transfer, "teleporter", teleporter),
            patch.object(server_transfer, "utils", utils),
            patch.object(server_transfer, "dedi", dedi),
        ):
            result = deposit_to_transfer_dedis(
                config["dedis"], config["settings"], config["players"], 1
            )

        self.assertTrue(result)
        self.assertEqual(runtime_settings.ping, 150)
        self.assertEqual(runtime_settings.station_yaw, 45.0)
        self.assertEqual(runtime_settings.bed_spawn, "Bed1")
        teleporter.teleport_not_default.assert_called_once_with(
            "DEST", fallback_bed_name="Bed1"
        )
        utils.zero_center.assert_called_once_with()
        self.assertEqual(dedi.open_deposit_all.call_count, 2)
        for call_args in dedi.open_deposit_all.call_args_list:
            self.assertEqual(call_args.args[0], "DEST")

    def test_failed_dedi_operation_stops_remaining_resource_sweep(self):
        config = ready_config()
        config["dedis"]["resource"]["items"] *= 3
        runtime_settings = SimpleNamespace()
        teleporter = SimpleNamespace(teleport_not_default=Mock())
        utils = SimpleNamespace(zero_center=Mock())
        dedi = ModuleType("source.utility.structures.dedi.dedi")
        dedi.open_withdraw_all = Mock(side_effect=[True, False, True])
        with (
            patch.object(server_transfer, "global_settings", runtime_settings),
            patch.object(server_transfer, "teleporter", teleporter),
            patch.object(server_transfer, "utils", utils),
            patch.object(server_transfer, "dedi", dedi),
        ):
            result = withdraw_from_transfer_dedis(
                config["dedis"], config["settings"], config["players"], 1
            )

        self.assertFalse(result)
        self.assertEqual(dedi.open_withdraw_all.call_count, 2)
        utils.zero_center.assert_called_once_with()

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
            launch_steam=Mock(),
        )
        kill = Mock()

        with (
            patch.dict(
                switch_steam_account.__globals__,
                {
                    "ark_game_setup": SimpleNamespace(kill_running_ark=kill),
                    "steam_accounts": steam_accounts,
                    "_wait_for_steam_window": Mock(return_value=True),
                    "utils": SimpleNamespace(close_ark_with_console_exit=Mock()),
                },
            ),
            patch.object(switch_steam_account.__globals__["time"], "sleep"),
        ):
            result = switch_steam_account(
                2, "alpha", players, default_transfer_ui_coords()
            )

        self.assertEqual(result, "beta")
        kill.assert_called_once()
        steam_accounts.select_auto_login_account.assert_called_once_with("beta")

    def test_force_restart_runs_for_current_account_in_safety_order(self):
        players = {"players": [{"bed_name": "Bed1", "steam_account": "alpha"}]}
        events = []
        steam_accounts = SimpleNamespace(
            select_auto_login_account=Mock(
                side_effect=lambda *_args: events.append("select")
            ),
            close_steam=Mock(side_effect=lambda: events.append("close_steam")),
            launch_steam=Mock(side_effect=lambda: events.append("launch_steam")),
        )
        loginusers = Path("loginusers.vdf")
        kill = Mock(side_effect=lambda: events.append("kill_ark"))

        with (
            patch.dict(
                switch_steam_account.__globals__,
                {
                    "ark_game_setup": SimpleNamespace(kill_running_ark=kill),
                    "steam_accounts": steam_accounts,
                    "_wait_for_steam_window": Mock(return_value=True),
                    "utils": SimpleNamespace(close_ark_with_console_exit=Mock()),
                },
            ),
            patch.object(switch_steam_account.__globals__["time"], "sleep"),
        ):
            result = switch_steam_account(
                1,
                "alpha",
                players,
                default_transfer_ui_coords(),
                force_restart=True,
                loginusers=loginusers,
            )

        self.assertEqual(result, "alpha")
        self.assertEqual(events, ["kill_ark", "select", "close_steam", "launch_steam"])
        steam_accounts.select_auto_login_account.assert_called_once_with(
            "alpha", loginusers
        )

    def test_current_account_remains_noop_without_force_restart(self):
        players = {"players": [{"bed_name": "Bed1", "steam_account": "alpha"}]}
        kill = Mock()
        with patch.dict(
            switch_steam_account.__globals__,
            {"ark_game_setup": SimpleNamespace(kill_running_ark=kill)},
        ):
            result = switch_steam_account(
                1, "alpha", players, default_transfer_ui_coords()
            )

        self.assertEqual(result, "alpha")
        kill.assert_not_called()

    def test_transfer_to_server_uses_transmitter_helper_after_teleport_and_yaw(self):
        config = ready_config()
        status = []
        teleporter = SimpleNamespace(teleport_not_default=Mock())
        utils = SimpleNamespace(zero_center=Mock())
        transmitter = SimpleNamespace(open_and_transfer=Mock(return_value=True))
        with (
            patch.object(server_transfer, "teleporter", teleporter),
            patch.object(server_transfer, "utils", utils),
            patch.object(server_transfer, "transmitter", transmitter),
        ):
            self.assertTrue(
                transfer_to_server(
                    "2222",
                    config["settings"],
                    status.append,
                    config["players"],
                    1,
                    config["dedis"],
                    "resource",
                )
            )

        teleporter.teleport_not_default.assert_called_once_with(
            "RESOURCE_TX", fallback_bed_name="Bed1"
        )
        transmitter.open_and_transfer.assert_called_once_with("RESOURCE_TX", "2222")
        self.assertEqual(status[-1], "Transfer to server 2222 requested.")

    def test_transfer_to_server_uses_legacy_settings_transmitter_fallback(self):
        config = ready_config()
        config["settings"]["transmitter_teleport"] = "LEGACY_TX"
        config["dedis"]["resource"]["transmitter_teleport"] = ""
        teleporter = SimpleNamespace(teleport_not_default=Mock())
        utils = SimpleNamespace(zero_center=Mock())
        transmitter = SimpleNamespace(open_and_transfer=Mock(return_value=True))
        with (
            patch.object(server_transfer, "teleporter", teleporter),
            patch.object(server_transfer, "utils", utils),
            patch.object(server_transfer, "transmitter", transmitter),
        ):
            self.assertTrue(
                transfer_to_server(
                    "2222",
                    config["settings"],
                    players=config["players"],
                    account=1,
                    dedis=config["dedis"],
                    transmitter_side="resource",
                )
            )

        teleporter.teleport_not_default.assert_called_once_with(
            "LEGACY_TX", fallback_bed_name="Bed1"
        )

    def test_transfer_to_server_recovers_after_failed_transmitter_attempt(self):
        config = ready_config()
        teleporter = SimpleNamespace(teleport_not_default=Mock())
        utils = SimpleNamespace(zero_center=Mock())
        transmitter = SimpleNamespace(open_and_transfer=Mock(side_effect=[False, True]))
        with (
            patch.object(server_transfer, "teleporter", teleporter),
            patch.object(server_transfer, "utils", utils),
            patch.object(server_transfer, "transmitter", transmitter),
            patch(
                "source.gacha_bot.server_transfer.check_transfer_player_state"
            ) as check_state,
            patch.object(server_transfer.time, "sleep"),
        ):
            self.assertTrue(
                transfer_to_server(
                    "2222",
                    config["settings"],
                    players=config["players"],
                    account=1,
                    dedis=config["dedis"],
                    transmitter_side="resource",
                )
            )

        self.assertEqual(transmitter.open_and_transfer.call_count, 2)
        check_state.assert_called_once_with(
            config["settings"],
            config["players"],
            1,
            "2222",
            config["dedis"],
            "resource",
        )


if __name__ == "__main__":
    unittest.main()
