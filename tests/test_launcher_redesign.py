"""Launcher presentation integration without disk writes or automation."""

import copy
import unittest
from unittest.mock import Mock, patch

import test_dashboard_redesign as fixture
from PySide6.QtCore import Qt
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit
from test_template_settings import template_document

from source.launcher.components.settings_sections import SettingsSectionHeader
from source.launcher.config.constants import ASSETS
from source.launcher.config.template_settings import TemplateCatalog, normalize_template
from source.launcher.dashboard_theme import asset_path
from source.launcher.gui_parts.settings_state import SettingsStateGuiMixin


class LauncherRedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.DashboardRedesignTests.setUpClass()
        cls.app = fixture.DashboardRedesignTests.app

    def window(self):
        window = fixture.DashboardRedesignTests.window(self, ("dialog",))
        window.show_page("settings")
        window._render_settings_group("LAUNCHER")
        return window

    def test_geometry_text_icons_and_dashboard_removal(self):
        window = self.window()
        for size in ((1200, 800), (1536, 1024), (1920, 1080), (2560, 1440)):
            window.resize(*size)
            QTest.qWait(25)
            self.assertEqual(
                [
                    h.height()
                    for h in window.settings_form.findChildren(SettingsSectionHeader)
                ],
                [104, 104],
            )
            self.assertEqual(
                window.settings_form_area.horizontalScrollBar().maximum(), 0
            )
            self.assertEqual(window.auto_keys_activation_key_field.height(), 44)
            for field in window.settings_form.findChildren(QLineEdit):
                self.assertEqual(field.height(), 44)
        self.assertFalse(window.settings_form.findChildren(QComboBox))
        self.assertIs(window.settings_breadcrumb.selector, window.template_selector)
        labels = [label.text() for label in window.settings_form.findChildren(QLabel)]
        self.assertIn("Interval", labels)
        self.assertIn("Trigger", labels)
        self.assertEqual(labels.count("(s)"), 2)
        self.assertNotIn("Key Hold", labels)
        self.assertFalse(
            any("rebinding" in text or "PRESS A KEY" in text for text in labels)
        )
        self.assertFalse(hasattr(window, "auto_start_switch"))
        self.assertIn("auto_start_program", window.fields)
        for name in ("launcher_settings", "auto_keys", "iguanodon"):
            self.assertTrue(QSvgRenderer(asset_path(ASSETS[f"icon.{name}"])).isValid())

    def test_binding_capture_validation_and_runtime_application(self):
        window = self.window()
        window.auto_keys_runtime = Mock()
        window.startup_complete = True
        with patch(
            "source.launcher.pages.settings.save_settings", side_effect=copy.deepcopy
        ) as save:
            button = window.auto_keys_activation_key_field
            button.click()
            self.assertEqual(button.text(), "PRESS A KEY...")
            QTest.keyClick(button, Qt.Key.Key_F2)
            self.assertEqual(button.text(), "SET KEY: F2")
            self.assertEqual(window.settings["auto_keys"]["activation_key"], "F2")
            window.auto_keys_interval_field.setText("0.2")
            window.auto_keys_interval_field.editingFinished.emit()
            self.assertEqual(window.settings["auto_keys"]["interval"], 0.2)
            window.auto_keys_hold_field.setText("2")
            window.auto_keys_hold_field.editingFinished.emit()
            self.assertEqual(window.settings["auto_keys"]["hold_duration"], 2)
            window.auto_keys_action_fields["MoveForward"].setChecked(False)
            self.assertFalse(window.settings["auto_keys"]["actions"]["MoveForward"])
            window.auto_keys_enabled_field.setChecked(
                not window.auto_keys_enabled_field.isChecked()
            )
            self.assertEqual(
                window.settings["auto_keys"]["enabled"],
                window.auto_keys_enabled_field.isChecked(),
            )
            self.assertTrue(window.auto_keys_runtime.configure.called)
            before = save.call_count
            window.auto_keys_interval_field.setText("0")
            window.auto_keys_interval_field.editingFinished.emit()
            self.assertEqual(save.call_count, before)
            window.dialog.assert_called()

    def test_launcher_profile_locks_only_launcher_fields(self):
        window = self.window()
        template, _ = normalize_template(template_document("Launcher profile"))
        template["data"]["settings"]["launcher_width"] = 1400
        catalog = TemplateCatalog({"launcher.json": template}, {}, {})
        before = copy.deepcopy(window.settings["auto_keys"])
        with (
            patch.object(window, "_template_catalog", return_value=catalog),
            patch(
                "source.launcher.pages.settings.save_settings",
                side_effect=copy.deepcopy,
            ),
        ):
            window._render_settings_group("LAUNCHER")
            window.template_selector.setCurrentIndex(
                window.template_selector.findData("launcher.json")
            )
            self.assertEqual(window.fields["launcher_width"].text(), "1400")
            self.assertFalse(window.fields["launcher_width"].isEnabled())
            self.assertTrue(window.auto_keys_interval_field.isEnabled())
            self.assertTrue(window.auto_keys_activation_key_field.isEnabled())
            self.assertEqual(window.settings["auto_keys"], before)
            window.template_selector.setCurrentIndex(0)
            self.assertTrue(window.fields["launcher_width"].isEnabled())

    def test_six_launcher_fields_use_existing_autosave(self):
        window = self.window()
        self.assertEqual(
            set(window.fields),
            {
                "auto_start_program",
                "helper_inactive_opacity",
                "allow_focus_ark_window",
                "focus_ark_window_interval",
                "launcher_width",
                "launcher_height",
            },
        )
        window.persist_settings_from_visible_fields = (
            SettingsStateGuiMixin.persist_settings_from_visible_fields.__get__(window)
        )
        try:
            with patch(
                "source.launcher.gui_parts.settings_state.save_settings"
            ) as save:
                for key, field in window.fields.items():
                    if isinstance(field, QLineEdit):
                        field.setText(
                            str(float(field.text()) + 0.1)
                            if key
                            in {"helper_inactive_opacity", "focus_ark_window_interval"}
                            else str(int(field.text()) + 1)
                        )
                        field.editingFinished.emit()
                    else:
                        field.setChecked(not field.isChecked())
                    self.assertEqual(
                        save.call_args.args[0][key], window._field_value(key, field)
                    )
        finally:
            window.persist_settings_from_visible_fields = lambda *args, **kwargs: False


if __name__ == "__main__":
    unittest.main()
