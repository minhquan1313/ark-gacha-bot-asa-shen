"""Pego presentation and action integration with isolated persistence."""

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import test_dashboard_redesign as fixture
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QPushButton
from test_template_settings import template_document

from source.launcher.components.settings_actions import (
    SettingsEntryRow,
    SettingsHoverActions,
    SettingsRowIndex,
)
from source.launcher.components.settings_sections import SettingsSectionHeader
from source.launcher.config.constants import ASSETS, TEMPLATE_GROUP_REFERENCE_KEYS
from source.launcher.config.station_config import (
    default_pego_entry,
    load_pego_config,
    save_pego_config,
)
from source.launcher.config.template_settings import TemplateCatalog, normalize_template


class PegoRedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.DashboardRedesignTests.setUpClass()

    def window(self, count: int = 5):
        """Use real JSON validation and writes exclusively in a temporary directory."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "pego.json"
        window = fixture.DashboardRedesignTests.window(
            self, ("dialog", "confirm", "copy_text")
        )
        window.pego_config = [default_pego_entry(i + 1) for i in range(count)]
        window.gacha_config = [{"name": "gacha1"}]
        save_pego_config(window.pego_config, self.path)
        for module in ("pego", "settings"):
            patcher = patch(
                f"source.launcher.pages.{module}.save_pego_config",
                side_effect=lambda entries: save_pego_config(entries, self.path),
            )
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch(
            "source.launcher.pages.settings.save_settings", side_effect=copy.deepcopy
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        window.show_page("settings")
        window._render_settings_group("PEGO")
        QTest.qWait(30)
        return window

    def button(self, window: object, text: str):
        """Find a live Pego action by its visible caption."""
        return next(
            b
            for b in window.settings_form.findChildren(QPushButton)
            if b.text() == text
        )

    def editor(self, window: object, title: str):
        """Find a current entry editor without relying on layout indices."""
        return next(
            f
            for f in window.settings_form.findChildren(QLineEdit)
            if f.accessibleName() == f"Pego 1 {title}"
        )

    def test_geometry_counts_artwork_and_capture(self):
        window = self.window()
        output = Path(".artifacts/pego")
        output.mkdir(parents=True, exist_ok=True)
        for count in (0, 1, 5, 30):
            window.pego_config = [default_pego_entry(i + 1) for i in range(count)]
            for width, height in (
                (1200, 800),
                (1536, 1024),
                (1920, 1080),
                (2560, 1440),
            ):
                window.resize(width, height)
                window._render_settings_group("PEGO")
                QTest.qWait(45)
                labels = [
                    label.text() for label in window.settings_form.findChildren(QLabel)
                ]
                self.assertIn(f"Pego ({count})", labels)
                self.assertIn("Pego delays", labels)
                self.assertNotIn("COPY ALL", labels)
                self.assertEqual(
                    [
                        h.height()
                        for h in window.settings_form.findChildren(
                            SettingsSectionHeader
                        )
                    ],
                    [104, 104],
                )
                self.assertFalse(window.settings_form.findChildren(QComboBox))
                self.assertEqual(
                    window.settings_form_area.horizontalScrollBar().maximum(), 0
                )
                self.assertEqual(
                    self.button(window, "Delete all").isEnabled(), bool(count)
                )
                for field in window.settings_form.findChildren(QLineEdit):
                    self.assertEqual(field.height(), 44)
                for entry in window.settings_form.findChildren(SettingsEntryRow):
                    fields_layout = entry.middle.layout()
                    widths = [fields_layout.itemAt(i).widget().width() for i in range(2)]
                    self.assertLessEqual(max(widths) - min(widths), 1)
                for index in range(count):
                    self.assertIn(f"{index + 1:02d}", labels)
                if count == 5:
                    scale = os.environ.get("QT_SCALE_FACTOR", "1")
                    window.grab().save(
                        str(output / f"pego-{width}x{height}-{scale}.png")
                    )
        for group in (
            "SERVER",
            "STATIONS",
            "PEGO",
            "DEDI",
            "GACHA",
            "CRAFT",
            "LAUNCHER",
        ):
            self.assertIn(f"settings.breadcrumb.{group.lower()}", ASSETS)
            window.settings_breadcrumb.set_group(group)
            self.assertEqual(window.settings_breadcrumb.bottom_lip, 12)
            self.assertEqual(
                window.settings_breadcrumb.cover_asset, ASSETS["settings.breadcrumb"]
            )

    def test_edit_copy_validation_bulk_and_collection_actions(self):
        window = self.window(1)
        for title, value in (
            ("Teleporter", "NEW_TELEPORT"),
            ("Delay", "432"),
        ):
            field = self.editor(window, title)
            field.setText(value)
            field.editingFinished.emit()
        self.assertEqual(
            load_pego_config(self.path)[0],
            {"teleporter": "NEW_TELEPORT", "delay": 432},
        )
        field = self.editor(window, "Delay")
        field.setText("invalid")
        field.editingFinished.emit()
        self.assertEqual(field.text(), "432")
        window.pego_bulk_delay_field.setText("99")
        self.button(window, "Set all delays").click()
        self.assertEqual(load_pego_config(self.path)[0]["delay"], 99)
        self.button(window, "Add Pego").click()
        self.assertEqual(len(load_pego_config(self.path)), 2)
        self.assertEqual(window.pego_config[-1]["delay"], 99)
        window.remove_pego(0)
        self.assertEqual(len(load_pego_config(self.path)), 1)
        window.confirm.return_value = False
        self.button(window, "Delete all").click()
        self.assertEqual(len(window.pego_config), 1)
        window.confirm.return_value = True
        self.button(window, "Delete all").click()
        self.assertEqual(load_pego_config(self.path), [])

    def test_calculator_and_always_visible_entries(self):
        window = self.window()
        self.button(window, "Calculator").click()
        self.assertTrue(window.pego_calculator_expanded)
        for field, value in zip(
            window._pego_calculator_fields(),
            ("3000", "5", "10", "2", "10"),
            strict=True,
        ):
            field.setText(value)
            field.editingFinished.emit()
        recommendation = window._pego_delay_recommendation()
        self.button(window, "Apply").click()
        self.assertTrue(
            all(
                entry["delay"] == recommendation
                for entry in load_pego_config(self.path)
            )
        )
        self.assertTrue(self.button(window, "Calculator").isChecked())
        self.button(window, "Reset").click()
        self.assertEqual(window.pego_calc_pego_count_field.text(), "5")
        window.pego_section_expanded = False
        window._render_settings_group("PEGO")
        QTest.qWait(20)
        self.assertFalse(
            any(
                b.toolTip() == "Expand or collapse Pego entries"
                for b in window.settings_form.findChildren(QPushButton)
            )
        )
        self.assertTrue(self.button(window, "Add Pego").isVisible())
        window.pego_calc_target_field.setText("bad")
        self.assertIsNone(window.update_pego_delay_recommendation(False))

    def test_missing_profile_and_page_specific_art_slot(self):
        window = self.window(1)
        for key in TEMPLATE_GROUP_REFERENCE_KEYS["PEGO"]:
            window.form_values[key] = "missing.json"
        with patch.object(
            window, "_template_catalog", return_value=TemplateCatalog({}, {}, {})
        ):
            window._render_settings_group("PEGO")
            QTest.qWait(20)
            self.assertIn("MISSING", window.template_selector.currentText())
            self.assertTrue(self.editor(window, "Teleporter").isEnabled())
            self.assertFalse(window.settings_form.findChildren(QComboBox))
        with patch.dict(ASSETS, {"settings.breadcrumb.pego": ASSETS["settings.berry"]}):
            window.settings_breadcrumb.set_group("PEGO")
            self.assertEqual(
                window.settings_breadcrumb.cover_asset, ASSETS["settings.berry"]
            )

    def test_sidebar_aligned_drop_and_decorated_indices(self):
        window = self.window(3)
        header = window.settings_breadcrumb
        for width in (1200, 1536, 1000):
            window.resize(width, 800)
            QTest.qWait(30)
            boundary = header.sidebar.mapToGlobal(QPoint(header.sidebar.width(), 0)).x()
            self.assertEqual(
                header.mapToGlobal(QPoint()).x() + header.cover_drop_start(), boundary
            )
            self.assertEqual(header.height(), 174 if header.width() < 960 else 112)
        header.sidebar.setFixedWidth(180)
        QTest.qWait(30)
        self.assertEqual(header.cover_drop_start(), 180)
        indices = window.settings_form.findChildren(SettingsRowIndex)
        self.assertEqual([index.text() for index in indices], ["01", "02", "03"])
        for index in indices:
            self.assertEqual((index.width(), index.height()), (34, 44))
        window.remove_pego(0)
        QTest.qWait(20)
        self.assertEqual(
            [
                index.text()
                for index in window.settings_form.findChildren(SettingsRowIndex)
            ],
            ["01", "02"],
        )
        badge = SettingsRowIndex(100)
        self.addCleanup(badge.close)
        self.assertEqual(badge.text(), "101")
        badge.show()
        QTest.qWait(10)
        image = badge.grab().toImage()
        ratio = badge.devicePixelRatioF()
        line = image.pixelColor(int(1.5 * ratio), round(10 * ratio))
        background = image.pixelColor(round(5 * ratio), round(10 * ratio))
        fill = image.pixelColor(round(20 * ratio), round(15 * ratio))
        self.assertNotEqual(line, background)
        self.assertNotEqual(fill, background)

    def test_header_profile_lock_and_manual(self):
        window = self.window()
        document, _ = normalize_template(template_document("Pego profile"))
        catalog = TemplateCatalog(
            templates={"Pego.json": document}, paths={}, errors={}
        )
        with patch.object(window, "_template_catalog", return_value=catalog):
            window._render_settings_group("PEGO")
            selector = window.settings_breadcrumb.selector
            selector.setCurrentIndex(selector.findData("Pego.json"))
            QTest.qWait(20)
            self.assertFalse(self.editor(window, "Teleporter").isEnabled())
            self.assertFalse(window.settings_form.findChildren(QComboBox))
            self.assertEqual(window.pego_config, document["data"]["pego"])
            selector = window.settings_breadcrumb.selector
            selector.setCurrentIndex(selector.findData(""))
            QTest.qWait(20)
            self.assertTrue(self.editor(window, "Teleporter").isEnabled())

    def test_pinned_actions_and_single_row_at_every_width(self):
        window = self.window(1)
        row = window.settings_form.findChild(SettingsEntryRow)
        original = self.editor(window, "Teleporter")
        original.setText("LIVE_EDIT")
        for width in (1050, 740, 620, 350, 140, 1050):
            row.setFixedWidth(width)
            QTest.qWait(30)
            compact = row.actions.stack.currentWidget() == row.actions.overflow
            if width <= 350:
                self.assertTrue(compact)
            if width == 1050:
                self.assertFalse(compact)
            action = row.actions.overflow if compact else row.actions.inline
            self.assertLessEqual(
                action.mapTo(row, QPoint(action.width(), 0)).x(), row.width()
            )
            self.assertEqual(
                original.mapTo(row, QPoint()).y(), action.mapTo(row, QPoint()).y()
            )
            self.assertEqual(original.text(), "LIVE_EDIT")
            self.assertIs(self.editor(window, "Teleporter"), original)
            if width <= 350:
                self.assertGreater(row.scroll.horizontalScrollBar().maximum(), 0)
                right = action.mapTo(row, QPoint()).x()
                row.scroll.horizontalScrollBar().setValue(
                    row.scroll.horizontalScrollBar().maximum()
                )
                self.assertEqual(action.mapTo(row, QPoint()).x(), right)
        row.setFixedWidth(350)
        QTest.qWait(20)
        row.actions.open_menu()
        QTest.qWait(10)
        self.assertEqual(
            [action.text() for action in row.actions.menu.actions()], ["Delete"]
        )
        row.setFixedWidth(1050)
        QTest.qWait(20)
        self.assertTrue(row.actions.menu.isVisible())
        remove_pego = window.remove_pego
        window.remove_pego = Mock()
        row.actions.menu.actions()[0].trigger()
        window.remove_pego.assert_called_once_with(0)
        row.actions.menu.close()
        QTest.qWait(20)
        self.assertIs(row.actions.stack.currentWidget(), row.actions.inline)
        window.remove_pego = remove_pego
        row.actions.menu.actions()[0].trigger()
        self.assertEqual(load_pego_config(self.path), [])

    def test_hover_actions_reserve_geometry_and_support_keyboard(self):
        window = self.window(1)
        hover = window.settings_form.findChild(SettingsHoverActions)
        window.setFocus()
        QApplication.sendEvent(hover.section, QEvent(QEvent.Type.Leave))
        QTest.qWait(10)
        before = [
            child.geometry() for child in hover.section.header.findChildren(QLabel)
        ]
        geometry = hover.geometry()
        self.assertFalse(hover.stack.currentWidget().isVisible())
        QApplication.sendEvent(hover.section, QEvent(QEvent.Type.Enter))
        self.assertTrue(hover.stack.currentWidget().isVisible())
        self.assertEqual(
            before,
            [child.geometry() for child in hover.section.header.findChildren(QLabel)],
        )
        self.assertEqual(geometry, hover.geometry())
        QApplication.sendEvent(hover.section, QEvent(QEvent.Type.Leave))
        self.assertFalse(hover.stack.currentWidget().isVisible())
        hover.setFocus(Qt.FocusReason.TabFocusReason)
        self.assertTrue(hover.stack.currentWidget().isVisible())
        QTest.keyClick(hover, Qt.Key.Key_Return)
        self.assertTrue(hover.menu.isVisible())
        window.confirm.return_value = False
        hover.menu.actions()[0].trigger()
        self.assertEqual(len(window.pego_config), 1)
        hover.menu.close()


if __name__ == "__main__":
    unittest.main()
