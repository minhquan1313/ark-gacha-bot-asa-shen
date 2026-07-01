import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load_deposit_module():
    logger = Mock()
    inventory = types.SimpleNamespace(close=Mock(), transfer_all_from=Mock())
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
    player.player_inventory = types.SimpleNamespace(
        close=Mock(),
        implant_eat=Mock(),
        search_in_inventory=Mock(),
        transfer_all_inventory=Mock(),
        wait_clear_search=Mock(),
    )
    player.player_state = player_state
    station_metadata = type("station_metadata", (), {})
    custom_stations = types.ModuleType("source.ASA.stations.custom_stations")
    custom_stations.station_metadata = station_metadata
    stations = types.ModuleType("source.ASA.stations")
    stations.custom_stations = custom_stations
    structures = types.ModuleType("source.ASA.strucutres")
    structures.inventory = inventory
    structures.teleporter = teleporter
    logs = types.ModuleType("source.logs.gachalogs")
    logs.logger = logger
    utility = types.ModuleType("source.utility")
    utility.template = template
    utility.utils = utils
    utility.variables = types.SimpleNamespace(get_pixel_loc=Mock(return_value=0))
    utility.windows = types.SimpleNamespace(click=Mock())
    captures = {}
    debug_screenshots = types.ModuleType("source.utility.debug_screenshots")
    debug_screenshots.CAPTURE_DEDI_DEPOSIT_CRYSTAL = False
    debug_screenshots.CAPTURE_DEDI_DEPOSIT_GRIND = False
    debug_screenshots.CAPTURE_GRINDER_WITHDRAW = False
    debug_screenshots.CAPTURE_ROUTE_READY = False
    debug_screenshots.CAPTURE_VAULT_TRANSFER = False

    def capture_for(category, active=False, delay=0.0):
        captures[category] = Mock()
        return captures[category]

    debug_screenshots.capture_for = capture_for
    utility.debug_screenshots = debug_screenshots
    utility_structures = types.ModuleType("source.utility.structures")
    dedi_package = types.ModuleType("source.utility.structures.dedi")
    dedi = types.ModuleType("source.utility.structures.dedi.dedi")
    dedi.capture_name = None
    dedi.open_deposit_all = Mock(return_value=True)
    dedi_package.dedi = dedi
    utility_types = types.ModuleType("source.utility.types")
    utility_types.DediStorageState = dict

    modules = {
        "settings": types.SimpleNamespace(lag_offset=1),
        "source.ASA.player": player,
        "source.ASA.stations": stations,
        "source.ASA.stations.custom_stations": custom_stations,
        "source.ASA.strucutres": structures,
        "source.logs.gachalogs": logs,
        "source.utility": utility,
        "source.utility.debug_screenshots": debug_screenshots,
        "source.utility.structures": utility_structures,
        "source.utility.structures.dedi": dedi_package,
        "source.utility.structures.dedi.dedi": dedi,
        "source.utility.types": utility_types,
    }
    spec = importlib.util.spec_from_file_location(
        "deposit_under_test", ROOT / "source" / "gacha_bot" / "deposit.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    module.debug_captures = captures
    return module, logger, inventory, teleporter, player_state, template, utils


class DediDepositGuardTests(unittest.TestCase):
    def setUp(self):
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

    def test_crystal_dedi_sets_capture_name_and_delegates_to_dedi(self):
        route = {"teleport": "CRYSTAL"}

        self.assertTrue(
            self.deposit._process_crystal_dedi(route, self.route, self.item, 1)
        )

        self.assertEqual(
            self.deposit.dedi.capture_name,
            "Crystal dedi 1 on teleport CRYSTAL",
        )
        self.deposit.dedi.open_deposit_all.assert_called_once_with(
            self.route, self.item
        )

    def test_grindable_dedi_sets_capture_name_and_delegates_to_dedi(self):
        route = {"teleport": "GRIND"}

        self.assertTrue(
            self.deposit._process_grindable_dedi(route, self.route, self.item, 2)
        )

        self.assertEqual(
            self.deposit.dedi.capture_name,
            "Grindable dedi 2 on teleport GRIND",
        )
        self.deposit.dedi.open_deposit_all.assert_called_once_with(
            self.route, self.item
        )

    def test_failed_dedi_delegation_runs_terminal_recovery_once(self):
        self.deposit.dedi.open_deposit_all.return_value = False
        self.deposit._recover_after_dedi_failure = Mock()
        route = {"teleport": "CRYSTAL"}

        self.assertFalse(
            self.deposit._process_crystal_dedi(route, self.route, self.item, 1)
        )

        self.deposit._recover_after_dedi_failure.assert_called_once_with(
            "Crystal dedi 1 on teleport CRYSTAL"
        )

    def test_crystal_route_ready_capture_happens_before_processing_dedis(self):
        self.deposit._process_crystal_dedi = Mock(return_value=True)
        self.deposit._process_vault = Mock()
        self.deposit._restore_route_view = Mock()
        route = {"teleport": "CRYSTAL", "dedi": {"items": [self.item]}}

        self.assertTrue(
            self.deposit._process_crystal_route(
                route,
                current_metadata=types.SimpleNamespace(name="CRYSTAL", yaw=12),
                skip_if_current=True,
            )
        )

        self.deposit.debug_captures["deposit_route_ready"].assert_called_once_with(
            "Crystal route CRYSTAL"
        )

    def test_stance_changes_before_final_dedi_aim(self):
        order = []
        self.player_state.human.crouched = True
        self.player_state.human.reset_crouch.side_effect = lambda: order.append("stand")
        self.utils.turn_to.side_effect = lambda yaw, pitch: order.append(
            ("turn", yaw, pitch)
        )

        self.deposit._turn_to_object(self.route, self.item)

        self.assertEqual(
            order,
            [
                "stand",
                ("turn", 34.0, 56.0),
            ],
        )

    def test_grinder_capture_happens_before_inventory_close(self):
        route = {"teleport": "GRIND", "grinder": self.item}
        self.deposit._open_inventory_template = Mock(return_value=True)
        self.template.check_template.return_value = True

        self.deposit._process_grinder(route, self.route)

        self.deposit.debug_captures["grinder_after_withdraw"].assert_called_once_with(
            "Grinder on teleport GRIND"
        )
        self.inventory.close.assert_called_once_with()

    def test_vault_capture_happens_before_inventory_close(self):
        route = {"teleport": "CRYSTAL"}
        vault = {**self.item, "items": ["obsidian"]}
        self.deposit._open_inventory_template = Mock(return_value=True)
        self.template.template_await_true.return_value = True

        self.deposit._process_vault(route, self.route, vault, 1)

        self.deposit.debug_captures["vault_after_transfer"].assert_called_once_with(
            "Vault 1 on teleport CRYSTAL"
        )
        self.inventory.close.assert_called_once_with()

    def test_grindable_sweep_restores_route_only_after_all_dedis(self):
        route = {"teleport": "GRIND", "dedi": {"items": [self.item, self.item]}}
        self.deposit._restore_route_view = Mock()

        self.assertTrue(self.deposit._process_grindable_route(route, self.route))

        self.assertEqual(self.deposit.dedi.open_deposit_all.call_count, 2)
        self.deposit._restore_route_view.assert_called_once_with(self.route)

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
                route,
                current_metadata=types.SimpleNamespace(name="CRYSTAL", yaw=12),
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

    def test_empty_grindable_routes_are_skipped(self):
        self.deposit._teleport_to_route = Mock()
        self.deposit.drop_useless = Mock()

        self.assertTrue(self.deposit._process_grindable_routes([]))

        self.deposit._teleport_to_route.assert_not_called()
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
