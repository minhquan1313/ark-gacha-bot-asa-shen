"""Real Gacha edits and renders with isolated persistence and no automation."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_dashboard_redesign as fixture
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QComboBox, QPushButton, QWidget
from test_template_settings import template_document

from source.gacha_bot.deposit_config import default_dedi_item, default_general_route
from source.launcher.components.gacha_editor import GachaSideCard
from source.launcher.components.settings_actions import SettingsHoverActions
from source.launcher.components.settings_sections import SettingsField, SettingsSectionCard
from source.launcher.config.station_config import default_gacha_collect_entry, default_gacha_entry, save_gacha_collect_config, save_gacha_config
from source.launcher.config.template_settings import TemplateCatalog, normalize_template


class GachaRedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.DashboardRedesignTests.setUpClass()

    def window(self):
        """Patch persistence only; use actual page widgets and save normalization."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)
        window = fixture.DashboardRedesignTests.window(self, ("dialog", "confirm"))
        # Replace the base close cleanup with disposal while save patches are active.
        self._cleanups.pop()
        window.confirm.return_value = True
        window.gacha_config = [default_gacha_entry("GACHA1", "left"), default_gacha_entry("GACHA1", "right"), default_gacha_entry("GACHA2", "left")]
        window.gacha_collect_config = [default_gacha_collect_entry("COLLECT1", "left", "paste")]
        window.gacha_collect_config[0]["dedi_teleport"] = "STORE1"
        routes = []
        for name in ("STORE1", "STORE2"):
            route = default_general_route()
            route["teleport"] = name
            route["dedi"]["items"] = [default_dedi_item()]
            routes.append(route)
        window.deposit_config = {"depositCrystalData": [], "depositGrindableData": [], "depositGeneralData": routes}
        patches = [
            patch("source.launcher.pages.gacha.load_deposit_config", return_value=window.deposit_config),
            patch("source.launcher.pages.gacha.save_gacha_config", side_effect=lambda data: save_gacha_config(data, self.path / "gacha.json")),
            patch("source.launcher.pages.gacha.save_gacha_collect_config", side_effect=lambda data: save_gacha_collect_config(data, self.path / "collect.json")),
            patch("source.launcher.pages.settings.save_settings", side_effect=copy.deepcopy),
            patch("source.launcher.pages.gacha.save_settings", side_effect=copy.deepcopy),
            patch("source.launcher.pages.settings.save_gacha_config", side_effect=lambda data: save_gacha_config(data, self.path / "gacha.json")),
            patch("source.launcher.pages.settings.save_gacha_collect_config", side_effect=lambda data: save_gacha_collect_config(data, self.path / "collect.json")),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        def dispose():
            """Destroy live editors before restoring real persistence functions."""
            window.close()
            window.deleteLater()
            QTest.qWait(20)
        self.addCleanup(dispose)
        window.show_page("settings")
        window._render_settings_group("GACHA")
        QTest.qWait(60)
        return window

    def cards(self, window: QWidget):
        """Return current cards after deleted form widgets have been released."""
        QTest.qWait(20)
        return window.settings_form.findChildren(GachaSideCard)

    def test_layout_and_captures(self):
        window = self.window()
        output = Path(".artifacts/gacha")
        output.mkdir(parents=True, exist_ok=True)
        scale = os.environ.get("QT_SCALE_FACTOR", "1")
        for width, height in ((1200, 800), (1536, 1024)):
            window.resize(width, height)
            QTest.qWait(80)
            cards = self.cards(window)
            self.assertEqual(len(cards), 6)
            for left, right in zip(cards[::2], cards[1::2], strict=True):
                self.assertEqual(left.y(), right.y())
                self.assertLessEqual(abs(left.width() - right.width()), 1)
                self.assertGreater(left.width(), 240)
                self.assertLessEqual(abs(left.height() - left.width() / 4), 1)
            self.assertEqual(window.settings_form_area.horizontalScrollBar().maximum(), 0)
            combos = window.settings_form.findChildren(QComboBox)
            self.assertEqual(len(combos), 1)
            self.assertTrue(all(c.objectName() == "GachaDestination" for c in combos))
            window.settings_form_area.verticalScrollBar().setValue(0)
            window.grab().save(str(output / f"gacha-{width}x{height}-{scale}.png"))
            window.settings_form_area.ensureWidgetVisible(cards[-1])
            QTest.qWait(40)
            window.grab().save(str(output / f"collect-{width}x{height}-{scale}.png"))
        window.settings_form.grab().save(str(output / f"full-{scale}.png"))
        self.assertTrue(window.settings_breadcrumb.profile.isVisible())
        self.assertEqual(len(window.settings_form.findChildren(SettingsSectionCard)), 2)

    def test_collapsed_bounds_reset_and_collect_focus(self):
        window = self.window()
        output = Path(".artifacts/gacha")
        output.mkdir(parents=True, exist_ok=True)
        scale = os.environ.get("QT_SCALE_FACTOR", "1")
        for size in ((1200, 800), (1536, 1024)):
            window.resize(*size)
            for button in window.settings_form.findChildren(QPushButton):
                if button.accessibleName().startswith("Expand Gacha"):
                    button.setChecked(False)
            QTest.qWait(60)
            for section in window.settings_form.findChildren(SettingsSectionCard):
                self.assertEqual(section.height(), section.header.height() + 4)
            window.grab().save(str(output / f"collapsed-{size[0]}x{size[1]}-{scale}.png"))
        before = copy.deepcopy(window.gacha_config)
        with patch("source.launcher.pages.gacha.save_gacha_collect_config", side_effect=OSError("disk unavailable")):
            window.reset_gacha_config()
        self.assertEqual(window.gacha_config, before)
        self.assertEqual(json.loads((self.path / "gacha.json").read_text()), before)
        window.confirm_reset()
        self.assertEqual(window.gacha_config, [])
        self.assertEqual(window.gacha_collect_config, [])
        window.add_gacha_group("collect")
        self.cards(window)
        self.assertEqual(window.gacha_collect_config, [{"teleporter": "", "side": "left", "item": "", "dedi_teleport": ""}])
        self.assertTrue(window._gacha_teleport_fields[("collect", "")].hasFocus())
        window.add_gacha_group("collect")
        self.assertEqual(len(window.gacha_collect_config), 1)

    def test_resizing_preserves_editors_and_scrolls_only_fields(self):
        from PySide6.QtWidgets import QScrollArea
        window = self.window()
        entry = window._gacha_collect_editors["COLLECT1"]
        editor = entry.item
        editor.setFocus()
        QTest.keyClicks(editor, "draft")
        text = editor.text()
        for width in (1536, 1200, 1000, 1536, 1200):
            window.resize(width, 800)
            QTest.qWait(40)
            self.assertIs(window._gacha_collect_editors["COLLECT1"].item, editor)
            self.assertEqual(editor.text(), text)
            self.assertTrue(editor.hasFocus())
        # Exercise the repeated entry independently at an unusually narrow width.
        entry.setFixedWidth(300)
        QTest.qWait(40)
        scroller = entry.findChildren(QScrollArea)[1]
        self.assertGreater(scroller.horizontalScrollBar().maximum(), 0)
        delete = next(b for b in entry.findChildren(QPushButton) if b.toolTip() == "Delete teleport station")
        self.assertLessEqual(delete.x() + delete.width(), entry.width())
        self.assertEqual(delete.width(), 44)

    def test_natural_labels_three_rows_and_styled_font_changes(self):
        from PySide6.QtCore import QPoint
        window = self.window()
        entry = window._gacha_collect_editors["COLLECT1"]
        teleport = window._gacha_teleport_fields[("collect", "COLLECT1")]
        previous = 0
        for width in (1200, 1536):
            window.resize(width, 800)
            QTest.qWait(50)
            for field in window.settings_form.findChildren(SettingsField):
                self.assertGreaterEqual(field.label.width(), field.label.sizeHint().width())
            top = teleport.mapTo(entry, QPoint(0, 0)).y()
            second = entry.item.mapTo(entry, QPoint(0, 0)).y()
            self.assertGreater(second, top)
            self.assertEqual(second, entry.destination.mapTo(entry, QPoint(0, 0)).y())
            self.assertGreater(self.cards(window)[-1].mapTo(entry, QPoint(0, 0)).y(), second)
            self.assertGreater(teleport.width(), previous)
            previous = teleport.width()
            item_group = entry.item.parentWidget()
            dedi_group = entry.destination.parentWidget()
            self.assertLessEqual(abs(item_group.width() - dedi_group.width()), 1)
        label = teleport.parentWidget().label
        label.setStyleSheet("font-size: 22px; font-weight: bold;")
        QTest.qWait(30)
        self.assertGreaterEqual(label.width(), label.sizeHint().width())

    def test_gradient_painting_and_adjustable_offset(self):
        from PySide6.QtGui import QColor, QPixmap

        from source.launcher import settings_theme
        window = self.window()
        for card in self.cards(window)[:2]:
            white = QPixmap(400, 100)
            white.fill(QColor("white"))
            card.art = white
            card.gray = white
            card._scaled_key = None
            card.set_present(True, animate=False)
            card.hover = 0
            def pixel(fraction: float, widget: GachaSideCard = card):
                """Sample away from labels and borders in physical image pixels."""
                image = widget.grab().toImage()
                return image.pixelColor(round(image.width() * fraction), round(image.height() * 0.2))
            clear_side, tinted_side = (0.1, 0.9) if card.side == "left" else (0.9, 0.1)
            with patch.object(settings_theme, "GACHA_TINT_MAX_OPACITY", 0):
                baseline = pixel(clear_side)
            self.assertEqual(pixel(clear_side), baseline)
            self.assertNotEqual(pixel(tinted_side), baseline)
            with patch.object(settings_theme, "GACHA_TINT_START_OFFSET_PX", 10000):
                self.assertEqual(pixel(tinted_side), baseline)
            card.set_present(False, animate=False)
            inactive = pixel(tinted_side)
            with patch.object(settings_theme, "GACHA_TINT_MAX_OPACITY", 0):
                self.assertEqual(pixel(tinted_side), inactive)

    def test_side_records_confirmation_and_rollback(self):
        window = self.window()
        cards = self.cards(window)
        right = cards[3]
        right.toggleRequested.emit()
        self.assertTrue(right.present)
        self.assertEqual(len(window.gacha_config), 4)
        self.assertIs(self.cards(window)[3], right)
        right.toggleRequested.emit()
        self.assertFalse(right.present)
        with patch("source.launcher.pages.gacha.save_gacha_config", side_effect=OSError("disk unavailable")):
            right.toggleRequested.emit()
        self.assertFalse(right.present)
        self.assertEqual(len(window.gacha_config), 3)
        window.confirm.return_value = False
        cards[2].toggleRequested.emit()
        self.assertEqual(len(window.gacha_config), 3)
        window.confirm.return_value = True
        cards[2].toggleRequested.emit()
        self.assertEqual(len(window.gacha_config), 2)
        self.assertEqual(len(self.cards(window)), 4)

    def test_collect_shared_values_and_rollback(self):
        window = self.window()
        left, right = self.cards(window)[-2:]
        right.toggleRequested.emit()
        self.assertEqual([r["item"] for r in window.gacha_collect_config], ["paste", "paste"])
        entry = window._gacha_collect_editors["COLLECT1"]
        entry.item.setText("metal")
        entry.item.textEdited.emit("metal")
        entry.item.editingFinished.emit()
        entry.destination.setCurrentIndex(entry.destination.findData("STORE2"))
        entry.destination.activated.emit(entry.destination.currentIndex())
        self.assertEqual([r["dedi_teleport"] for r in window.gacha_collect_config], ["STORE2", "STORE2"])
        QTest.mouseClick(entry.item, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
        self.assertTrue(right.present)
        with patch("source.launcher.pages.gacha.save_gacha_collect_config", side_effect=OSError("disk unavailable")):
            entry.item.setText("failed")
            entry.item.textEdited.emit("failed")
            entry.item.editingFinished.emit()
        self.assertEqual(entry.item.text(), "metal")
        right.toggleRequested.emit()
        right.toggleRequested.emit()
        self.assertEqual(window.gacha_collect_config[-1]["item"], "metal")
        self.assertIs(self.cards(window)[-1], right)
        self.assertNotIn("name", json.loads((self.path / "collect.json").read_text())[0])

    def test_mixed_fields_preserve_values_until_explicit_edit(self):
        window = self.window()
        other = {**window.gacha_collect_config[0], "side": "right", "item": "metal", "dedi_teleport": "STORE2"}
        window.gacha_collect_config.append(other)
        before = copy.deepcopy(window.gacha_collect_config)
        window._render_settings_group("GACHA")
        self.cards(window)
        entry = window._gacha_collect_editors["COLLECT1"]
        self.assertIn("Mixed", entry.item.placeholderText())
        self.assertIn("Left: paste", entry.warning.text())
        self.assertIn("Right: metal", entry.warning.text())
        entry.item.editingFinished.emit()
        self.assertEqual(window.gacha_collect_config, before)
        entry.item.setText("stone")
        entry.item.textEdited.emit("stone")
        entry.item.editingFinished.emit()
        self.assertEqual([r["item"] for r in window.gacha_collect_config], ["stone", "stone"])
        self.assertEqual([r["dedi_teleport"] for r in window.gacha_collect_config], ["STORE1", "STORE2"])
        entry.destination.setCurrentIndex(entry.destination.findData("STORE1"))
        entry.destination.activated.emit(entry.destination.currentIndex())
        self.assertFalse(entry.warning.isVisible())

    def test_add_focus_rename_delete_and_collapse(self):
        window = self.window()
        window.add_gacha_group()
        self.cards(window)
        self.assertEqual(window.gacha_config[-1]["teleporter"], "")
        self.assertEqual(window.gacha_config[-1]["side"], "left")
        count = len(window.gacha_config)
        window.add_gacha_group()
        self.cards(window)
        self.assertEqual(len(window.gacha_config), count)
        field = window._gacha_teleport_fields[("gacha", "")]
        self.assertTrue(field.hasFocus())
        field.setText("gacha1")
        field.editingFinished.emit()
        self.assertEqual(field.text(), "")
        field.setText("NEW")
        field.editingFinished.emit()
        self.cards(window)
        self.assertEqual(window.gacha_config[-1]["teleporter"], "NEW")
        window.remove_gacha_group("GACHA1")
        self.assertFalse(any(r["teleporter"] == "GACHA1" for r in window.gacha_config))
        self.cards(window)
        toggle = next(b for b in window.settings_form.findChildren(QPushButton) if b.accessibleName() == "Expand Gacha")
        icon = toggle.icon().cacheKey()
        toggle.click()
        self.assertNotEqual(toggle.icon().cacheKey(), icon)
        self.assertFalse(window.gacha_section_expanded["gacha"])
        window.confirm.return_value = False
        window.remove_gacha_section("gacha")
        self.assertTrue(window.gacha_config)
        window.confirm.return_value = True
        window.remove_gacha_section("gacha")
        self.assertEqual(window.gacha_config, [])

    def test_profiles_malformed_data_and_destination_warnings(self):
        """Lock both sections through the existing profile and preserve malformed records."""
        window = self.window()
        document = template_document()
        document["data"]["gacha"] = copy.deepcopy(window.gacha_config)
        document["data"]["gacha_collect"] = copy.deepcopy(window.gacha_collect_config)
        normalized, _ = normalize_template(document)
        with patch.object(window, "_template_catalog", return_value=TemplateCatalog({"gacha.json": normalized}, {}, {})):
            window._render_settings_group("GACHA")
            window.template_selector.setCurrentIndex(window.template_selector.findData("gacha.json"))
            self.assertTrue(all(not card.isEnabled() for card in self.cards(window)))
            window.template_selector.setCurrentIndex(0)
            self.assertTrue(all(card.isEnabled() for card in self.cards(window)))
        window.gacha_collect_config[0]["dedi_teleport"] = "DELETED"
        window.gacha_config.append(copy.deepcopy(window.gacha_config[0]))
        window._render_settings_group("GACHA")
        cards = self.cards(window)
        self.assertFalse(cards[0].isEnabled())
        self.assertFalse(cards[1].isEnabled())
        self.assertEqual(len(window.gacha_config), 4)
        self.assertTrue(window._gacha_collect_editors["COLLECT1"].destination.property("invalidDestination"))
        self.assertEqual(window._gacha_collect_editors["COLLECT1"].destination.currentData(), "DELETED")

    def test_animation_keyboard_and_hover_reserved_space(self):
        """Reuse animations, reverse mid-flight and keep header geometry stable."""
        window = self.window()
        card = self.cards(window)[3]
        animation = card.state_animation
        card.setFocus()
        QTest.keyClick(card, Qt.Key.Key_Space)
        QTest.qWait(65)
        self.assertGreater(card.progress, 0)
        self.assertLess(card.progress, 1)
        QTest.keyClick(card, Qt.Key.Key_Space)
        QTest.qWait(250)
        self.assertEqual(card.progress, 0)
        self.assertIs(card.state_animation, animation)
        hover = window.settings_form.findChild(SettingsHoverActions)
        before = hover.geometry()
        hover.eventFilter(hover.section, QEvent(QEvent.Type.Enter))
        QTest.qWait(20)
        self.assertEqual(hover.geometry(), before)
        hover.eventFilter(hover.section, QEvent(QEvent.Type.Leave))
        self.assertEqual(hover.geometry(), before)


if __name__ == "__main__":
    unittest.main()
