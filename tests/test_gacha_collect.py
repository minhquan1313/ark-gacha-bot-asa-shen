import importlib.util
import sys
import unittest
from pathlib import Path

import source.gacha_bot
from unittest.mock import Mock, call, patch

from test_debug_screenshots import load_gacha_module
from test_iguanadon_berry_guard import load_iguanadon_module, load_stations_module


class CollectStationTests(unittest.TestCase):
    def test_each_entry_prepares_feeds_and_deposits_in_order(self):
        stations, teleporter, iguanadon = load_stations_module()
        stations.deposit.deposit_collection = Mock()
        stations.deposit.resolve_collection_destination = Mock(return_value={"id": "selected"})
        stations.settings.gacha_collect_feed_delay = 900
        events = Mock()
        events.attach_mock(stations.player_state.check_state, "check")
        events.attach_mock(teleporter.teleport_not_default, "teleport")
        events.attach_mock(iguanadon.berry_station, "berries")
        events.attach_mock(iguanadon.iguanadon, "seeds")
        events.attach_mock(stations.gacha.drop_off_nocrop, "feed")
        events.attach_mock(stations.deposit.deposit_collection, "deposit")
        with patch.object(stations.time, "time", return_value=100):
            for side in ("left", "right"):
                task = stations.gacha_collect_station(side, "PAIR", side, "stone")
                task.execute()
                self.assertEqual(task.name, f"C.{side}")
                self.assertEqual(task.get_priority_level(), 4)
                self.assertEqual(task.get_requeue_delay(), 900)
        self.assertEqual(events.mock_calls, [
            call.check(), call.teleport("BERRIES"), call.berries(),
            call.teleport("IGUANADON"), call.seeds(), call.teleport("PAIR"),
            call.feed("PAIR", "left", "stone"), call.deposit({"id": "selected"}),
            call.check(), call.teleport("IGUANADON"), call.seeds(),
            call.teleport("PAIR"), call.feed("PAIR", "right", "stone"), call.deposit({"id": "selected"}),
        ])
        self.assertFalse(stations.did_collect_tek_troughs)

    def test_missing_item_skips_entire_route(self):
        stations, teleporter, iguanadon = load_stations_module()
        stations.deposit.deposit_collection = Mock()
        stations.deposit.resolve_collection_destination = Mock(return_value={"id": "selected"})
        with patch.object(stations.logs.logger, "warning") as warning:
            stations.gacha_collect_station("one", "PAIR", "left", "").execute()
        teleporter.teleport_not_default.assert_not_called()
        iguanadon.iguanadon.assert_not_called()
        stations.deposit.deposit_collection.assert_not_called()
        warning.assert_called_once()

    def test_external_refill_reconnects_before_seeding(self):
        stations, _, iguanadon = load_stations_module()
        stations.settings.external_berry = True
        stations.settings.wait_structure_load = 20
        stations.settings.wait_reconnect = 60
        stations.console.console_write = Mock()
        events = Mock()
        events.attach_mock(stations.console.console_write, "console")
        events.attach_mock(iguanadon.iguanadon, "seeds")
        with patch.object(stations.time, "sleep") as sleep:
            stations.gacha_station("one", "PAIR", "left").execute()
        self.assertEqual(events.mock_calls, [call.console("reconnect"), call.seeds()])
        self.assertEqual(sleep.call_args_list, [call(20), call(60)])
        stations.gacha.drop_off_nocrop.assert_called_once_with("PAIR", "left")


