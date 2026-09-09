import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, call, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QGridLayout, QLabel, QLineEdit, QPushButton, QWidget

from source.gacha_bot.craft_config import default_craft_route, load_craft_config, normalize_craft_config, valid_craft_route
from source.gacha_bot.deposit_config import default_deposit_config, default_dedi_item, default_general_route, deposit_destination_options, load_deposit_config, normalize_deposit_config, save_deposit_config
from source.launcher.config.station_config import default_gacha_collect_entry, load_gacha_collect_config, save_gacha_collect_config
from source.launcher.config.template_settings import build_template, convert_craft_yaw, convert_deposit_yaw, normalize_template
from source.launcher.pages.craft import CraftPagesMixin
from source.launcher.pages.dedi import DediPagesMixin
from source.launcher.pages.gacha import GachaPagesMixin
from source.launcher.pages import LauncherPagesMixin
from source.launcher.config.template_settings import TemplateCatalog
import test_template_ui_behavior
from test_deposit_guard import load_deposit_module
from test_iguanadon_berry_guard import load_stations_module
from test_template_settings import template_document


def current_configs():
    """Provide source stations and multi-crafter routes in the current format."""
    dedis = {"depositCrystalData": [], "depositGrindableData": [], "depositGeneralData": []}
    craft = {"generalCraftData": []}
    for name in ("FIRST", "SECOND"):
        dedis["depositGeneralData"].append({
            "teleport": name, "check_on_every_dedi": 3,
            "dedi": {"items": [{"location": {"yaw": 20.0, "pitch": 1.0}, "crouched": False}]},
        })
        craft["generalCraftData"].append({
            "teleport": name, "check_on_every_dedi": 3,
            "crafters": [{"item": "polymer", "location": {"yaw": 10.0, "pitch": -5.0}, "crouched": True}],
            "dedi": {"items": [{"location": {"yaw": 30.0, "pitch": 2.0}, "crouched": True}]},
        })
    return dedis, craft


class CraftConfigTests(unittest.TestCase):
    def test_current_template_and_yaw_round_trip(self):
        document = template_document()
        document["data"]["dedis"], document["data"]["craft"] = current_configs()
        document["data"]["gacha_collect"] = [{"item": "paste", "dedi_teleport": "SECOND"}]
        template, _ = normalize_template(document)
        data = template["data"]
        restored = convert_craft_yaw(data["craft"], 45.0, False)
        self.assertEqual(restored["generalCraftData"][0]["crafters"][0]["location"], {"yaw": 55.0, "pitch": -5.0})
        settings = {**data["settings"], "station_yaw": 45.0}
        exported = build_template("Roundtrip", settings, convert_deposit_yaw(data["dedis"], 45.0, False), data["gacha"], data["pego"], data["gacha_collect"], restored)
        self.assertEqual(exported["data"], data)
        self.assertEqual(normalize_template(exported)[0], exported)


