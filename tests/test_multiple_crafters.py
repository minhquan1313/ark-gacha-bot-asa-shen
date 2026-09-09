import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from PySide6.QtWidgets import QApplication, QLineEdit

from source.gacha_bot.craft_config import (
    default_crafter,
    load_craft_config,
    normalize_craft_config,
    valid_craft_route,
)
from source.launcher.config.template_settings import convert_craft_yaw, normalize_template
from source.launcher.deposit_route_helper import DepositRouteHelper
from test_craft_split import RouteEditor, current_configs
from test_deposit_guard import load_deposit_module
from test_template_settings import template_document


def single_config():
    """Build a current-format station containing one crafter."""
    config = current_configs()[1]
    config["generalCraftData"] = config["generalCraftData"][:1]
    return config


class MultipleCrafterConfigTests(unittest.TestCase):
    def test_current_load_preserves_bytes_without_creating_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "craft.json"
            config = single_config()
            path.write_text(json.dumps(config), encoding="utf-8")
            original = path.read_bytes()
            self.assertEqual(load_craft_config(path), config)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_empty_or_incomplete_crafter_lists_are_not_scheduled(self):
        raw = single_config()
        route = raw["generalCraftData"][0]
        crafter = route["crafters"][0]
        route["crafters"] = []
        self.assertFalse(valid_craft_route(normalize_craft_config(raw)["generalCraftData"][0]))
        route["crafters"] = [default_crafter(), crafter]
        self.assertTrue(valid_craft_route(normalize_craft_config(raw)["generalCraftData"][0]))
        route["crafters"] = {}
        with self.assertRaisesRegex(ValueError, "crafters must be an array"):
            normalize_craft_config(raw)

    def test_current_template_and_all_crafter_yaws_round_trip(self):
        document = template_document()
        document["data"]["craft"] = single_config()
        upgraded, _ = normalize_template(document)
        self.assertEqual(upgraded["version"], 4)
        config = upgraded["data"]["craft"]
        route = config["generalCraftData"][0]
        route["crafters"].append({"location": {"yaw": 170.0, "pitch": -30.0}, "crouched": False, "item": "element"})
        local = convert_craft_yaw(config, 45.0, False)
        self.assertEqual([crafter["location"]["yaw"] for crafter in local["generalCraftData"][0]["crafters"]], [55.0, -145.0])
        self.assertEqual(convert_craft_yaw(local, 45.0, True), config)
        self.assertEqual(normalize_template(upgraded)[0], upgraded)


class MultipleCrafterRuntimeTests(unittest.TestCase):
    def run_crafters(self, deposit_results: list):
        """Run a station with two configured crafters and one incomplete editor row."""
        deposit, *_ = load_deposit_module()
        route = normalize_craft_config(single_config())["generalCraftData"][0]
        second = {"location": {"yaw": 80.0, "pitch": -10.0}, "crouched": False, "item": "element"}
        route["crafters"] += [default_crafter(), second]
        events = Mock()
        deposit._teleport_to_route = events.teleport
        deposit._turn_to_object = events.aim
        deposit.utils.get_yaw_pitch = Mock()
        deposit.open_crafter = Mock(return_value=True)
        deposit.inventory.craft_item = events.craft
        deposit.inventory.wait_clear_search = Mock()
        deposit.player_inventory.g_last_check_can_drop = True
        deposit._deposit_collect_items = events.deposit
        events.deposit.side_effect = deposit_results
        with patch.object(deposit.time, "sleep"):
            result = deposit.craft(route)
        return result, route, events, deposit

    def test_one_teleport_and_each_crafter_deposits_before_next_crafter(self):
        result, route, events, deposit = self.run_crafters([True, True])
        self.assertTrue(result)
        self.assertEqual(events.mock_calls, [
            call.teleport(route),
            call.aim(route["crafters"][0]), call.craft("polymer", 12),
            call.deposit(route, route["dedi"]["items"], "crafted-item"),
            call.aim(route["crafters"][2]), call.craft("element", 12),
            call.deposit(route, route["dedi"]["items"], "crafted-item"),
        ])
        self.assertEqual(deposit.inventory.transfer_all_from.call_count, 2)

    def test_failed_output_deposit_stops_before_collecting_more_output(self):
        result, _, events, _ = self.run_crafters([False])
        self.assertFalse(result)
        events.craft.assert_called_once_with("polymer", 12)
        events.teleport.assert_called_once()


class MultipleCrafterUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_launcher_add_edit_and_remove_preserve_other_crafters_and_dedis(self):
        editor = RouteEditor()
        editor.save_craft_routes = Mock(return_value=True)
        route = editor.craft_config["generalCraftData"][0]
        original = copy.deepcopy(route)
        editor.add_crafter(0)
        editor._render_craft_group()
        field = next(field for field in editor.findChildren(QLineEdit) if field.text() == "")
        field.setText("element")
        field.editingFinished.emit()
        self.assertEqual(route["crafters"][1]["item"], "element")
        editor.remove_crafter(0, 0)
        self.assertEqual([crafter["item"] for crafter in route["crafters"]], ["element"])
        self.assertEqual(route["dedi"], original["dedi"])
        self.assertEqual(route["teleport"], original["teleport"])
        editor.close()

    def test_helper_add_capture_index_edit_and_remove_target_correct_crafter(self):
        config = normalize_craft_config(single_config())
        owner = SimpleNamespace(
            styleSheet=Mock(return_value=""), screen=Mock(return_value=None),
            settings={"helper_inactive_opacity": 0.3, "station_yaw": 0.0},
            isActiveWindow=Mock(return_value=False), forget_deposit_helper=Mock(),
            craft_config=config, save_craft_routes=Mock(return_value=True),
        )
        with patch("source.launcher.deposit_route_helper.register_alt_n_hotkey", return_value=False):
            helper = DepositRouteHelper(owner, "craft", 0)
        try:
            first = copy.deepcopy(helper.route()["crafters"][0])
            added = helper.add_entry("crafter")
            self.assertIs(helper._entry("crafter", 1), added)
            helper.update_float(added, "yaw", QLineEdit("95"))
            helper.update_crafter_item(added, QLineEdit("element"))
            self.assertEqual(helper.route()["crafters"][0], first)
            helper.delete_entry("crafter", 0)
            self.assertEqual(helper._entry("crafter", 0)["location"]["yaw"], 95)
            self.assertEqual(helper._entry("crafter", 0)["item"], "element")
            owner.save_craft_routes.assert_called_with(show_log=False)
        finally:
            helper.close()
