from PySide6.QtCore import QEvent, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
    QWidget,
)

from source.launcher.config.constants import COLORS, UI_METRICS


class NoWheelComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(UI_METRICS["control_height"])

    def wheelEvent(self, event):
        event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(COLORS["cyan"]), 1.7))
        center_x = self.width() - 15
        center_y = self.height() // 2
        painter.drawLine(center_x - 4, center_y - 2, center_x, center_y + 2)
        painter.drawLine(center_x, center_y + 2, center_x + 4, center_y - 2)


class _RemovableComboDelegate(QStyledItemDelegate):
    REMOVE_AREA_WIDTH = 30

    def __init__(self, combo: "RemovableComboBox"):
        super().__init__(combo)
        self.combo = combo

    @classmethod
    def remove_rect(cls, row_rect: QRect):
        """Return the right-edge remove hit area for a popup row."""
        return QRect(
            row_rect.right() - cls.REMOVE_AREA_WIDTH + 1,
            row_rect.top(),
            cls.REMOVE_AREA_WIDTH,
            row_rect.height(),
        )

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        super().paint(painter, option, index)
        remove_rect = self.remove_rect(option.rect)
        hovered = self.combo.remove_hovered_row == index.row()

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if hovered:
            painter.fillRect(remove_rect, QColor(COLORS["red"]))
        painter.setPen(
            QPen(QColor(COLORS["text"] if hovered else COLORS["muted"]), 2.0)
        )
        center = remove_rect.center()
        painter.drawLine(center.x() - 4, center.y() - 4, center.x() + 4, center.y() + 4)
        painter.drawLine(center.x() + 4, center.y() - 4, center.x() - 4, center.y() + 4)
        painter.restore()


class RemovableComboBox(NoWheelComboBox):
    """Display a close-style remove action on every popup item row."""

    item_remove_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.remove_hovered_row = -1
        self._remove_delegate = _RemovableComboDelegate(self)
        self.setItemDelegate(self._remove_delegate)
        self.view().setMouseTracking(True)
        viewport = self.view().viewport()
        viewport.setAttribute(Qt.WidgetAttribute.WA_Hover)
        viewport.installEventFilter(self)

    def eventFilter(self, watched, event):
        viewport = self.view().viewport()
        if watched is not viewport:
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.Leave:
            self._set_remove_hovered_row(-1)
            return False
        if event.type() not in {
            QEvent.Type.HoverMove,
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.ToolTip,
        }:
            return False

        position = (
            event.pos()
            if event.type() == QEvent.Type.ToolTip
            else event.position().toPoint()
        )
        index = self.view().indexAt(position)
        remove_hovered = index.isValid() and self._remove_delegate.remove_rect(
            self.view().visualRect(index)
        ).contains(position)
        self._set_remove_hovered_row(index.row() if remove_hovered else -1)

        if event.type() == QEvent.Type.ToolTip and remove_hovered:
            QToolTip.showText(event.globalPos(), "Remove item", self)
            return True
        if (
            remove_hovered
            and event.type()
            in {QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease}
            and event.button() == Qt.MouseButton.LeftButton
        ):
            if event.type() == QEvent.Type.MouseButtonRelease:
                self.item_remove_requested.emit(index.row())
                QTimer.singleShot(0, self._restore_popup_after_removal)
            return True
        return False

    def _set_remove_hovered_row(self, row: int):
        """Repaint the popup when its remove-button hover row changes."""
        if self.remove_hovered_row == row:
            return
        self.remove_hovered_row = row
        self.view().viewport().update()

    def _restore_popup_after_removal(self):
        """Keep the popup available for further removals while items remain."""
        if self.count() > 0:
            self.showPopup()
