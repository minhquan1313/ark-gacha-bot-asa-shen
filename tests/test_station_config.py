import json
import tempfile
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

from source.gacha_bot.deposit_config import (
    default_crystal_route,
    default_dedi_item,
    default_grindable_route,
    default_vault_item,
    normalize_deposit_config,
)
from source.launcher.pages import (
    LauncherPagesMixin,
    _counted_title,
    _deposit_route_child_count,
)
from source.launcher.config.station_config import (
    calculate_pego_delay,
    default_gacha_entry,
    default_pego_entry,
    grouped_gacha_entries,
    load_gacha_config,
    load_pego_config,
    risky_teleporter_names,
    save_gacha_config,
    save_pego_config,
    set_all_pego_delays,
)


class StationConfigTests(unittest.TestCase):
    def test_gacha_load_save_drops_legacy_resource_type_and_depo_tp(self):
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

            self.assertEqual(
                saved[0], {"teleporter": "SNAIL", "side": "left"}
            )

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

    def test_pego_load_save_normalizes_delay_to_int(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pego.json"
            path.write_text(
                json.dumps([{"name": "pego1", "teleporter": "pego1", "delay": "1600"}]),
                encoding="utf-8",
            )

            data = load_pego_config(path)
            saved = save_pego_config(data, path)

            self.assertEqual(
                saved, [{"teleporter": "pego1", "delay": 1600}]
            )

    def test_grouping_is_by_exact_teleporter(self):
        entries = [
            default_gacha_entry("GACHAPAIR_1", "left"),
            default_gacha_entry("GACHAPAIR_1", "right"),
            default_gacha_entry("GACHAPAIR_10", "left"),
        ]

        groups = grouped_gacha_entries(entries)

        self.assertEqual(
            [teleporter for teleporter, _ in groups], ["GACHAPAIR_1", "GACHAPAIR_10"]
        )
        self.assertEqual(len(groups[0][1]), 2)

    def test_risky_teleporter_names_warn_on_prefix_number_overlap(self):
        entries = [
            default_gacha_entry("GACHAPAIR2", "left"),
            default_gacha_entry("GACHAPAIR20", "left"),
            default_gacha_entry("GACHAPAIR_2", "left"),
        ]

        self.assertEqual(risky_teleporter_names(entries), {"GACHAPAIR2", "GACHAPAIR20"})

    def test_pego_defaults_and_bulk_delay(self):
        entries = [default_pego_entry(1), default_pego_entry(2, delay=2000)]

        set_all_pego_delays(entries, "1800")

        self.assertEqual([entry["delay"] for entry in entries], [1800, 1800])

    def test_pego_delay_calculator_uses_counts_owls_and_station_time(self):
        self.assertEqual(calculate_pego_delay(290, 3, 40, 5, 90), 1767)

    def test_pego_delay_calculator_scales_with_gacha_and_owl_counts(self):
        baseline = calculate_pego_delay(290, 3, 40, 5, 90)

        self.assertLess(calculate_pego_delay(290, 3, 80, 5, 90), baseline)
        self.assertLess(calculate_pego_delay(290, 3, 40, 10, 90), baseline)

    def test_pego_delay_calculator_scales_with_pego_count(self):
        baseline = calculate_pego_delay(290, 3, 40, 5, 90)

        self.assertGreater(calculate_pego_delay(290, 6, 40, 5, 90), baseline)

    def test_pego_delay_calculator_subtracts_station_time_from_delay(self):
        self.assertEqual(calculate_pego_delay(290, 3, 40, 5, 120), 1737)

    def test_pego_delay_calculator_rejects_invalid_inputs(self):
        with self.assertRaisesRegex(ValueError, "pego amount"):
            calculate_pego_delay(290, 0, 40, 5, 90)
        with self.assertRaisesRegex(ValueError, "gacha amount"):
            calculate_pego_delay(290, 3, 0, 5, 90)
        with self.assertRaisesRegex(ValueError, "snow owl amount"):
            calculate_pego_delay(290, 3, 40, 0, 90)
        with self.assertRaisesRegex(ValueError, "pego station seconds"):
            calculate_pego_delay(290, 3, 40, 5, -1)

    def test_gacha_teleporter_unchanged_value_is_noop(self):
        launcher = SimpleNamespace(
            gacha_config=[default_gacha_entry("SAME", "left")],
            gacha_group_expanded={"SAME": True},
            save_gacha_config=Mock(),
            _render_settings_group=Mock(),
            _ensure_gacha_config=lambda: None,
        )
        launcher.update_gacha_group_teleporter = MethodType(
            LauncherPagesMixin.update_gacha_group_teleporter, launcher
        )
        field = SimpleNamespace(text=Mock(return_value="SAME"))

        launcher.update_gacha_group_teleporter("SAME", field)

        launcher.save_gacha_config.assert_not_called()
        launcher._render_settings_group.assert_not_called()

    def test_settings_counter_title_formats_single_and_group_entry_counts(self):
        self.assertEqual(_counted_title("PEGO SETTINGS", 5), "PEGO SETTINGS - 5")
        self.assertEqual(
            _counted_title("GACHA SETTINGS", "44(88)"),
            "GACHA SETTINGS - 44(88)",
        )
        self.assertEqual(_counted_title("DEDIS", 0), "DEDIS - 0")

    def test_crystal_route_counter_includes_dedis_and_vaults(self):
        route = default_crystal_route()
        route["dedi"]["items"] = [default_dedi_item(), default_dedi_item()]
        route["vault"]["items"] = [default_vault_item()]

        self.assertEqual(_deposit_route_child_count(route), 3)

    def test_grindable_route_counter_always_includes_grinder(self):
        route = default_grindable_route()

        self.assertEqual(_deposit_route_child_count(route), 1)
        route["dedi"]["items"] = [default_dedi_item(), default_dedi_item()]
        self.assertEqual(_deposit_route_child_count(route), 3)

    def test_deposit_route_check_interval_defaults_to_six(self):
        data = {
            "depositCrystalData": [{"teleport": "CRYSTAL"}],
            "depositGrindableData": [{"teleport": "GRINDABLE"}],
        }

        normalized = normalize_deposit_config(data)

        self.assertEqual(
            normalized["depositCrystalData"][0]["check_on_every_dedi"], 6
        )
        self.assertEqual(
            normalized["depositGrindableData"][0]["check_on_every_dedi"], 6
        )

    def test_deposit_route_arrays_can_be_empty(self):
        data = {
            "depositCrystalData": [],
            "depositGrindableData": [],
        }

        normalized = normalize_deposit_config(data)

        self.assertEqual(normalized["depositCrystalData"], [])
        self.assertEqual(normalized["depositGrindableData"], [])

    def test_deposit_route_ui_can_remove_last_routes(self):
        launcher = SimpleNamespace(
            deposit_config={
                "depositCrystalData": [default_crystal_route()],
                "depositGrindableData": [default_grindable_route()],
            },
            save_deposit_routes=Mock(),
            _render_settings_group=Mock(),
        )
        launcher.remove_crystal_route = MethodType(
            LauncherPagesMixin.remove_crystal_route, launcher
        )
        launcher.remove_grindable_route = MethodType(
            LauncherPagesMixin.remove_grindable_route, launcher
        )

        launcher.remove_crystal_route(0)
        launcher.remove_grindable_route(0)

        self.assertEqual(launcher.deposit_config["depositCrystalData"], [])
        self.assertEqual(launcher.deposit_config["depositGrindableData"], [])
        self.assertEqual(launcher.save_deposit_routes.call_count, 2)
        self.assertEqual(launcher._render_settings_group.call_count, 2)

    def test_deposit_route_check_interval_is_preserved(self):
        data = {
            "depositCrystalData": [
                {"teleport": "CRYSTAL", "check_on_every_dedi": "4"}
            ],
            "depositGrindableData": [
                {"teleport": "GRINDABLE", "check_on_every_dedi": 8}
            ],
        }

        normalized = normalize_deposit_config(data)

        self.assertEqual(
            normalized["depositCrystalData"][0]["check_on_every_dedi"], 4
        )
        self.assertEqual(
            normalized["depositGrindableData"][0]["check_on_every_dedi"], 8
        )

    def test_deposit_route_check_interval_rejects_non_positive_values(self):
        data = {
            "depositCrystalData": [
                {"teleport": "CRYSTAL", "check_on_every_dedi": 0}
            ],
            "depositGrindableData": [{"teleport": "GRINDABLE"}],
        }

        with self.assertRaisesRegex(ValueError, "check_on_every_dedi"):
            normalize_deposit_config(data)

    def test_deposit_route_check_interval_rejects_non_integer_values(self):
        data = {
            "depositCrystalData": [
                {"teleport": "CRYSTAL", "check_on_every_dedi": "bad"}
            ],
            "depositGrindableData": [{"teleport": "GRINDABLE"}],
        }

        with self.assertRaisesRegex(ValueError, "check_on_every_dedi"):
            normalize_deposit_config(data)


if __name__ == "__main__":
    unittest.main()
