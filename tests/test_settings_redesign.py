"""Integration checks for the approved Server and Stations presentation."""

import copy
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import test_dashboard_redesign as dashboard_fixture
from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QLineEdit
from test_template_settings import template_document

from source.launcher.components.settings_sections import SettingsSectionHeader
from source.launcher.config.constants import TEMPLATE_GROUP_REFERENCE_KEYS
from source.launcher.config.template_settings import TemplateCatalog, normalize_template
from source.launcher.gui_parts.settings_state import SettingsStateGuiMixin


class SettingsRedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dashboard_fixture.DashboardRedesignTests.setUpClass()
        cls.app = dashboard_fixture.DashboardRedesignTests.app

    def window(self, callbacks=()):
        window = dashboard_fixture.DashboardRedesignTests.window(self, callbacks)
        window.show_page("settings")
        return window

    def test_sidebar_follows_raised_header_edge_without_moving_content(self):
        window = self.window()
        for size in ((1200, 800), (1536, 1024), (1000, 800), (1200, 800)):
            window.resize(*size)
            for group in ("SERVER", "STATIONS", "PEGO", "LAUNCHER"):
                window._render_settings_group(group)
                QTest.qWait(40)
                header = window.settings_breadcrumb
                sidebar = header.sidebar
                header_bottom = header.mapTo(window, QPoint()).y() + header.height()
                sidebar_top = sidebar.mapTo(window, QPoint()).y()
                content_top = window.settings_form_area.mapTo(window, QPoint()).y()
                self.assertEqual(content_top - header_bottom, 12)
                self.assertEqual(sidebar_top - (header_bottom - header.bottom_lip), 12)
                self.assertEqual(content_top - sidebar_top, header.bottom_lip)
                self.assertEqual(sidebar.width(), 164)
                self.assertEqual(sidebar.layout().spacing(), 6)
                self.assertEqual(
                    sidebar_top + sidebar.height(),
                    content_top + window.settings_form_area.height(),
                )

    def test_fields_geometry_copy_and_capture_callback(self):
        window = self.window(("open_position_render_helper",))
        expected = {
            "SERVER": {"server_number", "ping", "singleplayer"},
            "STATIONS": {
                "bed_spawn",
                "station_yaw",
                "iguanadon",
                "iguanadon_seed_throw_amount",
                "berry_station",
                "berry_type",
                "time_to_reberry",
                "external_berry",
            },
        }
        for size in ((1200, 800), (1536, 1024), (1920, 1080), (2560, 1440)):
            window.resize(*size)
            for group, keys in expected.items():
                window._render_settings_group(group)
                QTest.qWait(30)
                self.assertEqual(set(window.fields), keys)
                self.assertEqual(
                    window.settings_breadcrumb.title.text(), f"SETTINGS  >  {group}"
                )
                headers = window.settings_form.findChildren(SettingsSectionHeader)
                self.assertEqual(
                    [h.height() for h in headers],
                    [104] * (1 if group == "SERVER" else 3),
                )
                self.assertEqual(window.template_selector.height(), 44)
                self.assertFalse(window.settings_form.findChildren(QComboBox))
                self.assertEqual(
                    window.settings_form_area.horizontalScrollBar().maximum(), 0
                )
                for field in window.fields.values():
                    if isinstance(field, QLineEdit):
                        self.assertEqual(field.height(), 44)
                if group == "STATIONS":
                    button = window.station_yaw_capture_button
                    self.assertEqual((button.width(), button.height()), (44, 44))
                    self.assertEqual(button.text(), "")
                    self.assertEqual(button.toolTip(), "Open position helper")
                    texts = [
                        label.text()
                        for label in window.settings_form.findChildren(QLabel)
                    ]
                    self.assertIn("(s)", texts)
                    self.assertIn(
                        "True if trough is not in render, but far away", texts
                    )
                    self.assertNotIn("Capture from game", texts)
                    self.assertFalse(any("minutes" in text for text in texts))
        window.station_yaw_capture_button.click()
        window.open_position_render_helper.assert_called_once()

    def test_header_profile_applies_group_and_keeps_yaw_local(self):
        window = self.window()
        document, _ = normalize_template(template_document("Saved profile"))
        document["data"]["settings"]["bed_spawn"] = "PROFILEBED"
        document["data"]["settings"]["server_number"] = "9999"
        catalog = TemplateCatalog({"one.json": document, "two.json": document}, {}, {})
        with (
            patch.object(window, "_template_catalog", return_value=catalog),
            patch(
                "source.launcher.pages.settings.save_settings",
                side_effect=copy.deepcopy,
            ) as save,
        ):
            window._render_settings_group("STATIONS")
            yaw = window.fields["station_yaw"].text()
            server = window.settings["server_number"]
            selector = window.template_selector
            self.assertIn("one.json", selector.itemText(selector.findData("one.json")))
            selector.setCurrentIndex(selector.findData("one.json"))
            QTest.qWait(20)
            self.assertEqual(save.call_count, 1)
            self.assertEqual(window.template_selector.currentData(), "one.json")
            self.assertEqual(window.fields["bed_spawn"].text(), "PROFILEBED")
            self.assertFalse(window.fields["bed_spawn"].isEnabled())
            self.assertTrue(window.fields["station_yaw"].isEnabled())
            self.assertTrue(window.station_yaw_capture_button.isEnabled())
            self.assertEqual(window.fields["station_yaw"].text(), yaw)
            self.assertEqual(window.fields["bed_spawn"].height(), 44)
            self.assertEqual(window.settings["server_number"], server)
            window.template_selector.setCurrentIndex(0)
            self.assertEqual(window.fields["bed_spawn"].text(), "PROFILEBED")
            self.assertTrue(window.fields["bed_spawn"].isEnabled())
            self.assertEqual(window.template_selector.currentData(), "")

    def test_missing_mixed_and_navigation_profile_state(self):
        window = self.window()
        with patch.object(
            window, "_template_catalog", return_value=TemplateCatalog({}, {}, {})
        ):
            for key in TEMPLATE_GROUP_REFERENCE_KEYS["SERVER"]:
                window.form_values[key] = "gone.json"
            window._render_settings_group("SERVER")
            self.assertEqual(
                window.template_selector.objectName(), "MissingTemplateSelector"
            )
            self.assertIn("MISSING", window.template_selector.currentText())
            self.assertTrue(window.fields["server_number"].isEnabled())
            window.form_values["ping_template"] = "different.json"
            window._render_settings_group("SERVER")
            self.assertEqual(
                window.template_selector.currentText(), "MIXED ASSIGNMENTS"
            )
            for group in (
                "PEGO",
                "DEDI",
                "GACHA",
                "CRAFT",
                "LAUNCHER",
                "STATIONS",
                "SERVER",
            ):
                window._render_settings_group(group)
                QTest.qWait(10)
                approved = group in {"SERVER", "STATIONS", "LAUNCHER", "PEGO", "DEDI", "CRAFT", "GACHA"}
                self.assertEqual(
                    window.settings_breadcrumb.profile.isHidden(), not approved
                )
                self.assertEqual(
                    any(combo.objectName() != "GachaDestination" for combo in window.settings_form.findChildren(QComboBox)), not approved
                )
                self.assertEqual(
                    bool(window.settings_form.findChildren(SettingsSectionHeader)),
                    approved,
                )

    def test_header_and_footer_actions_reuse_handlers(self):
        names = (
            "import_template_setting",
            "export_template_setting",
            "browse_template_settings",
            "refresh_json_configs",
            "confirm_reset",
        )
        window = self.window(names)
        for group in ("SERVER", "STATIONS", "LAUNCHER"):
            window._render_settings_group(group)
            window.template_import_action.trigger()
            window.template_export_action.trigger()
            window.template_browse_action.trigger()
            window.settings_refresh_button.click()
            window.settings_reset_button.click()
        for name in names:
            self.assertEqual(getattr(window, name).call_count, 3)

    def test_all_editors_autosave_using_existing_validation(self):
        window = self.window()
        # Restore the real persistence method, replacing only the disk boundary.
        window.persist_settings_from_visible_fields = (
            SettingsStateGuiMixin.persist_settings_from_visible_fields.__get__(window)
        )
        with patch("source.launcher.gui_parts.settings_state.save_settings") as save:
            for group in ("SERVER", "STATIONS"):
                window._render_settings_group(group)
                for key, field in window.fields.items():
                    if isinstance(field, QLineEdit):
                        old = window.form_values[key]
                        value = (
                            str(old + 1)
                            if isinstance(old, (int, float))
                            else str(old) + "X"
                        )
                        field.setText(value)
                        field.editingFinished.emit()
                        self.assertEqual(str(window.settings[key]), value)
                        field.returnPressed.emit()
                    else:
                        field.setChecked(not field.isChecked())
                        self.assertEqual(window.settings[key], field.isChecked())
                    self.assertEqual(save.call_args.args[0][key], window.settings[key])
        # Closing the fixture must never write real settings.
        window.persist_settings_from_visible_fields = lambda *args, **kwargs: False

    def test_refresh_and_reset_keep_current_group_and_header_in_sync(self):
        window = self.window(("dialog", "close_external_helpers"))
        window._render_settings_group("STATIONS")
        refreshed = copy.deepcopy(window.settings)
        refreshed["station_yaw"] = 12.5
        module = "source.launcher.pages.settings."
        with ExitStack() as stack:
            stack.enter_context(patch(module + "load_settings", return_value=refreshed))
            for loader, attr in (
                ("load_deposit_config", "deposit_config"),
                ("load_gacha_config", "gacha_config"),
                ("load_gacha_collect_config", "gacha_collect_config"),
                ("load_pego_config", "pego_config"),
                ("load_craft_config", "craft_config"),
            ):
                stack.enter_context(
                    patch(module + loader, return_value=getattr(window, attr, {}))
                )
            stack.enter_context(
                patch.object(
                    window,
                    "_template_catalog",
                    return_value=TemplateCatalog({}, {}, {}),
                )
            )
            stack.enter_context(
                patch(module + "save_settings", side_effect=copy.deepcopy)
            )
            window.settings_refresh_button.click()
            self.assertEqual(window.current_settings_group, "STATIONS")
            self.assertEqual(window.fields["station_yaw"].text(), "12.5")
            self.assertIs(window.settings_breadcrumb.selector, window.template_selector)
            window.close_external_helpers.assert_called_once()
            with (
                patch.object(window, "confirm", return_value=False),
                patch.object(window, "apply_default_template_to_all_groups") as apply,
            ):
                window.settings_reset_button.click()
                apply.assert_not_called()

            def apply_default():
                window.form_values["bed_spawn"] = "RESETBED"
                return True

            with (
                patch.object(window, "confirm", return_value=True),
                patch.object(
                    window,
                    "apply_default_template_to_all_groups",
                    side_effect=apply_default,
                ),
            ):
                window.settings_reset_button.click()
            self.assertEqual(window.fields["bed_spawn"].text(), "RESETBED")
            self.assertEqual(window.fields["station_yaw"].text(), "12.5")
            self.assertIs(window.settings_breadcrumb.selector, window.template_selector)

    def test_import_export_and_browse_preserve_existing_workflow(self):
        window = self.window(("dialog",))
        document, _ = normalize_template(template_document("Imported"))
        module = "source.launcher.pages.settings."
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            destination = Path(directory) / "profile.json"
            stack.enter_context(patch(module + "TEMPLATE_DIRECTORY", Path(directory)))
            stack.enter_context(
                patch(
                    module + "QFileDialog.getOpenFileName",
                    return_value=(str(destination), ""),
                )
            )
            stack.enter_context(
                patch(module + "read_template", return_value=(document, []))
            )
            store = stack.enter_context(
                patch.object(
                    window, "_store_template_with_conflict", return_value=destination
                )
            )
            refresh = stack.enter_context(
                patch.object(window, "_refresh_current_settings_group")
            )
            reveal = stack.enter_context(
                patch.object(window, "_show_exported_template")
            )
            open_url = stack.enter_context(patch(module + "QDesktopServices.openUrl"))
            window.template_import_action.trigger()
            store.assert_called_once_with(document, "profile.json")
            refresh.assert_called_once()
            dialog = stack.enter_context(patch(module + "CyberTextInputDialog"))
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.text_value.return_value = "Exported"
            build = stack.enter_context(
                patch(module + "build_template", return_value=document)
            )
            for loader in (
                "load_deposit_config",
                "load_gacha_config",
                "load_pego_config",
                "load_gacha_collect_config",
                "load_craft_config",
            ):
                stack.enter_context(
                    patch(module + loader, return_value={"isolated": loader})
                )
            window.template_export_action.trigger()
            self.assertEqual(build.call_args.args[1], window.settings)
            self.assertEqual(len(build.call_args.args), 7)
            self.assertEqual(refresh.call_count, 2)
            reveal.assert_called_once_with(destination)
            window.template_browse_action.trigger()
            self.assertEqual(
                Path(open_url.call_args.args[0].toLocalFile()), Path(directory)
            )


if __name__ == "__main__":
    unittest.main()
