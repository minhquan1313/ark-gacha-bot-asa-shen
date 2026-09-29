"""Name-free Gacha records remain compatible with legacy files and templates."""

import json
import tempfile
import unittest
from pathlib import Path

from test_iguanadon_berry_guard import load_stations_module
from test_template_settings import template_document

from source.launcher.config.station_config import (
    load_gacha_collect_config,
    load_gacha_config,
    save_gacha_collect_config,
    save_gacha_config,
)
from source.launcher.config.template_settings import normalize_template


class GachaNameTests(unittest.TestCase):
    def test_missing_files_start_empty_and_legacy_names_disappear_only_on_save(self):
        with tempfile.TemporaryDirectory() as directory:
            for kind, load, save in (
                ("gacha", load_gacha_config, save_gacha_config),
                ("collect", load_gacha_collect_config, save_gacha_collect_config),
            ):
                path = Path(directory) / f"{kind}.json"
                self.assertEqual(load(path, create_missing=False), [])
                self.assertFalse(path.exists())
                self.assertEqual(load(path), [])
                self.assertEqual(json.loads(path.read_text()), [])
                record = {"name": "obsolete", "teleporter": "PAIR", "side": "right"}
                if kind == "collect":
                    record.update(item="paste", dedi_teleport="STORE")
                path.write_text(json.dumps([record]))
                original = path.read_bytes()
                entries = load(path)
                self.assertEqual(path.read_bytes(), original)
                self.assertNotIn("name", entries[0])
                self.assertEqual(save(entries, path), [{k: v for k, v in record.items() if k != "name"}])
                self.assertNotIn("name", json.loads(path.read_text())[0])

    def test_templates_strip_record_names_preserving_values_and_template_name(self):
        document = template_document("Personal")
        document["data"]["gacha"] = [{"name": "old", "teleporter": "PAIR", "side": "left"}]
        document["data"]["gacha_collect"] = [
            {"name": side, "teleporter": "PAIR", "side": side, "item": item, "dedi_teleport": item}
            for side, item in (("left", "paste"), ("right", "metal"))
        ]
        normalized, _ = normalize_template(document)
        self.assertEqual(normalized["name"], "Personal")
        self.assertEqual(normalized["version"], 4)
        for kind in ("gacha", "gacha_collect"):
            self.assertTrue(all("name" not in entry for entry in normalized["data"][kind]))
        self.assertEqual([r["item"] for r in normalized["data"]["gacha_collect"]], ["paste", "metal"])
        self.assertEqual(normalize_template(normalized)[0], normalized)

    def test_runtime_generates_distinct_side_names(self):
        stations, _, _ = load_stations_module()
        self.assertEqual(
            [stations.gacha_station("PAIR", side).name for side in ("left", "right")],
            ["Gacha.PAIR.left", "Gacha.PAIR.right"],
        )
        self.assertEqual(
            [stations.gacha_collect_station("PAIR", side, "paste").name for side in ("left", "right")],
            ["Collect.PAIR.left", "Collect.PAIR.right"],
        )
