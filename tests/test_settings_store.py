import unittest

from source.launcher.constants import (
    DEFAULT_SETTINGS,
    HIDDEN_SETTINGS,
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
        self.assertEqual(setting_label("unmapped_example"), "Unmapped example")


if __name__ == "__main__":
    unittest.main()
