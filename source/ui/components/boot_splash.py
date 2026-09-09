"""Lightweight painted startup surface; independent of launcher page imports."""

import math
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QElapsedTimer,
    QEvent,
    QObject,
    QRect,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QCursor,
    QFont,
    QImage,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid


class _SplashImages(QObject):
    """Decode startup artwork off the GUI thread without delaying first feedback."""

    loaded = Signal(QImage, QImage)

    def __init__(self, assets: Path):
        """Keep cancellation independent of the receiving widget's lifetime."""
        super().__init__()
        self._assets = assets
        self._stop = threading.Event()

    def start(self):
        """Decode once on a daemon worker; never join it from the GUI thread."""
        threading.Thread(target=self._load, daemon=True, name="splash-images").start()

    def cancel(self):
        """Discard pending decoding results without blocking shutdown."""
        self._stop.set()

    def _load(self):
        """Load thread-safe QImages, leaving QPixmap creation to the GUI thread."""
        images = []
        for name in ("logo.png", "dashboard.png"):
            if self._stop.is_set():
                return
            images.append(QImage(str(self._assets / name)))
        if not self._stop.is_set():
            self.loaded.emit(*images)


class _TransitionSurface(QWidget):
    """Paint the reveal in a separate window whose native geometry never changes."""

    first_painted = Signal()
    cancelled = Signal()

    def __init__(
        self,
        paint_frame: Callable[[QPainter], object],
        cancel_click: Callable[[QMouseEvent], object],
    ):
        """Create a hidden canvas and defer readiness until its first paint returns."""
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._paint_frame = paint_frame
        self._cancel_click = cancel_click
        self._painted = False
        self._ready = QTimer(self)
        self._ready.setSingleShot(True)
        self._ready.timeout.connect(self.first_painted.emit)

    def paintEvent(self, event: QPaintEvent):
        """Allow the first native frame to be presented before publishing readiness."""
        painter = QPainter(self)
        self._paint_frame(painter)
        painter.end()
        if not self._painted:
            self._painted = True
            self._ready.start(16)

    def mousePressEvent(self, event: QMouseEvent):
        """Forward clicks to the splash's existing cancellation control."""
        self._cancel_click(event)

    def closeEvent(self, event: QCloseEvent):
        """Treat a user closing the transition as startup cancellation."""
        self.cancelled.emit()
        super().closeEvent(event)

    def dispose(self):
        """Cancel queued readiness and release the independent native surface."""
        self._ready.stop()
        self.hide()
        self.deleteLater()


