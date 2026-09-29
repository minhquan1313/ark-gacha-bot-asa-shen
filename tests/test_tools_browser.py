"""Tools catalog layout, direct activation, and shared browser spacing checks."""
import os
import unittest
from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_dashboard_redesign import DashboardRedesignTests


class ToolsBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        DashboardRedesignTests.setUpClass()

    def window(self):
        """Use isolated shell fixtures and mock every helper launch callback."""
        self.handlers = ('open_auto_join_server_helper', 'open_fertilizer_refresh_helper', 'open_auto_fishing_helper', 'open_auto_feed_helper', 'open_server_transfer_helper', 'open_switch_steam_helper')
        window = DashboardRedesignTests.window(self, self.handlers)
        window.show_page('tools')
        QTest.qWait(40)
        return window, window.tools_gallery

    def test_layout_filters_and_direct_actions(self):
        window, gallery = self.window()
        for width, height in ((1200, 800), (1536, 1024)):
            window.resize(width, height)
            QTest.qWait(50)
            hero = gallery.layout().itemAt(0).widget()
            self.assertEqual(gallery.search.y() - hero.geometry().bottom() - 1, 12)
            self.assertEqual(gallery.scroll.y() - gallery.search.geometry().bottom() - 1, 12)
            self.assertEqual(gallery.category.x() - gallery.search.geometry().right() - 1, 8)
            for card in gallery.cards:
                self.assertLessEqual(card.width(), 320)
                self.assertEqual(card.image_rect.width()*3, card.image_rect.height()*4)
            self.assertEqual(gallery.scroll.horizontalScrollBar().maximum(), 0)
        self.assertEqual([gallery.category.itemText(i) for i in range(gallery.category.count())], ['All Categories', 'QoL', 'Transfer'])
        gallery.search.setText('fertilizer')
        self.assertEqual([c.title for c in gallery.cards if c.isVisible()], ['Crop Plot Fertilizer Refresh'])
        gallery.search.clear()
        gallery.category.setCurrentText('Transfer')
        self.assertEqual(len([c for c in gallery.cards if c.isVisible()]), 2)
        self.assertEqual(window.btemplates_gallery.category.currentText(), 'All Categories')
        gallery.category.setCurrentIndex(0)
        gallery.sort.setCurrentIndex(1)
        ordered = sorted(gallery.cards, key=lambda c:(c.y(), c.x()))
        self.assertEqual([c.title for c in ordered], sorted(c.title for c in gallery.cards))
        gallery.sort.setCurrentIndex(0)
        for card, handler in zip(gallery.cards, self.handlers, strict=True):
            QTest.keyClick(card, Qt.Key.Key_Return)
            getattr(window, handler).assert_called_once()
        gallery.view_group.buttons()[1].click()
        self.assertTrue(all(c.height() == 84 for c in gallery.cards))
        gallery.search.setText('nothing matches')
        self.assertTrue(gallery.empty.isVisible())

    def test_captures_and_borderless_hover(self):
        window, gallery = self.window()
        output = Path('.artifacts/tools')
        output.mkdir(parents=True, exist_ok=True)
        scale = os.environ.get('QT_SCALE_FACTOR', '1')
        for width, height in ((1200, 800), (1536, 1024)):
            window.resize(width, height)
            gallery.view_group.buttons()[0].click()
            QTest.qWait(60)
            window.grab().save(str(output / f'grid-{width}x{height}-{scale}.png'))
            card = gallery.cards[0]
            card.clearFocus()
            card._animate(0.0)
            before = card.grab().toImage()
            card._animate(1.0)
            after = card.grab().toImage()
            ratio = card.devicePixelRatioF()
            # The information-panel edge stays unchanged: no hover outline.
            edge_y = round((card.image_rect.height()+8)*ratio)
            self.assertEqual(before.pixelColor(0, edge_y), after.pixelColor(0, edge_y))
            window.grab().save(str(output / f'hover-{width}x{height}-{scale}.png'))
            gallery.view_group.buttons()[1].click()
            QTest.qWait(40)
            window.grab().save(str(output / f'list-{width}x{height}-{scale}.png'))
            QApplication.sendEvent(card, QEvent(QEvent.Type.Leave))
