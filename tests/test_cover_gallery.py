import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from source.launcher.components.gallery import CoverGallery, ToolCoverCard
from source.launcher.utils import building_templates


class TemplateServiceTests(unittest.TestCase):
    def test_discovery_sorts_and_matches_previews_and_categories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("z.template", "GachaBot - Gacha Pair.template", "a.template", "a.png", "a.jpg"):
                (root / name).write_bytes(b"example")
            entries = building_templates.discover_templates(root)
            self.assertEqual([path.stem for path, _ in entries], ["a", "GachaBot - Gacha Pair", "z"])
            self.assertEqual(entries[0][1], root / "a.jpg")
            self.assertIsNone(entries[-1][1])
            self.assertEqual(building_templates.TEMPLATE_CATEGORIES[entries[1][0].stem], "Gacha")
            self.assertEqual(building_templates.TOOL_CATEGORIES["Server Transfer"], "Transfer")

    def test_import_creates_saved_destination_and_overwrites_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "example.template"
            source.write_bytes(b"\x00template\xff")
            settings = root / "ARK/ShooterGame/Saved/Config/Windows/GameUserSettings.ini"
            with patch.object(building_templates.ark_game_setup, "find_game_user_settings_path", return_value=settings):
                destination = building_templates.import_template(source)
                self.assertEqual(destination, root / "ARK/ShooterGame/Saved/StructureTemplates/example.template")
                self.assertEqual(destination.read_bytes(), source.read_bytes())
                self.assertEqual(source.read_bytes(), b"\x00template\xff")
                destination.write_bytes(b"old")
                building_templates.import_template(source)
                self.assertEqual(destination.read_bytes(), source.read_bytes())

    def test_import_propagates_detection_and_copy_errors(self):
        with patch.object(building_templates.ark_game_setup, "find_game_user_settings_path", side_effect=RuntimeError("missing ARK")), self.assertRaisesRegex(RuntimeError, "missing ARK"):
            building_templates.import_template(Path("example.template"))
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / "Saved/Config/Windows/GameUserSettings.ini"
            with patch.object(building_templates.ark_game_setup, "find_game_user_settings_path", return_value=settings), patch.object(building_templates.shutil, "copyfile", side_effect=PermissionError("read only")):
                with self.assertRaisesRegex(PermissionError, "read only"):
                    building_templates.import_template(Path("example.template"))


class GalleryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def gallery(self, count=7):
        gallery = CoverGallery("Tools")
        for index in range(count):
            gallery.add_card(ToolCoverCard(f"Tool {index}", "Helpful description", "", "Open Tool", "Gacha" if index % 2 else "Transfer"))
        gallery.resize(900, 600)
        gallery.show()
        self.addCleanup(gallery.close)
        QTest.qWait(30)
        return gallery

    def test_ratio_reflow_last_row_scroll_and_empty_results(self):
        gallery = self.gallery()
        for width, expected_columns in ((620, 2), (920, 3), (1250, 4)):
            gallery.resize(width, 500)
            QTest.qWait(40)
            row = [card for card in gallery.cards if card.y() == 0]
            self.assertEqual(len(row), expected_columns)
            self.assertEqual(len({(card.width(), card.height()) for card in gallery.cards}), 1)
            for card in gallery.cards:
                self.assertEqual(card.width() * 3, card.height() * 4)
            self.assertEqual(gallery.scroll.horizontalScrollBar().maximum(), 0)
        gallery.search.setText("absent")
        QTest.qWait(20)
        self.assertTrue(gallery.empty.isVisible())
        self.assertFalse(any(card.isVisible() for card in gallery.cards))
        gallery.search.clear()
        QTest.qWait(20)
        self.assertFalse(gallery.empty.isVisible())

    def test_filter_and_search_are_combined_and_independent(self):
        first, second = self.gallery(), self.gallery()
        first.category.setCurrentText("Gacha")
        first.search.setText("TOOL 1")
        self.assertEqual([card.title for card in first.cards if card.isVisible()], ["Tool 1"])
        self.assertEqual(second.category.currentText(), "All")
        self.assertEqual(second.search.text(), "")
        self.assertEqual(sum(card.isVisible() for card in second.cards), 7)
        first.search.setText("helpful")
        self.assertEqual(sum(card.isVisible() for card in first.cards), 3)
        first.hide()
        first.show()
        self.assertEqual(first.category.currentText(), "Gacha")

    def test_whole_card_click_keyboard_hover_and_unreadable_art(self):
        gallery = self.gallery(1)
        card = gallery.cards[0]
        activated = Mock()
        card.activated.connect(activated)
        for point in (QPoint(10, 10), card.rect().center(), QPoint(20, card.height() - 20)):
            QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=point)
        self.assertEqual(activated.call_count, 3)
        card.setFocus()
        QTest.qWait(250)
        self.assertAlmostEqual(card._progress, 1)
        QTest.keyClick(card, Qt.Key.Key_Return)
        QTest.keyClick(card, Qt.Key.Key_Space)
        self.assertEqual(activated.call_count, 5)
        card.setEnabled(False)
        QTest.qWait(250)
        self.assertAlmostEqual(card._progress, 0)
        self.assertFalse(card.grab().isNull())
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "broken.jpg"
            bad.write_bytes(b"bad image")
            fallback = ToolCoverCard("Missing art", "", str(bad), "Import")
            fallback.resize(280, 210)
            self.assertTrue(fallback.pixmap.isNull())
            self.assertFalse(fallback.grab().isNull())

    def test_worker_does_not_block_or_duplicate_and_delivers_errors(self):
        gallery = self.gallery(1)
        release = threading.Event()
        self.addCleanup(release.set)
        entered = threading.Event()
        completion, duplicate = Mock(), Mock()

        def work():
            entered.set()
            release.wait(2)
            raise OSError("copy failed")

        gallery.run_work(work, completion)
        self.assertTrue(entered.wait(1))
        gallery.run_work(duplicate, duplicate)
        self.assertFalse(gallery.cards[0].isEnabled())
        gallery.search.setText("tool")
        self.app.processEvents()
        release.set()
        for _ in range(100):
            if completion.called:
                break
            QTest.qWait(10)
        completion.assert_called_once_with(None, "copy failed")
        duplicate.assert_not_called()
        self.assertTrue(gallery.cards[0].isEnabled())



if __name__ == "__main__":
    unittest.main()