class BootSplash(QWidget):
    first_presented = Signal()
    finished = Signal()
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, reveal_delay_ms: int = 0):
        """Show a cinematic boot surface centered on the active display."""
        super().__init__()
        self.setWindowTitle("Shen GBot")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(600, 340)
        self._screen = (
            QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        )
        geometry = self.geometry()
        geometry.moveCenter(self._screen.availableGeometry().center())
        self.setGeometry(geometry)
        self._logo = QPixmap()
        self._artwork = QPixmap()
        self._images = _SplashImages(
            Path(__file__).resolve().parents[3] / "assets/app/image"
        )
        self._images.loaded.connect(self._apply_images)
        self._first_frame = QTimer(self)
        self._first_frame.setSingleShot(True)
        self._first_frame.timeout.connect(self._notify_presented)
        self._painted = False
        self._presented = False
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.setTimerType(Qt.TimerType.PreciseTimer)
        self._hold.setInterval(max(0, reveal_delay_ms))
        self._hold.timeout.connect(self._begin_reveal)
        self._status = "Starting launcher"
        self._window = None
        self._finished = False
        self._cancelled = False
        self._expansion = 0.0
        self._fade = 0.0
        self._dashboard = QPixmap()
        self._compact = QPixmap()
        self._surface: _TransitionSurface | None = None
        self._reveal_started = False
        self._stopped = False
        self._paint_bounds = QRectF(self.rect())
        self._prepare = QTimer(self)
        self._prepare.setSingleShot(True)
        self._prepare.timeout.connect(self._capture_dashboard)
        self._handoff = QTimer(self)
        self._handoff.setSingleShot(True)
        self._handoff.timeout.connect(self._complete_handoff)
        self._clock = QElapsedTimer()
        self._clock.start()
        self._pulse = QTimer(self)
        self._pulse.setTimerType(Qt.TimerType.PreciseTimer)
        self._pulse.timeout.connect(self._update_surface)
        self._pulse.start(16)
        self._reveal = QVariantAnimation(self)
        self._reveal.setStartValue(0.0)
        self._reveal.setEndValue(800.0)
        self._reveal.setDuration(800)
        self._reveal.valueChanged.connect(self._animate_reveal)
        self._reveal.finished.connect(self._finish_reveal)

    def _notify_presented(self):
        """Release initialization only after the first native frame can be displayed."""
        if self._stopped or self._presented:
            return
        self._presented = True
        self._images.start()
        self.first_presented.emit()

    def _apply_images(self, logo: QImage, artwork: QImage):
        """Apply decoded images on the GUI thread, rejecting retired results."""
        if self._stopped or not self._compact.isNull():
            return
        self._logo = QPixmap.fromImage(logo)
        self._artwork = QPixmap.fromImage(artwork)
        self.update()

    def set_status(self, text: str):
        """Display the current startup stage without changing layout."""
        self._status = text.rstrip(".… ")
        self.update()

    def reveal(self, window: QWidget):
        """Expand over a fully painted, stationary launcher and crossfade into it."""
        if self._cancelled or self._finished or self._window is not None:
            return
        self._window = window
        window.installEventFilter(self)
        if self._hold.interval():
            self.set_status("Almost there...")
            self._hold.start()
        else:
            self._begin_reveal()

    def _begin_reveal(self):
        """Prepare the launcher first frame after the cancellable debug hold."""
        if (
            self._stopped
            or self._cancelled
            or self._window is None
            or not isValid(self._window)
        ):
            self.cancel()
            return
        window = self._window
        available = self._screen.availableGeometry()
        target = QRect(window.geometry())
        target.moveCenter(available.center())
        target.moveLeft(
            max(
                available.left(),
                min(target.left(), available.right() - target.width() + 1),
            )
        )
        target.moveTop(
            max(
                available.top(),
                min(target.top(), available.bottom() - target.height() + 1),
            )
        )
        # A narrow saved launcher can be smaller than the compact splash.
        # A transparent union canvas preserves both without clipping either.
        self._canvas = target.united(self.geometry())
        self._destination = QRectF(target)
        self._destination.translate(-self._canvas.x(), -self._canvas.y())
        self._origin = QRectF(self.geometry())
        self._origin.translate(-self._canvas.x(), -self._canvas.y())
        window.setGeometry(target)
        window.setWindowOpacity(0.0)
        window.show()
        # Let show/resize callbacks settle before capturing the final layout.
        self._prepare.start(0)

    def _capture_dashboard(self):
        """Capture one settled dashboard frame and start the painted expansion."""
        if (
            self._stopped
            or self._cancelled
            or self._window is None
            or not isValid(self._window)
        ):
            self.cancel()
            return
        try:
            self._dashboard = self._window.grab()
            if self._dashboard.isNull():
                raise RuntimeError("Could not prepare the launcher presentation.")
            self._compact = self.grab()
            self._paint_bounds = QRectF(self._origin)
            surface = _TransitionSurface(self._paint_transition, self._transition_click)
            self._surface = surface
            surface.setGeometry(self._canvas)
            surface.first_painted.connect(self._start_expansion)
            surface.cancelled.connect(self.cancel)
            surface.show()
            self.raise_()
        except Exception as exc:
            self.stop_animation()
            self.failed.emit(str(exc))

    def _start_expansion(self):
        """Swap surfaces only when the stationary replacement has painted."""
        surface = self._surface
        if self._stopped or self._cancelled or self._reveal_started or surface is None:
            return
        if not surface._painted:
            return
        if self._window is None or not isValid(self._window):
            self.cancel()
            return
        self._reveal_started = True
        surface.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        surface.raise_()
        surface.activateWindow()
        self.hide()
        self._reveal.start()

    def _update_surface(self):
        """Refresh the active surface without moving either native window."""
        if self._surface is not None:
            self._surface.update()
        else:
            self.update()

    def _paint_transition(self, painter: QPainter):
        """Keep the replacement's first frame pixel-identical to the compact splash."""
        if not self._reveal_started:
            painter.drawPixmap(
                self._origin, self._compact, QRectF(self._compact.rect())
            )
        else:
            self._paint_frame(painter)

    def _animate_reveal(self, elapsed: float):
        """Expand the painted surface for 500 ms, then blend for 300 ms."""
        if (
            self._stopped
            or self._cancelled
            or self._window is None
            or not isValid(self._window)
        ):
            self.cancel()
            return
        curve = QEasingCurve(QEasingCurve.Type.InOutCubic)
        self._expansion = curve.valueForProgress(min(1.0, elapsed / 500.0))
        origin = self._origin
        target = self._destination
        progress = self._expansion
        self._paint_bounds = QRectF(
            origin.x() + (target.x() - origin.x()) * progress,
            origin.y() + (target.y() - origin.y()) * progress,
            origin.width() + (target.width() - origin.width()) * progress,
            origin.height() + (target.height() - origin.height()) * progress,
        )
        self._fade = curve.valueForProgress(
            max(0.0, min(1.0, (elapsed - 500.0) / 300.0))
        )
        self._update_surface()

    def _finish_reveal(self):
        """Paint the live dashboard behind its identical fully visible snapshot."""
        if self._finished or self._cancelled or self._handoff.isActive():
            return
        if self._window is None or not isValid(self._window):
            self.cancel()
            return
        self._window.setWindowOpacity(1.0)
        self._window.repaint()
        if self._surface is not None:
            self._surface.repaint()
        # Keep the snapshot covering the first live frame until the next Qt turn.
        self._handoff.start(16)

    def _complete_handoff(self):
        """Release the startup modal once the live dashboard has painted."""
        if self._finished or self._cancelled:
            return
        if self._window is None or not isValid(self._window):
            self.cancel()
            return
        self._finished = True
        self.stop_animation()
        self._window.removeEventFilter(self)
        self.close()
        self._window.activateWindow()
        self.finished.emit()

    def stop_animation(self):
        """Stop all animation callbacks during shutdown or startup failure."""
        self._stopped = True
        self._first_frame.stop()
        self._images.cancel()
        if self._surface is not None:
            self._surface.dispose()
            self._surface = None
        self._compact = QPixmap()
        self._prepare.stop()
        self._handoff.stop()
        self._dashboard = QPixmap()
        self._hold.stop()
        self._pulse.stop()
        self._reveal.stop()

    def cancel(self):
        """Cancel startup exactly once, including during the expansion."""
        if self._finished or self._cancelled:
            return
        self._cancelled = True
        self.stop_animation()
        if self._window is not None and isValid(self._window):
            self._window.removeEventFilter(self)
            self._window.hide()
        self.hide()
        self.cancelled.emit()

    def eventFilter(self, watched: QObject, event: QEvent):
        """Cancel the reveal if the launcher closes before presentation finishes."""
        if watched is self._window and event.type() == QEvent.Type.Close:
            self.cancel()
        return super().eventFilter(watched, event)

    def closeEvent(self, event: QCloseEvent):
        """Treat a splash close as cancellation until the reveal completes."""
        if not self._finished:
            self.cancel()
        super().closeEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """Allow cancellation through the small custom close control."""
        bounds = QRectF(self.rect())
        if QRectF(bounds.right() - 32, bounds.top() + 8, 24, 24).contains(
            event.position()
        ):
            self.cancel()

    def _transition_click(self, event: QMouseEvent):
        """Hit-test the transition close control in its own canvas coordinates."""
        bounds = self._paint_bounds
        if QRectF(bounds.right() - 32, bounds.top() + 8, 24, 24).contains(
            event.position()
        ):
            self.cancel()

    def paintEvent(self, event: QPaintEvent):
        """Paint cinematic artwork, angular neon accents, and a moving scan light."""
        painter = QPainter(self)
        if not self._compact.isNull():
            painter.drawPixmap(self.rect(), self._compact)
        else:
            self._paint_frame(painter)
        painter.end()
        if not self._painted and not self._stopped and self.isVisible():
            self._painted = True
            self._first_frame.start(16)

    def _paint_frame(self, painter: QPainter):
        """Render the shared splash artwork and dashboard blend into either surface."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        inset = 5 * (1.0 - self._expansion)
        bounds = self._paint_bounds.adjusted(inset, inset, -inset, -inset)
        if self._expansion == 1 and self._window is not None:
            mask = self._window.mask()
            if not mask.isEmpty():
                painter.setClipRegion(
                    mask.translated(
                        round(self._destination.x()), round(self._destination.y())
                    )
                )
        surface = QPainterPath()
        surface.addRoundedRect(bounds, 12, 12)
        pulse = (math.sin(self._clock.elapsed() / 650.0) + 1.0) / 2.0
        for width, alpha in ((9, 6), (5, 12), (2, 24)):
            painter.setPen(
                QPen(
                    QColor(40, 217, 241, round(alpha * (1.0 - self._expansion))), width
                )
            )
            painter.drawPath(surface)
        painter.fillPath(surface, QColor("#080f20"))
        painter.save()
        painter.setClipPath(surface)
        content_opacity = max(0.0, 1.0 - self._expansion / 0.85)
        if not self._artwork.isNull():
            # Crop to fill without distorting the existing artwork.
            ratio = max(
                bounds.width() / self._artwork.width(),
                bounds.height() / self._artwork.height(),
            )
            crop = QRectF(0, 0, bounds.width() / ratio, bounds.height() / ratio)
            crop.moveCenter(QRectF(self._artwork.rect()).center())
            painter.drawPixmap(bounds, self._artwork, crop)
        overlay = QLinearGradient(bounds.topLeft(), bounds.topRight())
        overlay.setColorAt(0, QColor(4, 11, 26, 245))
        overlay.setColorAt(0.55, QColor(6, 14, 31, 205))
        overlay.setColorAt(1, QColor(8, 12, 30, 95))
        painter.fillRect(bounds, overlay)
        shade = QLinearGradient(bounds.topLeft(), bounds.bottomLeft())
        shade.setColorAt(0, QColor(5, 10, 25, 45))
        shade.setColorAt(1, QColor(5, 10, 25, 225))
        painter.fillRect(bounds, shade)
        # Keep the content at its original logical size throughout expansion.
        painter.setOpacity(content_opacity)
        painter.translate(bounds.center().x() - 300, bounds.center().y() - 170)
        painter.setPen(QPen(QColor(72, 233, 255, 190), 2))
        painter.drawLine(30, 72, 30, 35)
        painter.drawLine(30, 35, 168, 35)
        painter.drawLine(168, 35, 182, 21)
        painter.setPen(QPen(QColor(241, 77, 186, 180), 3))
        painter.drawLine(530, 280, 567, 243)
        painter.drawLine(567, 243, 567, 177)
        painter.setPen(QPen(QColor(91, 225, 251, 30), 1))
        for offset in range(4):
            painter.drawLine(420 + offset * 12, 295, 482 + offset * 12, 233)

        if not self._logo.isNull():
            logo = QRectF(46, 65, 108, 94)
            painter.drawPixmap(logo, self._logo, QRectF(self._logo.rect()))
        font = QFont("Segoe UI")
        font.setPixelSize(20)
        painter.setFont(font)
        painter.setPen(QColor("#69e4f4"))
        painter.drawText(
            QRectF(177, 90, 170, 32), Qt.AlignmentFlag.AlignLeft, "STARTING"
        )
        font = QFont("Segoe UI")
        font.setPixelSize(12)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        painter.setFont(font)
        painter.setPen(QColor("#89a8c2"))
        painter.drawText(
            QRectF(178, 125, 260, 24), Qt.AlignmentFlag.AlignLeft, "ARK / LAUNCHER"
        )
        font.setPixelSize(32)
        font.setWeight(QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        painter.setFont(font)
        painter.setPen(QColor("#f1faff"))
        painter.drawText(
            QRectF(46, 165, 500, 50), Qt.AlignmentFlag.AlignLeft, "SHEN GBOT"
        )
        font.setPixelSize(18)
        font.setWeight(QFont.Weight.Normal)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0)
        painter.setFont(font)
        painter.setPen(QColor("#b4cbdc"))
        status = painter.fontMetrics().elidedText(
            self._status, Qt.TextElideMode.ElideMiddle, 490
        )
        painter.drawText(QRectF(48, 224, 490, 30), Qt.AlignmentFlag.AlignLeft, status)
        painter.setPen(QPen(QColor(68, 196, 225, 50), 1))
        painter.drawLine(48, 281, 510, 281)
        scan_x = 48 + (self._clock.elapsed() % 2400) / 2400 * 462
        scan = QLinearGradient(scan_x - 90, 0, scan_x + 12, 0)
        scan.setColorAt(0, QColor(66, 234, 255, 0))
        scan.setColorAt(0.85, QColor(66, 234, 255, round(160 + pulse * 80)))
        scan.setColorAt(1, QColor(66, 234, 255, 0))
        painter.setClipRect(QRectF(48, 270, 462, 22), Qt.ClipOperation.IntersectClip)
        painter.fillRect(QRectF(scan_x - 90, 279, 102, 3), scan)
        painter.restore()
        border = QLinearGradient(bounds.topLeft(), bounds.bottomRight())
        border.setColorAt(0, QColor(53, 230, 247, 140))
        border.setColorAt(0.45, QColor(68, 99, 138, 38))
        border.setColorAt(1, QColor(241, 79, 177, 110))
        painter.setOpacity(1.0 - self._expansion)
        painter.setPen(QPen(border, 1))
        painter.drawPath(surface)
        painter.setOpacity(content_opacity)
        painter.setPen(QPen(QColor("#a5c3d5"), 1.5))
        painter.translate(self._paint_bounds.topLeft())
        painter.drawLine(
            round(self._paint_bounds.width()) - 25,
            18,
            round(self._paint_bounds.width()) - 19,
            24,
        )
        painter.drawLine(
            round(self._paint_bounds.width()) - 19,
            18,
            round(self._paint_bounds.width()) - 25,
            24,
        )
        painter.resetTransform()
        if self._fade and not self._dashboard.isNull():
            painter.setOpacity(self._fade)
            painter.drawPixmap(
                self._destination, self._dashboard, QRectF(self._dashboard.rect())
            )
