import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox

from source.launcher.auto_feed_helper import AutoBabyFeedingHelper, AutoFeedGuide
from source.launcher.styles import launcher_style_sheet


class AutoFeedHelperUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _owner(self):
        return SimpleNamespace(
            styleSheet=Mock(return_value=""),
            screen=Mock(return_value=None),
            settings={"helper_inactive_opacity": 0.3},
            isActiveWindow=Mock(return_value=False),
            forget_deposit_helper=Mock(),
            require_ark_window=Mock(return_value=True),
        )

    def _config(self):
        return {
            "ping": 100,
            "tek_pod": True,
            "station_yaw": 0.0,
            "food_slot": -1,
            "water_slot": -1,
            "feed_cycle": 30,
            "babies": [
                {
                    "location": {"yaw": 1.0, "pitch": 2.0},
                    "crouched": False,
                    "food": "meat",
                }
            ],
        }

    def _helper(self):
        patches = [
            patch(
                "source.launcher.auto_feed_helper.load_auto_feed",
                return_value=self._config(),
            ),
            patch(
                "source.launcher.auto_feed_helper.save_auto_feed",
                side_effect=lambda config: config,
            ),
            patch(
                "source.launcher.auto_feed_helper.preload_capture_view_dependencies",
                return_value=None,
            ),
            patch(
                "source.launcher.auto_feed_helper.register_alt_n_hotkey",
                return_value=False,
            ),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        helper = AutoBabyFeedingHelper(self._owner())
        self.addCleanup(helper.close)
        return helper

    def test_baby_rows_match_transfer_summary_structure(self):
        helper = self._helper()
        row = helper.baby_rows[0]

        self.assertEqual(helper.baby_section_label.text(), "Baby - 1")
        self.assertEqual(row.index_label.text(), "B1")
        self.assertEqual(row.summary.text(), "Yaw 1.0 | Pitch 2.0 | Crouch off")
        self.assertIsInstance(row.crouched, QCheckBox)
        self.assertTrue(row.details.isHidden())

        row._toggle(row.expand_button)
        self.assertFalse(row.details.isHidden())

    def test_checkbox_and_remove_update_config_and_row_count(self):
        helper = self._helper()
        row = helper.baby_rows[0]

        row.crouched.setChecked(True)
        self.assertTrue(helper.config["babies"][0]["crouched"])
        self.assertIn("Crouch on", row.summary.text())

        helper._add_baby()
        self.assertEqual(helper.baby_section_label.text(), "Baby - 2")
        self.assertEqual(helper.baby_rows[1].index_label.text(), "B2")
        helper._remove_baby(0)
        self.assertEqual(helper.baby_section_label.text(), "Baby - 1")
        self.assertEqual(helper.baby_rows[0].index_label.text(), "B1")

    def test_sections_start_expanded_and_can_collapse_independently(self):
        helper = self._helper()

        self.assertEqual(len(helper.collapsible_sections), 2)
        feeding_body, feeding_toggle = helper.collapsible_sections[0]
        baby_body, baby_toggle = helper.collapsible_sections[1]
        self.assertEqual(feeding_toggle.text(), "v")
        self.assertEqual(baby_toggle.text(), "v")
        self.assertFalse(feeding_body.isHidden())
        self.assertFalse(baby_body.isHidden())

        feeding_toggle.click()
        self.assertEqual(feeding_toggle.text(), ">")
        self.assertTrue(feeding_body.isHidden())
        self.assertFalse(baby_body.isHidden())

        baby_toggle.click()
        self.assertEqual(baby_toggle.text(), ">")
        self.assertTrue(baby_body.isHidden())

    def test_auto_feed_fields_use_scoped_borderless_style(self):
        helper = self._helper()
        row = helper.baby_rows[0]
        fields = [
            helper.station_yaw,
            helper.food_slot,
            helper.water_slot,
            helper.feed_cycle,
            row.yaw,
            row.pitch,
            row.food,
        ]
        self.assertTrue(all(field.objectName() == "AutoFeedField" for field in fields))
        style = launcher_style_sheet()
        self.assertIn("QLineEdit#AutoFeedField", style)
        self.assertIn("QLineEdit#SettingField", style)

    def test_guide_uses_shared_paginated_helper_structure(self):
        helper = self._helper()
        guide = AutoFeedGuide(helper)
        self.addCleanup(guide.close)

        self.assertEqual(len(guide.PAGES), 4)
        self.assertEqual(guide.page_label.text(), "1 / 4")
        self.assertFalse(guide.prev_button.isEnabled())
        self.assertTrue(guide.next_button.isEnabled())
        self.assertIsNotNone(guide.stack)
        self.assertEqual(guide.header_title.text(), "HELPER GUIDE")

        guide.next_page()
        self.assertEqual(guide.page_label.text(), "2 / 4")
        self.assertTrue(guide.prev_button.isEnabled())
        guide.page_index = len(guide.PAGES) - 1
        guide._sync_page_controls()
        self.assertEqual(guide.page_label.text(), "4 / 4")
        self.assertFalse(guide.next_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
