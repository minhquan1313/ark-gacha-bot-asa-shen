"""One rounded geometry for cover artwork, shading, and the final border."""

from contextlib import contextmanager

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

from source.launcher.config.constants import COVER_OVERLAY_COLOR, COVER_OVERLAY_STOPS


def paint_header_overlay(painter: QPainter, bounds: QRectF):
    """Apply the shared left-to-right Settings header readability gradient."""
    shade = QLinearGradient(bounds.topLeft(), bounds.topRight())
    for stop, opacity in COVER_OVERLAY_STOPS:
        color = QColor(COVER_OVERLAY_COLOR)
        color.setAlphaF(opacity)
        shade.setColorAt(stop, color)
    painter.fillRect(bounds, shade)


@contextmanager
def painted_cover(
    painter: QPainter,
    bounds: QRectF,
    radius: float,
    artwork: QPixmap,
    position: QPointF,
    border: QPen,
    background: QColor,
    artwork_bounds: QRectF,
    bottom_lip: float = 0,
    drop_start: float = 0,
):
    """Paint a cover, yield for foreground content, then stroke its unclipped border."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    inset = border.widthF() / 2
    frame = bounds.adjusted(inset, inset, -inset, -inset)
    path = QPainterPath()
    if bottom_lip:
        left, top, right, bottom = (
            frame.left(),
            frame.top(),
            frame.right(),
            frame.bottom(),
        )
        base = bottom - bottom_lip
        transition = 24.0
        start = max(left + radius, min(drop_start, right - radius - transition))
        path.moveTo(left + radius, top)
        path.lineTo(right - radius, top)
        path.quadTo(right, top, right, top + radius)
        path.lineTo(right, bottom - radius)
        path.quadTo(right, bottom, right - radius, bottom)
        path.lineTo(start + transition, bottom)
        path.cubicTo(start + transition / 2, bottom, start + transition / 2, base, start, base)
        path.lineTo(left + radius, base)
        path.quadTo(left, base, left, base - radius)
        path.lineTo(left, top + radius)
        path.quadTo(left, top, left + radius, top)
        path.closeSubpath()
    else:
        path.addRoundedRect(frame, radius, radius)
    painter.fillPath(path, background)
    painter.save()
    painter.setClipPath(path, Qt.ClipOperation.IntersectClip)
    painter.save()
    painter.setClipRect(artwork_bounds, Qt.ClipOperation.IntersectClip)
    painter.setOpacity(1.0)
    if not artwork.isNull():
        painter.drawPixmap(position, artwork)
    paint_header_overlay(painter, artwork_bounds)
    painter.restore()
    try:
        yield
    finally:
        painter.restore()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(border)
        painter.drawPath(path)
        painter.restore()
