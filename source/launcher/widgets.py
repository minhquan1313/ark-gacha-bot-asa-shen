import os

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QRect,
    QSize,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from source.launcher.constants import (
    APP_TITLE,
    APP_VERSION,
    ASSETS,
    BUTTON_STYLES,
    BUTTON_TRANSITION_MS,
    COLORS,
    FONT_SIZES,
    TITLE_BAR_HEIGHT,
)


class LogBridge(QObject):
    line = Signal(str)


class ClickableTextEdit(QTextEdit):
    copied = Signal()

    def mouseDoubleClickEvent(self, event):
        self.selectAll()
        self.copy()
        self.copied.emit()
        super().mouseDoubleClickEvent(event)


class CyberSwitch(QCheckBox):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(32)
        self.setMinimumWidth(58)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFont(QFont("Segoe UI", FONT_SIZES["form"]))

    def sizeHint(self):
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        label_width = text_width + 12 if self.text() else 0
        return QSize(max(58, 58 + label_width), 32)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        track_x = 3
        track_y = max(3, (self.height() - 22) // 2)
        track = QRect(track_x, track_y, 50, 22)
        checked = self.isChecked()
        track_color = QColor("#0E3A4D" if checked else "#101820")
        border_color = QColor(COLORS["cyan"] if checked else COLORS["border"])
        knob_color = QColor(COLORS["cyan"] if checked else COLORS["muted"])

        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 10, 10)

        knob_x = track_x + (27 if checked else 4)
        knob_y = track_y + 4
        painter.setPen(Qt.NoPen)
        painter.setBrush(knob_color)
        painter.drawEllipse(knob_x, knob_y, 14, 14)

        if self.text():
            text_x = track.right() + 12
            painter.setPen(QColor(COLORS["text"]))
            painter.setFont(self.font())
            painter.drawText(
                text_x,
                0,
                max(0, self.width() - text_x),
                self.height(),
                Qt.AlignVCenter,
                self.text(),
            )


