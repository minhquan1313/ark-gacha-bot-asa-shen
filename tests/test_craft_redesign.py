"""Craft presentation and entry-delay migration with isolated persistence."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_dashboard_redesign as fixture
from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton, QWidget
from test_template_settings import template_document

from source.gacha_bot.craft_config import (
    default_craft_route,
    default_crafter,
    load_craft_config,
    normalize_craft_config,
    save_craft_config,
)
from source.gacha_bot.deposit_config import default_dedi_item
from source.launcher.components.dedi_editor import DediPointRow, DediRouteEditor
from source.launcher.config.template_settings import TemplateCatalog, normalize_template


class CraftDelayTests(unittest.TestCase):
    def test_migration_preserves_data_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "craft.json"
            route = default_craft_route()
            route.pop("delay")
            route["unrelated"] = "preserve"
            other = default_craft_route() | {"delay": 42}
            raw = {"generalCraftData": [route, other], "extra": [1, 2]}
            path.write_text(json.dumps(raw))
            normalized = load_craft_config(path)
            self.assertEqual(
                [r["delay"] for r in normalized["generalCraftData"]], [180, 42]
            )
            saved = json.loads(path.read_text())
            self.assertEqual(saved["extra"], [1, 2])
            self.assertEqual(saved["generalCraftData"][0]["unrelated"], "preserve")
            stamp, content = path.stat().st_mtime_ns, path.read_bytes()
            load_craft_config(path)
            self.assertEqual(
                (path.stat().st_mtime_ns, path.read_bytes()), (stamp, content)
            )

    def test_invalid_delays_never_rewrite_source(self):
        for value in (-1, 1.5, "180", True, None):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "craft.json"
                data = {"generalCraftData": [default_craft_route() | {"delay": value}]}
                path.write_text(json.dumps(data))
                before = path.read_bytes()
                with self.assertRaises(ValueError):
                    load_craft_config(path)
                self.assertEqual(path.read_bytes(), before)
        self.assertEqual(
            normalize_craft_config(
                {"generalCraftData": [default_craft_route() | {"delay": 0}]}
            )["generalCraftData"][0]["delay"],
            0,
        )

    def test_legacy_template_ignores_global_delay(self):
        document = template_document()
        document["data"]["settings"]["craft_delay"] = 999
        route = default_craft_route()
        route.pop("delay")
        document["data"]["craft"] = {
            "generalCraftData": [route, default_craft_route() | {"delay": 73}]
        }
        normalized, _ = normalize_template(document)
        self.assertNotIn("craft_delay", normalized["data"]["settings"])
        self.assertEqual(
            [r["delay"] for r in normalized["data"]["craft"]["generalCraftData"]],
            [180, 73],
        )
        self.assertEqual(normalize_template(normalized)[0], normalized)


class CraftRedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.DashboardRedesignTests.setUpClass()

    def window(self):
        """Use real save validation without touching the user's files."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "craft.json"
        window = fixture.DashboardRedesignTests.window(
            self, ("dialog", "open_deposit_helper")
        )
        route = default_craft_route()
        route["teleport"] = "GACHACRAFT"
        route["crafters"] = [default_crafter() | {"item": "polymer"} for _ in range(2)]
        route["dedi"]["items"] = [default_dedi_item() for _ in range(3)]
        window.craft_config = {"generalCraftData": [route]}
        for module in ("craft", "settings"):
            patcher = patch(
                f"source.launcher.pages.{module}.save_craft_config",
                side_effect=lambda data: save_craft_config(data, self.path),
            )
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch(
            "source.launcher.pages.settings.save_settings", side_effect=copy.deepcopy
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        window.show_page("settings")
        window._render_settings_group("CRAFT")
        QTest.qWait(30)
        return window

    def card(self, window: QWidget):
        """Find the live entry after deferred rerender deletion."""
        QTest.qWait(20)
        return window.settings_form.findChild(DediRouteEditor)

    def test_layout_screenshots_and_editing(self):
        window = self.window()
        output = Path(".artifacts/craft")
        output.mkdir(parents=True, exist_ok=True)
        scale = os.environ.get("QT_SCALE_FACTOR", "1")
        card = self.card(window)
        previous_yaw_width = 0
        for width, height in ((1200, 800), (1536, 1024)):
            window.resize(width, height)
            for expanded in (False, True):
                card.toggle.setChecked(expanded)
                QTest.qWait(60)
                window.settings_form_area.verticalScrollBar().setValue(0)
                self.assertEqual(
                    window.settings_form_area.horizontalScrollBar().maximum(), 0
                )
                window.grab().save(
                    str(
                        output
                        / f"craft-{width}x{height}-{'expanded' if expanded else 'overview'}-{scale}.png"
                    )
                )
            for point in card.findChildren(DediPointRow):
                groups = point.fields.core.layout()
                widths = [groups.itemAt(i).widget().width() for i in range(3)]
                self.assertLessEqual(max(widths) - min(widths), 1)
            yaw = next(f for f in card.findChildren(QLineEdit) if f.property("dediField") == "yaw")
            self.assertGreater(yaw.width(), previous_yaw_width)
            previous_yaw_width = yaw.width()
            settings = card.findChild(QWidget, "CraftEntrySettings")
            fields = settings.findChildren(QLineEdit)
            self.assertEqual(len(fields), 3)
            for field in fields:
                if field.property("dediField") in {"delay", "check_on_every_dedi"}:
                    self.assertEqual(field.width(), 80)
            self.assertEqual({f.height() for f in fields}, {44})
            self.assertEqual(len({f.mapTo(settings, QPoint()).y() for f in fields}), 1)
        window.settings_form.grab().save(str(output / f"craft-full-{scale}.png"))
        self.assertFalse(window.settings_form.findChildren(QComboBox))
        self.assertEqual(card.title.text(), "GACHACRAFT - 3")
        self.assertEqual(card.points.text(), "5 points")
        delay = next(
            f
            for f in card.findChildren(QLineEdit)
            if f.property("dediField") == "delay"
        )
        for value, expected in (("73", 73), ("0", 0), ("-1", 0), ("bad", 0)):
            delay.setText(value)
            delay.editingFinished.emit()
            self.assertEqual(
                window.craft_config["generalCraftData"][0]["delay"], expected
            )
            self.assertEqual(delay.text(), str(expected))
        self.assertEqual(
            json.loads(self.path.read_text())["generalCraftData"][0]["delay"], 0
        )
        card.actions.menu.actions()[0].trigger()
        window.open_deposit_helper.assert_called_once_with("craft", 0)
        next(
            b for b in card.findChildren(QPushButton) if b.text() == "Add crafter"
        ).click()
        self.assertTrue(self.card(window).toggle.isChecked())
        self.assertEqual(self.card(window).points.text(), "6 points")

    def test_profile_locking_and_manual(self):
        window = self.window()
        document = template_document()
        document["data"]["craft"] = copy.deepcopy(window.craft_config)
        document["data"]["craft"]["generalCraftData"][0]["delay"] = 93
        normalized, _ = normalize_template(document)
        with patch.object(
            window,
            "_template_catalog",
            return_value=TemplateCatalog({"craft.json": normalized}, {}, {}),
        ):
            window._render_settings_group("CRAFT")
            window.template_selector.setCurrentIndex(
                window.template_selector.findData("craft.json")
            )
            self.assertFalse(self.card(window).isEnabled())
            self.assertEqual(window.craft_config["generalCraftData"][0]["delay"], 93)
            window.template_selector.setCurrentIndex(0)
            self.assertTrue(self.card(window).isEnabled())

    def test_failed_delay_save_and_child_edits(self):
        """Keep failed saves reversible and child changes on the Craft save path."""
        window = self.window()
        card = self.card(window)
        card.toggle.setChecked(True)
        route = window.craft_config["generalCraftData"][0]
        fields = card.findChildren(QLineEdit)
        delay = next(f for f in fields if f.property("dediField") == "delay")
        with patch.object(window, "save_craft_routes", return_value=False):
            delay.setText("92")
            delay.editingFinished.emit()
        self.assertEqual(route["delay"], 180)
        self.assertEqual(delay.text(), "180")
        item = next(f for f in fields if f.property("dediField") == "item")
        item.setText("electronics")
        item.editingFinished.emit()
        saved = json.loads(self.path.read_text())["generalCraftData"][0]
        self.assertEqual(saved["crafters"][0]["item"], "electronics")
        window.add_craft_dedi(0)
        self.assertEqual(self.card(window).points.text(), "6 points")
        self.assertEqual(self.card(window).title.text(), "GACHACRAFT - 4")
        window.remove_craft_dedi(0, 3)
        self.assertEqual(self.card(window).points.text(), "5 points")
        window.remove_crafter(0, 1)
        self.assertEqual(self.card(window).points.text(), "4 points")
        self.assertTrue(self.card(window).toggle.isChecked())


if __name__ == "__main__":
    unittest.main()
