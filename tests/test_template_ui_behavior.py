import copy
import os
import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, call, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFrame,
    QGridLayout,
    QLabel,
    QToolButton,
    QWidget,
)
from test_template_settings import template_document  # noqa: E402

from source.launcher.config.constants import (  # noqa: E402
    DEFAULT_SETTINGS,
    TEMPLATE_REFERENCE_DEFAULTS,
)
from source.launcher.config.template_settings import (  # noqa: E402
    DEFAULT_TEMPLATE_FILENAME,
    TemplateCatalog,
    normalize_template,
)
from source.launcher.pages import LauncherPagesMixin  # noqa: E402
from source.launcher.position_render_helper import PositionRenderHelper  # noqa: E402


class TemplateUiBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def launcher(self, catalog: TemplateCatalog) -> SimpleNamespace:
        settings = DEFAULT_SETTINGS | TEMPLATE_REFERENCE_DEFAULTS
        launcher = SimpleNamespace(
            settings=copy.deepcopy(settings),
            form_values=copy.deepcopy(settings),
            _template_catalog=Mock(return_value=catalog),
            _render_settings_group=Mock(),
            _update_auto_start_switch=Mock(),
            append_log=Mock(),
            dialog=Mock(),
        )
        launcher._set_group_template_references = MethodType(
            LauncherPagesMixin._set_group_template_references, launcher
        )
        launcher.change_template_group = MethodType(
            LauncherPagesMixin.change_template_group, launcher
        )
        launcher._template_group_state = MethodType(
            LauncherPagesMixin._template_group_state, launcher
        )
        launcher.sync_configured_templates = MethodType(
            LauncherPagesMixin.sync_configured_templates, launcher
        )
        return launcher

    def test_server_template_updates_only_server_values_and_references(self) -> None:
        template, _warnings = normalize_template(template_document("Template A"))
        template["data"]["settings"]["lag_offset"] = 2.5
        template["data"]["settings"]["server_number"] = "777"
        catalog = TemplateCatalog(
            templates={"Template_A.json": template}, paths={}, errors={}
        )
        launcher = self.launcher(catalog)

        with patch(
            "source.launcher.pages.settings.save_settings", side_effect=copy.deepcopy
        ):
            result = launcher.change_template_group("SERVER", "Template_A.json")

        self.assertTrue(result)
        self.assertEqual(launcher.settings["lag_offset"], 2.5)
        self.assertEqual(launcher.settings["server_number"], "777")
        self.assertEqual(launcher.settings["lag_offset_template"], "Template_A.json")
        self.assertEqual(launcher.settings["singleplayer_template"], "Template_A.json")
        self.assertEqual(launcher.settings["auto_start_program_template"], "")
        self.assertEqual(launcher.settings["iguanadon_template"], "")
        self.assertEqual(
            launcher.settings["station_yaw"], DEFAULT_SETTINGS["station_yaw"]
        )

    def test_switching_to_manual_retains_last_applied_values(self) -> None:
        launcher = self.launcher(TemplateCatalog({}, {}, {}))
        launcher.settings["lag_offset"] = 2.5
        launcher.settings["lag_offset_template"] = "Template_A.json"
        launcher.form_values = launcher.settings.copy()

        with patch(
            "source.launcher.pages.settings.save_settings", side_effect=copy.deepcopy
        ):
            result = launcher.change_template_group("SERVER", "")

        self.assertTrue(result)
        self.assertEqual(launcher.settings["lag_offset"], 2.5)
        self.assertEqual(launcher.settings["lag_offset_template"], "")

    def test_missing_template_reference_is_preserved_as_warning_state(self) -> None:
        catalog = TemplateCatalog(
            {}, {}, {"Gone.json": "Unsupported template version: 2."}
        )
        launcher = self.launcher(catalog)
        for key in (
            "lag_offset_template",
            "server_number_template",
            "singleplayer_template",
        ):
            launcher.form_values[key] = "Gone.json"

        state = launcher._template_group_state("SERVER")

        self.assertEqual(
            state,
            ("missing", "Gone.json", "Unsupported template version: 2."),
        )
        self.assertEqual(launcher.form_values["lag_offset_template"], "Gone.json")
        self.assertEqual(launcher.form_values["singleplayer_template"], "Gone.json")

    def test_startup_sync_reapplies_valid_references_and_skips_missing(self) -> None:
        template, _warnings = normalize_template(template_document("Template A"))
        catalog = TemplateCatalog(
            {"Template_A.json": template}, {}, {"Gone.json": "missing"}
        )
        launcher = self.launcher(catalog)
        for key in (
            "lag_offset_template",
            "server_number_template",
            "singleplayer_template",
        ):
            launcher.settings[key] = "Template_A.json"
        launcher.settings["dedis_template"] = "Gone.json"
        launcher.change_template_group = Mock(return_value=True)

        launcher.sync_configured_templates()

        launcher.change_template_group.assert_called_once_with(
            "SERVER", "Template_A.json"
        )

    def test_default_template_reset_applies_canonical_filename_to_every_group(
        self,
    ) -> None:
        launcher = SimpleNamespace(
            settings=DEFAULT_SETTINGS | TEMPLATE_REFERENCE_DEFAULTS,
            change_template_group=Mock(return_value=True),
        )
        launcher.apply_default_template_to_all_groups = MethodType(
            LauncherPagesMixin.apply_default_template_to_all_groups, launcher
        )

        with (
            patch("source.launcher.pages.settings.load_deposit_config", return_value={}),
            patch("source.launcher.pages.settings.load_gacha_config", return_value=[]),
            patch("source.launcher.pages.settings.load_pego_config", return_value=[]),
        ):
            result = launcher.apply_default_template_to_all_groups()

        self.assertTrue(result)
        launcher.change_template_group.assert_has_calls(
            [
                call(group_name, DEFAULT_TEMPLATE_FILENAME)
                for group_name in (
                    "SERVER",
                    "STATIONS",
                    "PEGO",
                    "DEDI",
                    "GACHA",
                    "LAUNCHER",
                )
            ]
        )
        self.assertEqual(launcher.change_template_group.call_count, 6)

    def test_template_action_split_button_keeps_import_as_default(self) -> None:
        launcher = SimpleNamespace(
            import_template_setting=Mock(),
            export_template_setting=Mock(),
            browse_template_settings=Mock(),
        )
        launcher._template_action_split_button = MethodType(
            LauncherPagesMixin._template_action_split_button, launcher
        )

        button = launcher._template_action_split_button()
        menu_actions = button.menu().actions()

        self.assertEqual(button.popupMode(), QToolButton.MenuButtonPopup)
        self.assertEqual(button.defaultAction().text(), "IMPORT")
        self.assertEqual(
            [action.text() for action in menu_actions],
            ["EXPORT TEMPLATE", "BROWSE TEMPLATE FOLDER"],
        )
        button.defaultAction().trigger()
        menu_actions[0].trigger()
        menu_actions[1].trigger()
        launcher.import_template_setting.assert_called_once()
        launcher.export_template_setting.assert_called_once()
        launcher.browse_template_settings.assert_called_once()

    def test_selector_displays_names_but_stores_filename_ids(self) -> None:
        catalog = TemplateCatalog(
            {
                "first.json": template_document("Duplicate"),
                "second.json": template_document("Duplicate"),
            },
            {},
            {},
        )
        container = QWidget()
        launcher = SimpleNamespace(
            form_values=DEFAULT_SETTINGS | TEMPLATE_REFERENCE_DEFAULTS,
            settings_form_layout=QGridLayout(container),
            _template_catalog=Mock(return_value=catalog),
            change_template_group=Mock(),
        )
        launcher._template_group_state = MethodType(
            LauncherPagesMixin._template_group_state, launcher
        )
        launcher._add_template_selector = MethodType(
            LauncherPagesMixin._add_template_selector, launcher
        )

        launcher._add_template_selector("SERVER")
        selector = launcher.template_selector

        self.assertEqual(selector.itemText(1), "Duplicate — first.json")
        self.assertEqual(selector.itemData(1), "first.json")
        self.assertEqual(selector.itemText(2), "Duplicate — second.json")
        self.assertEqual(selector.itemData(2), "second.json")

    def test_position_render_helper_builds_one_station_yaw_row(self) -> None:
        owner = SimpleNamespace(
            settings=copy.deepcopy(DEFAULT_SETTINGS),
            form_values=copy.deepcopy(DEFAULT_SETTINGS),
            fields={},
            styleSheet=Mock(return_value=""),
            require_ark_window=Mock(return_value=False),
            last_ark_window_error="missing",
            persist_settings_from_visible_fields=Mock(),
            _render_settings_group=Mock(),
        )

        helper = PositionRenderHelper(owner)
        helper.guide_timer.stop()
        try:
            rows = [
                frame
                for frame in helper.findChildren(QFrame)
                if frame.objectName() == "HelperRow"
            ]
            labels = [
                label.text()
                for label in helper.findChildren(QLabel)
                if label.objectName() == "HelperRowSummary"
            ]

            self.assertEqual(len(rows), 1)
            self.assertIn("Station yaw", labels)
        finally:
            helper.close()


if __name__ == "__main__":
    unittest.main()
