import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QHoverEvent, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from source.launcher.components.custom_pyside_component import RemovableComboBox
from source.launcher.config.constants import COLORS


class RemovableComboBoxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.combo = RemovableComboBox()
        self.combo.addItems(["first", "second"])
        self.combo.show()

    def tearDown(self):
        self.combo.hidePopup()
        self.combo.close()

    def _row_position(self, row: int, *, remove_area: bool):
        """Return a popup position over either a row label or its remove control."""
        self.combo.showPopup()
        self.app.processEvents()
        index = self.combo.model().index(row, 0)
        row_rect = self.combo.view().visualRect(index)
        position = row_rect.center()
        position.setX(row_rect.right() - 8 if remove_area else row_rect.left() + 8)
        return position

    def _send_hover(self, position, old_position=None):
        """Send the hover event used by a real Qt popup viewport."""
        old_position = old_position or position
        global_position = self.combo.view().viewport().mapToGlobal(position)
        event = QHoverEvent(
            QEvent.Type.HoverMove,
            QPointF(position),
            QPointF(global_position),
            QPointF(old_position),
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(self.combo.view().viewport(), event)
        self.app.processEvents()

    def test_remove_control_emits_index_and_keeps_popup_open(self):
        removed = []

        def remove_item(index: int):
            removed.append(index)
            self.combo.removeItem(index)

        self.combo.item_remove_requested.connect(remove_item)
        position = self._row_position(0, remove_area=True)

        QTest.mouseClick(
            self.combo.view().viewport(),
            Qt.MouseButton.LeftButton,
            pos=position,
        )
        self.app.processEvents()

        self.assertEqual(removed, [0])
        self.assertEqual(
            [self.combo.itemText(index) for index in range(self.combo.count())],
            ["second"],
        )
        self.assertTrue(self.combo.view().isVisible())

    def test_remove_control_tracks_hovered_row(self):
        position = self._row_position(1, remove_area=True)

        QTest.mouseMove(self.combo.view().viewport(), position)
        self.app.processEvents()

        self.assertEqual(self.combo.remove_hovered_row, 1)

    def test_hover_event_activates_x_before_click_and_clears_over_text(self):
        remove_position = self._row_position(1, remove_area=True)
        text_position = self._row_position(1, remove_area=False)

        self._send_hover(remove_position)
        self.assertEqual(self.combo.remove_hovered_row, 1)

        self._send_hover(text_position, remove_position)
        self.assertEqual(self.combo.remove_hovered_row, -1)

    def test_hovered_x_area_renders_danger_red(self):
        remove_position = self._row_position(0, remove_area=True)
        self._send_hover(remove_position)
        viewport = self.combo.view().viewport()
        pixmap = QPixmap(viewport.size())
        pixmap.fill(Qt.GlobalColor.transparent)

        viewport.render(pixmap)

        sample_position = QPointF(remove_position).toPoint()
        first_row = self.combo.view().visualRect(self.combo.model().index(0, 0))
        sample_position.setX(first_row.right() - 3)
        self.assertEqual(
            pixmap.toImage().pixelColor(sample_position), QColor(COLORS["red"])
        )

    def test_clicking_row_text_still_selects_item(self):
        self.combo.setCurrentIndex(1)
        position = self._row_position(0, remove_area=False)

        QTest.mouseClick(
            self.combo.view().viewport(),
            Qt.MouseButton.LeftButton,
            pos=position,
        )
        self.app.processEvents()

        self.assertEqual(self.combo.currentIndex(), 0)

    def test_editable_unsaved_text_does_not_create_removable_row(self):
        self.combo.setEditable(True)
        self.combo.setEditText("unsaved")

        self.assertEqual(self.combo.count(), 2)
        self.assertEqual(self.combo.findText("unsaved"), -1)


if __name__ == "__main__":
    unittest.main()
