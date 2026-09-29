import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from test_craft_split import current_configs
from test_deposit_guard import load_deposit_module
from test_iguanadon_berry_guard import load_stations_module
from test_template_settings import template_document

from source.gacha_bot.craft_config import load_craft_config, normalize_craft_config
from source.gacha_bot.deposit_config import (
    default_deposit_config,
    deposit_destination_options,
    load_deposit_config,
    save_deposit_config,
)
from source.launcher.config.station_config import (
    default_gacha_collect_entry,
    load_gacha_collect_config,
    save_gacha_collect_config,
)
from source.launcher.config.template_settings import normalize_template
from source.launcher.utils.settings_store import load_settings


def pair_entries():
    """Build a pair sharing one destination in the flat collection JSON."""
    return [
        {**default_gacha_collect_entry("PAIR", side, "paste"), "dedi_teleport": "FIRST"}
        for side in ("left", "right")
    ]


class TeleportConfigTests(unittest.TestCase):
    def test_duplicate_names_rejected_on_save_but_blank_drafts_allowed(self):
        config = default_deposit_config()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dedis.json"
            save_deposit_config(config, path)
            original = path.read_bytes()
            config["depositCrystalData"][0]["teleport"] = "DUPLICATE"
            config["depositGrindableData"][0]["teleport"] = "DUPLICATE"
            with self.assertRaisesRegex(ValueError, "must be unique"):
                save_deposit_config(config, path)
            self.assertEqual(path.read_bytes(), original)

    def test_all_loaders_preserve_existing_bytes_and_create_no_backups(self):
        dedis, craft = current_configs()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {"dedis.json": dedis, "craft.json": craft, "gacha_collect.json": pair_entries(), "settings.json": {"craft_delay": 300}}
            for name, data in files.items():
                (root / name).write_text(json.dumps(data), encoding="utf-8")
            originals = {path.name: path.read_bytes() for path in root.iterdir()}
            load_deposit_config(root / "dedis.json")
            load_craft_config(root / "craft.json")
            load_gacha_collect_config(root / "gacha_collect.json")
            load_settings(root / "settings.json")
            self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, originals)

    def test_current_flat_collection_round_trip_and_no_legacy_templates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gacha_collect.json"
            save_gacha_collect_config(pair_entries(), path)
            self.assertEqual(load_gacha_collect_config(path), pair_entries())
        document = template_document()
        for version in (1, 2, 3):
            document["version"] = version
            with self.assertRaisesRegex(ValueError, "Unsupported template version"):
                normalize_template(document)
        route = current_configs()[1]["generalCraftData"][0]
        route["crafter"] = route.pop("crafters")[0]
        with self.assertRaisesRegex(ValueError, "crafters must be an array"):
            normalize_craft_config({"generalCraftData": [route]})

    def test_exact_teleport_resolution_rejects_duplicate_empty_and_unusable_names(self):
        deposit, *_ = load_deposit_module()
        config, _ = current_configs()
        first = config["depositGeneralData"][0]
        deposit.load_deposit_config = Mock(return_value=config)
        self.assertIs(deposit.resolve_collection_destination("FIRST"), first)
        for name in ("", "first", " FIRST", "deleted"):
            self.assertIsNone(deposit.resolve_collection_destination(name))
        config["depositCrystalData"] = [copy.deepcopy(first)]
        self.assertIsNone(deposit.resolve_collection_destination("FIRST"))
        self.assertEqual(deposit_destination_options(config), ["FIRST", "SECOND"])
        config["depositCrystalData"] = []
        first["dedi"]["items"] = []
        self.assertIsNone(deposit.resolve_collection_destination("FIRST"))


class PairSchedulerTests(unittest.TestCase):
    def test_independent_destinations_enqueue_both_collection_tasks(self):
        import source.gacha_bot

        stations, _, _ = load_stations_module()
        stations.settings.bed_spawn = "RENDER"
        spec = importlib.util.spec_from_file_location("pair_scheduler_under_test", Path(__file__).resolve().parents[1] / "task_manager.py")
        manager = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"source.gacha_bot.stations": stations}), patch.object(source.gacha_bot, "stations", stations, create=True):
            spec.loader.exec_module(manager)
        entries = pair_entries()
        entries[1]["dedi_teleport"] = "SECOND"
        with patch.object(manager, "load_resolution_data", side_effect=[[], [{"name": "unfinished", "teleporter": "", "side": "left"}], entries + [{"name": "unfinished collect", "teleporter": "", "side": "left"}]]), patch.object(manager, "load_craft_config", return_value={"generalCraftData": []}), patch.object(manager, "task_scheduler") as scheduler:
            manager.prepare()
        tasks = [call.args[0] for call in scheduler.return_value.add_task.call_args_list]
        self.assertEqual(len(tasks), 3)
        self.assertEqual([task.dedi_teleport for task in tasks[:2]], ["FIRST", "SECOND"])
        self.assertIsInstance(tasks[-1], stations.render_station)
