import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

ROOT = Path(__file__).resolve().parents[1]


def load_deposit_module():
    logger = Mock()
    inventory_lag = Mock()
    inventory_lag.__enter__ = Mock()
    inventory_lag.__exit__ = Mock(return_value=False)
    inventory = types.SimpleNamespace(
        close=Mock(),
        detect_lag_long_process=Mock(return_value=inventory_lag),
        is_open=Mock(return_value=True),
        is_turned_on=Mock(return_value=True),
        open=Mock(),
        transfer_all_from=Mock(),
        turn_on=Mock(),
        was_server_lag_last_open=False,
        was_server_lag_last_open_long=False,
    )
    teleporter = types.SimpleNamespace(teleport_not_default=Mock())
    player_inventory = types.SimpleNamespace(
        close=Mock(),
        drop_all_inv=Mock(),
        implant_eat=Mock(),
        is_can_transfer_all=Mock(return_value=True),
        is_open=Mock(return_value=True),
        open=Mock(),
        search_in_inventory=Mock(),
        transfer_all_inventory=Mock(),
        wait_clear_search=Mock(),
        g_last_check_can_transfer=True,
    )
    player_state = types.SimpleNamespace(
        check_disconnected=Mock(),
        check_state=Mock(),
        human=types.SimpleNamespace(crouched=False, crouch=Mock(), reset_crouch=Mock()),
    )
    template = types.SimpleNamespace(
        check_template=Mock(return_value=True),
        template_await_true=Mock(return_value=True),
        template_await_false=Mock(),
    )
    utils = types.SimpleNamespace(
        press_key=Mock(),
        turn_to=Mock(),
        zero_center=Mock(),
    )

    player = types.ModuleType("source.ASA.player")
    player.player_inventory = player_inventory
    player.player_state = player_state
    structures = types.ModuleType("source.ASA.strucutres")
    structures.inventory = inventory
    structures.teleporter = teleporter
    logs = types.ModuleType("source.logs.gachalogs")
    logs.logger = logger
    logs_package = types.ModuleType("source.logs")
    logs_package.gachalogs = logs
    utility = types.ModuleType("source.utility")
    utility.template = template
    utility.utils = utils
    utility.utils_simple = types.SimpleNamespace(
        get_default_clock=Mock(return_value=Mock(return_value=False))
    )
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
    dedi.unsafe_fast_deposit_all = Mock(return_value=True)
    dedi_package.dedi = dedi
    utility_types = types.ModuleType("source.utility.types")
    utility_types.CrystalDepositRoute = dict
    utility_types.DediStorageContainer = dict
    utility_types.DediStorageState = dict
    utility_types.DepositConfig = dict
    utility_types.DepositRouteBase = dict
    utility_types.GrindableDepositRoute = dict
    utility_types.GrinderStorageState = dict
    utility_types.VaultStorageContainer = dict
    utility_types.VaultStorageState = dict
    pego = types.ModuleType("source.gacha_bot.pego")
    pego.is_crystal_hotbar_visible = Mock(return_value=False)

    modules = {
        "settings": types.SimpleNamespace(ping=1),
        "source.gacha_bot.config": types.SimpleNamespace(grinder_attempts=3),
        "source.gacha_bot.pego": pego,
        "source.ASA.player": player,
        "source.ASA.strucutres": structures,
        "source.logs": logs_package,
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
    return module, logger, inventory, teleporter, player_inventory, player_state, utils


class DediDepositGuardTests(unittest.TestCase):
    def setUp(self):
        (
            self.deposit,
            self.logger,
            self.inventory,
            self.teleporter,
            self.player_inventory,
            self.player_state,
            self.utils,
        ) = load_deposit_module()
        self.item = {"location": {"yaw": 34, "pitch": 56}, "crouched": False}

    def test_fast_dedi_sets_capture_name_and_delegates(self):
        route = {"teleport": "CRYSTAL"}

        self.assertTrue(self.deposit.process_fast_dedi(route, self.item, 1, "crystal"))

        self.assertEqual(
            self.deposit.dedi.capture_name,
            "Crystal dedi 1 on teleport CRYSTAL",
        )
        self.deposit.dedi.unsafe_fast_deposit_all.assert_called_once_with(self.item)

    def test_restore_route_view_uses_default_station_yaw(self):
        self.deposit._restore_route_view("CRYSTAL")

        self.player_state.human.reset_crouch.assert_called_once_with()
        self.utils.zero_center.assert_called_once_with()

    def test_route_ready_capture_happens_before_route_processing(self):
        route = {"teleport": "CRYSTAL", "check_on_every_dedi": 1, "dedi": {"items": []}}
        self.deposit.process_dedi_list_route = Mock(return_value=True)

        self.assertTrue(
            self.deposit._process_crystal_routes(
                route,
                current_metadata="CRYSTAL",
                skip_if_current=True,
            )
        )

        self.teleporter.teleport_not_default.assert_not_called()
        self.deposit.debug_captures["deposit_route_ready"].assert_called_once_with(
            "Crystal route CRYSTAL"
        )
        self.deposit.process_dedi_list_route.assert_called_once_with(
            route, "CRYSTAL", "crystal"
        )

    def test_stance_changes_before_final_dedi_aim(self):
        order = []
        self.player_state.human.crouched = True
        self.player_state.human.reset_crouch.side_effect = lambda: order.append("stand")
        self.utils.turn_to.side_effect = lambda yaw, pitch: order.append(
            ("turn", yaw, pitch)
        )

        self.deposit._turn_to_object(self.item)

        self.assertEqual(order, ["stand", ("turn", 34.0, 56.0)])

    def test_grinder_capture_happens_before_inventory_close(self):
        route = {"teleport": "GRIND", "grinder": self.item}
        self.deposit._open_inventory_template = Mock(return_value=True)

        self.deposit._process_grinder(route, "GRIND")

        self.deposit.debug_captures["grinder_after_withdraw"].assert_called_once_with(
            "Grinder on teleport GRIND"
        )
        self.inventory.close.assert_called()

    def test_vault_capture_happens_before_inventory_close(self):
        route = {"teleport": "CRYSTAL"}
        vault = {**self.item, "items": ["obsidian"]}
        self.deposit._open_inventory_template = Mock(return_value=True)

        self.deposit._process_vault(route, "CRYSTAL", vault, 1)

        self.deposit.debug_captures["vault_after_transfer"].assert_called_once_with(
            "Vault 1 on teleport CRYSTAL"
        )
        self.inventory.close.assert_called_once_with()

    def test_process_dedi_list_retries_batch_after_server_lag(self):
        first_item = {"location": {"yaw": 10, "pitch": 20}, "crouched": False}
        check_item = {"location": {"yaw": 30, "pitch": 40}, "crouched": False}
        route = {
            "teleport": "CRYSTAL",
            "check_on_every_dedi": 2,
            "dedi": {"items": [first_item, check_item]},
        }
        self.inventory.was_server_lag_last_open_long = True
        self.deposit.process_fast_dedi = Mock(return_value=True)

        self.assertTrue(self.deposit.process_dedi_list_route(route, "CRYSTAL"))

        self.deposit.dedi.open_deposit_all.assert_called_once_with("CRYSTAL", check_item)
        self.deposit.process_fast_dedi.assert_has_calls(
            [
                call(route, first_item, 0, "crystal"),
                call(route, first_item, 0, "crystal"),
            ]
        )
        self.assertEqual(self.deposit.process_fast_dedi.call_count, 2)
        self.logger.warning.assert_called_once()

    def test_empty_grindable_routes_are_skipped(self):
        self.deposit._teleport_to_route = Mock()
        self.deposit.drop_useless = Mock()

        self.assertTrue(self.deposit._process_grindable_routes([]))

        self.deposit._teleport_to_route.assert_not_called()
        self.deposit.drop_useless.assert_not_called()

    def test_active_grindable_route_processes_active_then_rest(self):
        active_route = {
            "teleport": "GRIND1",
            "grinder": {"active": True},
            "check_on_every_dedi": 1,
            "dedi": {"items": []},
        }
        later_route = {
            "teleport": "GRIND2",
            "grinder": {"active": False},
            "check_on_every_dedi": 1,
            "dedi": {"items": []},
        }
        self.deposit._process_grinder = Mock()
        self.deposit.process_dedi_list_route = Mock(return_value=True)
        self.deposit.drop_useless = Mock()

        self.assertTrue(self.deposit._process_grindable_routes([active_route, later_route]))

        self.assertEqual(
            self.teleporter.teleport_not_default.call_args_list,
            [call("GRIND1"), call("GRIND2")],
        )
        self.assertEqual(self.deposit.process_dedi_list_route.call_count, 2)
        self.deposit.drop_useless.assert_called_once_with()

    def test_deposit_all_stops_when_first_crystal_route_fails(self):
        route = {"teleport": "CRYSTAL"}
        self.deposit.load_deposit_config = Mock(
            return_value={
                "depositCrystalData": [route, route],
                "depositGrindableData": [{"teleport": "GRIND"}],
            }
        )
        self.deposit._process_crystal_routes = Mock(return_value=False)
        self.deposit._process_grindable_routes = Mock()

        self.assertFalse(self.deposit.deposit_all(None))

        self.deposit._process_crystal_routes.assert_called_once()
        self.deposit._process_grindable_routes.assert_not_called()


if __name__ == "__main__":
    unittest.main()
