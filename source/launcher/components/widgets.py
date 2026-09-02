import os

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QEnterEvent,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QPolygon,
    QRegion,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from source.launcher.config.constants import (
    APP_TITLE,
    APP_VERSION,
    ASSETS,
    BUTTON_STYLES,
    BUTTON_TRANSITION_MS,
    COLORS,
    FONT_SIZES,
    TITLE_BAR_HEIGHT,
    UI_COLORS,
    UI_FONTS,
    UI_METRICS,
)


def sync_rounded_window_mask(widget: QWidget, radius: int, enabled: bool = True):
    """Apply or clear a rounded mask for a frameless top-level widget."""
    if not enabled or radius <= 0 or widget.width() <= 0 or widget.height() <= 0:
        widget.clearMask()
        return
    path = QPainterPath()
    path.addRoundedRect(QRectF(widget.rect()), radius, radius)
    widget.setMask(QRegion(path.toFillPolygon().toPolygon()))


def _qcolor_from_css(value: str):
    """Convert a project CSS color token into a QColor."""
    value = value.strip()
    if value.startswith("rgba(") and value.endswith(")"):
        parts = [int(part.strip()) for part in value[5:-1].split(",")]
        return QColor(*parts)
    return QColor(value)


class _RoundedBorderOverlay(QWidget):
    """Draw the shell border above child widgets."""

    def __init__(self, shell: "RoundedShellFrame"):
        super().__init__(shell)
        self.shell = shell
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        path = QPainterPath()
        path.addRoundedRect(rect, self.shell.radius, self.shell.radius)
        painter.setPen(QPen(_qcolor_from_css(self.shell.border), 1.25))
        painter.drawPath(path)


class RoundedShellFrame(QFrame):
    """Paint a translucent rounded shell with an overlaid inside border."""

    def __init__(
        self,
        background: str | None = None,
        border: str | None = None,
        radius: int | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.background = background or UI_COLORS["helper_shell_bg"]
        self.border = border or UI_COLORS["border_active"]
        self.radius = radius or UI_METRICS["radius_lg"]
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._border_overlay = _RoundedBorderOverlay(self)
        self._border_overlay.raise_()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)
        painter.fillPath(path, _qcolor_from_css(self.background))
        super().paintEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._border_overlay.setGeometry(self.rect())
        self._border_overlay.raise_()


class LogBridge(QObject):
    line = Signal(str)


class WrappedStatusLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text):
        super().setText(text)
        self._sync_minimum_height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_minimum_height()

    def _sync_minimum_height(self):
        width = self.width()
        if width > 0:
            height = self.heightForWidth(width)
            if height < 0:
                height = max(0, self.sizeHint().height())
            self.setMinimumHeight(height)
            self.updateGeometry()


