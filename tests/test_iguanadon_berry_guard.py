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
        is_open=Mock(return_value=True),
        open=Mock(),
        transfer_all_from=Mock(),
    )
    template = types.SimpleNamespace(
        check_template=Mock(),
        template_await_true=Mock(return_value=True),
    )
    utils = types.SimpleNamespace(turn_down=Mock(), turn_up=Mock())
    logs = types.ModuleType("source.logs.gachalogs")
    logs.logger = Mock()
    utility = types.ModuleType("source.utility")
    utility.local_player = types.SimpleNamespace()
    utility.screen = types.SimpleNamespace()
    utility.template = template
    utility.utils = utils
    utility.variables = types.SimpleNamespace()
    utility.windows = types.SimpleNamespace()
    teleporter = types.SimpleNamespace(teleport_not_default=Mock())
    structures = types.ModuleType("source.ASA.strucutres")
    structures.inventory = inventory
    structures.teleporter = teleporter
    stations = types.ModuleType("source.ASA.stations")
    stations.custom_stations = types.SimpleNamespace()
    player_inventory = types.SimpleNamespace(implant_eat=Mock())
    player_state = types.SimpleNamespace(check_state=Mock())
    player = types.ModuleType("source.ASA.player")
    player.player_inventory = player_inventory
    player.player_state = player_state
    modules = {
        "settings": types.SimpleNamespace(
            berry_type="mejoberry", external_berry=external_berry, lag_offset=1
        ),
        "source.logs.gachalogs": logs,
        "source.utility": utility,
        "source.ASA.strucutres": structures,
        "source.ASA.stations": stations,
        "source.ASA.player": player,
    }
    spec = importlib.util.spec_from_file_location(
        "iguanadon_under_test", ROOT / "source" / "gacha_bot" / "iguanadon.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    module.time.sleep = Mock()
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
    logs = types.ModuleType("source.logs.gachalogs")
    logs.logger = Mock()
    teleporter = types.SimpleNamespace(teleport_not_default=Mock())
    structures = types.ModuleType("source.ASA.strucutres")
    structures.bed = types.SimpleNamespace()
    structures.inventory = types.SimpleNamespace()
    structures.teleporter = teleporter
    metadata = {}

    def get_station_metadata(name):
        metadata.setdefault(name, types.SimpleNamespace(name=name))
        return metadata[name]

    custom_stations = types.SimpleNamespace(
        get_station_metadata=Mock(side_effect=get_station_metadata)
    )
    asa_stations = types.ModuleType("source.ASA.stations")
    asa_stations.custom_stations = custom_stations
    player = types.ModuleType("source.ASA.player")
    player.console = types.SimpleNamespace()
    player.player_inventory = types.SimpleNamespace()
    player.player_state = types.SimpleNamespace(check_state=Mock())
    player.tribelog = types.SimpleNamespace()
    utility = types.ModuleType("source.utility")
    utility.local_player = types.SimpleNamespace()
    utility.screen = types.SimpleNamespace()
    utility.template = types.SimpleNamespace(check_template=Mock(return_value=False))
    utility.utils = types.SimpleNamespace()
    utility.variables = types.SimpleNamespace()
    utility.windows = types.SimpleNamespace()
    iguanadon = types.SimpleNamespace(berry_station=Mock(), iguanadon=Mock())
    gacha = types.SimpleNamespace(drop_off_nocrop=Mock(), drop_off=Mock())
    bot_modules = types.ModuleType("source.gacha_bot")
    bot_modules.config = types.SimpleNamespace(time_to_reberry=0.01)
    bot_modules.deposit = types.SimpleNamespace()
    bot_modules.gacha = gacha
    bot_modules.iguanadon = iguanadon
    bot_modules.pego = types.SimpleNamespace()
    bot_modules.render = types.SimpleNamespace()
    modules = {
        "settings": types.SimpleNamespace(
            berry_station="BERRIES",
            iguanadon="IGUANADON",
            y_trap_bot=False,
            external_berry=False,
            seeds_230=False,
            side_crop_plot=False,
        ),
        "source.logs.gachalogs": logs,
        "source.utility": utility,
        "source.ASA.strucutres": structures,
        "source.ASA.stations": asa_stations,
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
    return module, teleporter, iguanadon, metadata


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
        self.metadata = types.SimpleNamespace(name="BERRIES", yaw=12)

    def tearDown(self):
        config.tek_trough_attempts = self.original_attempts

    def test_valid_first_trough_transfers_then_collects_second_without_revalidation(self):
        self.iguanadon.berry_station(self.metadata)

        self.assertEqual(self.inventory.open.call_count, 2)
        self.assertEqual(self.inventory.transfer_all_from.call_count, 2)
        self.assertEqual(self.inventory.close.call_count, 2)
        self.template.template_await_true.assert_called_once_with(
            self.template.check_template, 1, "tek_trough", 0.7
        )
        self.utils.turn_down.assert_called_once_with(50)
        self.utils.turn_up.assert_called_once_with(50)

    def test_wrong_first_inventory_closes_teleports_and_retries_without_withdrawing(self):
        self.template.template_await_true.side_effect = [False, True]

        self.iguanadon._collect_first_trough(self.metadata)

        self.assertEqual(self.inventory.transfer_all_from.call_count, 1)
        self.assertEqual(self.inventory.close.call_count, 2)
        self.teleporter.teleport_not_default.assert_called_once_with(self.metadata)
        self.player_inventory.implant_eat.assert_not_called()

    def test_three_wrong_opens_suicide_respawn_and_restart_collection(self):
        self.template.template_await_true.side_effect = [False, False, False, True]

        self.iguanadon._collect_first_trough(self.metadata)

        self.assertEqual(self.inventory.transfer_all_from.call_count, 1)
        self.assertEqual(self.inventory.close.call_count, 4)
        self.assertEqual(
            self.teleporter.teleport_not_default.call_args_list,
            [call(self.metadata), call(self.metadata), call(self.metadata)],
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
        template.template_await_true.side_effect = [False, True]

        iguanadon._collect_first_trough(self.metadata)

        teleporter.teleport_not_default.assert_called_once_with(self.metadata)
        iguanadon.time.sleep.assert_any_call(20)


class BerryStationTaskGuardTests(unittest.TestCase):
    def test_station_passes_berry_metadata_to_collection(self):
        stations, teleporter, iguanadon, metadata = load_stations_module()

        stations.gacha_station("gacha1", "GACHA1", "left").execute()

        iguanadon.berry_station.assert_called_once_with(metadata["BERRIES"])
        self.assertEqual(
            teleporter.teleport_not_default.call_args_list[0], call(metadata["BERRIES"])
        )


if __name__ == "__main__":
    unittest.main()
