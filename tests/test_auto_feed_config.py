import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from source.launcher.config import auto_feed_config


class AutoFeedConfigTests(unittest.TestCase):
    def test_normalizes_legacy_zero_slots_to_disabled(self):
        config = auto_feed_config.normalize_auto_feed(
            {
                "food_slot": 0,
                "water_slot": 0,
                "feed_cycle": 30,
                "babies": [],
            }
        )
        self.assertEqual(config["food_slot"], -1)
        self.assertEqual(config["water_slot"], -1)

    def test_rejects_invalid_slots_and_cycle(self):
        with self.assertRaises(ValueError):
            auto_feed_config.normalize_auto_feed({"food_slot": 11})
        with self.assertRaises(ValueError):
            auto_feed_config.normalize_auto_feed({"feed_cycle": 0})

    def test_save_and_load_preserve_baby_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            config = {
                "tek_pod": False,
                "station_yaw": 12,
                "food_slot": 1,
                "water_slot": -1,
                "feed_cycle": 20,
                "babies": [
                    {
                        "location": {"yaw": 20, "pitch": -4},
                        "crouched": True,
                        "food": "meat",
                    }
                ],
            }
            with patch.object(auto_feed_config, "AUTO_FEED_PATH", path):
                auto_feed_config.save_auto_feed(config)
                loaded = auto_feed_config.load_auto_feed()

            self.assertEqual(loaded["babies"][0]["location"]["pitch"], -4.0)
            self.assertTrue(loaded["babies"][0]["crouched"])
            self.assertEqual(json.loads(path.read_text())["food_slot"], 1)


if __name__ == "__main__":
    unittest.main()
