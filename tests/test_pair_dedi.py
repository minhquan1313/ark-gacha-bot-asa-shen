import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QWidget

from source.gacha_bot.craft_config import load_craft_config, normalize_craft_config
from source.gacha_bot.deposit_config import (
    collection_destination_error,
    default_deposit_config,
    default_dedi_item,
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
from test_craft_split import RouteEditor, current_configs
from test_deposit_guard import load_deposit_module
from test_iguanadon_berry_guard import load_stations_module
from test_template_settings import template_document


def pair_entries():
    """Build a pair sharing one destination in the flat collection JSON."""
    return [
        {**default_gacha_collect_entry(side, "PAIR", side, "paste"), "dedi_teleport": "FIRST"}
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


class PairDediUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def editor(self):
        """Prepare the real pair controls with inert save and navigation actions."""
        editor = RouteEditor()
        editor.gacha_config = []
        editor.gacha_collect_config = pair_entries()
        editor.gacha_group_expanded = {}
        editor.gacha_section_expanded = {"gacha": False, "collect": True}
        editor.save_gacha_collect_config = Mock(return_value=True)
        self.addCleanup(editor.close)
        return editor

    def selector(self, editor: RouteEditor):
        """Render the destination control against the current pair and stations."""
        wrapper = editor._collection_dedi_selector("PAIR", list(enumerate(editor.gacha_collect_config)))
        self.addCleanup(wrapper.close)
        return wrapper.findChild(QComboBox)

    def test_one_selector_per_pair_updates_both_entries(self):
        editor = self.editor()
        card = editor._gacha_group_card("PAIR", list(enumerate(editor.gacha_collect_config)), set(), "collect")
        self.addCleanup(card.close)
        selectors = card.findChildren(QWidget, "PairDediSelector")
        self.assertEqual(len(selectors), 1)
        combo = selectors[0].findChild(QComboBox)
        self.assertEqual(combo.objectName(), "HelperCombo")
        combo.setCurrentIndex(combo.findData("SECOND"))
        self.assertEqual([entry["dedi_teleport"] for entry in editor.gacha_collect_config], ["SECOND", "SECOND"])
        editor.save_gacha_collect_config.assert_called_once()

    def test_adding_second_gacha_inherits_destination_and_new_pair_is_unselected(self):
        editor = self.editor()
        editor.gacha_collect_config = editor.gacha_collect_config[:1]
        editor.add_gacha_to_group("PAIR", "collect")
        self.assertEqual([entry["dedi_teleport"] for entry in editor.gacha_collect_config], ["FIRST", "FIRST"])
        editor.add_gacha_group("collect")
        self.assertEqual([entry["dedi_teleport"] for entry in editor.gacha_collect_config[2:]], ["", ""])

    def test_empty_missing_duplicate_conflicting_and_unusable_selections_are_red(self):
        for state in ("empty", "renamed", "deleted", "duplicate", "conflict", "no_dedis"):
            with self.subTest(state=state):
                editor = self.editor()
                first = editor.deposit_config["depositGeneralData"][0]
                if state == "empty":
                    for entry in editor.gacha_collect_config:
                        entry["dedi_teleport"] = ""
                elif state == "renamed":
                    first["teleport"] = "RENAMED"
                elif state == "deleted":
                    del editor.deposit_config["depositGeneralData"][0]
                elif state == "duplicate":
                    editor.deposit_config["depositCrystalData"] = [copy.deepcopy(first)]
                elif state == "conflict":
                    editor.gacha_collect_config[1]["dedi_teleport"] = "SECOND"
                else:
                    first["dedi"]["items"] = []
                combo = self.selector(editor)
                self.assertEqual(combo.objectName(), "MissingTemplateSelector")
                self.assertTrue(combo.toolTip())
                combo.setCurrentIndex(combo.findData("SECOND"))
                self.assertEqual(combo.objectName(), "HelperCombo")
                self.assertEqual([entry["dedi_teleport"] for entry in editor.gacha_collect_config], ["SECOND", "SECOND"])

    def test_opening_gacha_reloads_stations_and_marks_renamed_destination(self):
        editor = self.editor()
        refreshed = copy.deepcopy(editor.deposit_config)
        refreshed["depositGeneralData"][0]["teleport"] = "RENAMED"
        with patch("source.launcher.pages.gacha.load_deposit_config", return_value=refreshed) as load:
            editor._render_gacha_group()
        load.assert_called_once_with(create_missing=False)
        combo = editor.findChild(QWidget, "PairDediSelector").findChild(QComboBox)
        self.assertEqual(combo.objectName(), "MissingTemplateSelector")
        self.assertEqual(combo.currentData(), "FIRST")

    def test_duplicate_dedi_rename_is_rejected_without_changing_pair_selections(self):
        editor = self.editor()
        first = editor.deposit_config["depositGeneralData"][0]
        with patch("source.launcher.pages.dedi.save_deposit_config", side_effect=ValueError("Dedi names must be unique")):
            field = QLineEdit("SECOND")
            editor.update_deposit_text(first, "teleport", field)
        self.assertEqual(first["teleport"], "FIRST")
        self.assertEqual(field.text(), "FIRST")
        self.assertEqual(editor.gacha_collect_config, pair_entries())


class PairSchedulerTests(unittest.TestCase):
    def test_conflicting_pair_enqueues_neither_collection_task(self):
        import source.gacha_bot

        stations, _, _ = load_stations_module()
        stations.settings.bed_spawn = "RENDER"
        spec = importlib.util.spec_from_file_location("pair_scheduler_under_test", Path(__file__).resolve().parents[1] / "task_manager.py")
        manager = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"source.gacha_bot.stations": stations}), patch.object(source.gacha_bot, "stations", stations, create=True):
            spec.loader.exec_module(manager)
        entries = pair_entries()
        entries[1]["dedi_teleport"] = "SECOND"
        with patch.object(manager, "load_resolution_data", side_effect=[[], [], entries]), patch.object(manager, "load_craft_config", return_value={"generalCraftData": []}), patch.object(manager, "task_scheduler") as scheduler:
            manager.prepare()
        self.assertEqual(scheduler.return_value.add_task.call_count, 1)
        self.assertIsInstance(scheduler.return_value.add_task.call_args.args[0], stations.render_station)
