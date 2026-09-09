import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

import source.gacha_bot.config as config

ROOT = Path(__file__).resolve().parents[1]


def load_iguanadon_module(external_berry=False):
    inventory = types.SimpleNamespace(
        close=Mock(),
        detect_lag_long_process=Mock(),
        is_open=Mock(return_value=True),
        open=Mock(),
        popcorn=Mock(),
        search_in_object=Mock(),
        transfer_all_from=Mock(),
        was_server_lag_last_open=False,
    )
    inventory.detect_lag_long_process.return_value.__enter__ = Mock()
    inventory.detect_lag_long_process.return_value.__exit__ = Mock(return_value=False)
    template = types.SimpleNamespace(
        check_template=Mock(return_value=True),
        template_await_true=Mock(return_value=True),
    )
    utils = types.SimpleNamespace(
        press_key=Mock(),
        turn_down=Mock(),
        turn_up=Mock(),
        zero=Mock(),
        zero_center=Mock(),
    )
    logs = types.ModuleType("source.logs.gachalogs")
    logs.logger = Mock()
    logs_package = types.ModuleType("source.logs")
    logs_package.gachalogs = logs
    utility = types.ModuleType("source.utility")
    utility.local_player = types.SimpleNamespace()
    utility.screen = types.SimpleNamespace()
    utility.template = template
    utility.utils = utils
    utility.utils_simple = types.SimpleNamespace(
        get_default_clock=Mock(return_value=Mock(return_value=False))
    )
    utility.variables = types.SimpleNamespace()
    utility.windows = types.SimpleNamespace()
    captures = {}
    debug_screenshots = types.ModuleType("source.utility.debug_screenshots")
    debug_screenshots.CAPTURE_IGUANADON_SEED = False

    def capture_for(category, active=False, delay=0.0):
        captures[category] = Mock()
        return captures[category]

    debug_screenshots.capture_for = capture_for
    utility.debug_screenshots = debug_screenshots
    teleporter = types.SimpleNamespace(teleport_not_default=Mock())
    structures = types.ModuleType("source.ASA.strucutres")
    structures.inventory = inventory
    structures.teleporter = teleporter
    player_inventory = types.SimpleNamespace(
        close=Mock(),
        drop_all_inv=Mock(),
        implant_eat=Mock(),
        is_can_drop=Mock(return_value=False),
        search_in_inventory=Mock(),
        transfer_all_inventory=Mock(),
    )
    player_state = types.SimpleNamespace(check_state=Mock())
    player = types.ModuleType("source.ASA.player")
    player.player_inventory = player_inventory
    player.player_state = player_state
    modules = {
        "settings": types.SimpleNamespace(
            berry_type="mejoberry",
            external_berry=external_berry,
            iguanadon_seed_throw_amount=0,
            ping=1,
        ),
        "source.gacha_bot": types.SimpleNamespace(
            stations=types.SimpleNamespace(did_collect_tek_troughs=False)
        ),
        "source.gacha_bot.config": types.SimpleNamespace(
            iguanadon_attempts=3,
            tek_trough_attempts=3,
        ),
        "source.gacha_bot.stations": types.SimpleNamespace(
            did_collect_tek_troughs=False
        ),
        "source.logs": logs_package,
        "source.logs.gachalogs": logs,
        "source.utility": utility,
        "source.utility.debug_screenshots": debug_screenshots,
        "source.ASA.strucutres": structures,
        "source.ASA.player": player,
    }
    spec = importlib.util.spec_from_file_location(
        "iguanadon_under_test", ROOT / "source" / "gacha_bot" / "iguanadon.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    module.time.sleep = Mock()
    module.debug_captures = captures
    return (
        module,
        inventory,
        template,
        utils,
        teleporter,
        player_inventory,
        player_state,
        logs.logger,
    )


def load_stations_module():
    from source.utility import utils_simple

    logs = types.ModuleType("source.logs.gachalogs")
    logs.logger = Mock()
    teleporter = types.SimpleNamespace(teleport_not_default=Mock())
    structures = types.ModuleType("source.ASA.strucutres")
    structures.bed = types.SimpleNamespace()
    structures.inventory = types.SimpleNamespace()
    structures.teleporter = teleporter
    player = types.ModuleType("source.ASA.player")
    player.console = types.SimpleNamespace()
    player.player_inventory = types.SimpleNamespace()
    player.player_state = types.SimpleNamespace(check_state=Mock())
    player.tribelog = types.SimpleNamespace()
    utility = types.ModuleType("source.utility")
    utility.local_player = types.SimpleNamespace()
    utility.screen = types.SimpleNamespace()
    utility.template = types.SimpleNamespace(check_template=Mock(return_value=False))
    utility.utils = types.SimpleNamespace(zero_center=Mock())
    utility.utils_simple = utils_simple
    utility.variables = types.SimpleNamespace()
    utility.windows = types.SimpleNamespace()
    iguanadon = types.SimpleNamespace(berry_station=Mock(), iguanadon=Mock())
    gacha = types.SimpleNamespace(
        collection=Mock(), drop_off_nocrop=Mock()
    )
    bot_modules = types.ModuleType("source.gacha_bot")
    bot_modules.config = types.SimpleNamespace()
    bot_modules.deposit = types.SimpleNamespace(deposit_all=Mock())
    bot_modules.gacha = gacha
    bot_modules.iguanadon = iguanadon
    bot_modules.pego = types.SimpleNamespace(pego_pickup=Mock())
    bot_modules.render = types.SimpleNamespace()
    modules = {
        "settings": types.SimpleNamespace(
            berry_station="BERRIES",
            iguanadon="IGUANADON",
            external_berry=False,
            time_to_reberry=0.01,
            gacha_feed_delay=123,
            gacha_collect_feed_delay=456,
        ),
        "source.logs.gachalogs": logs,
        "source.utility": utility,
        "source.ASA.strucutres": structures,
        "source.ASA.player": player,
        "source.gacha_bot": bot_modules,
        "source.gacha_bot.config": bot_modules.config,
        "source.gacha_bot.deposit": bot_modules.deposit,
        "source.gacha_bot.gacha": gacha,
        "source.gacha_bot.iguanadon": iguanadon,
        "source.gacha_bot.pego": bot_modules.pego,
        "source.gacha_bot.render": bot_modules.render,
    }
    spec = importlib.util.spec_from_file_location(
        "stations_under_test", ROOT / "source" / "gacha_bot" / "stations.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module, teleporter, iguanadon


class BerryCollectionGuardTests(unittest.TestCase):
    def setUp(self):
        self.original_attempts = config.tek_trough_attempts
        (
            self.iguanadon,
            self.inventory,
            self.template,
            self.utils,
            self.teleporter,
            self.player_inventory,
            self.player_state,
            self.logger,
        ) = load_iguanadon_module()
        self.teleporter_name = "BERRIES"

    def tearDown(self):
        config.tek_trough_attempts = self.original_attempts

    def test_valid_first_trough_transfers_then_collects_second_without_revalidation(
        self,
    ):
        self.iguanadon.berry_station(self.teleporter_name)

        self.assertEqual(self.inventory.open.call_count, 2)
        self.assertEqual(self.inventory.transfer_all_from.call_count, 2)
        self.assertEqual(self.inventory.close.call_count, 2)
        self.assertEqual(self.template.check_template.call_count, 2)
        self.assertEqual(
            self.utils.turn_down.call_args_list,
            [call(0), call(50)],
        )

    def test_wrong_first_inventory_closes_teleports_and_retries_without_withdrawing(
        self,
    ):
        self.template.check_template.side_effect = [False, True]

        self.iguanadon.berry_collection(self.teleporter_name, 0)

        self.assertEqual(self.inventory.transfer_all_from.call_count, 1)
        self.assertEqual(self.inventory.close.call_count, 1)
        self.teleporter.teleport_not_default.assert_called_once_with(
            self.teleporter_name
        )
        self.player_inventory.implant_eat.assert_not_called()

    def test_three_wrong_opens_suicide_respawn_and_restart_collection(self):
        deadline = Mock(side_effect=[False, True, False, True])
        deadline.reset = Mock()
        self.iguanadon.utils_simple.get_default_clock.return_value = deadline
        self.template.check_template.side_effect = [False, False, False, True]

        self.iguanadon.berry_collection(self.teleporter_name, 0)

        self.assertEqual(self.inventory.transfer_all_from.call_count, 1)
        self.assertEqual(self.inventory.close.call_count, 1)
        self.assertEqual(
            self.teleporter.teleport_not_default.call_args_list,
            [
                call(self.teleporter_name),
                call(self.teleporter_name),
                call(self.teleporter_name),
            ],
        )
        self.player_inventory.implant_eat.assert_called_once_with()
        self.player_state.check_state.assert_called_once_with()
        self.logger.critical.assert_called_once()

    def test_external_recovery_waits_for_station_to_render(self):
        (
            iguanadon,
            _,
            template,
            _,
            teleporter,
            _,
            _,
            _,
        ) = load_iguanadon_module(external_berry=True)
        template.check_template.side_effect = [False, True]

        iguanadon.berry_collection(self.teleporter_name, 0)

        teleporter.teleport_not_default.assert_called_once_with(self.teleporter_name)
        iguanadon.time.sleep.assert_any_call(20)

    def test_seed_capture_happens_after_withdrawing_seeds(self):
        self.iguanadon.g_teleporter_name = "IGUANADON"

        self.iguanadon.seed(2)

        self.iguanadon.debug_captures[
            "iguanadon_seed_withdraw"
        ].assert_called_once_with("seed_2")
        self.assertGreaterEqual(self.inventory.close.call_count, 1)

    def test_seed_requires_initialized_teleport_name(self):
        self.iguanadon.g_teleporter_name = None

        with self.assertRaisesRegex(RuntimeError, "teleport name is not initialized"):
            self.iguanadon.seed(2)

    def test_seed_two_cleanup_drop_when_troughs_collected_and_inventory_can_drop(self):
        self.iguanadon.g_teleporter_name = "IGUANADON"
        self.iguanadon.stations.did_collect_tek_troughs = True
        self.player_inventory.is_can_drop.return_value = True

        self.iguanadon.seed(2)

        self.player_inventory.drop_all_inv.assert_called_once_with()

    def test_seed_one_does_not_run_lag_guard_or_cleanup_drop(self):
        self.iguanadon.g_teleporter_name = "IGUANADON"

        self.iguanadon.seed(1)

        self.player_inventory.drop_all_inv.assert_not_called()


class BerryStationTaskGuardTests(unittest.TestCase):
    def test_station_passes_berry_name_to_collection(self):
        stations, teleporter, iguanadon = load_stations_module()

        stations.gacha_station("gacha1", "GACHA1", "left").execute()

        iguanadon.berry_station.assert_called_once_with("BERRIES")
        self.assertEqual(
            teleporter.teleport_not_default.call_args_list[0], call("BERRIES")
        )

    def test_normal_gacha_requeue_delay_uses_setting(self):
        stations, _, _ = load_stations_module()

        self.assertEqual(
            stations.gacha_station("gacha1", "GACHA1", "left").get_requeue_delay(),
            123,
        )

    def test_pego_uses_dedi_routes_for_crystal_deposit(self):
        stations, teleporter, _ = load_stations_module()
        stations.template.check_template.return_value = True

        stations.pego_station("pego1", "PEGO", 100).execute()

        teleporter.teleport_not_default.assert_called_once_with("PEGO")
        stations.deposit.deposit_all.assert_called_once_with(None)


if __name__ == "__main__":
    unittest.main()
