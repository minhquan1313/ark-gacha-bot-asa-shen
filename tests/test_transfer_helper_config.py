import tempfile
import unittest
from pathlib import Path

from source.launcher.transfer_helper_config import (
    account_slot_for_target,
    bed_name,
    default_transfer_ui_coords,
    displayed_account_order,
    load_transfer_dedis,
    load_transfer_settings,
    missing_runtime_inputs,
    normalize_transfer_dedis,
    normalize_transfer_settings,
    suggested_loop_count,
)


class TransferHelperConfigTests(unittest.TestCase):
    def test_missing_settings_file_creates_loadable_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"

            settings = load_transfer_settings(path)

            self.assertTrue(path.exists())
            self.assertEqual(settings["resource_server"], "0")
            self.assertEqual(settings["destination_server"], "0")

    def test_normalize_settings_rejects_invalid_account_and_loop_values(self):
        with self.assertRaisesRegex(ValueError, "account_count"):
            normalize_transfer_settings({"account_count": 5})
        with self.assertRaisesRegex(ValueError, "loop_count"):
            normalize_transfer_settings({"loop_count": 0})

    def test_bed_name_uses_pad_width_only_when_positive(self):
        self.assertEqual(bed_name("BedPlayer", 2, 0), "BedPlayer2")
        self.assertEqual(bed_name("BedPlayer", 2, 2), "BedPlayer02")
        self.assertEqual(bed_name("BedPlayer", 2, 3), "BedPlayer002")

    def test_suggested_loop_count_ceilings_dedi_transfer_capacity(self):
        self.assertEqual(suggested_loop_count(1, 4), 2)
        self.assertEqual(suggested_loop_count(2, 4), 3)
        self.assertEqual(suggested_loop_count(3, 2), 9)

    def test_dedi_config_normalizes_enabled_items(self):
        config = normalize_transfer_dedis(
            {
                "teleport": "TRANSFERDEDI",
                "items": [
                    {
                        "enabled": False,
                        "location": {"yaw": "12.5", "pitch": "-4"},
                        "crouched": True,
                    }
                ],
            }
        )

        self.assertEqual(config["teleport"], "TRANSFERDEDI")
        self.assertEqual(config["items"][0]["location"]["yaw"], 12.5)
        self.assertFalse(config["items"][0]["enabled"])
        self.assertTrue(config["items"][0]["crouched"])

    def test_missing_dedis_file_creates_default_route(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "dedis.json"

            dedis = load_transfer_dedis(path)

            self.assertTrue(path.exists())
            self.assertEqual(len(dedis["items"]), 1)

    def test_account_display_order_places_current_account_first(self):
        self.assertEqual(displayed_account_order(3, 1), [1, 2, 3])
        self.assertEqual(displayed_account_order(3, 2), [2, 1, 3])
        self.assertEqual(displayed_account_order(3, 3), [3, 1, 2])

    def test_account_slot_for_target_uses_reordered_picker_slots(self):
        coords = default_transfer_ui_coords()

        self.assertEqual(
            account_slot_for_target(coords, 3, current_account=2, target_account=3),
            {"x": 447, "y": 242},
        )
        self.assertIsNone(
            account_slot_for_target(coords, 3, current_account=2, target_account=2)
        )

    def test_validation_blocks_four_accounts_without_four_slot_map(self):
        settings = normalize_transfer_settings(
            {
                "resource_server": "1111",
                "destination_server": "2222",
                "transmitter_teleport": "TX",
                "account_count": 4,
            }
        )
        dedis = normalize_transfer_dedis({"teleport": "DEDI"})
        coords = default_transfer_ui_coords()

        missing = missing_runtime_inputs(settings, dedis, coords)

        self.assertIn("ui_coords.steam.account_slots.4", missing)


if __name__ == "__main__":
    unittest.main()
