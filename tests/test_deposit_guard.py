import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import source.gacha_bot.config as config

ROOT = Path(__file__).resolve().parents[1]


class FakeClock:
    def __init__(self):
        self.value = 0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


def load_deposit_module():
    logger = Mock()
    inventory = types.SimpleNamespace(close=Mock())
    teleporter = types.SimpleNamespace(teleport_not_default=Mock())
    player_state = types.SimpleNamespace(
        check_disconnected=Mock(),
        check_state=Mock(),
        human=types.SimpleNamespace(crouched=False, crouch=Mock(), reset_crouch=Mock()),
    )
    template = types.SimpleNamespace(
        check_template=Mock(),
        template_await_true=Mock(),
        template_await_false=Mock(),
    )
    utils = types.SimpleNamespace(
        press_key=Mock(), turn_to=Mock(), zero=Mock(return_value=True)
    )

    player = types.ModuleType("source.ASA.player")
    player.player_inventory = types.SimpleNamespace(implant_eat=Mock())
    player.player_state = player_state
    stations = types.ModuleType("source.ASA.stations")
    stations.custom_stations = types.SimpleNamespace()
    structures = types.ModuleType("source.ASA.strucutres")
    structures.inventory = inventory
    structures.teleporter = teleporter
    logs = types.ModuleType("source.logs.gachalogs")
    logs.logger = logger
    utility = types.ModuleType("source.utility")
    utility.template = template
    utility.utils = utils
    utility.variables = types.SimpleNamespace()
    utility.windows = types.SimpleNamespace()

    modules = {
        "settings": types.SimpleNamespace(
            lag_offset=1, drop_off="", grindables="", dedi_handshake_timeout=30
        ),
        "source.ASA.player": player,
        "source.ASA.stations": stations,
        "source.ASA.strucutres": structures,
        "source.logs.gachalogs": logs,
        "source.utility": utility,
    }
    spec = importlib.util.spec_from_file_location(
        "deposit_under_test", ROOT / "source" / "gacha_bot" / "deposit.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module, logger, inventory, teleporter, player_state, template, utils


class DediDepositGuardTests(unittest.TestCase):
    def setUp(self):
        self.original_attempts = config.dedi_handshake_recovery_attempts
        (
            self.deposit,
            self.logger,
            self.inventory,
            self.teleporter,
            self.player_state,
            self.template,
            self.utils,
        ) = load_deposit_module()
        self.route = types.SimpleNamespace(yaw=12)
        self.item = {"location": {"yaw": 34, "pitch": 56}, "crouched": False}

    def tearDown(self):
        config.dedi_handshake_recovery_attempts = self.original_attempts

    def test_successful_handshake_opens_and_closes_same_dedi_before_returning(self):
        self.deposit.time.sleep = Mock()
        self.template.template_await_true.side_effect = (
            lambda _, __, name, ___: name == "inventory"
        )
        self.template.check_template.side_effect = lambda name, _: name == "inventory"

        self.assertTrue(self.deposit._deposit_to_dedi(self.route, self.item, "dedi"))

        self.assertEqual(
            [call.args[0] for call in self.utils.press_key.call_args_list],
            ["Use", "AccessInventory"],
        )
        self.inventory.close.assert_called_once_with()

    def test_handshake_waits_for_remote_loading_to_clear(self):
        self.deposit.time.sleep = Mock()
        waiting = iter([True, False, False])
        self.template.template_await_true.return_value = True
        self.template.check_template.side_effect = lambda name, _: (
            True if name == "inventory" else next(waiting)
        )

        self.assertTrue(self.deposit._deposit_to_dedi(self.route, self.item, "dedi"))

        self.assertEqual(self.player_state.check_disconnected.call_count, 2)
        self.deposit.time.sleep.assert_any_call(0.05)
        self.inventory.close.assert_called_once_with()

    def test_frozen_remote_loading_does_not_rotate_before_timeout(self):
        self.deposit.settings.dedi_handshake_timeout = 1
        config.dedi_handshake_recovery_attempts = 1
        clock = FakeClock()
        self.deposit.time.monotonic = clock.monotonic
        self.deposit.time.sleep = clock.sleep
        self.template.template_await_true.return_value = True
        self.template.check_template.return_value = True
        self.deposit._turn_to_object = Mock()
        self.deposit._recover_dedi_position = Mock()
        self.deposit._recover_after_dedi_failure = Mock()

        self.assertFalse(self.deposit._deposit_to_dedi(self.route, self.item, "dedi"))

        self.deposit._turn_to_object.assert_called_once_with(self.route, self.item)
        self.deposit._recover_dedi_position.assert_not_called()
        self.deposit._recover_after_dedi_failure.assert_called_once_with("dedi")

    def test_attempt_waits_full_30_seconds_without_in_attempt_reteleport(self):
        self.deposit.settings.dedi_handshake_timeout = 30
        config.dedi_handshake_recovery_attempts = 1
        clock = FakeClock()
        self.deposit.time.monotonic = clock.monotonic
        self.deposit.time.sleep = clock.sleep
        self.template.template_await_true.return_value = False
        self.deposit._recover_dedi_position = Mock()
        self.deposit._recover_after_dedi_failure = Mock()

        self.assertFalse(self.deposit._deposit_to_dedi(self.route, self.item, "dedi"))

        self.assertGreaterEqual(clock.value, 30)
        self.assertLess(clock.value, 31)
        self.deposit._recover_dedi_position.assert_not_called()
        self.deposit._recover_after_dedi_failure.assert_called_once_with("dedi")

    def test_three_timeout_cycles_recover_between_attempts_then_abort(self):
        self.deposit.settings.dedi_handshake_timeout = 1
        config.dedi_handshake_recovery_attempts = 3
        clock = FakeClock()
        self.deposit.time.monotonic = clock.monotonic
        self.deposit.time.sleep = clock.sleep
        self.template.template_await_true.return_value = False
        self.deposit._recover_dedi_position = Mock()
        self.deposit._recover_after_dedi_failure = Mock()

        self.assertFalse(self.deposit._deposit_to_dedi(self.route, self.item, "dedi"))

        self.assertEqual(
            [call.args[0] for call in self.utils.press_key.call_args_list].count("Use"),
            3,
        )
        self.assertEqual(self.deposit._recover_dedi_position.call_count, 2)
        self.deposit._recover_after_dedi_failure.assert_called_once_with("dedi")

    def test_unavailable_inventory_checks_disconnect_and_recovers_same_dedi(self):
        self.deposit.settings.dedi_handshake_timeout = 11
        config.dedi_handshake_recovery_attempts = 1
        clock = FakeClock()
        self.deposit.time.monotonic = clock.monotonic
        self.deposit.time.sleep = clock.sleep
        self.template.template_await_true.return_value = False
        self.deposit._recover_dedi_position = Mock()
        self.deposit._recover_after_dedi_failure = Mock()

        self.assertFalse(self.deposit._deposit_to_dedi(self.route, self.item, "dedi"))

        self.assertGreater(self.player_state.check_disconnected.call_count, 0)
        self.deposit._recover_dedi_position.assert_not_called()
        self.deposit._recover_after_dedi_failure.assert_called_once_with("dedi")

    def test_recovery_checks_state_reteleports_and_reaims_same_dedi(self):
        self.deposit._restore_route_view = Mock()
        self.deposit._turn_to_object = Mock()

        self.deposit._recover_dedi_position(self.route, self.item, "dedi")

        self.player_state.check_state.assert_called_once_with()
        self.teleporter.teleport_not_default.assert_called_once_with(self.route)
        self.deposit._restore_route_view.assert_called_once_with(self.route)
        self.deposit._turn_to_object.assert_called_once_with(self.route, self.item)

    def test_crystal_and_grindable_sweeps_use_guard(self):
        self.deposit._deposit_to_dedi = Mock(return_value=True)
        self.deposit._restore_route_view = Mock()
        route = {"teleport": "TEST"}

        self.deposit._process_crystal_dedi(route, self.route, self.item, 1)
        self.deposit._process_grindable_dedi(route, self.route, self.item, 2)

        self.assertEqual(self.deposit._deposit_to_dedi.call_count, 2)

    def test_final_failure_reconnects_suicides_and_checks_state(self):
        self.deposit._recover_after_dedi_failure("dedi")

        self.inventory.close.assert_called_once_with()
        self.player_state.check_disconnected.assert_called_once_with()
        self.deposit.player_inventory.implant_eat.assert_called_once_with()
        self.player_state.check_state.assert_called_once_with()
        self.logger.critical.assert_called_once()

    def test_failed_crystal_dedi_skips_vaults_remaining_routes_and_grindables(self):
        route = {
            "teleport": "CRYSTAL",
            "dedi": {"items": [self.item, self.item]},
            "vault": {"items": [{"items": ["riot"]}]},
        }
        self.deposit._process_crystal_dedi = Mock(return_value=False)
        self.deposit._process_vault = Mock()
        self.deposit._restore_route_view = Mock()

        self.assertFalse(
            self.deposit._process_crystal_route(
                route, current_metadata=types.SimpleNamespace(name="CRYSTAL", yaw=12),
                skip_if_current=True,
            )
        )

        self.deposit._process_crystal_dedi.assert_called_once()
        self.deposit._process_vault.assert_not_called()

        self.deposit.load_deposit_config = Mock(
            return_value={
                "depositCrystalData": [route, route],
                "depositGrindableData": [{"teleport": "GRIND"}],
            }
        )
        self.deposit._process_crystal_route = Mock(return_value=False)
        self.deposit._process_grindable_routes = Mock()

        self.assertFalse(self.deposit.deposit_all(None))
        self.deposit._process_crystal_route.assert_called_once()
        self.deposit._process_grindable_routes.assert_not_called()

    def test_failed_grindable_dedi_skips_remaining_routes_and_drop(self):
        active_route = {
            "teleport": "GRIND1",
            "grinder": {"active": True},
            "dedi": {"items": []},
        }
        later_route = {
            "teleport": "GRIND2",
            "grinder": {"active": False},
            "dedi": {"items": []},
        }
        self.deposit._teleport_to_route = Mock(return_value=self.route)
        self.deposit._restore_route_view = Mock()
        self.deposit._process_grinder = Mock()
        self.deposit._sync_post_grinder_route_view = Mock(return_value=True)
        self.deposit._process_grindable_route = Mock(return_value=False)
        self.deposit.drop_useless = Mock()

        self.assertFalse(
            self.deposit._process_grindable_routes([active_route, later_route])
        )

        self.deposit._teleport_to_route.assert_called_once_with(active_route)
        self.deposit._process_grindable_route.assert_called_once_with(
            active_route, self.route
        )
        self.deposit.drop_useless.assert_not_called()

    def test_active_grinder_route_resyncs_once_after_grinder_before_dedis(self):
        order = []
        route = {
            "teleport": "GRIND",
            "grinder": {"active": True},
            "dedi": {"items": []},
        }
        self.deposit._teleport_to_route = Mock(
            side_effect=lambda _: order.append("teleport") or self.route
        )
        self.deposit._restore_route_view = Mock(
            side_effect=lambda _: order.append("restore")
        )
        self.deposit._process_grinder = Mock(
            side_effect=lambda *_: order.append("grinder")
        )
        self.utils.zero.side_effect = lambda: order.append("zero") or True
        self.deposit._process_grindable_route = Mock(
            side_effect=lambda *_: order.append("dedi sweep") or True
        )
        self.deposit.drop_useless = Mock(side_effect=lambda: order.append("drop"))

        self.deposit._process_grindable_routes([route])

        self.assertEqual(
            order,
            [
                "teleport",
                "restore",
                "grinder",
                "zero",
                "restore",
                "dedi sweep",
                "drop",
                "restore",
            ],
        )
        self.utils.zero.assert_called_once_with()

    def test_failed_post_grinder_reset_aborts_before_dedis_and_drop(self):
        route = {
            "teleport": "GRIND",
            "grinder": {"active": True},
            "dedi": {"items": []},
        }
        self.deposit._teleport_to_route = Mock(return_value=self.route)
        self.deposit._restore_route_view = Mock()
        self.deposit._process_grinder = Mock()
        self.utils.zero.return_value = False
        self.deposit._process_grindable_route = Mock()
        self.deposit.drop_useless = Mock()

        self.assertFalse(self.deposit._process_grindable_routes([route]))

        self.deposit._process_grindable_route.assert_not_called()
        self.deposit.drop_useless.assert_not_called()
        self.assertEqual(self.deposit._restore_route_view.call_count, 1)
        self.logger.error.assert_called_once()
        self.assertIn(
            "aborting grindable deposits", self.logger.error.call_args.args[0]
        )


if __name__ == "__main__":
    unittest.main()
