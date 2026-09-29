"""Portrait template catalog and overlay checks with isolated import destinations."""

import os
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton
from test_dashboard_redesign import DashboardRedesignTests

from source.launcher.components.gallery import CoverGallery
from source.launcher.components.template_browser import (
    TEMPLATE_CARD_MAX_WIDTH,
    TEMPLATE_HEADER_GAP,
    TEMPLATE_LIST_ROW_HEIGHT,
    TEMPLATE_PREVIEW_CLOSE_MS,
    TEMPLATE_PREVIEW_OPEN_MS,
    TEMPLATE_TOOLBAR_GAP,
    TemplateBrowser,
    TemplateModel,
    load_template_models,
)


class TemplateBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        DashboardRedesignTests.setUpClass()

    def window(self):
        """Use the full shell while suppressing automatic background startup work."""
        window = DashboardRedesignTests.window(self, ('toast',))
        window.show_page('btemplates')
        gallery = window.btemplates_gallery
        image = QImage(480, 480, QImage.Format.Format_RGB32)
        image.fill(QColor('#447b91'))
        gallery._loaded([
            TemplateModel(Path(f'{index}.template'), None, f'Template {index}', 'Gacha' if index % 2 else 'Unsorted', index * 120 + 100, index, image if index % 2 else QImage())
            for index in range(12)
        ], '')
        QTest.qWait(40)
        return window, gallery

    def test_portrait_grid_filters_sort_and_missing_art(self):
        window, gallery = self.window()
        for width, columns in ((1200, 3), (1536, 4), (900, 3)):
            window.resize(width, 800)
            QTest.qWait(40)
            self.assertEqual(len([c for c in gallery.cards if c.y() == 0]), columns)
            for card in gallery.cards:
                self.assertEqual(card.image_rect.width() * 3, card.image_rect.height() * 4)
                self.assertEqual(card.height() - card.image_rect.height(), 76)
                self.assertLessEqual(card.width(), TEMPLATE_CARD_MAX_WIDTH)
            self.assertEqual(gallery.scroll.horizontalScrollBar().maximum(), 0)
        hero = gallery.layout().itemAt(0).widget()
        self.assertEqual(gallery.search.y() - (hero.y() + hero.height()), TEMPLATE_HEADER_GAP)
        self.assertEqual(gallery.scroll.y() - gallery.search.geometry().bottom() - 1, TEMPLATE_HEADER_GAP)
        self.assertEqual(gallery.category.x() - (gallery.search.x() + gallery.search.width()), TEMPLATE_TOOLBAR_GAP)
        card = gallery.cards[1]
        shot = card.grab().toImage()
        ratio = card.devicePixelRatioF()
        self.assertNotEqual(shot.pixelColor(0, 0), shot.pixelColor(round(20 * ratio), round(20 * ratio)))
        self.assertEqual(gallery.category.count(), 3)
        gallery.category.setCurrentText('Gacha')
        gallery.search.setText('template 1')
        self.assertEqual({c.model.name for c in gallery.cards if c.isVisible()}, {'Template 1', 'Template 11'})
        gallery.sort.setCurrentIndex(1)
        self.assertLess(gallery.cards[1].x(), gallery.cards[11].x())
        gallery.search.setText('absent')
        self.assertTrue(gallery.empty.isVisible())
        self.assertFalse(any(c.isVisible() for c in gallery.cards))
        self.assertEqual(len(gallery.findChildren(QPushButton)), 2)

    def test_preview_animation_dimming_keyboard_and_scroll_retention(self):
        window, gallery = self.window()
        window.resize(1200, 800)
        gallery.scroll.verticalScrollBar().setValue(550)
        QTest.qWait(30)
        position = gallery.scroll.verticalScrollBar().value()
        card = next(c for c in gallery.cards if c.isVisible() and c.y() >= position and not c.pixmap.isNull())
        card.setFocus()
        original = window.grab().toImage().pixelColor(30, 270)
        QTest.keyClick(card, Qt.Key.Key_Return)
        overlay = gallery.overlay
        self.assertEqual(overlay.animation.duration(), TEMPLATE_PREVIEW_OPEN_MS)
        self.assertEqual(overlay.image_source.topLeft(), overlay.mapFromGlobal(card.mapToGlobal(card.image_rect.topLeft())))
        self.assertEqual(overlay.image_source.size(), card.image_rect.size())
        QTest.qWait(80)
        self.assertGreater(overlay.progress, 0)
        self.assertLess(overlay.progress, 1)
        gallery.open_preview(gallery.cards[0])
        self.assertIs(overlay.card, card)
        QTest.qWait(TEMPLATE_PREVIEW_OPEN_MS)
        self.assertEqual(overlay.progress, 1)
        self.assertTrue(overlay.panel.isVisible())
        self.assertLess(window.grab().toImage().pixelColor(30, 270).lightness(), original.lightness())
        self.assertEqual(overlay.image.width(), overlay.image.height())
        QTest.keyClick(overlay.close_button, Qt.Key.Key_Tab)
        self.assertTrue(overlay.import_button.hasFocus())
        QTest.keyClick(overlay.import_button, Qt.Key.Key_Escape)
        self.assertEqual(overlay.animation.duration(), TEMPLATE_PREVIEW_CLOSE_MS)
        QTest.qWait(TEMPLATE_PREVIEW_CLOSE_MS + 40)
        self.assertFalse(overlay.isVisible())
        self.assertEqual(gallery.scroll.verticalScrollBar().value(), position)
        self.assertTrue(card.hasFocus())
        gallery.open_preview(card)
        QTest.qWait(40)
        overlay.close_preview()
        QTest.qWait(TEMPLATE_PREVIEW_CLOSE_MS + 40)
        self.assertFalse(overlay.isVisible())
        gallery.open_preview(card)
        window.resize(1536, 1024)
        QTest.qWait(TEMPLATE_PREVIEW_OPEN_MS + 40)
        self.assertTrue(window.rect().contains(overlay.panel.geometry()))
        QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
        QTest.qWait(TEMPLATE_PREVIEW_CLOSE_MS + 40)
        self.assertFalse(overlay.isVisible())

    def test_list_mode_and_uncropped_preview(self):
        window, gallery = self.window()
        gallery.view_group.buttons()[1].click()
        QTest.qWait(40)
        self.assertTrue(gallery.list_mode)
        self.assertTrue(all(card.x() == 0 and card.height() == TEMPLATE_LIST_ROW_HEIGHT for card in gallery.cards))
        card = gallery.cards[1]
        gallery.open_preview(card)
        QTest.qWait(TEMPLATE_PREVIEW_OPEN_MS + 40)
        self.assertEqual(gallery.overlay.image.width(), gallery.overlay.image.height())
        self.assertEqual(gallery.overlay.image.pixmap().width(), gallery.overlay.image.pixmap().height())
        gallery.overlay.close_preview()
        QTest.qWait(TEMPLATE_PREVIEW_CLOSE_MS + 40)
        gallery.view_group.buttons()[0].click()
        self.assertFalse(gallery.list_mode)
        self.assertFalse(gallery.category.itemIcon(0).isNull())
        self.assertFalse(gallery.sort.itemIcon(0).isNull())

    def test_import_is_explicit_retryable_and_survives_close(self):
        window, gallery = self.window()
        # The fixture suppresses automatic discovery; enable the real worker only here.
        # CoverGallery.run_work is patched by the fixture, so obtain an unpatched worker below.
        gallery.run_work = REAL_RUN_WORK.__get__(gallery, TemplateBrowser)
        gallery.open_preview(gallery.cards[1])
        QTest.qWait(TEMPLATE_PREVIEW_OPEN_MS + 40)
        with patch('source.launcher.components.template_browser.import_template', side_effect=PermissionError('read only')) as importer:
            gallery.overlay.import_button.click()
            for _ in range(50):
                if not gallery._busy:
                    break
                QTest.qWait(10)
            self.assertIn('read only', gallery.overlay.status.text())
            self.assertTrue(gallery.overlay.import_button.isEnabled())
            importer.assert_called_once_with(gallery.cards[1].model.source)
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def copy_file(source: Path):
            """Hold the copy until close and duplicate-click behavior are checked."""
            entered.set()
            release.wait(2)
            return source
        with patch('source.launcher.components.template_browser.import_template', side_effect=copy_file) as importer:
            gallery.overlay.import_button.click()
            self.assertTrue(entered.wait(1))
            gallery.import_selected(gallery.cards[1].model)
            gallery.overlay.close_button.click()
            QTest.qWait(TEMPLATE_PREVIEW_CLOSE_MS + 40)
            release.set()
            for _ in range(50):
                if not gallery._busy:
                    break
                QTest.qWait(10)
            self.assertEqual(importer.call_count, 1)
            window.toast.assert_called_once()
            self.assertFalse(gallery.overlay.isVisible())

    def test_real_library_captures(self):
        window, gallery = self.window()
        # Remove fixture cards before populating the actual read-only bundled library.
        for card in gallery.cards:
            card.hide()
            card.deleteLater()
        gallery.cards.clear()
        gallery._loaded(load_template_models(), '')
        output = Path('.artifacts/btemplates')
        output.mkdir(parents=True, exist_ok=True)
        scale = os.environ.get('QT_SCALE_FACTOR', '1')
        for width, height in ((1200, 800), (1536, 1024)):
            window.resize(width, height)
            gallery.category.setCurrentText('Gacha')
            QTest.qWait(80)
            window.grab().save(str(output / f'browser-{width}x{height}-{scale}.png'))
            card = next(c for c in gallery.cards if c.isVisible() and not c.pixmap.isNull())
            gallery.open_preview(card)
            QTest.qWait(TEMPLATE_PREVIEW_OPEN_MS + 40)
            self.assertGreater(gallery.overlay.image.height(), card.image_rect.height())
            self.assertEqual(gallery.overlay.image.width(), gallery.overlay.image.height())
            window.grab().save(str(output / f'preview-{width}x{height}-{scale}.png'))
            gallery.overlay.close_button.click()
            QTest.qWait(TEMPLATE_PREVIEW_CLOSE_MS + 40)
        gallery.view_group.buttons()[1].click()
        gallery.scroll.verticalScrollBar().setValue(0)
        QTest.qWait(50)
        window.grab().save(str(output / f'list-{scale}.png'))
        gallery.view_group.buttons()[0].click()
        gallery.category.setCurrentIndex(0)
        gallery.scroll.verticalScrollBar().setValue(0)
        QTest.qWait(50)
        window.grab().save(str(output / f'all-templates-{scale}.png'))


REAL_RUN_WORK = CoverGallery.run_work
