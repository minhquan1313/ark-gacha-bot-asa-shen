"""Dedi redesign integration with temporary persistence and inactive automation."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_dashboard_redesign as fixture
from PySide6.QtCore import QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QPushButton,
    QScrollArea,
)
from test_template_settings import template_document

from source.gacha_bot.deposit_config import (
    default_crystal_route,
    default_dedi_item,
    default_general_route,
    default_grindable_route,
    default_vault_item,
    save_deposit_config,
)
from source.launcher.components.dedi_editor import (
    DediPointRow,
    DediRouteEditor,
    GrinderCard,
)
from source.launcher.components.settings_actions import (
    SettingsHoverActions,
    SettingsRowIndex,
)
from source.launcher.components.settings_sections import (
    SettingsSectionCard,
    SettingsSectionHeader,
)
from source.launcher.components.widgets import CyberCheckBox, CyberSwitch
from source.launcher.config.template_settings import TemplateCatalog, normalize_template


class DediRedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.DashboardRedesignTests.setUpClass()

    def window(self):
        """Exercise real JSON saves through an isolated path."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "dedi.json"
        window = fixture.DashboardRedesignTests.window(
            self, ("dialog", "open_deposit_helper")
        )
        config = {}
        for key, factory, teleport in (
            ("depositCrystalData", default_crystal_route, "GACHADEDI1"),
            ("depositGrindableData", default_grindable_route, "GACHAGRIND1"),
            ("depositGeneralData", default_general_route, "GACHACRAFT"),
        ):
            route = factory()
            route["teleport"] = teleport
            route["dedi"]["items"] = [default_dedi_item() for _ in range(3)]
            if "vault" in route:
                route["vault"]["items"] = [default_vault_item()]
            config[key] = [route]
        window.deposit_config = config
        save_deposit_config(config, self.path)
        for module in ("dedi", "settings"):
            p = patch(
                f"source.launcher.pages.{module}.save_deposit_config",
                side_effect=lambda data: save_deposit_config(data, self.path),
            )
            p.start()
            self.addCleanup(p.stop)
        p = patch(
            "source.launcher.pages.settings.save_settings", side_effect=copy.deepcopy
        )
        p.start()
        self.addCleanup(p.stop)
        window.show_page("settings")
        window._render_settings_group("DEDI")
        QTest.qWait(30)
        return window

    def cards(self, window: object):
        """Return live route editors after deferred deletion completes."""
        QTest.qWait(10)
        return window.settings_form.findChildren(DediRouteEditor)

    def field(self, card: DediRouteEditor, key: str):
        """Locate an editor by model key instead of layout position."""
        return next(
            f for f in card.findChildren(QLineEdit) if f.property("dediField") == key
        )

    def button(self, parent: object, caption: str):
        """Find an existing action by its visible label."""
        return next(b for b in parent.findChildren(QPushButton) if b.text() == caption)

    def test_layout_and_screenshots(self):
        window = self.window()
        output = Path(".artifacts/dedi")
        output.mkdir(parents=True, exist_ok=True)
        scale = os.environ.get("QT_SCALE_FACTOR", "1")
        for width, height in ((1200, 800), (1536, 1024), (1920, 1080), (1000, 800)):
            window.resize(width, height)
            cards = self.cards(window)
            for card in cards:
                card.toggle.setChecked(False)
            window.settings_form_area.verticalScrollBar().setValue(0)
            QTest.qWait(70)
            self.assertFalse(window.settings_form.findChildren(QComboBox))
            self.assertEqual(
                [
                    h.height()
                    for h in window.settings_form.findChildren(SettingsSectionHeader)
                ],
                [104] * 3,
            )
            self.assertEqual(
                window.settings_form_area.horizontalScrollBar().maximum(), 0
            )
            self.assertFalse(
                any(
                    b.text() in ("[B]", "Copy", "COPY")
                    for b in window.settings_form.findChildren(QPushButton)
                )
            )
            window.grab().save(str(output / f"overview-{width}x{height}-{scale}.png"))
            for card in cards:
                down_icon = card.toggle.icon().cacheKey()
                card.toggle.setChecked(True)
                self.assertNotEqual(card.toggle.icon().cacheKey(), down_icon)
                QTest.qWait(40)
                for segment in (card.interval, card.points):
                    for label in (segment.caption, segment.value):
                        self.assertGreaterEqual(
                            label.width(),
                            label.fontMetrics().horizontalAdvance(label.text()),
                        )
                window.settings_form_area.ensureWidgetVisible(card, 0, 0)
                window.settings_form_area.verticalScrollBar().setValue(
                    card.mapTo(window.settings_form, card.rect().topLeft()).y() - 120
                )
                QTest.qWait(40)
                window.grab().save(
                    str(output / f"{card.kind}-{width}x{height}-{scale}.png")
                )
                self.assertEqual(
                    window.settings_form_area.horizontalScrollBar().maximum(), 0
                )
                self.assertTrue(
                    all(f.height() == 44 for f in card.findChildren(QLineEdit))
                )
                if width >= 1200:
                    centers = [
                        widget.geometry().center().y()
                        for widget in (
                            card.toggle,
                            card.title,
                            card.actions,
                            card.metadata,
                        )
                    ]
                    self.assertLessEqual(max(centers) - min(centers), 1)
                    for point in card.findChildren(DediPointRow):
                        groups = point.fields.core.layout()
                        widths = [groups.itemAt(i).widget().width() for i in range(3)]
                        self.assertLessEqual(max(widths) - min(widths), 1)
                        self.assertFalse(point._wrapped)
                        self.assertFalse(point.fields._wrapped)
                        self.assertEqual(point.height(), 64)
                        controls = point.findChildren(QLineEdit) + point.findChildren(
                            CyberCheckBox
                        )
                        positions = [
                            control.mapTo(point, control.rect().center()).y()
                            for control in controls
                        ]
                        self.assertLessEqual(max(positions) - min(positions), 1)
                    grinder = card.findChild(GrinderCard)
                    if grinder:
                        self.assertFalse(grinder._wrapped)
                        self.assertEqual(grinder.available.text(), "Available")
                card.toggle.setChecked(False)
                self.assertEqual(card.toggle.icon().cacheKey(), down_icon)
        window.resize(1536, 1024)
        for card in self.cards(window):
            card.toggle.setChecked(True)
        QTest.qWait(80)
        window.settings_form.grab().save(
            str(output / f"all-expanded-content-{scale}.png")
        )
        self.assertEqual(len(window.settings_form.findChildren(SettingsRowIndex)), 10)

    def test_callbacks_validation_and_expansion(self):
        window = self.window()
        crystal, grindable, general = self.cards(window)
        crystal.toggle.click()
        for key, value in (
            ("teleport", "CHANGED"),
            ("check_on_every_dedi", "3"),
            ("yaw", "12.5"),
            ("pitch", "-7.5"),
            ("items", "metal, fab"),
        ):
            editor = self.field(crystal, key)
            editor.setText(value)
            editor.editingFinished.emit()
        persisted = json.loads(self.path.read_text())["depositCrystalData"][0]
        self.assertEqual(persisted["teleport"], "CHANGED")
        self.assertEqual(persisted["check_on_every_dedi"], 3)
        self.assertEqual(
            persisted["dedi"]["items"][0]["location"], {"yaw": 12.5, "pitch": -7.5}
        )
        self.assertEqual(persisted["vault"]["items"][0]["items"], ["metal", "fab"])
        self.assertEqual(crystal.title.text(), "CHANGED - 4")
        for key, invalid, previous in (
            ("yaw", "bad", "12.5"),
            ("check_on_every_dedi", "0", "3"),
        ):
            editor = self.field(crystal, key)
            editor.setText(invalid)
            editor.editingFinished.emit()
            self.assertEqual(editor.text(), previous)
        crystal.findChildren(CyberCheckBox)[0].click()
        grindable.findChild(CyberSwitch).setChecked(True)
        data = json.loads(self.path.read_text())
        self.assertTrue(data["depositCrystalData"][0]["dedi"]["items"][0]["crouched"])
        self.assertTrue(data["depositGrindableData"][0]["grinder"]["active"])
        self.assertEqual(grindable.points.text(), "4 points")
        for card in (crystal, grindable, general):
            card.actions.menu.actions()[0].trigger()
            window.open_deposit_helper.assert_called_with(card.kind, 0)
        self.button(crystal, "Add dedi").click()
        crystal = self.cards(window)[0]
        self.assertTrue(crystal.toggle.isChecked())
        self.assertEqual(crystal.title.text(), "CHANGED - 5")
        self.button(crystal, "Add vault").click()
        crystal = self.cards(window)[0]
        self.assertEqual(crystal.points.text(), "6 points")
        window.remove_crystal_vault(0, 0)
        window.remove_crystal_dedi(0, 0)
        crystal = self.cards(window)[0]
        self.assertTrue(crystal.toggle.isChecked())
        self.assertEqual(crystal.points.text(), "4 points")
        self.assertNotIn(
            "Add vault",
            [b.text() for b in self.cards(window)[2].findChildren(QPushButton)],
        )

    def test_empty_sections_add_remove_and_long_names(self):
        window = self.window()
        for key in window.deposit_config:
            window.deposit_config[key] = []
        window._render_settings_group("DEDI")
        QTest.qWait(20)
        self.assertFalse(self.cards(window))
        for kind, key in (
            ("crystal", "depositCrystalData"),
            ("grindable", "depositGrindableData"),
            ("general", "depositGeneralData"),
        ):
            getattr(window, f"add_{kind}_route")()
            window.deposit_config[key][0]["teleport"] = kind * 40
        window._render_settings_group("DEDI")
        window.resize(1200, 800)
        QTest.qWait(40)
        self.assertEqual(len(self.cards(window)), 3)
        self.assertEqual(window.settings_form_area.horizontalScrollBar().maximum(), 0)
        for kind in ("crystal", "grindable", "general"):
            getattr(window, f"remove_{kind}_route")(0)
        self.assertFalse(self.cards(window))

    def test_profile_lock_and_craft_isolation(self):
        window = self.window()
        document, _ = normalize_template(template_document("Dedi profile"))
        catalog = TemplateCatalog({"dedi.json": document}, {}, {})
        with patch.object(window, "_template_catalog", return_value=catalog):
            window._render_settings_group("DEDI")
            window.template_selector.setCurrentIndex(
                window.template_selector.findData("dedi.json")
            )
            QTest.qWait(20)
            sections = window.settings_form.findChildren(SettingsSectionCard)
            self.assertTrue(sections)
            self.assertTrue(all(not section.isEnabled() for section in sections))
            self.assertFalse(window.settings_form.findChildren(QComboBox))
            window.template_selector.setCurrentIndex(0)
            QTest.qWait(20)
            self.assertTrue(
                all(
                    s.isEnabled()
                    for s in window.settings_form.findChildren(SettingsSectionCard)
                )
            )
        window._render_settings_group("CRAFT")
        QTest.qWait(20)
        self.assertTrue(all(c.kind == "craft" for c in window.settings_form.findChildren(DediRouteEditor)))
        self.assertFalse(window.settings_form.findChildren(QComboBox))
        window._render_settings_group("DEDI")
        QTest.qWait(20)
        self.assertIs(window.settings_breadcrumb.selector, window.template_selector)
        for hover in window.settings_form.findChildren(SettingsHoverActions):
            self.assertEqual(
                [action.text() for action in hover.menu.actions()], ["Add route"]
            )

    def test_large_list_hover_and_child_actions(self):
        """Keep large collections on the page scroll and preserve reserved actions."""
        window = self.window()
        for kind in ("grindable", "general"):
            getattr(window, f"add_{kind}_dedi")(0)
            getattr(window, f"remove_{kind}_dedi")(0, 0)
        route = window.deposit_config["depositGeneralData"][0]
        route["dedi"]["items"] = [default_dedi_item() for _ in range(100)]
        window._render_settings_group("DEDI")
        general = self.cards(window)[2]
        general.toggle.click()
        window.resize(1000, 800)
        QTest.qWait(60)
        self.assertEqual(general.points.text(), "100 points")
        self.assertFalse(general.findChildren(QScrollArea))
        self.assertEqual(window.settings_form_area.horizontalScrollBar().maximum(), 0)
        self.assertEqual(general.findChildren(SettingsRowIndex)[-1].text(), "100")
        hover = window.settings_form.findChildren(SettingsHoverActions)[0]
        QApplication.sendEvent(hover.section, QEvent(QEvent.Type.Leave))
        geometry = hover.geometry()
        self.assertTrue(hover.stack.currentWidget().isHidden())
        QApplication.sendEvent(hover.section, QEvent(QEvent.Type.Enter))
        self.assertFalse(hover.stack.currentWidget().isHidden())
        self.assertEqual(hover.geometry(), geometry)
        QApplication.sendEvent(hover.section, QEvent(QEvent.Type.Leave))
        hover.setFocus()
        QTest.qWait(10)
        self.assertFalse(hover.stack.currentWidget().isHidden())
        self.assertEqual(hover.geometry(), geometry)


if __name__ == "__main__":
    unittest.main()
