"""Legacy Pego names are discarded; runtime identity follows entry order."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from test_iguanadon_berry_guard import load_stations_module
from test_template_settings import template_document

from source.launcher.config.station_config import (
    default_pego_entry,
    load_pego_config,
    next_pego_index,
    normalize_pego_config,
    save_pego_config,
)
from source.launcher.config.template_settings import normalize_template


class PegoRuntimeNameTests(unittest.TestCase):
    def test_old_json_round_trip_removes_only_name(self):
        """Old named entries remain usable and save without the obsolete field."""
        old = [{"name": "custom", "teleporter": "PEGO", "delay": 123}]
        expected = [{"teleporter": "PEGO", "delay": 123}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pego.json"
            path.write_text(json.dumps(old))
            self.assertEqual(load_pego_config(path), expected)
            save_pego_config(load_pego_config(path), path)
            self.assertEqual(json.loads(path.read_text()), expected)
            self.assertEqual(load_pego_config(path), expected)

    def test_old_and_new_template_round_trip(self):
        """Template normalization strips names without changing routing or delays."""
        document = template_document()
        document["data"]["pego"] = [
            {"name": "old", "teleporter": "SAME", "delay": 100},
            {"teleporter": "SAME", "delay": 200},
        ]
        normalized, _ = normalize_template(document)
        entries = normalized["data"]["pego"]
        self.assertEqual(entries, normalize_pego_config(document["data"]["pego"]))
        self.assertTrue(all("name" not in entry for entry in entries))
        self.assertEqual(normalize_template(copy.deepcopy(normalized))[0], normalized)

    def test_runtime_names_and_delays_remain_distinct(self):
        """Duplicate teleporters have separate queue identities and intervals."""
        stations, _, _ = load_stations_module()
        first = stations.pego_station(0, "SAME", 100)
        second = stations.pego_station(1, "SAME", 200)
        self.assertEqual([first.name, second.name], ["Pego.1.SAME", "Pego.2.SAME"])
        self.assertEqual([first.get_requeue_delay(), second.get_requeue_delay()], [100, 200])
        self.assertEqual(first.get_priority_level(), 2)

    def test_default_teleporter_reuses_first_free_number(self):
        """Deletion opens a default teleporter slot without consulting old names."""
        entries = [default_pego_entry(1), default_pego_entry(3)]
        self.assertEqual(next_pego_index(entries), 2)
        entries.append(default_pego_entry(2))
        self.assertEqual(next_pego_index(entries), 4)
        self.assertNotIn("name", default_pego_entry())


if __name__ == "__main__":
    unittest.main()
