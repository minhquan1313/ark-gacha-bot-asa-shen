import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton

from source.launcher.config.constants import TEMPLATE_GROUP_REFERENCE_KEYS
from source.launcher.config.template_settings import normalize_template, write_template
from source.launcher.pages.gacha import GachaPagesMixin
from source.launcher.utils.settings_store import load_settings, save_settings
from test_iguanadon_berry_guard import load_stations_module
from test_template_settings import template_document


class CollectDelayTests(unittest.TestCase):
    def test_old_settings_default_and_independent_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            save_settings({"gacha_feed_delay": 123}, path)
            settings = load_settings(path)
            self.assertEqual(settings["gacha_collect_feed_delay"], 6600)
            settings.update(gacha_collect_feed_delay=456, craft_delay=900)
            save_settings(settings, path)
            saved = load_settings(path)
            self.assertEqual(
                [saved[key] for key in (
                    "gacha_feed_delay", "gacha_collect_feed_delay", "craft_delay"
                )], [123, 456, 900]
            )

    def test_old_template_default_and_independent_round_trip(self):
        document = template_document()
        settings = document["data"]["settings"]
        settings["gacha_feed_delay"] = 123
        del settings["gacha_collect_feed_delay"]
        normalized, _ = normalize_template(document)
        self.assertEqual(normalized["data"]["settings"]["gacha_collect_feed_delay"], 6600)
        settings["gacha_collect_feed_delay"] = 456
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.json"
            write_template(document, path.name, directory)
            saved, _ = normalize_template(json.loads(path.read_text(encoding="utf-8")))
        self.assertEqual(saved["data"]["settings"]["gacha_collect_feed_delay"], 456)
        self.assertEqual(saved["data"]["settings"]["gacha_feed_delay"], 123)
        self.assertIn("gacha_collect_feed_delay_template", TEMPLATE_GROUP_REFERENCE_KEYS["GACHA"])

    def test_collection_and_craft_use_independent_scheduler_delays(self):
        stations, _, _ = load_stations_module()
        stations.settings.craft_delay = 900
        collection = stations.gacha_collect_station("one", "PAIR", "left", "stone")
        craft = stations.craft_station({"teleport": "CRAFT"}, 0)
        self.assertEqual(collection.get_requeue_delay(), 456)
        self.assertEqual(craft.get_requeue_delay(), 900)
        self.assertEqual(craft.get_priority_level(), 5)
        self.assertEqual(stations.gacha_station("one", "PAIR", "left").get_requeue_delay(), 123)

    def test_every_scheduled_collection_run_feeds_and_deposits(self):
        stations, _, _ = load_stations_module()
        route = {"id": "chosen"}
        stations.deposit.resolve_collection_destination = Mock(return_value=route)
        stations.deposit.deposit_collection = Mock()
        stations.deposit.craft = Mock()
        task = stations.gacha_collect_station("one", "PAIR", "left", "stone", "chosen")
        task.execute()
        task.execute()
        self.assertEqual(stations.gacha.drop_off_nocrop.call_count, 2)
        self.assertEqual(stations.deposit.deposit_collection.call_args_list, [unittest.mock.call(route)] * 2)
        stations.deposit.craft.assert_not_called()

    def test_collect_ui_has_only_feed_delay(self):
        app = QApplication.instance() or QApplication([])
        fields = []

        def field(key: str):
            """Record the setting bound to each rendered editor."""
            fields.append(key)
            return QLineEdit()

        launcher = SimpleNamespace(
            gacha_section_expanded={"collect": True},
            _button=lambda text, style: QPushButton(text),
            _icon_button=lambda icon, text, style: QPushButton(text),
            _setting_field=field,
            _setting_field_container=lambda widget, *args: widget,
            remove_gacha_section=Mock(),
            add_gacha_group=Mock(),
        )
        section = GachaPagesMixin._gacha_section(
            launcher, "GACHA COLLECT", "collect", [], [],
            "gacha_collect_feed_delay", "local", "", ""
        )
        self.assertEqual(fields, ["gacha_collect_feed_delay"])
        self.assertEqual(
            [label.text() for label in section.findChildren(QLabel)][1:],
            ["Feed delay (s)"]
        )
        section.close()


if __name__ == "__main__":
    unittest.main()
