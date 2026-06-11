import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from source.gacha_bot.server_transfer import (
    TransferConfigError,
    _refresh_join_sim_ark_handle,
    _template_item,
    check_transfer_player_state,
    join_server,
    run_transfer_helper,
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
        "players": {"players": [{"bed_name": "Bed1"}]},
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
            _template_item("assets/icons1080/steam_switch_account.png"),
            "steam_switch_account",
        )

    def test_refresh_ark_handle_returns_live_handle_without_cached_assignment(self):
        with patch(
            "source.gacha_bot.server_transfer._ark_window_handle", return_value=123
        ):
            self.assertEqual(_refresh_join_sim_ark_handle(), 123)

    def test_join_server_focuses_ark_then_reuses_auto_join(self):
        with (
            patch("source.launcher.system.validate_ark_window", return_value=(1920, 1080)),
            patch("source.gacha_bot.server_transfer._focus_ark_window_for_join") as focus,
            patch(
                "source.join_sim.source.auto_join.run_auto_join_server",
                return_value=True,
            ) as auto_join,
        ):
            self.assertTrue(join_server("5147", Mock()))

        focus.assert_called_once_with((1920, 1080))
        auto_join.assert_called_once()
        self.assertEqual(auto_join.call_args.args[0], "5147")

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


if __name__ == "__main__":
    unittest.main()
