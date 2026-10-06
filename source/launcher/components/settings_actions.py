"""Pinned row actions and reserved hover actions for Settings collections."""

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QWidget,
)

from source.launcher.components.settings_sections import SettingsActionButton
from source.launcher.dashboard_theme import PALETTE
from source.launcher.settings_theme import CONTROL_HEIGHT, ENTRY_ROW_PADDING_Y


class SettingsRowActions(QWidget):
    """Keep inline buttons and their equivalent overflow menu alive across resizes."""

    def __init__(self, buttons: list[tuple[str, SettingsActionButton]]):
        super().__init__()
        self.setFixedHeight(CONTROL_HEIGHT)
        self.stack = QStackedLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.inline = QWidget()
        row = QHBoxLayout(self.inline)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.menu = QMenu(self)
        self.menu.setObjectName("TemplateActionMenu")
        for caption, button in buttons:
            if button.text():
                button.ensurePolished()
                button.setFixedWidth(button.sizeHint().width())
            row.addWidget(button)
            action = self.menu.addAction(button.icon(), caption)
            action.setEnabled(button.isEnabled())
            action.triggered.connect(button.click)
        self.inline_width = row.sizeHint().width()
        self.overflow = SettingsActionButton("", "more_vertical")
        self.overflow.setFixedSize(CONTROL_HEIGHT, CONTROL_HEIGHT)
        self.overflow.setToolTip("Actions")
        self.overflow.setAccessibleName("Actions")
        self.overflow.clicked.connect(self.open_menu)
        self.stack.addWidget(self.inline)
        self.stack.addWidget(self.overflow)
        self.set_compact(False)

    def open_menu(self):
        """Open a non-blocking menu anchored to the pinned overflow button."""
        self.menu.popup(self.overflow.mapToGlobal(QPoint(0, CONTROL_HEIGHT)))

    def set_compact(self, compact: bool):
        """Switch presentation without recreating actions or dismissing an open menu."""
        compact = compact or self.menu.isVisible()
        self.stack.setCurrentWidget(self.overflow if compact else self.inline)
        self.setFixedWidth(CONTROL_HEIGHT if compact else self.inline_width)


class SettingsRowIndex(QLabel):
    """A compact pinned row number with a cyan accent and circular badge."""

    def __init__(self, index: int):
        super().__init__(f"{index + 1:02d}")
        self.setFixedSize(34, CONTROL_HEIGHT)
        self.setAccessibleName(f"Row {index + 1}")

    def paintEvent(self, event: QPaintEvent):
        """Paint the badge at logical-pixel precision without blur or raster assets."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cyan = QColor(PALETTE["cyan"])
        painter.setPen(QPen(cyan, 1.0))
        center = self.height() / 2
        painter.drawLine(QPointF(1.5, center - 16), QPointF(1.5, center + 16))
        badge = QRectF(8, center - 12, 24, 24)
        fill = QColor(cyan)
        fill.setAlphaF(0.18)
        outline = QColor(cyan)
        outline.setAlphaF(0.55)
        painter.setBrush(fill)
        painter.setPen(QPen(outline, 0.75))
        painter.drawEllipse(badge)
        font = QFont("Segoe UI")
        font.setWeight(QFont.Weight.DemiBold)
        font.setPixelSize(11)
        while QFontMetricsF(font).horizontalAdvance(self.text()) > 21 and font.pixelSize() > 1:
            font.setPixelSize(font.pixelSize() - 1)
        painter.setFont(font)
        painter.setPen(cyan)
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, self.text())


class SettingsEntryRow(QFrame):
    """Pin the index and actions while only the middle editor region can scroll."""

    def __init__(self, index: int, fields: list[QWidget], actions: SettingsRowActions):
        super().__init__()
        self.setObjectName("SettingsEntryRow")
        self.setMinimumWidth(0)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(8, ENTRY_ROW_PADDING_Y, 8, ENTRY_ROW_PADDING_Y)
        self.row.setSpacing(8)
        self.index = SettingsRowIndex(index)
        self.row.addWidget(self.index, 0, Qt.AlignmentFlag.AlignTop)
        self.middle = QWidget()
        grid = QHBoxLayout(self.middle)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        for field in fields:
            grid.addWidget(field, 1)
        self.middle.ensurePolished()
        self.middle.setMinimumWidth(grid.minimumSize().width())
        self.scroll = QScrollArea()
        self.scroll.setObjectName("SettingsEntryScroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumWidth(0)
        self.scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setWidget(self.middle)
        self.middle.setAutoFillBackground(False)
        self.scroll.viewport().setAutoFillBackground(False)
        self.row.addWidget(self.scroll, 1, Qt.AlignmentFlag.AlignTop)
        self.actions = actions
        self.row.addWidget(actions, 0, Qt.AlignmentFlag.AlignTop)
        self.actions.menu.aboutToHide.connect(lambda: QTimer.singleShot(0, self._reflow))
        self._reflow()

    def _reflow(self):
        """Use real minimum field and action widths to choose the inline breakpoint."""
        fixed = 16 + self.index.width() + 2 * self.row.spacing()
        available = max(0, self.width() - fixed)
        minimum = self.middle.minimumWidth()
        self.actions.set_compact(available < minimum + self.actions.inline_width)
        scrolling = available - self.actions.width() < minimum
        bar = self.scroll.horizontalScrollBar().sizeHint().height() if scrolling else 0
        self.scroll.setFixedHeight(CONTROL_HEIGHT + bar)
        self.setFixedHeight(CONTROL_HEIGHT + bar + 2 * ENTRY_ROW_PADDING_Y)

    def resizeEvent(self, event: QResizeEvent):
        """Keep row height compact and the rightmost action accessible."""
        super().resizeEvent(event)
        self._reflow()


class SettingsHoverActions(SettingsRowActions):
    """Reserve header space and reveal actions on section hover or keyboard focus."""

    def __init__(
        self,
        section: QWidget,
        button: SettingsActionButton,
        caption: str = "Delete all",
        accessible_name: str = "Pego group actions",
    ):
        super().__init__([(caption, button)])
        self.section = section
        self.hovered = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(accessible_name)
        section.installEventFilter(self)
        section.header.installEventFilter(self)
        QApplication.instance().focusChanged.connect(self._focus_changed)
        self.menu.aboutToHide.connect(lambda: QTimer.singleShot(0, self._sync_visibility))
        self._sync_visibility()

    def _focus_changed(self, old: QWidget, current: QWidget):
        """Reveal keyboard actions without changing the reserved geometry."""
        self._sync_visibility()

    def _sync_visibility(self):
        """Keep menus usable while suppressing destructive visual noise at rest."""
        focused = QApplication.focusWidget()
        reveal = self.hovered or self.menu.isVisible() or focused == self or (focused is not None and self.isAncestorOf(focused))
        self.stack.currentWidget().setVisible(reveal)

    def eventFilter(self, watched: QWidget, event: QEvent):
        """Observe the whole section; child transitions do not count as leaving it."""
        if watched == self.section:
            if event.type() == QEvent.Type.Enter:
                self.hovered = True
                self._sync_visibility()
            elif event.type() == QEvent.Type.Leave:
                self.hovered = False
                self._sync_visibility()
        elif watched == self.section.header and event.type() == QEvent.Type.Resize:
            self.set_compact(watched.width() < 650)
            self._sync_visibility()
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        """Expose the group action menu through the reserved keyboard focus stop."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.open_menu()
        else:
            super().keyPressEvent(event)
