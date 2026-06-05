import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call

from source.gacha_bot.server_transfer import TransferConfigError, run_transfer_helper
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
            "account_count": account_count,
            "loop_count": loop_count,
            "bed_prefix": "BedPlayer",
            "bed_prefix_pad_start": 2,
        }
    )
    dedis = normalize_transfer_dedis({"teleport": "DEDI"})
    coords = default_transfer_ui_coords()
    for key in ("menu", "change_account", "continue"):
        coords["steam"][key] = {"x": 1, "y": 1}
    for key in (
        "transfer_button",
        "server_search",
        "first_server",
        "join_button",
        "not_ready_ok",
    ):
        coords["transfer"][key] = {"x": 1, "y": 1}
    coords["transfer"]["transmitter_title_template"] = "README.md"
    coords["transfer"]["not_ready_template"] = "README.md"
    return {"settings": settings, "dedis": dedis, "ui_coords": coords}


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

    def test_flow_uses_padded_bed_names_and_transfer_servers(self):
        dependencies = deps()

        self.assertTrue(
            run_transfer_helper(ready_config(), threading.Event(), dependencies=dependencies)
        )

        dependencies.fast_travel_to_bed.assert_has_calls(
            [call("BedPlayer01"), call("BedPlayer02")]
        )
        dependencies.transfer_to_server.assert_has_calls(
            [call("2222"), call("1111"), call("2222"), call("1111")]
        )
        dependencies.spawn_bed.assert_has_calls(
            [
                call("BedPlayer01"),
                call("BedPlayer01"),
                call("BedPlayer02"),
                call("BedPlayer02"),
            ]
        )

    def test_stop_event_exits_before_first_account(self):
        stop_event = threading.Event()
        stop_event.set()
        dependencies = deps()

        self.assertFalse(
            run_transfer_helper(ready_config(), stop_event, dependencies=dependencies)
        )

        dependencies.switch_account.assert_not_called()


if __name__ == "__main__":
    unittest.main()
