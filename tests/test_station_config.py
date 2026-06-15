import json
import tempfile
import unittest
from pathlib import Path

from source.launcher.station_config import (
    auto_fill_gacha_group,
    default_gacha_entry,
    default_gacha_pair,
    default_pego_entry,
    grouped_gacha_entries,
    load_gacha_config,
    load_pego_config,
    missing_gacha_side,
    next_gacha_teleporter,
    risky_teleporter_names,
    save_gacha_config,
    save_pego_config,
    set_all_pego_delays,
)


class StationConfigTests(unittest.TestCase):
    def test_gacha_load_save_drops_obsolete_mode_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gacha.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "name": "snail1",
                            "teleporter": "SNAIL",
                            "side": "left",
                            "resource_type": "collect",
                            "depo_tp": "DEPO",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            data = load_gacha_config(path)
            saved = save_gacha_config(data, path)

            self.assertNotIn("resource_type", saved[0])
            self.assertNotIn("depo_tp", saved[0])

    def test_gacha_save_drops_normal_resource_type(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gacha.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "name": "gacha1",
                            "teleporter": "GACHAPAIR_1",
                            "side": "left",
                            "resource_type": "element",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            data = load_gacha_config(path)
            saved = save_gacha_config(data, path)

            self.assertNotIn("resource_type", saved[0])
            self.assertNotIn("depo_tp", saved[0])

    def test_pego_load_save_normalizes_delay_to_int(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pego.json"
            path.write_text(
                json.dumps([{"name": "pego1", "teleporter": "pego1", "delay": "1600"}]),
                encoding="utf-8",
            )

            data = load_pego_config(path)
            saved = save_pego_config(data, path)

            self.assertEqual(saved, [{"name": "pego1", "teleporter": "pego1", "delay": 1600}])

    def test_default_gacha_pair_uses_expected_teleporter_and_sides(self):
        self.assertEqual(
            default_gacha_pair(index=2),
            [
                {"name": "GACHAPAIR_2_left", "teleporter": "GACHAPAIR_2", "side": "left"},
                {"name": "GACHAPAIR_2_right", "teleporter": "GACHAPAIR_2", "side": "right"},
            ],
        )

    def test_grouping_is_by_exact_teleporter(self):
        entries = [
            default_gacha_entry("a", "GACHAPAIR_1", "left"),
            default_gacha_entry("b", "GACHAPAIR_1", "right"),
            default_gacha_entry("c", "GACHAPAIR_10", "left"),
        ]

        groups = grouped_gacha_entries(entries)

        self.assertEqual([teleporter for teleporter, _ in groups], ["GACHAPAIR_1", "GACHAPAIR_10"])
        self.assertEqual(len(groups[0][1]), 2)

    def test_missing_gacha_side_fills_left_then_right(self):
        self.assertEqual(missing_gacha_side([]), "left")
        self.assertEqual(
            missing_gacha_side([default_gacha_entry("a", "GACHAPAIR_1", "left")]),
            "right",
        )
        self.assertIsNone(
            missing_gacha_side(
                [
                    default_gacha_entry("a", "GACHAPAIR_1", "left"),
                    default_gacha_entry("b", "GACHAPAIR_1", "right"),
                ]
            )
        )

    def test_next_gacha_teleporter_uses_underscore_and_skips_existing(self):
        entries = default_gacha_pair(index=1) + default_gacha_pair(index=2)

        self.assertEqual(next_gacha_teleporter(entries), "GACHAPAIR_3")

    def test_auto_fill_gacha_group_resets_names_and_sides(self):
        group = [
            default_gacha_entry("wrong", "GACHAPAIR_7", "banana"),
            default_gacha_entry("also_wrong", "GACHAPAIR_7", "other"),
        ]

        auto_fill_gacha_group(group)

        self.assertEqual(
            group,
            [
                {"name": "GACHAPAIR_7_left", "teleporter": "GACHAPAIR_7", "side": "left"},
                {"name": "GACHAPAIR_7_right", "teleporter": "GACHAPAIR_7", "side": "right"},
            ],
        )

    def test_auto_fill_gacha_group_can_reset_teleporter(self):
        group = [
            default_gacha_entry("wrong", "bad_name", "banana"),
            default_gacha_entry("also_wrong", "bad_name", "other"),
        ]

        auto_fill_gacha_group(group, "GACHAPAIR_2")

        self.assertEqual(
            group,
            [
                {"name": "GACHAPAIR_2_left", "teleporter": "GACHAPAIR_2", "side": "left"},
                {"name": "GACHAPAIR_2_right", "teleporter": "GACHAPAIR_2", "side": "right"},
            ],
        )

    def test_risky_teleporter_names_warn_on_prefix_number_overlap(self):
        entries = [
            default_gacha_entry("a", "GACHAPAIR2", "left"),
            default_gacha_entry("b", "GACHAPAIR20", "left"),
            default_gacha_entry("c", "GACHAPAIR_2", "left"),
        ]

        self.assertEqual(risky_teleporter_names(entries), {"GACHAPAIR2", "GACHAPAIR20"})

    def test_pego_defaults_and_bulk_delay(self):
        entries = [default_pego_entry(1), default_pego_entry(2, delay=2000)]

        set_all_pego_delays(entries, "1800")

        self.assertEqual([entry["delay"] for entry in entries], [1800, 1800])


if __name__ == "__main__":
    unittest.main()
