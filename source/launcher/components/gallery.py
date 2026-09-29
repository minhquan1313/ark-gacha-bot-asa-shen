"""Responsive image galleries shared by tools and building templates."""

import contextlib
import threading
from collections.abc import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QTextLayout,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from source.launcher.components.cover_painting import painted_cover
from source.launcher.components.custom_pyside_component import NoWheelComboBox
from source.launcher.utils.building_templates import CATEGORIES


class ToolCoverCard(QFrame):
    """Paint a clickable cover with clear artwork and an animated action."""

    activated = Signal()

    def __init__(
        self,
        title: str,
        description: str,
        image_path: str,
        action: str,
        category: str = "Unsorted",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.title, self.description, self.category = title, description, category
        self.action = action
        self.pixmap = QPixmap(image_path) if image_path else QPixmap()
        self._cache_size = None
        self._art = QPixmap()
        self._progress = 0.0
        self._pressed = False
        self.setObjectName("ToolCoverCard")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(title + ("\n" + description if description else ""))
        self.setAccessibleName(f"{action}: {title}")
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(220)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self._animate)

    def _animate(self, value: float):
        """Apply one animation frame."""
        self._progress = float(value)
        self.update()

    def _transition(self):
        """Reverse smoothly when hover or keyboard focus changes."""
        self.animation.stop()
        self.animation.setStartValue(self._progress)
        self.animation.setEndValue(1.0 if self.isEnabled() and (self.underMouse() or self.hasFocus()) else 0.0)
        self.animation.start()

    def event(self, event: QEvent):
        """Reveal the action for hover and keyboard navigation."""
        result = super().event(event)
        if event.type() in (
            QEvent.Type.Enter,
            QEvent.Type.Leave,
            QEvent.Type.FocusIn,
            QEvent.Type.FocusOut,
            QEvent.Type.EnabledChange,
        ):
            self._transition()
        return result

    def mousePressEvent(self, event: QMouseEvent):
        """Arm a whole-card left click."""
        self._pressed = event.button() == Qt.MouseButton.LeftButton
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Activate once only when the click ends inside the card."""
        activate = self._pressed and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint())
        self._pressed = False
        if activate and self.isEnabled():
            self.activated.emit()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        """Activate keyboard actions without auto-repeat imports."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if not event.isAutoRepeat() and self.isEnabled():
                self.activated.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _cache_art(self):
        """Cache proportional artwork at the current display pixel density."""
        ratio = self.devicePixelRatioF()
        key = (self.width(), self.height(), ratio)
        if self._cache_size == key or self.pixmap.isNull():
            return
        self._cache_size = key
        width, height = round(self.width() * ratio), round(self.height() * ratio)
        scaled = self.pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._art = scaled.copy(
            (scaled.width() - width) // 2,
            (scaled.height() - height) // 2,
            width,
            height,
        )
        self._art.setDevicePixelRatio(ratio)

    @staticmethod
    def _text_lines(text: str, font: QFont, width: int, limit: int):
        """Wrap text into a bounded set of lines and elide overflow."""
        layout = QTextLayout(text, font)
        layout.beginLayout()
        lines = []
        for index in range(limit):
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(width)
            start, length = line.textStart(), line.textLength()
            value = text[start : start + length].strip()
            if index == limit - 1 and start + length < len(text):
                value = QFontMetrics(font).elidedText(text[start:], Qt.TextElideMode.ElideRight, width)
            lines.append(value)
        layout.endLayout()
        return lines

    def paintEvent(self, event: QPaintEvent):
        """Paint clear artwork and readable copy inside one continuous border."""
        self._cache_art()
        painter = QPainter(self)
        with painted_cover(
            painter,
            QRectF(self.rect()),
            10,
            self._art,
            QPointF(),
            QPen(QColor(0, 216, 255, int(35 + 140 * self._progress)), 1),
            QColor("#142431"),
            QRectF(self.rect()),
        ):
            title_font = QFont(self.font())
            title_font.setPixelSize(17)
            title_font.setBold(True)
            body_font = QFont(self.font())
            body_font.setPixelSize(12)
            width = max(1, self.width() - 32)
            titles = self._text_lines(self.title, title_font, width, 2)
            title_height = QFontMetrics(title_font).height()
            body_height = QFontMetrics(body_font).height()
            description_limit = max(
                1,
                min(
                    3,
                    int((self.height() / 2 - 53 - len(titles) * title_height) // body_height),
                ),
            )
            descriptions = self._text_lines(self.description, body_font, width, description_limit) if self.description else []
            copy_height = len(titles) * title_height + len(descriptions) * body_height + (6 if descriptions else 0)
            top = self.height() - 16 - copy_height
            painter.setFont(title_font)
            painter.setPen(QColor("#f4f8ff"))
            y = top
            for line in titles:
                painter.setPen(QColor(0, 0, 0, 210))
                painter.drawText(
                    QRectF(17, y + 1, width, title_height),
                    Qt.AlignmentFlag.AlignLeft,
                    line,
                )
                painter.setPen(QColor("#f4f8ff"))
                painter.drawText(QRectF(16, y, width, title_height), Qt.AlignmentFlag.AlignLeft, line)
                y += title_height
            painter.setFont(body_font)
            painter.setPen(QColor("#c3d1de"))
            y += 6
            for line in descriptions:
                painter.setPen(QColor(0, 0, 0, 210))
                painter.drawText(
                    QRectF(17, y + 1, width, body_height),
                    Qt.AlignmentFlag.AlignLeft,
                    line,
                )
                painter.setPen(QColor("#c3d1de"))
                painter.drawText(QRectF(16, y, width, body_height), Qt.AlignmentFlag.AlignLeft, line)
                y += body_height

            if self._progress > 0:
                painter.save()
                painter.setOpacity(self._progress)
                action_font = QFont(title_font)
                action_font.setPixelSize(14)
                painter.setFont(action_font)
                action_width = max(112, QFontMetrics(action_font).horizontalAdvance(self.action) + 40)
                action_rect = QRectF(
                    (self.width() - action_width) / 2,
                    (self.height() - 42) / 2 + 8 * (1 - self._progress),
                    action_width,
                    42,
                )
                painter.setPen(QColor("#00d8ff"))
                painter.setBrush(QColor(5, 35, 48, 240))
                painter.drawRoundedRect(action_rect, 9, 9)
                painter.setPen(QColor("#f4f8ff"))
                painter.drawText(action_rect, Qt.AlignmentFlag.AlignCenter, self.action)
                painter.restore()


class CoverGallery(QWidget):
    """Own independent search/filter state and a reflowing 4:3 card grid."""

    work_finished = Signal(object, str)

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.cards = []
        self._busy = False
        self._completion = None
        self.work_finished.connect(self._finish_work)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("PageTitle")
        header.addWidget(label)
        header.addStretch()
        self.search = QLineEdit()
        self.search.setObjectName("SettingField")
        self.search.setPlaceholderText("Search…")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(220)
        self.search.setAccessibleName(f"Search {title}")
        self.category = NoWheelComboBox()
        self.category.setObjectName("HelperCombo")
        self.category.addItems(CATEGORIES)
        self.category.setAccessibleName(f"{title} category")
        header.addWidget(self.search)
        header.addWidget(self.category)
        layout.addLayout(header)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("GalleryScroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("GalleryContent")
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)
        self.empty = QLabel("No matching items.", self.content)
        self.empty.setObjectName("MutedCopy")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.viewport().installEventFilter(self)
        self.search.textChanged.connect(self.reflow)
        self.category.currentTextChanged.connect(self.reflow)

    def add_card(self, card: ToolCoverCard):
        """Add an existing card while retaining stable ordering."""
        card.setParent(self.content)
        self.cards.append(card)
        self.reflow()

    def eventFilter(self, watched: QWidget, event: QEvent):
        """Recompute columns after viewport and scrollbar geometry settles."""
        if watched is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.reflow)
        return super().eventFilter(watched, event)

    def reflow(self, _value: str = ""):
        """Filter and position equal-size cards without stretching the last row."""
        query = self.search.text().strip().casefold()
        category = self.category.currentText()
        visible = [card for card in self.cards if query in f"{card.title} {card.description}".casefold() and (category == "All" or category == card.category)]
        viewport_width = max(4, self.scroll.viewport().width())
        columns = max(1, (viewport_width + 12) // 292)
        width = max(4, ((viewport_width - (columns - 1) * 12) // columns) // 4 * 4)
        height = width * 3 // 4
        for card in self.cards:
            card.setVisible(card in visible)
        for index, card in enumerate(visible):
            row, col = divmod(index, columns)
            card.setGeometry(col * (width + 12), row * (height + 12), width, height)
        rows = (len(visible) + columns - 1) // columns
        self.content.setMinimumHeight(max(0, rows * (height + 12) - 12))
        self.empty.setVisible(not visible)
        self.empty.setGeometry(0, 0, viewport_width, 90)

    def run_work(self, operation: Callable, completion: Callable):
        """Run discovery or import in a worker and deliver results on the UI thread."""
        if self._busy:
            return
        self._busy = True
        self._completion = completion
        for card in self.cards:
            card.setEnabled(False)

        def execute():
            """Capture worker errors for the existing launcher dialog."""
            result, error = None, ""
            try:
                result = operation()
            except Exception as exc:
                error = str(exc)
            # The launcher may have closed while filesystem work finished.
            with contextlib.suppress(RuntimeError):
                self.work_finished.emit(result, error)

        threading.Thread(target=execute, daemon=True).start()

    def _finish_work(self, result: object, error: str):
        """Restore interaction before invoking the UI completion callback."""
        self._busy = False
        for card in self.cards:
            card.setEnabled(True)
        completion, self._completion = self._completion, None
        if completion is not None:
            completion(result, error)