class MeterBar(QWidget):
    def __init__(self, accent=None, parent=None):
        super().__init__(parent)
        self.percent = 0
        self.accent = accent or COLORS["green"]
        self.setFixedHeight(11)

    def set_percent(self, percent):
        self.percent = max(0, min(100, int(percent)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        width = rect.width()
        used_width = int(width * self.percent / 100)
        painter.setPen(Qt.NoPen)

        rail_y = (rect.height() - 5) // 2
        total_rect = QRect(0, rail_y, width, 5)
        painter.setBrush(QColor("#24566A"))
        painter.drawRoundedRect(total_rect, 2, 2)

        used_rect = QRect(0, rail_y, used_width, 5)
        painter.setBrush(
            QColor(COLORS["yellow"] if self.percent >= 80 else self.accent)
        )
        painter.drawRoundedRect(used_rect, 2, 2)


class AnimatedButton(QPushButton):
    def __init__(self, text="", variant="secondary", parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self._state = "normal"
        self._animation = None
        self._colors = BUTTON_STYLES[variant]["normal"].copy()
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Segoe UI", FONT_SIZES["button"], QFont.Bold))
        self._apply_style()
        self.toggled.connect(self._handle_toggled)

    def set_state(self, state):
        if not self.isEnabled():
            state = "disabled"
        self._state = state
        self._animate_to(BUTTON_STYLES[self.variant][state])

    def set_variant(self, variant):
        if self.variant == variant:
            return
        self.variant = variant
        self._colors = BUTTON_STYLES[variant]["normal"].copy()
        self.set_state("normal")

    def setObjectName(self, name):
        super().setObjectName(name)
        self._apply_style()

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.set_state("normal" if enabled else "disabled")

    def enterEvent(self, event):
        if self.isEnabled() and not self.isChecked():
            self.set_state("hover")
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.isEnabled() and not self.isChecked():
            self.set_state("normal")
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == Qt.LeftButton:
            self.set_state("active")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if not self.isEnabled():
            return
        if self.isChecked():
            self.set_state("active")
        elif self.underMouse():
            self.set_state("hover")
        else:
            self.set_state("normal")

    def _handle_toggled(self, checked):
        if self.isEnabled():
            self.set_state("active" if checked else "normal")

    def _animate_to(self, target):
        start = self._colors.copy()
        if self._animation:
            self._animation.stop()
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(BUTTON_TRANSITION_MS)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)

        def update(value):
            self._colors = {
                key: self._mix_color(start[key], target[key], value)
                for key in ("bg", "fg", "border")
            }
            self._apply_style()

        self._animation.valueChanged.connect(update)
        self._animation.start()

    def _apply_style(self):
        selector = (
            f"QPushButton#{self.objectName()}" if self.objectName() else "QPushButton"
        )
        min_height = "0px" if self.variant in ("chrome", "close") else "34px"
        padding = "0px" if self.variant in ("chrome", "close") else "5px 16px"
        self.setStyleSheet(f"""
            {selector} {{
                min-height: {min_height};
                padding: {padding};
                background: {self._colors["bg"]};
                color: {self._colors["fg"]};
                border: 1px solid {self._colors["border"]};
                font-weight: 900;
            }}
            {selector}:disabled {{
                background: {BUTTON_STYLES[self.variant]["disabled"]["bg"]};
                color: {BUTTON_STYLES[self.variant]["disabled"]["fg"]};
                border: 1px solid {BUTTON_STYLES[self.variant]["disabled"]["border"]};
            }}
            {selector}:hover, {selector}:checked {{
                background: {self._colors["bg"]};
                color: {self._colors["fg"]};
                border: 1px solid {self._colors["border"]};
            }}
            """)

    @staticmethod
    def _mix_color(start, end, ratio):
        start_color = QColor(start)
        end_color = QColor(end)
        red = round(start_color.red() + (end_color.red() - start_color.red()) * ratio)
        green = round(
            start_color.green() + (end_color.green() - start_color.green()) * ratio
        )
        blue = round(
            start_color.blue() + (end_color.blue() - start_color.blue()) * ratio
        )
        return QColor(red, green, blue).name()


class ChromeIconButton(AnimatedButton):
    def __init__(self, icon_name, parent=None):
        variant = "close" if icon_name == "close" else "chrome"
        super().__init__("", variant, parent)
        self.icon_name = icon_name
        self.setFixedSize(46, TITLE_BAR_HEIGHT)
        self.setObjectName("ChromeIconButton")
        self.set_state("normal")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(self._colors["fg"]), 2.4)
        painter.setPen(pen)
        center_y = self.height() // 2
        if self.icon_name == "minimize":
            painter.drawLine(14, center_y + 7, self.width() - 14, center_y + 7)
        elif self.icon_name == "maximize":
            painter.drawRect(14, 13, self.width() - 28, self.height() - 26)
        elif self.icon_name == "restore":
            painter.drawRect(12, 16, self.width() - 30, self.height() - 27)
            painter.drawRect(17, 11, self.width() - 30, self.height() - 27)
        elif self.icon_name == "close":
            painter.drawLine(15, 12, self.width() - 15, self.height() - 12)
            painter.drawLine(self.width() - 15, 12, 15, self.height() - 12)

    def set_icon(self, icon_name):
        self.icon_name = icon_name
        self.update()


class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.drag_position = None
        self.setObjectName("TitleBar")
        self.setFixedHeight(TITLE_BAR_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel(APP_TITLE)
        title.setObjectName("ChromeTitle")
        version = QLabel(APP_VERSION)
        version.setObjectName("ChromeVersion")
        status = QLabel("SYSTEM READY")
        status.setObjectName("ChromeStatus")

        layout.addWidget(title)
        layout.addWidget(version)
        layout.addStretch()
        layout.addWidget(status)
        layout.addSpacing(10)

        self.minimize_button = ChromeIconButton("minimize")
        self.maximize_button = ChromeIconButton("maximize")
        self.close_button = ChromeIconButton("close")
        self.minimize_button.clicked.connect(window.showMinimized)
        self.maximize_button.clicked.connect(window.toggle_max_restore)
        self.close_button.clicked.connect(window.close)
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.window.is_custom_maximized:
            ratio = event.position().x() / max(1, self.width())
            self.window.start_drag_from_custom_maximized(
                event.globalPosition().toPoint(), ratio
            )
            self.drag_position = (
                event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if getattr(self, "drag_position", None) and event.buttons() & Qt.LeftButton:
            self.window.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window.toggle_max_restore()
            event.accept()

    def sync_maximize_icon(self):
        self.maximize_button.set_icon(
            "restore" if self.window.is_custom_maximized else "maximize"
        )


class CyberDialog(QDialog):
    def __init__(
        self,
        parent,
        title,
        message,
        variant="info",
        confirm_text="OK",
        cancel_text=None,
    ):
        super().__init__(parent)
        self.setObjectName("CyberDialog")
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        accent = {
            "success": COLORS["green"],
            "warning": COLORS["yellow"],
            "error": COLORS["red"],
            "confirm": COLORS["cyan"],
            "info": COLORS["cyan"],
        }.get(variant, COLORS["cyan"])

        shell = QFrame()
        shell.setObjectName("DialogShell")
        shell.setStyleSheet(f"""
            QFrame#DialogShell {{
                background: #050B12;
                border: 1px solid {accent};
            }}
            QLabel#DialogTitle {{ color: {accent}; font-size: {FONT_SIZES["dialog_title"]}px; font-weight: 800; }}
            QLabel#DialogMessage {{ color: {COLORS["text"]}; font-size: {FONT_SIZES["dialog_message"]}px; }}
            """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(shell)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        heading = QLabel(title.upper())
        heading.setObjectName("DialogTitle")
        body = QLabel(message)
        body.setObjectName("DialogMessage")
        body.setWordWrap(True)

        actions = QHBoxLayout()
        actions.addStretch()
        if cancel_text:
            cancel = AnimatedButton(cancel_text, "secondary")
            cancel.clicked.connect(self.reject)
            actions.addWidget(cancel)
        confirm = AnimatedButton(confirm_text, "primary")
        confirm.clicked.connect(self.accept)
        actions.addWidget(confirm)

        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addLayout(actions)
        self.setFixedWidth(430)


class HeroBanner(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.logo = (
            QPixmap(ASSETS["logo"]) if os.path.exists(ASSETS["logo"]) else QPixmap()
        )
        self.art = (
            QPixmap(ASSETS["dashboard"])
            if os.path.exists(ASSETS["dashboard"])
            else QPixmap()
        )
        self.setObjectName("HeroBanner")
        self.setMinimumHeight(150)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor("#03070C"))

        if not self.art.isNull():
            art = self.art.scaled(
                rect.width(),
                rect.height() + 180,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            painter.setOpacity(0.62)
            painter.drawPixmap(rect.width() - art.width(), -80, art)
            painter.setOpacity(1)

        painter.fillRect(rect, QBrush(QColor(3, 7, 12, 110)))
        painter.setPen(QColor("#0E3D54"))
        for x in range(-80, rect.width() + 80, 42):
            painter.drawLine(x, 0, x + 80, rect.height())

        painter.setPen(QColor(COLORS["cyan"]))
        painter.drawLine(0, rect.height() - 2, rect.width(), rect.height() - 2)

        if not self.logo.isNull() and rect.width() > 760:
            logo = self.logo.scaled(
                118, 118, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            painter.drawPixmap(rect.width() - 150, 16, logo)

        painter.setPen(QColor(COLORS["cyan"]))
        painter.setFont(QFont("Segoe UI", FONT_SIZES["section_heading"], QFont.Bold))
        painter.drawText(28, 42, "WELCOME BACK,")
        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(QFont("Segoe UI", FONT_SIZES["welcome_title"], QFont.Bold))
        painter.drawText(28, 88, f"{APP_TITLE}.")
        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Consolas", FONT_SIZES["chrome_status"]))
        painter.drawText(28, 128, "SYSTEM STATUS")
        painter.setPen(QColor(COLORS["green"]))
        painter.setFont(QFont("Consolas", FONT_SIZES["form"], QFont.Bold))
        painter.drawText(165, 128, "ONLINE")