class CraftRuntimeTests(unittest.TestCase):
    def test_scheduler_adds_each_valid_crafter_without_collection_entries(self):
        import source.gacha_bot

        stations, _, _ = load_stations_module()
        stations.settings.bed_spawn = "RENDER"
        stations.settings.craft_delay = 321
        spec = importlib.util.spec_from_file_location("craft_scheduler_under_test", Path(__file__).resolve().parents[1] / "task_manager.py")
        manager = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"source.gacha_bot.stations": stations}), patch.object(source.gacha_bot, "stations", stations, create=True):
            spec.loader.exec_module(manager)
        craft = current_configs()[1]
        craft["generalCraftData"].append(default_craft_route())
        with patch.object(manager, "load_resolution_data", return_value=[]), patch.object(manager, "load_craft_config", return_value=craft), patch.object(manager, "task_scheduler") as scheduler:
            manager.prepare()
        tasks = [args.args[0] for args in scheduler.return_value.add_task.call_args_list]
        self.assertEqual(len(tasks), 3)  # Both crafters, plus render.
        self.assertEqual([task.route["teleport"] for task in tasks[:2]], ["FIRST", "SECOND"])
        self.assertEqual([task.get_requeue_delay() for task in tasks[:2]], [321, 321])
        self.assertEqual([task.get_priority_level() for task in tasks[:2]], [5, 5])
        stations.deposit.craft = Mock()
        for task in tasks[:2]:
            task.execute()
        self.assertEqual(stations.deposit.craft.call_args_list, [call(route) for route in craft["generalCraftData"][:2]])

    def test_invalid_destination_skips_before_feeding(self):
        stations, teleporter, iguanadon = load_stations_module()
        stations.deposit.resolve_collection_destination = Mock(return_value=None)
        stations.deposit.deposit_collection = Mock()
        stations.gacha_collect_station("one", "PAIR", "left", "paste", "deleted").execute()
        stations.deposit.resolve_collection_destination.assert_called_once_with("deleted")
        teleporter.teleport_not_default.assert_not_called()
        iguanadon.iguanadon.assert_not_called()
        stations.gacha.drop_off_nocrop.assert_not_called()
        stations.deposit.deposit_collection.assert_not_called()

    def test_destination_resolution_and_deposit_never_processes_other_structures(self):
        deposit, *_ = load_deposit_module()
        config = default_deposit_config()
        general = default_general_route()
        config["depositGeneralData"] = [general]
        routes = [config["depositCrystalData"][0], config["depositGrindableData"][0], general]
        for index, route in enumerate(routes):
            route["teleport"] = f"STATION{index}"
            route["dedi"]["items"] = [default_dedi_item()]
        deposit.load_deposit_config = Mock(return_value=config)
        deposit._teleport_to_route = Mock()
        deposit.utils.get_yaw_pitch = Mock()
        deposit.process_dedi_list_route = Mock(return_value=True)
        deposit._process_crystal_routes = Mock()
        deposit._process_grindable_routes = Mock()
        for route in routes:
            self.assertIs(deposit.resolve_collection_destination(route["teleport"]), route)
            self.assertTrue(deposit.deposit_collection(route))
            deposit._teleport_to_route.assert_called_with(route)
        deposit._process_crystal_routes.assert_not_called()
        deposit._process_grindable_routes.assert_not_called()
        self.assertIsNone(deposit.resolve_collection_destination("deleted"))
        general["teleport"] = " "
        self.assertIsNone(deposit.resolve_collection_destination("STATION2"))
        general["teleport"] = "STATION"
        general["dedi"]["items"] = []
        self.assertIsNone(deposit.resolve_collection_destination("STATION2"))

    def test_crafting_preserves_sequence_and_quantity(self):
        deposit, *_ = load_deposit_module()
        route = current_configs()[1]["generalCraftData"][0]
        deposit._teleport_to_route = Mock()
        deposit.utils.get_yaw_pitch = Mock()
        deposit.open_crafter = Mock(return_value=True)
        deposit.inventory.craft_item = Mock()
        deposit.inventory.wait_clear_search = Mock()
        deposit.player_inventory.g_last_check_can_drop = True
        deposit._deposit_collect_items = Mock(return_value=True)
        events = Mock()
        events.attach_mock(deposit._teleport_to_route, "teleport")
        events.attach_mock(deposit.open_crafter, "open")
        events.attach_mock(deposit.inventory.craft_item, "craft")
        events.attach_mock(deposit.inventory.transfer_all_from, "withdraw")
        events.attach_mock(deposit._deposit_collect_items, "deposit")
        with patch.object(deposit.time, "sleep"):
            self.assertTrue(deposit.craft(route))
        self.assertEqual(events.mock_calls, [call.teleport(route), call.open(route["crafters"][0]), call.craft("polymer", 12), call.withdraw(), call.open(route["crafters"][0]), call.deposit(route, route["dedi"]["items"], "crafted-item")])


