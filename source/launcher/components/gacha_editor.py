"""Illustrated Gacha side controls; record mutation belongs to the page handler."""

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QSizePolicy

from source.launcher import settings_theme
from source.launcher.config.constants import ASSETS
from source.launcher.dashboard_theme import asset_path


@lru_cache(maxsize=8)
def side_art(side: str):
    """Load replaceable artwork and a grayscale variant once per side."""
    candidates = (f"settings.gacha_{side}", "settings.breadcrumb", "dashboard")
    path = next(asset_path(ASSETS[key]) for key in candidates if Path(asset_path(ASSETS[key])).is_file())
    color = QPixmap(path)
    gray = QPixmap.fromImage(color.toImage().convertToFormat(QImage.Format.Format_Grayscale8))
    return color, gray


class GachaSideCard(QFrame):
    """Animate record presence independently of Qt's profile-lock enabled state."""

    toggleRequested = Signal()

    def __init__(self, side: str, present: bool):
        super().__init__()
        self.side = side
        self.present = present
        self.progress = float(present)
        self.hover = 0.0
        self.setMinimumWidth(0)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        arrow = Path(asset_path(ASSETS["icon.double_chevron"])).read_bytes()
        if side == "right":
            arrow = arrow.replace(b"#00D9FF", b"#FF4677")
        self.arrow = QSvgRenderer(arrow, self)
        self.art, self.gray = side_art(side)
        self._scaled_key = None
        self._scaled = ()
        self.state_animation = self._animation(220, self._state_frame)
        self.hover_animation = self._animation(150, self._hover_frame)
        self.set_present(present, animate=False)

    def resizeEvent(self, event: object):
        """Constrain the layout height after the parent allocates actual width."""
        height = self.heightForWidth(self.width())
        if self.minimumHeight() != height or self.maximumHeight() != height:
            self.setFixedHeight(height)
            self.updateGeometry()
        super().resizeEvent(event)

    def heightForWidth(self, width: int):
        """Keep both side variants at the shared panoramic 4:1 ratio."""
        return round(width / 4)

    def sizeHint(self):
        """Supply a width-based preferred size to Qt layouts."""
        return QSize(320, 80)

    def minimumSizeHint(self):
        """Allow the parent layout to shrink without imposing a fixed height."""
        return QSize(120, 30)

    def _animation(self, duration: int, callback: object):
        """Allocate and connect each animation only once."""
        animation = QVariantAnimation(self)
        animation.setDuration(duration)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        animation.valueChanged.connect(callback)
        return animation

    def _state_frame(self, value: float):
        """Paint interpolated color without accessing files or settings."""
        self.progress = float(value)
        self.update()

    def _hover_frame(self, value: float):
        """Update the restrained hover highlight."""
        self.hover = float(value)
        self.update()

    def set_present(self, present: bool, animate: bool = True):
        """Reflect a successfully saved side record, reversing from current progress."""
        self.present = present
        self.setAccessibleName(f"{self.side.title()} side: {'enabled' if present else 'absent'}")
        self.setToolTip("Click to remove this side" if present else "Click to add this side")
        self.state_animation.stop()
        if animate:
            self.state_animation.setStartValue(self.progress)
            self.state_animation.setEndValue(float(present))
            self.state_animation.start()
        else:
            self._state_frame(float(present))

    def enterEvent(self, event: object):
        """Brighten without changing the card geometry."""
        self.hover_animation.stop()
        self.hover_animation.setStartValue(self.hover)
        self.hover_animation.setEndValue(1.0)
        self.hover_animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event: object):
        """Return smoothly to the idle border."""
        self.hover_animation.stop()
        self.hover_animation.setStartValue(self.hover)
        self.hover_animation.setEndValue(0.0)
        self.hover_animation.start()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: object):
        """Activate only the card background; editors consume their own clicks."""
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.toggleRequested.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: object):
        """Offer the same action from keyboard focus."""
        if self.isEnabled() and event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            self.toggleRequested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event: object):
        """Clip proportional artwork and all overlays to one antialiased shape."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        bounds = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(bounds, 8, 8)
        font = QFont("Segoe UI")
        font.setPixelSize(16)
        font.setBold(True)
        painter.setFont(font)
        label = "LEFT SIDE" if self.side == "left" else "RIGHT SIDE"
        text_width = painter.fontMetrics().horizontalAdvance(label)
        x = (self.width() - text_width - 30) / 2
        y = (self.height() - 24) / 2
        text_x = x + 30 if self.side == "left" else x
        arrow_x = x if self.side == "left" else x + text_width + 6
        painter.fillPath(path, QColor("#03111B"))
        painter.save()
        painter.setClipPath(path)
        ratio = self.devicePixelRatioF()
        key = (self.width(), self.height(), ratio)
        if key != self._scaled_key:
            self._scaled = tuple(
                p.scaled(round(self.width() * ratio), round(self.height() * ratio), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                for p in (self.gray, self.art)
            )
            for pixmap in self._scaled:
                pixmap.setDevicePixelRatio(ratio)
            self._scaled_key = key
        for pixmap, opacity in zip(self._scaled, (1.0, self.progress), strict=True):
            painter.setOpacity(opacity)
            painter.drawPixmap(round((self.width() - pixmap.width() / ratio) / 2), round((self.height() - pixmap.height() / ratio) / 2), pixmap)
        painter.setOpacity(1)
        painter.fillRect(bounds, QColor(1, 9, 16, round(180 - 70 * self.progress - 15 * self.hover)))
        accent = QColor("#00D9FF" if self.side == "left" else "#FF4677")
        tint = QColor(accent)
        tint.setAlphaF(max(0.0, min(1.0, settings_theme.GACHA_TINT_MAX_OPACITY)) * self.progress)
        clear = QColor(accent)
        clear.setAlphaF(0)
        gradient = QLinearGradient(bounds.topLeft(), bounds.topRight())
        offset = settings_theme.GACHA_TINT_START_OFFSET_PX
        start = arrow_x + offset if self.side == "left" else arrow_x + 24 - offset
        stop = max(0.0, min(1.0, (start - bounds.left()) / max(1.0, bounds.width())))
        if self.side == "left":
            gradient.setColorAt(0, clear)
            gradient.setColorAt(min(stop, 0.999999), clear)
            gradient.setColorAt(1, tint)
        else:
            gradient.setColorAt(0, tint)
            gradient.setColorAt(max(stop, 0.000001), clear)
            gradient.setColorAt(1, clear)
        painter.fillRect(bounds, gradient)
        painter.restore()
        muted = QColor("#46606A")
        border = QColor(*(round(a + (b - a) * self.progress) for a, b in zip(muted.getRgb()[:3], accent.getRgb()[:3], strict=True)))
        border.setAlphaF(0.22 + 0.18 * self.progress + 0.12 * self.hover)
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)
        painter.setPen(accent if self.present else QColor("#80919C"))
        painter.drawText(QRectF(text_x, y, text_width, 24), Qt.AlignmentFlag.AlignCenter, label)
        painter.save()
        painter.setOpacity(0.9 if self.present else 0.4)
        painter.translate(arrow_x + 12, y + 12)
        if self.side == "right":
            painter.rotate(180)
        self.arrow.render(painter, QRectF(-12, -12, 24, 24))
        painter.restore()
        if self.hasFocus():
            painter.setPen(QPen(accent, 1, Qt.PenStyle.DotLine))
            painter.drawRoundedRect(bounds.adjusted(3, 3, -3, -3), 6, 6)