class LoadingSpinner(QWidget):
    """Paint a compact rotating spinner for launcher loading states."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self._advance)
        self.setFixedSize(18, 18)
        self.hide()

    def start(self):
        if not self.timer.isActive():
            self.timer.start()
        self.show()

    def stop(self):
        self.timer.stop()
        self.hide()

    def _advance(self):
        self.angle = (self.angle + 30) % 360
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.setPen(QPen(QColor(COLORS["cyan"]), 2.2))
        painter.drawArc(rect, -self.angle * 16, 270 * 16)


class ClickableTextEdit(QTextEdit):
    copied = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scroll_animation = None
        self._scroll_target = None

    def mouseDoubleClickEvent(self, event):
        self.selectAll()
        self.copy()
        self.copied.emit()
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        if self._smooth_scroll(event.angleDelta().y()):
            event.accept()
            return
        super().wheelEvent(event)

    def _smooth_scroll(self, delta_y):
        if delta_y == 0:
            return False
        scrollbar = self.verticalScrollBar()
        step = scrollbar.singleStep() * 3
        start = (
            int(self._scroll_animation.endValue())
            if self._scroll_animation is not None
            and self._scroll_animation.state() == QVariantAnimation.State.Running
            else scrollbar.value()
        )
        target = start - int(delta_y / 120 * step)
        target = max(scrollbar.minimum(), min(scrollbar.maximum(), target))
        if target == scrollbar.value():
            return False
        if self._scroll_animation is not None:
            self._scroll_animation.stop()
        self._scroll_animation = QVariantAnimation(self)
        self._scroll_animation.setDuration(UI_METRICS["smooth_scroll_ms"])
        self._scroll_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_target = target
        self._scroll_animation.setStartValue(scrollbar.value())
        self._scroll_animation.setEndValue(target)
        self._scroll_animation.valueChanged.connect(
            lambda value: scrollbar.setValue(int(value))
        )
        self._scroll_animation.start()
        return True


class SmoothScrollArea(QScrollArea):
    """Animate wheel scrolling while leaving programmatic scrolling immediate."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scroll_animation = None
        self._scroll_target = None

    def wheelEvent(self, event):
        delta_y = event.angleDelta().y()
        if delta_y == 0:
            super().wheelEvent(event)
            return
        scrollbar = self.verticalScrollBar()
        step = scrollbar.singleStep() * 3
        start = (
            int(self._scroll_animation.endValue())
            if self._scroll_animation is not None
            and self._scroll_animation.state() == QVariantAnimation.State.Running
            else scrollbar.value()
        )
        target = start - int(delta_y / 120 * step)
        target = max(scrollbar.minimum(), min(scrollbar.maximum(), target))
        if target == scrollbar.value():
            super().wheelEvent(event)
            return
        if self._scroll_animation is not None:
            self._scroll_animation.stop()
        self._scroll_animation = QVariantAnimation(self)
        self._scroll_animation.setDuration(UI_METRICS["smooth_scroll_ms"])
        self._scroll_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_target = target
        self._scroll_animation.setStartValue(scrollbar.value())
        self._scroll_animation.setEndValue(target)
        self._scroll_animation.valueChanged.connect(
            lambda value: scrollbar.setValue(int(value))
        )
        self._scroll_animation.start()
        event.accept()


