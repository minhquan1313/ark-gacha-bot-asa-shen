import unittest
from pathlib import Path

from source.launcher.config.constants import (
    DEFAULT_SETTINGS,
    HIDDEN_SETTINGS,
    PHONE_MINIMUM_SIZE,
    SETTINGS_GROUPS,
    TEMPLATE_REFERENCE_DEFAULTS,
    TEMPLATE_SETTING_KEYS,
    setting_label,
    setting_tooltip,
)
from source.launcher.config import constants
from source.launcher.utils.settings_store import _normalize_settings


class SettingsStoreTests(unittest.TestCase):
    def test_gacha_feed_delay_default_is_preserved(self):
        settings = _normalize_settings({})

        self.assertEqual(settings["gacha_feed_delay"], 6600)
        self.assertIsInstance(DEFAULT_SETTINGS["gacha_feed_delay"], int)
        self.assertEqual(settings["time_to_reberry"], 30)
        self.assertIsInstance(DEFAULT_SETTINGS["time_to_reberry"], int)

    def test_legacy_screen_resolution_setting_is_discarded(self):
        settings = _normalize_settings({"screen_resolution": 1440})

        self.assertNotIn("screen_resolution", settings)
        self.assertNotIn("screen_resolution", DEFAULT_SETTINGS)

    def test_unknown_and_retired_settings_are_discarded(self):
        settings = _normalize_settings(
            {
                "base_path": "obsolete",
                "crafting": True,
                "drop_off": "GACHADEDI",
                "grindables": "GACHAGRINDABLES",
                "height_ele": 3,
                "height_grind": 3,
                "render_pushout": -165.96,
                "y_trap_bot": True,
                "custom_setting": "obsolete",
                "server_number": "5147",
            }
        )

        self.assertNotIn("base_path", settings)
        self.assertNotIn("crafting", settings)
        self.assertNotIn("drop_off", settings)
        self.assertNotIn("grindables", settings)
        self.assertNotIn("height_ele", settings)
        self.assertNotIn("height_grind", settings)
        self.assertNotIn("render_pushout", settings)
        self.assertNotIn("y_trap_bot", settings)
        self.assertNotIn("custom_setting", settings)
        self.assertEqual(settings["server_number"], "5147")

    def test_removed_gacha_settings_are_discarded(self):
        old_seed_key = "seeds" + "_230"
        old_delay_key = "gacha" + "_230_feed_delay"
        old_crop_key = "side" + "_crop_plot"
        settings = _normalize_settings(
            {
                old_seed_key: True,
                old_delay_key: 12345,
                old_crop_key: True,
            }
        )

        self.assertNotIn(old_seed_key, settings)
        self.assertNotIn(old_delay_key, settings)
        self.assertNotIn(old_crop_key, settings)
        self.assertEqual(HIDDEN_SETTINGS, set())

    def test_launcher_size_defaults_are_preserved(self):
        settings = _normalize_settings({})

        self.assertEqual(settings["launcher_width"], 1200)
        self.assertEqual(settings["launcher_height"], 800)

    def test_template_references_default_to_manual_and_are_preserved(self):
        settings = _normalize_settings({"lag_offset_template": "Template A"})

        self.assertEqual(settings["lag_offset_template"], "Template A")
        self.assertEqual(settings["dedis_template"], "")
        self.assertIn("time_to_reberry_template", TEMPLATE_REFERENCE_DEFAULTS)
        self.assertTrue(set(TEMPLATE_REFERENCE_DEFAULTS) <= set(settings))
        self.assertNotIn("station_yaw_template", settings)

    def test_launcher_size_is_clamped_to_phone_minimum(self):
        settings = _normalize_settings({"launcher_width": 100, "launcher_height": 200})

        self.assertEqual(settings["launcher_width"], PHONE_MINIMUM_SIZE[0])
        self.assertEqual(settings["launcher_height"], PHONE_MINIMUM_SIZE[1])

    def test_obsolete_resolution_artifacts_are_removed(self):
        project_root = Path(__file__).resolve().parents[1]

        self.assertFalse((project_root / "assets" / "icons1440").exists())
        self.assertFalse(
            (project_root / "source" / "join_sim" / "assets" / "icons1440").exists()
        )
        self.assertFalse((project_root / "json_files" / "resolution.json").exists())

    def test_settings_groups_follow_workflow_order(self):
        self.assertEqual(
            list(SETTINGS_GROUPS),
            [
                "SERVER",
                "STATIONS",
                "PEGO",
                "DEDI",
                "GACHA",
                "LAUNCHER",
            ],
        )
        self.assertEqual(SETTINGS_GROUPS["DEDI"], [])
        self.assertEqual(SETTINGS_GROUPS["PEGO"], [])
        self.assertEqual(SETTINGS_GROUPS["GACHA"], ["gacha_feed_delay"])
        self.assertEqual(SETTINGS_GROUPS["STATIONS"].count("time_to_reberry"), 1)
        self.assertFalse(hasattr(constants, "SETTINGS_GROUP_ROWS"))

    def test_visible_non_storage_settings_are_grouped_once(self):
        grouped_keys = [
            key
            for group_name, keys in SETTINGS_GROUPS.items()
            if group_name not in {"DEDI", "PEGO"}
            for key in keys
        ]
        visible_keys = set(DEFAULT_SETTINGS) - HIDDEN_SETTINGS

        self.assertEqual(set(grouped_keys), visible_keys)
        self.assertEqual(len(grouped_keys), len(set(grouped_keys)))
        self.assertNotIn("station_yaw", TEMPLATE_SETTING_KEYS)
        self.assertIn("auto_start_program", SETTINGS_GROUPS["LAUNCHER"])

    def test_setting_labels_are_sentence_case_with_safe_fallback(self):
        self.assertEqual(setting_label("server_number"), "Server")
        self.assertEqual(setting_label("bed_spawn"), "Bed spawn")
        self.assertEqual(setting_label("external_berry"), "Troughs away?")
        self.assertEqual(setting_label("time_to_reberry"), "Time to reberry")
        self.assertEqual(setting_label("launcher_width"), "Launcher startup width")
        self.assertEqual(setting_label("unmapped_example"), "Unmapped example")

    def test_requested_setting_tooltips_are_exposed(self):
        self.assertIn("Gacha Tower", setting_tooltip("server_number"))
        self.assertIn("Single player mode", setting_tooltip("singleplayer"))
        self.assertIn("SnowOwl pells", setting_tooltip("iguanadon_seed_throw_amount"))
        self.assertIn("Seconds", setting_tooltip("time_to_reberry"))
        self.assertEqual(setting_tooltip("lag_offset"), "")


if __name__ == "__main__":
    unittest.main()
