import unittest
from pathlib import Path

from source.launcher.constants import (
    DEFAULT_SETTINGS,
    HIDDEN_SETTINGS,
    PHONE_MINIMUM_SIZE,
    SETTINGS_GROUPS,
    setting_label,
)
from source.launcher.settings_store import _normalize_settings


class SettingsStoreTests(unittest.TestCase):
    def test_gacha_feed_delay_defaults_are_preserved(self):
        settings = _normalize_settings({})

        self.assertEqual(settings["gacha_feed_delay"], 6600)
        self.assertEqual(settings["gacha_230_feed_delay"], 10700)
        self.assertIsInstance(DEFAULT_SETTINGS["gacha_feed_delay"], int)
        self.assertIsInstance(DEFAULT_SETTINGS["gacha_230_feed_delay"], int)

    def test_legacy_screen_resolution_setting_is_discarded(self):
        settings = _normalize_settings({"screen_resolution": 1440})

        self.assertNotIn("screen_resolution", settings)
        self.assertNotIn("screen_resolution", DEFAULT_SETTINGS)

    def test_launcher_size_defaults_are_preserved(self):
        settings = _normalize_settings({})

        self.assertEqual(settings["launcher_width"], 1400)
        self.assertEqual(settings["launcher_height"], 800)

    def test_launcher_size_is_clamped_to_phone_minimum(self):
        settings = _normalize_settings(
            {"launcher_width": 100, "launcher_height": 200}
        )

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
                "GENERAL",
                "STATIONS",
                "POSITION / RENDER",
                "STORAGE",
                "FEATURES",
                "WINDOW / HELPERS",
            ],
        )
        self.assertEqual(SETTINGS_GROUPS["STORAGE"], [])

    def test_visible_non_storage_settings_are_grouped_once(self):
        grouped_keys = [
            key
            for group_name, keys in SETTINGS_GROUPS.items()
            if group_name != "STORAGE"
            for key in keys
        ]
        visible_keys = set(DEFAULT_SETTINGS) - HIDDEN_SETTINGS - {
            "dedi_handshake_timeout"
        }

        self.assertEqual(set(grouped_keys), visible_keys)
        self.assertEqual(len(grouped_keys), len(set(grouped_keys)))

    def test_setting_labels_are_sentence_case_with_safe_fallback(self):
        self.assertEqual(setting_label("server_number"), "Server number")
        self.assertEqual(
            setting_label("dedi_handshake_timeout"), "Dedi handshake timeout"
        )
        self.assertEqual(setting_label("launcher_width"), "Launcher startup width")
        self.assertEqual(setting_label("unmapped_example"), "Unmapped example")


if __name__ == "__main__":
    unittest.main()