class CyberCheckBox(QCheckBox):
    """Paint a compact, high-contrast checkbox with native toggle semantics."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self._check_progress = 1.0 if self.isChecked() else 0.0
        self._check_animation = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        font = QFont(UI_FONTS["body"], FONT_SIZES["form"])
        font.setWeight(QFont.Weight.Bold)
        self.setFont(font)
        self.toggled.connect(self._animate_check)

    def sizeHint(self):
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        return QSize(18 + (8 + text_width if self.text() else 0), 24)

    def setChecked(self, checked: bool):
        was_checked = self.isChecked()
        signals_blocked = self.signalsBlocked()
        super().setChecked(checked)
        if signals_blocked and checked != was_checked:
            self._check_progress = 1.0 if checked else 0.0
            self.update()

    def _animate_check(self, checked: bool):
        """Animate the indicator fill when the checked state changes."""
        if self._check_animation is not None:
            self._check_animation.stop()
        self._check_animation = QVariantAnimation(self)
        self._check_animation.setDuration(140)
        self._check_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._check_animation.setStartValue(self._check_progress)
        self._check_animation.setEndValue(1.0 if checked else 0.0)
        self._check_animation.valueChanged.connect(self._set_check_progress)
        self._check_animation.start()

    def _set_check_progress(self, value: float):
        """Update the animated checked-state progress."""
        self._check_progress = float(value)
        self.update()

    def enterEvent(self, event: QEnterEvent):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        indicator_size = 18
        indicator = QRectF(
            0,
            (self.height() - indicator_size) / 2,
            indicator_size,
            indicator_size,
        )
        enabled = self.isEnabled()
        hovered = self.underMouse() and enabled
        unchecked_fill = QColor("#071019")
        checked_fill = QColor(COLORS["cyan"] if enabled else COLORS["muted"])
        fill = CyberSwitch._blend(unchecked_fill, checked_fill, self._check_progress)
        border = QColor(COLORS["cyan"] if enabled else COLORS["border"])
        if hovered:
            border = border.lighter(125)

        painter.setPen(QPen(border, 1.5))
        painter.setBrush(fill)
        painter.drawRoundedRect(indicator, 4, 4)

        if self._check_progress > 0:
            check_color = QColor(COLORS["text"])
            check_color.setAlpha(round(255 * self._check_progress))
            check_pen = QPen(check_color, 2.4)
            check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            check_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(check_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath()
            path.moveTo(4.5, indicator.center().y())
            path.lineTo(8.0, indicator.bottom() - 4.5)
            path.lineTo(14.0, indicator.top() + 4.5)
            painter.drawPath(path)

        if self.hasFocus():
            focus_color = QColor(COLORS["cyan"])
            focus_color.setAlpha(115)
            painter.setPen(QPen(focus_color, 1, Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 4, 4)

        if self.text():
            text_x = indicator_size + 8
            painter.setPen(QColor(COLORS["cyan"] if enabled else COLORS["muted"]))
            painter.setFont(self.font())
            painter.drawText(
                text_x,
                0,
                max(0, self.width() - text_x),
                self.height(),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self.text(),
            )


class CyberSwitch(QCheckBox):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._knob_progress = 0.0
        self._switch_animation = None
        self._loading = False
        self._loading_progress = 0.0
        self._loading_animation = QVariantAnimation(self)
        self._loading_animation.setDuration(900)
        self._loading_animation.setStartValue(0.0)
        self._loading_animation.setEndValue(1.0)
        self._loading_animation.setLoopCount(-1)
        self._loading_animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._loading_animation.valueChanged.connect(self._set_loading_progress)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(UI_METRICS["switch_height"])
        self.setMinimumWidth(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFont(QFont(UI_FONTS["body"], FONT_SIZES["form"]))
        self.toggled.connect(self._animate_toggle)

    def sizeHint(self):
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        label_width = text_width + 12 if self.text() else 0
        return QSize(max(58, 58 + label_width), UI_METRICS["switch_height"])

    def setChecked(self, checked):
        was_checked = self.isChecked()
        signals_blocked = self.signalsBlocked()
        super().setChecked(checked)
        if signals_blocked and checked != was_checked:
            self._knob_progress = 1.0 if checked else 0.0
            self.update()

    def hitButton(self, pos):
        return not self._loading and self.rect().contains(pos)

    @property
    def is_loading(self):
        """Return whether the integrated loading sweep is active."""
        return self._loading

    def set_loading(self, active: bool):
        """Show or hide the non-interactive loading sweep inside the switch."""
        active = bool(active)
        if active == self._loading:
            return
        self._loading = active
        if active:
            self.setCursor(Qt.CursorShape.BusyCursor)
            self._loading_animation.start()
        else:
            self._loading_animation.stop()
            self._loading_progress = 0.0
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update()

    def nextCheckState(self):
        if not self._loading:
            super().nextCheckState()

    def _set_loading_progress(self, value: float):
        """Advance the cyan loading sweep through the switch track."""
        self._loading_progress = float(value)
        self.update()

    def _animate_toggle(self, checked):
        start = self._knob_progress
        end = 1.0 if checked else 0.0
        if self._switch_animation is not None:
            self._switch_animation.stop()
        self._switch_animation = QVariantAnimation(self)
        self._switch_animation.setDuration(140)
        self._switch_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._switch_animation.setStartValue(start)
        self._switch_animation.setEndValue(end)

        def update(value):
            self._knob_progress = float(value)
            self.update()

        self._switch_animation.valueChanged.connect(update)
        self._switch_animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_x = 3
        track_y = max(3, (self.height() - 22) // 2)
        track = QRect(track_x, track_y, 50, 22)
        track_color = self._blend("#101820", "#0E3A4D", self._knob_progress)
        border_color = self._blend(
            COLORS["border"], COLORS["cyan"], self._knob_progress
        )
        knob_color = self._blend(COLORS["muted"], COLORS["cyan"], self._knob_progress)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 10, 10)

        if self._loading:
            sweep_center = (
                track.left() - 18 + self._loading_progress * (track.width() + 36)
            )
            sweep = QLinearGradient(sweep_center - 14, 0, sweep_center + 14, 0)
            transparent = QColor(COLORS["cyan"])
            transparent.setAlpha(0)
            highlight = QColor(COLORS["cyan"])
            highlight.setAlpha(145)
            sweep.setColorAt(0.0, transparent)
            sweep.setColorAt(0.5, highlight)
            sweep.setColorAt(1.0, transparent)
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(track), 10, 10)
            painter.save()
            painter.setClipPath(clip)
            painter.fillRect(track, sweep)
            painter.restore()

        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(track, 10, 10)

        knob_x = track_x + 4 + round(23 * self._knob_progress)
        knob_y = track_y + 4
        painter.setPen(Qt.PenStyle.NoPen)
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
                Qt.AlignmentFlag.AlignVCenter,
                self.text(),
            )

    @staticmethod
    def _blend(start, end, ratio):
        start_color = QColor(start)
        end_color = QColor(end)
        red = round(start_color.red() + (end_color.red() - start_color.red()) * ratio)
        green = round(
            start_color.green() + (end_color.green() - start_color.green()) * ratio
        )
        blue = round(
            start_color.blue() + (end_color.blue() - start_color.blue()) * ratio
        )
        return QColor(red, green, blue)


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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        width = rect.width()
        used_width = int(width * self.percent / 100)
        painter.setPen(Qt.PenStyle.NoPen)

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
        self._loading = False
        self._loading_angle = 0
        self._loading_text = ""
        self._loading_was_enabled = True
        self._loading_timer = QTimer(self)
        self._loading_timer.setInterval(80)
        self._loading_timer.timeout.connect(self._advance_loading_spinner)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(
            QFont(UI_FONTS["display"], FONT_SIZES["button"], QFont.Weight.Bold)
        )
        self._apply_style()
        self.toggled.connect(self._handle_toggled)

    def set_loading(self, active: bool, text: str = "LOADING"):
        """Show or hide a disabled rotating loading indicator on the button."""
        if active == self._loading:
            return
        self._loading = active
        if active:
            self._loading_text = self.text()
            self._loading_was_enabled = self.isEnabled()
            self.setText(text)
            self.setEnabled(False)
            self._loading_timer.start()
        else:
            self._loading_timer.stop()
            self.setText(self._loading_text)
            self.setEnabled(self._loading_was_enabled)
        self.update()

    def _advance_loading_spinner(self):
        """Advance the loading arc by one animation frame."""
        self._loading_angle = (self._loading_angle - 30) % 360
        self.update()

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
        if self.isEnabled() == enabled:
            return
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
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self.set_state("active")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        try:
            if not self.isEnabled():
                return
            if self.isChecked():
                self.set_state("active")
            elif self.underMouse():
                self.set_state("hover")
            else:
                self.set_state("normal")
        except RuntimeError:
            return

    def paintEvent(self, event: QPaintEvent):
        """Paint the normal button and its optional loading arc."""
        super().paintEvent(event)
        if not self._loading:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(COLORS["cyan"]), 2.2))
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        spinner_size = 14
        spinner_x = max(8, (self.width() - text_width) // 2 - spinner_size - 8)
        spinner_y = (self.height() - spinner_size) // 2
        painter.drawArc(
            QRect(spinner_x, spinner_y, spinner_size, spinner_size),
            self._loading_angle * 16,
            250 * 16,
        )

    def _handle_toggled(self, checked):
        if self.isEnabled():
            self.set_state("active" if checked else "normal")

    def _animate_to(self, target):
        start = self._colors.copy()
        if self._animation:
            self._animation.stop()
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(BUTTON_TRANSITION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
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
        is_expand = self.objectName() == "HelperExpandButton"
        min_height = (
            "0px"
            if self.variant in ("chrome", "close")
            else (
                f"{UI_METRICS['helper_expand_height']}px"
                if is_expand
                else f"{UI_METRICS['control_height']}px"
            )
        )
        padding = (
            "0px"
            if self.variant in ("chrome", "close") or is_expand
            else UI_METRICS["control_padding"]
        )
        compact_size = (
            f"min-width: {UI_METRICS['helper_expand_width']}px; "
            f"max-width: {UI_METRICS['helper_expand_width'] + 2}px;"
            if is_expand
            else ""
        )
        is_chrome = self.variant in ("chrome", "close")
        border = "none" if is_chrome else f"1px solid {self._colors['border']}"
        disabled_border = (
            "none"
            if is_chrome
            else f"1px solid {BUTTON_STYLES[self.variant]['disabled']['border']}"
        )
        radius = "0px" if is_chrome else f"{UI_METRICS['radius_sm']}px"
        self.setStyleSheet(f"""
            {selector} {{
                min-height: {min_height};
                padding: {padding};
                background: {self._colors["bg"]};
                color: {self._colors["fg"]};
                border: {border};
                border-radius: {radius};
                font-weight: 900;
                {compact_size}
            }}
            {selector}:disabled {{
                background: {BUTTON_STYLES[self.variant]["disabled"]["bg"]};
                color: {BUTTON_STYLES[self.variant]["disabled"]["fg"]};
                border: {disabled_border};
                border-radius: {radius};
            }}
            {selector}:hover, {selector}:checked {{
                background: {self._colors["bg"]};
                color: {self._colors["fg"]};
                border: {border};
                border-radius: {radius};
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
        self.setFixedSize(46, TITLE_BAR_HEIGHT - 1)
        self.setObjectName("ChromeIconButton")
        self.set_state("normal")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
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


class ToolCoverCard(QFrame):
    """Paint an image-led tool card with a dark readability overlay."""

    def __init__(self, image_path="", parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.pixmap = (
            QPixmap(image_path)
            if image_path and os.path.exists(image_path)
            else QPixmap()
        )
        self.setObjectName("ToolCoverCard")
        self.setMinimumHeight(UI_METRICS["tool_cover_min_height"])
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        radius = UI_METRICS["radius_lg"]
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)
        painter.setClipPath(path)
        painter.fillRect(rect, QColor("#03070C"))

        if not self.pixmap.isNull():
            art = self.pixmap.scaled(
                rect.width(),
                rect.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(
                (rect.width() - art.width()) // 2,
                (rect.height() - art.height()) // 2,
                art,
            )

        overlay = QLinearGradient(QPointF(0, 0), QPointF(rect.width(), rect.height()))
        overlay.setColorAt(0.0, QColor(3, 7, 12, 230))
        overlay.setColorAt(0.55, QColor(3, 7, 12, 160))
        overlay.setColorAt(1.0, QColor(3, 7, 12, 92))
        painter.fillRect(rect, QBrush(overlay))
        painter.setClipping(False)
        painter.setPen(QPen(QColor(0, 216, 255, 70), 1))
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), radius, radius)


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
        self.status_label = status

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
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.window.is_custom_maximized
        ):
            ratio = event.position().x() / max(1, self.width())
            self.window.start_drag_from_custom_maximized(
                event.globalPosition().toPoint(), ratio
            )
            self.drag_position = (
                event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if (
            getattr(self, "drag_position", None)
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.window.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
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
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

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


class CyberTextInputDialog(QDialog):
    """Collect one text value using the launcher's custom dialog styling."""

    def __init__(
        self,
        parent: QWidget,
        title: str,
        message: str,
        value: str = "",
        confirm_text: str = "SAVE",
    ):
        super().__init__(parent)
        self.setObjectName("CyberDialog")
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        shell = QFrame()
        shell.setObjectName("DialogShell")
        shell.setStyleSheet(f"""
            QFrame#DialogShell {{ background: #050B12; border: 1px solid {COLORS["cyan"]}; }}
            QLabel#DialogTitle {{ color: {COLORS["cyan"]}; font-size: {FONT_SIZES["dialog_title"]}px; font-weight: 800; }}
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
        self.field = QLineEdit(value)
        self.field.setObjectName("SettingField")
        self.field.selectAll()

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = AnimatedButton("CANCEL", "secondary")
        cancel.clicked.connect(self.reject)
        confirm = AnimatedButton(confirm_text, "primary")
        confirm.clicked.connect(self._accept_non_empty)
        actions.addWidget(cancel)
        actions.addWidget(confirm)
        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addWidget(self.field)
        layout.addLayout(actions)
        self.setFixedWidth(430)

    def _accept_non_empty(self):
        """Accept only when a non-empty display name was entered."""
        if self.field.text().strip():
            self.accept()

    def text_value(self):
        """Return the exact entered display name."""
        return self.field.text()


class CyberTemplateConflictDialog(QDialog):
    """Offer replace, keep-both, or cancel for a template collision."""

    KEEP_BOTH_RESULT = 2

    def __init__(self, parent: QWidget, template_name: str):
        super().__init__(parent)
        self.setObjectName("CyberDialog")
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        shell = QFrame()
        shell.setObjectName("DialogShell")
        shell.setStyleSheet(f"""
            QFrame#DialogShell {{ background: #050B12; border: 1px solid {COLORS["yellow"]}; }}
            QLabel#DialogTitle {{ color: {COLORS["yellow"]}; font-size: {FONT_SIZES["dialog_title"]}px; font-weight: 800; }}
            QLabel#DialogMessage {{ color: {COLORS["text"]}; font-size: {FONT_SIZES["dialog_message"]}px; }}
            """)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(shell)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)
        heading = QLabel("TEMPLATE ALREADY EXISTS")
        heading.setObjectName("DialogTitle")
        body = QLabel(
            f'A template conflicts with "{template_name}". Replace the existing '
            "template or keep both under a new incoming name?"
        )
        body.setObjectName("DialogMessage")
        body.setWordWrap(True)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = AnimatedButton("CANCEL", "secondary")
        cancel.clicked.connect(self.reject)
        keep = AnimatedButton("KEEP BOTH", "secondary")
        keep.clicked.connect(lambda: self.done(self.KEEP_BOTH_RESULT))
        replace = AnimatedButton("REPLACE", "danger")
        replace.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(keep)
        actions.addWidget(replace)
        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addLayout(actions)
        self.setFixedWidth(520)


class HeroBanner(QFrame):
    BANNER_HEIGHT = 180

    ART_HEIGHT = 480
    ART_RIGHT_MARGIN = 8
    ART_TOP = -96

    BACKDROP_TOP_WIDTH = 520
    BACKDROP_BOTTOM_WIDTH = 420
    BACKDROP_OPACITY = 120
    BACKDROP_FADE_START = 0.4

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
        self.setMinimumHeight(self.BANNER_HEIGHT)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor("#03070C"))

        if not self.art.isNull():
            # Object fit cover
            # art = self.art.scaled(
            #     rect.width(),
            #     rect.height(),
            #     Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            #     Qt.TransformationMode.SmoothTransformation,
            # )

            # Object fixed
            art = self.art.scaledToHeight(
                self.ART_HEIGHT, Qt.TransformationMode.SmoothTransformation
            )

            painter.drawPixmap(
                rect.width() - art.width() - self.ART_RIGHT_MARGIN,
                self.ART_TOP,
                art,
            )

        backdrop = QPolygon(
            [
                QPoint(0, 0),
                QPoint(self.BACKDROP_TOP_WIDTH, 0),
                QPoint(self.BACKDROP_BOTTOM_WIDTH, rect.height()),
                QPoint(0, rect.height()),
            ]
        )
        edge_height = rect.height()
        edge_width = self.BACKDROP_TOP_WIDTH - self.BACKDROP_BOTTOM_WIDTH
        edge_normal_length_squared = edge_height**2 + edge_width**2
        edge_offset = edge_height * self.BACKDROP_TOP_WIDTH
        backdrop_gradient = QLinearGradient(
            QPointF(0, 0),
            QPointF(
                edge_height * edge_offset / edge_normal_length_squared,
                edge_width * edge_offset / edge_normal_length_squared,
            ),
        )
        backdrop_color = QColor("#03070C")
        backdrop_color.setAlpha(self.BACKDROP_OPACITY)
        backdrop_transparent = QColor("#03070C")
        backdrop_transparent.setAlpha(0)
        backdrop_gradient.setColorAt(0, backdrop_color)
        backdrop_gradient.setColorAt(self.BACKDROP_FADE_START, backdrop_color)
        backdrop_gradient.setColorAt(1, backdrop_transparent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(backdrop_gradient))
        painter.drawPolygon(backdrop)

        painter.setPen(QColor(COLORS["cyan"]))
        painter.drawLine(0, rect.height() - 2, rect.width(), rect.height())

        painter.setPen(QColor(COLORS["cyan"]))
        painter.setFont(
            QFont(UI_FONTS["display"], FONT_SIZES["section_heading"], QFont.Weight.Bold)
        )
        painter.drawText(28, 42, "WELCOME BACK,")
        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(
            QFont(UI_FONTS["display"], FONT_SIZES["welcome_title"], QFont.Weight.Bold)
        )
        painter.drawText(28, 88, f"{APP_TITLE}.")
        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont(UI_FONTS["mono"], FONT_SIZES["chrome_status"]))
        painter.drawText(28, 128, "SYSTEM STATUS")
        painter.setPen(QColor(COLORS["green"]))
        painter.setFont(QFont(UI_FONTS["mono"], FONT_SIZES["form"], QFont.Weight.Bold))
        painter.drawText(165, 128, "ONLINE")