class RouteEditor(DediPagesMixin, CraftPagesMixin, GachaPagesMixin, QWidget):
    def __init__(self):
        """Provide real route widgets with inert launcher services for UI tests."""
        super().__init__()
        self.settings_form_layout = QGridLayout(self)
        self.deposit_config, self.craft_config = current_configs()
        self._button = lambda text, style: QPushButton(text)
        self._icon_button = lambda icon, text, style: QPushButton(text)
        self._add_template_selector = Mock(return_value=("local", "", ""))
        self._style_template_collection = Mock()
        self._setting_field = lambda key: QLineEdit("600")
        self._setting_field_container = lambda widget, *args: widget
        self._render_settings_group = Mock()
        self.open_deposit_helper = Mock()
        self.append_log = Mock()
        self.dialog = Mock()


class CraftUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_craft_page_edits_only_craft_config_without_active_switch(self):
        editor = RouteEditor()
        editor._render_craft_group()
        labels = [label.text() for label in editor.findChildren(QLabel)]
        self.assertTrue(any("GENERAL CRAFT" in label for label in labels))
        self.assertIn("Craft delay (s)", labels)
        self.assertFalse(any(button.text() == "ACTIVE" for button in editor.findChildren(QPushButton)))
        with patch("source.launcher.pages.craft.save_craft_config") as save_craft, patch("source.launcher.pages.dedi.save_deposit_config") as save_deposit:
            field = next(field for field in editor.findChildren(QLineEdit) if field.text() == "polymer")
            field.setText("element")
            field.editingFinished.emit()
            self.assertEqual(editor.craft_config["generalCraftData"][0]["crafters"][0]["item"], "element")
            save_craft.assert_called_once()
            save_deposit.assert_not_called()
            editor.update_deposit_float(editor.craft_config["generalCraftData"][0]["crafters"][0]["location"], "yaw", QLineEdit("125"))
            self.assertEqual(save_craft.call_count, 2)
            editor.update_deposit_text(editor.deposit_config["depositGeneralData"][0], "teleport", QLineEdit("RENAMED"))
            save_deposit.assert_called_once()
        editor.close()

    def test_craft_template_apply_and_failed_save_roll_back_independently(self):
        document = template_document()
        document["data"]["dedis"], document["data"]["craft"] = current_configs()
        template, _ = normalize_template(document)
        launcher = test_template_ui_behavior.TemplateUiBehaviorTests().launcher(TemplateCatalog({"craft.json": template}, {}, {}))
        launcher.craft_config = {"generalCraftData": [default_craft_route()]}
        launcher.settings["station_yaw"] = 45.0
        original = copy.deepcopy(launcher.craft_config)
        launcher._rollback_template_group = MethodType(LauncherPagesMixin._rollback_template_group, launcher)
        with patch("source.launcher.pages.settings.save_craft_config", side_effect=copy.deepcopy) as craft_save, patch("source.launcher.pages.settings.save_deposit_config") as deposit_save, patch("source.launcher.pages.settings.save_settings", side_effect=[OSError("disk unavailable"), copy.deepcopy(launcher.settings)]):
            self.assertFalse(launcher.change_template_group("CRAFT", "craft.json"))
            self.assertEqual(craft_save.call_args_list[-1], call(original))
            self.assertEqual(launcher.craft_config, original)
            deposit_save.assert_not_called()
        with patch("source.launcher.pages.settings.save_craft_config", side_effect=copy.deepcopy), patch("source.launcher.pages.settings.save_settings", side_effect=copy.deepcopy):
            self.assertTrue(launcher.change_template_group("CRAFT", "craft.json"))
        self.assertEqual(launcher.craft_config["generalCraftData"][0]["crafters"][0]["location"]["yaw"], 55.0)
        self.assertEqual(launcher.settings["craft_template"], "craft.json")
        self.assertEqual(launcher.settings["craft_delay_template"], "craft.json")
        self.assertEqual(launcher.settings["dedis_template"], "")

