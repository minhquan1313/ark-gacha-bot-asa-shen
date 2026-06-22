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
)
from source.launcher.pages import (
    LauncherPagesMixin,
    _counted_title,
    _deposit_route_child_count,
)
from source.launcher.config.station_config import (
    auto_fill_gacha_group,
    calculate_pego_delay,
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
                saved[0], {"name": "snail1", "teleporter": "SNAIL", "side": "left"}
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
                saved, [{"name": "pego1", "teleporter": "pego1", "delay": 1600}]
            )

    def test_default_gacha_pair_uses_expected_teleporter_and_sides(self):
        self.assertEqual(
            default_gacha_pair(index=2),
            [
                {
                    "name": "GACHAPAIR_2_left",
                    "teleporter": "GACHAPAIR_2",
                    "side": "left",
                },
                {
                    "name": "GACHAPAIR_2_right",
                    "teleporter": "GACHAPAIR_2",
                    "side": "right",
                },
            ],
        )

    def test_grouping_is_by_exact_teleporter(self):
        entries = [
            default_gacha_entry("a", "GACHAPAIR_1", "left"),
            default_gacha_entry("b", "GACHAPAIR_1", "right"),
            default_gacha_entry("c", "GACHAPAIR_10", "left"),
        ]

        groups = grouped_gacha_entries(entries)

        self.assertEqual(
            [teleporter for teleporter, _ in groups], ["GACHAPAIR_1", "GACHAPAIR_10"]
        )
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
                {
                    "name": "GACHAPAIR_7_left",
                    "teleporter": "GACHAPAIR_7",
                    "side": "left",
                },
                {
                    "name": "GACHAPAIR_7_right",
                    "teleporter": "GACHAPAIR_7",
                    "side": "right",
                },
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
                {
                    "name": "GACHAPAIR_2_left",
                    "teleporter": "GACHAPAIR_2",
                    "side": "left",
                },
                {
                    "name": "GACHAPAIR_2_right",
                    "teleporter": "GACHAPAIR_2",
                    "side": "right",
                },
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

    def test_gacha_auto_fill_requires_confirmation(self):
        launcher = SimpleNamespace(
            gacha_config=[default_gacha_entry("wrong", "GACHAPAIR_1", "banana")],
            confirm=Mock(return_value=False),
            save_gacha_config=Mock(),
            _render_settings_group=Mock(),
            _ensure_gacha_config=lambda: None,
        )
        launcher.auto_fill_gacha_group = MethodType(
            LauncherPagesMixin.auto_fill_gacha_group, launcher
        )

        launcher.auto_fill_gacha_group("GACHAPAIR_1")

        self.assertEqual(launcher.gacha_config[0]["name"], "wrong")
        launcher.save_gacha_config.assert_not_called()
        launcher._render_settings_group.assert_not_called()

    def test_gacha_auto_fill_updates_after_confirmation(self):
        launcher = SimpleNamespace(
            gacha_config=[default_gacha_entry("wrong", "GACHAPAIR_1", "banana")],
            confirm=Mock(return_value=True),
            save_gacha_config=Mock(),
            _render_settings_group=Mock(),
            _ensure_gacha_config=lambda: None,
        )
        launcher.auto_fill_gacha_group = MethodType(
            LauncherPagesMixin.auto_fill_gacha_group, launcher
        )

        launcher.auto_fill_gacha_group("GACHAPAIR_1")

        self.assertEqual(launcher.gacha_config[0]["name"], "GACHAPAIR_1_left")
        self.assertEqual(launcher.gacha_config[0]["side"], "left")
        launcher.save_gacha_config.assert_called_once_with()
        launcher._render_settings_group.assert_called_once_with("GACHA")

    def test_gacha_auto_fill_replaces_bad_teleporter_with_next_available(self):
        launcher = SimpleNamespace(
            gacha_config=[
                default_gacha_entry("existing_left", "GACHAPAIR_1", "left"),
                default_gacha_entry("existing_right", "GACHAPAIR_1", "right"),
                default_gacha_entry("wrong", "bad_name", "banana"),
            ],
            gacha_group_expanded={"bad_name": True},
            confirm=Mock(return_value=True),
            save_gacha_config=Mock(),
            _render_settings_group=Mock(),
            _ensure_gacha_config=lambda: None,
        )
        launcher.auto_fill_gacha_group = MethodType(
            LauncherPagesMixin.auto_fill_gacha_group, launcher
        )

        launcher.auto_fill_gacha_group("bad_name")

        self.assertEqual(launcher.gacha_config[2]["teleporter"], "GACHAPAIR_2")
        self.assertEqual(launcher.gacha_config[2]["name"], "GACHAPAIR_2_left")
        self.assertEqual(launcher.gacha_config[2]["side"], "left")
        self.assertIn("GACHAPAIR_2", launcher.gacha_group_expanded)
        self.assertNotIn("bad_name", launcher.gacha_group_expanded)

    def test_gacha_side_update_saves_without_rerender(self):
        launcher = SimpleNamespace(
            gacha_config=[default_gacha_entry("gacha", "GACHAPAIR_1", "left")],
            save_gacha_config=Mock(),
            _render_settings_group=Mock(),
            _ensure_gacha_config=lambda: None,
        )
        launcher.update_gacha_side = MethodType(
            LauncherPagesMixin.update_gacha_side, launcher
        )
        field = SimpleNamespace(currentText=Mock(return_value="right"))

        launcher.update_gacha_side(0, field)

        self.assertEqual(launcher.gacha_config[0]["side"], "right")
        launcher.save_gacha_config.assert_called_once_with()
        launcher._render_settings_group.assert_not_called()

    def test_gacha_name_update_saves_without_rerender(self):
        launcher = SimpleNamespace(
            gacha_config=[default_gacha_entry("old", "GACHAPAIR_1", "left")],
            save_gacha_config=Mock(),
            _render_settings_group=Mock(),
            _ensure_gacha_config=lambda: None,
        )
        launcher.update_station_field = MethodType(
            LauncherPagesMixin.update_station_field, launcher
        )
        field = SimpleNamespace(text=Mock(return_value="new"))

        launcher.update_station_field("gacha", 0, "name", field)

        self.assertEqual(launcher.gacha_config[0]["name"], "new")
        launcher.save_gacha_config.assert_called_once_with()
        launcher._render_settings_group.assert_not_called()

    def test_gacha_teleporter_update_still_rerenders(self):
        launcher = SimpleNamespace(
            gacha_config=[default_gacha_entry("gacha", "OLD", "left")],
            gacha_group_expanded={"OLD": True},
            save_gacha_config=Mock(),
            _render_settings_group=Mock(),
            _ensure_gacha_config=lambda: None,
        )
        launcher.update_station_field = MethodType(
            LauncherPagesMixin.update_station_field, launcher
        )
        field = SimpleNamespace(text=Mock(return_value="NEW"))

        launcher.update_station_field("gacha", 0, "teleporter", field)

        self.assertEqual(launcher.gacha_config[0]["teleporter"], "NEW")
        launcher.save_gacha_config.assert_called_once_with()
        launcher._render_settings_group.assert_called_once_with("GACHA")

    def test_gacha_teleporter_update_rejects_case_insensitive_duplicate(self):
        launcher = SimpleNamespace(
            gacha_config=[
                default_gacha_entry("old_left", "OLD", "left"),
                default_gacha_entry("old_right", "OLD", "right"),
                default_gacha_entry("taken", "Taken", "left"),
            ],
            gacha_group_expanded={"OLD": True, "Taken": False},
            dialog=Mock(),
            save_gacha_config=Mock(),
            _render_settings_group=Mock(),
            _ensure_gacha_config=lambda: None,
        )
        launcher.update_gacha_group_teleporter = MethodType(
            LauncherPagesMixin.update_gacha_group_teleporter, launcher
        )
        field = SimpleNamespace(
            text=Mock(return_value="TAKEN"),
            setText=Mock(),
        )

        launcher.update_gacha_group_teleporter("OLD", field)

        self.assertEqual(
            [entry["teleporter"] for entry in launcher.gacha_config],
            ["OLD", "OLD", "Taken"],
        )
        field.setText.assert_called_once_with("OLD")
        launcher.dialog.assert_called_once()
        self.assertEqual(launcher.dialog.call_args.args[2], "error")
        launcher.save_gacha_config.assert_not_called()
        launcher._render_settings_group.assert_not_called()

    def test_gacha_teleporter_update_rejects_exact_duplicate(self):
        launcher = SimpleNamespace(
            gacha_config=[
                default_gacha_entry("old", "OLD", "left"),
                default_gacha_entry("taken", "TAKEN", "left"),
            ],
            gacha_group_expanded={"OLD": True, "TAKEN": False},
            dialog=Mock(),
            save_gacha_config=Mock(),
            _render_settings_group=Mock(),
            _ensure_gacha_config=lambda: None,
        )
        launcher.update_gacha_group_teleporter = MethodType(
            LauncherPagesMixin.update_gacha_group_teleporter, launcher
        )
        field = SimpleNamespace(text=Mock(return_value="TAKEN"), setText=Mock())

        launcher.update_gacha_group_teleporter("OLD", field)

        field.setText.assert_called_once_with("OLD")
        launcher.save_gacha_config.assert_not_called()
        launcher._render_settings_group.assert_not_called()

    def test_gacha_teleporter_update_allows_case_only_change_for_same_group(self):
        launcher = SimpleNamespace(
            gacha_config=[
                default_gacha_entry("old_left", "Old", "left"),
                default_gacha_entry("old_right", "Old", "right"),
            ],
            gacha_group_expanded={"Old": True},
            dialog=Mock(),
            save_gacha_config=Mock(),
            _render_settings_group=Mock(),
            _ensure_gacha_config=lambda: None,
        )
        launcher.update_gacha_group_teleporter = MethodType(
            LauncherPagesMixin.update_gacha_group_teleporter, launcher
        )
        field = SimpleNamespace(text=Mock(return_value="OLD"))

        launcher.update_gacha_group_teleporter("Old", field)

        self.assertEqual(
            [entry["teleporter"] for entry in launcher.gacha_config],
            ["OLD", "OLD"],
        )
        self.assertEqual(launcher.gacha_group_expanded, {"OLD": True})
        launcher.dialog.assert_not_called()
        launcher.save_gacha_config.assert_called_once_with()
        launcher._render_settings_group.assert_called_once_with("GACHA")

    def test_gacha_teleporter_unchanged_value_is_noop(self):
        launcher = SimpleNamespace(
            gacha_config=[default_gacha_entry("gacha", "SAME", "left")],
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


if __name__ == "__main__":
    unittest.main()