class CollectInventoryTests(unittest.TestCase):
    def setUp(self):
        self.gacha, _, _, self.inventory = load_gacha_module()
        self.player = self.gacha.player_inventory
        self.player.wait_clear_search = Mock()
        self.gacha.open_gacha_inv = Mock()

    def test_collection_precedes_cleanup_even_during_lag_retry(self):
        self.inventory.was_server_lag_last_open = True
        events = Mock()
        for name in ("search_in_object", "transfer_all_from", "drop_all_obj"):
            events.attach_mock(getattr(self.inventory, name), name)
        self.gacha.drop_off_nocrop("PAIR", "right", "stone")
        cycle = [call.search_in_object("stone"), call.transfer_all_from(),
                 call.search_in_object(""), call.search_in_object("pell"),
                 call.transfer_all_from(), call.drop_all_obj()]
        self.assertEqual(events.mock_calls, cycle + cycle)
        self.assertEqual(self.player.search_in_inventory.call_args_list,
                         [call("seed"), call("pell"), call("")])
        self.player.wait_clear_search.assert_called_once()

    def test_collected_pellets_are_not_fed_back(self):
        self.gacha.drop_off_nocrop("PAIR", "left", "Snow Owl Pellet")
        self.assertEqual(self.player.search_in_inventory.call_args_list,
                         [call("seed"), call("")])
        self.player.transfer_all_inventory.assert_called_once()

    def test_collected_seeds_are_not_fed_back(self):
        self.gacha.drop_off_nocrop("PAIR", "left", "seed")
        self.assertEqual(self.player.search_in_inventory.call_args_list,
                         [call("pell"), call("")])

    def test_failed_open_does_not_collect_drop_or_feed(self):
        self.inventory.is_open.return_value = False
        self.gacha.drop_off_nocrop("PAIR", "left", "stone")
        self.inventory.transfer_all_from.assert_not_called()
        self.inventory.drop_all_obj.assert_not_called()
        self.player.transfer_all_inventory.assert_not_called()
        self.inventory.close.assert_called_once()

    def test_failed_reopen_does_not_feed(self):
        self.inventory.is_open.side_effect = [True, False]
        self.gacha.drop_off_nocrop("PAIR", "left", "stone")
        self.player.transfer_all_inventory.assert_not_called()

    def test_normal_feeding_keeps_unfiltered_transfer(self):
        self.gacha.drop_off_nocrop("PAIR", "left")
        self.player.search_in_inventory.assert_not_called()
        self.player.transfer_all_inventory.assert_called_once()
        self.inventory.search_in_object.assert_called_once_with("pell")


class CollectConfigurationTests(unittest.TestCase):
    def test_scheduler_keeps_shared_teleporter_entries_independent(self):
        stations, _, _ = load_stations_module()
        stations.settings.bed_spawn = "RENDER"
        spec = importlib.util.spec_from_file_location(
            "collect_task_manager_under_test",
            Path(__file__).resolve().parents[1] / "task_manager.py",
        )
        manager = importlib.util.module_from_spec(spec)
        with (
            patch.dict(sys.modules, {"source.gacha_bot.stations": stations}),
            patch.object(source.gacha_bot, "stations", stations, create=True),
        ):
            spec.loader.exec_module(manager)
        entries = [
            {"name": "one", "teleporter": "PAIR", "side": "left", "item": "stone"},
            {"name": "two", "teleporter": "PAIR", "side": "right", "item": "wood"},
            {"name": "invalid", "teleporter": "", "item": "stone"},
        ]
        with (
            patch.object(manager, "load_resolution_data", side_effect=[[], [], entries]),
            patch.object(manager, "task_scheduler") as scheduler,
            patch.object(manager, "load_craft_config", return_value={"generalCraftData": []}),
        ):
            manager.prepare()
        tasks = [args.args[0] for args in scheduler.return_value.add_task.call_args_list]
        self.assertEqual(len(tasks), 3)  # Two collect tasks plus render.
        self.assertEqual([task.name for task in tasks[:2]],
                         ["C.one", "C.two"])
        self.assertEqual([(task.teleporter_name, task.direction, task.item)
                          for task in tasks[:2]],
                         [("PAIR", "left", "stone"), ("PAIR", "right", "wood")])

    def test_seed_preparation_uses_configured_global_berry(self):
        iguanadon, _, _, _, _, player, _, _ = load_iguanadon_module()
        iguanadon.settings.berry_type = "narcoberry"
        iguanadon._seed_reset()
        player.search_in_inventory.assert_called_once_with("narcoberry")
