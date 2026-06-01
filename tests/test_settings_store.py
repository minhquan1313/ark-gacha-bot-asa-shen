import unittest

from source.launcher.constants import DEFAULT_SETTINGS
from source.launcher.settings_store import _normalize_settings


class SettingsStoreTests(unittest.TestCase):
    def test_gacha_feed_delay_defaults_are_preserved(self):
        settings = _normalize_settings({})

        self.assertEqual(settings["gacha_feed_delay"], 6600)
        self.assertEqual(settings["gacha_230_feed_delay"], 10700)
        self.assertIsInstance(DEFAULT_SETTINGS["gacha_feed_delay"], int)
        self.assertIsInstance(DEFAULT_SETTINGS["gacha_230_feed_delay"], int)


if __name__ == "__main__":
    unittest.main()
