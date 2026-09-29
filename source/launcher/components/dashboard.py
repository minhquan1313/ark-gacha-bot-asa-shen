"""Reusable, functional dashboard surfaces and vector decorations."""

from collections.abc import Callable
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QRadialGradient,
    QTextCursor,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from source.launcher.components.cover_painting import painted_cover
from source.launcher.components.widgets import (
    AnimatedButton,
    ClickableTextEdit,
    CyberSwitch,
    MeterBar,
)
from source.launcher.config.constants import ASSETS
from source.launcher.dashboard_theme import PALETTE, asset_path, button_style


@lru_cache(maxsize=128)
def line_icon(name: str, color: str = PALETTE["cyan"]):
    """Load a registered SVG and preserve the requested icon color."""
    pixmap = QPixmap(96, 96)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(asset_path(ASSETS[f"icon.{name}"])).render(painter)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color))
    painter.end()
    return QIcon(pixmap)


def text_label(text: str, role: str):
    """Create a layout label styled by the dashboard theme."""
    label = QLabel(text)
    label.setProperty("role", role)
    label.setMinimumWidth(0)
    return label


class DashboardButton(AnimatedButton):
    """Keep the existing runtime button interface with dashboard-only styling."""

    def __init__(
        self,
        text: str,
        variant: str = "secondary",
        icon: str = "",
        compact: bool = False,
    ):
        self.scale = 1.0
        self.compact = compact
        self.icon_name = icon
        super().__init__(text, variant)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.set_scale(1.0)

    def _apply_style(self):
        """Apply centralized states without changing styles on other buttons."""
        self.setStyleSheet(button_style(self.variant, self.scale, self.compact))
        if self.icon_name:
            name = "stop" if self.icon_name == "play" and self.variant == "danger" else self.icon_name
            self.setIcon(line_icon(name, "#00121E" if self.variant == "primary" else PALETTE["cyan"]))

    def _animate_to(self, target: dict):
        """Use inexpensive native hover/pressed states instead of QSS per frame."""
        self._colors = target.copy()
        self._apply_style()

    def set_scale(self, scale: float):
        """Size a button in logical pixels using the reference proportions."""
        self.scale = scale
        height = 36 if self.compact else 58 if self.variant == "nav" else 54
        self.setFixedHeight(round(height * scale))
        self.setIconSize(QSize(round(24 * scale), round(24 * scale)))
        self._apply_style()


class SidebarButton(DashboardButton):
    """One keyboard-accessible, checkable navigation entry."""

    def __init__(self, text: str, icon: str):
        super().__init__(text, "nav", icon)
        self.setCheckable(True)
        self.setToolTip(text)
        self.setAccessibleName(text)


class SidebarFrame(QFrame):
    """Shell sidebar with non-interactive circuit-line decoration."""

    def paintEvent(self, event: QPaintEvent):
        """Keep decoration below the navigation and above the build details."""
        super().paintEvent(event)
        if self.width() < 100 or self.height() < 850:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath(QPointF(0, self.height() - 128))
        path.lineTo(20, self.height() - 150)
        path.lineTo(self.width() * 0.45, self.height() - 150)
        path.lineTo(self.width() - 28, self.height() - 252)
        painter.setPen(QPen(QColor("#05628C"), 1))
        painter.drawPath(path)
        painter.setPen(QPen(QColor("#0B3044"), 1))
        painter.translate(0, -20)
        painter.drawPath(path)


class DashboardSwitch(CyberSwitch):
    """Preserve checkbox signals and animation with a bright, readable thumb."""

    def paintEvent(self, event: QPaintEvent):
        """Paint the reference switch without changing the shared settings switch."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(3, (self.height() - 24) / 2, 52, 24)
        painter.setPen(QPen(QColor("#4A8EAF"), 1))
        gradient = QLinearGradient(track.topLeft(), track.bottomRight())
        gradient.setColorAt(0, self._blend("#244967", "#00D9FF", self._knob_progress))
        gradient.setColorAt(1, self._blend("#12304A", "#0088CB", self._knob_progress))
        painter.setBrush(gradient)
        painter.drawRoundedRect(track, 12, 12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#F4F7FA" if self.isEnabled() else "#678395"))
        painter.drawEllipse(QRectF(6 + 28 * self._knob_progress, track.top() + 3, 18, 18))
        painter.setPen(QColor(PALETTE["text"] if self.isEnabled() else PALETTE["muted"]))
        painter.setFont(self.font())
        painter.drawText(
            self.rect().adjusted(70, 0, 0, 0),
            Qt.AlignmentFlag.AlignVCenter,
            self.text(),
        )


class NeonPanel(QFrame):
    """Paint a restrained cyan outline, corner highlights, and navy gradient."""

    def __init__(self, parent: QFrame | None = None):
        super().__init__(parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def paintEvent(self, event: QPaintEvent):
        """Draw inexpensive layered strokes instead of per-panel blur effects."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, QColor("#082436"))
        gradient.setColorAt(0.35, QColor(PALETTE["panel"]))
        gradient.setColorAt(0.8, QColor("#03101A"))
        gradient.setColorAt(1, QColor("#093149"))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(PALETTE["cyan"]), 1))
        painter.drawRoundedRect(rect, 11, 11)
        path = QPainterPath()
        path.addRoundedRect(rect, 11, 11)
        painter.save()
        painter.setClipPath(path)
        for point in (rect.topLeft(), rect.bottomRight()):
            glow = QRadialGradient(point, 75)
            glow.setColorAt(0, QColor(0, 160, 255, 95))
            glow.setColorAt(0.45, QColor(0, 120, 220, 18))
            glow.setColorAt(1, QColor(0, 120, 220, 0))
            painter.fillRect(rect, glow)
        painter.restore()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for width, alpha in ((6, 12), (3, 28), (1, 200)):
            color = QColor(PALETTE["bright"])
            color.setAlpha(alpha)
            painter.setPen(QPen(color, width))
            painter.drawLine(rect.topLeft() + QPointF(12, 0), rect.topLeft() + QPointF(65, 0))
            painter.drawLine(
                int(rect.right() - 65),
                int(rect.bottom()),
                int(rect.right() - 12),
                int(rect.bottom()),
            )
        painter.setPen(QPen(QColor("#96E8FF"), 1))
        painter.drawArc(QRectF(1, 1, 22, 22), 90 * 16, 90 * 16)
        painter.drawArc(QRectF(self.width() - 23, self.height() - 23, 22, 22), 270 * 16, 90 * 16)


class IconBadge(QLabel):
    """A line icon in the circular badge used by the stat cards."""

    def __init__(self, name: str, circle: bool = True):
        super().__init__()
        self.name = name
        self.circle = circle
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(72 if circle else 28, 72 if circle else 28)

    def paintEvent(self, event: QPaintEvent):
        """Draw an antialiased circle and crisp vector glyph."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.circle:
            painter.setBrush(QColor("#032132"))
            painter.setPen(QPen(QColor("#00628A"), 1))
            painter.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))
        inset = round(self.width() * 0.26) if self.circle else 2
        line_icon(self.name).paint(painter, self.rect().adjusted(inset, inset, -inset, -inset))


class StatCard(NeonPanel):
    """A dashboard value whose QLabel remains compatible with runtime updates."""

    def __init__(self, label: str, unit: str, icon: str):
        super().__init__()
        self.row = QHBoxLayout(self)
        self.badge = IconBadge(icon)
        self.row.addWidget(self.badge)
        labels = QVBoxLayout()
        labels.setSpacing(4)
        self.title = text_label(label, "statLabel")
        self.value = text_label("--", "timeValue" if icon == "clock" and label == "UPTIME" else "statValue")
        self.unit = text_label(unit, "muted")
        labels.addWidget(self.title)
        labels.addWidget(self.value)
        labels.addWidget(self.unit)
        self.row.addLayout(labels, 1)

    def set_scale(self, scale: float):
        """Maintain equal card heights and reference icon/text spacing."""
        self.setFixedHeight(round(136 * scale))
        self.row.setContentsMargins(round(22 * scale), 10, round(18 * scale), 10)
        self.row.setSpacing(round(25 * scale))
        self.badge.setFixedSize(round(76 * scale), round(76 * scale))


class ProgressMetric(MeterBar):
    """Keep the existing set_percent interface with the reference cyan track."""

    def paintEvent(self, event: QPaintEvent):
        """Paint a stable flat meter without a timer or animation."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(PALETTE["border"]), 1))
        painter.setBrush(QColor("#032033"))
        painter.drawRoundedRect(rect, 3, 3)
        if self.percent:
            rect.setWidth(rect.width() * self.percent / 100)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(PALETTE["cyan"]))
            painter.drawRoundedRect(rect, 3, 3)


class StatusCard(NeonPanel):
    """Compact runner/time status or a system metric with a progress bar."""

    def __init__(self, title: str, icon: str, meter: bool = False, memory: bool = False):
        super().__init__()
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(16, 12, 16, 12)
        head = QHBoxLayout()
        self.icon = IconBadge(icon, False)
        head.addWidget(self.icon)
        head.addWidget(text_label(title, "footer"), 1)
        self.box.addLayout(head)
        row = QHBoxLayout()
        self.meter = ProgressMetric(PALETTE["cyan"]) if meter else None
        if self.meter is not None:
            row.addWidget(self.meter, 1)
        self.value = text_label("--", "muted" if memory else "percent" if meter else "metricValue")
        self.value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.value)
        self.percent = text_label("--", "percent") if memory else None
        if self.percent is not None:
            row.addWidget(self.percent)
        self.box.addLayout(row)

    def set_scale(self, scale: float):
        """Keep all bottom metrics aligned at the selected dashboard density."""
        self.setFixedHeight(round(92 * scale))
        self.box.setContentsMargins(round(18 * scale), round(12 * scale), round(18 * scale), round(12 * scale))
        self.icon.setFixedSize(round(24 * scale), round(24 * scale))


class DashboardHero(NeonPanel):
    """Layout-based welcome text over manually positioned, cached artwork."""

    # Artwork dimensions and offsets in logical pixels, independent of panel scale.
    ART_HEIGHT = 480
    ART_RIGHT_MARGIN = -8  # Increase to move the artwork left.
    ART_TOP = -96  # Increase to move the artwork down.

    def __init__(self):
        super().__init__()
        self.art = QPixmap(asset_path(ASSETS["dashboard"]))
        self._art_height = 0
        self._scaled_art = QPixmap()
        self.box = QVBoxLayout(self)
        self.box.setSpacing(0)
        self.box.addStretch(1)
        self.box.addWidget(text_label("WELCOME BACK,", "eyebrow"))
        self.box.addWidget(text_label('SHEN <span style="color:#00D9FF">GBOT.</span>', "heroTitle"))
        self.box.addWidget(text_label("AUTOMATE TODAY. HIGHER TOMORROW.", "subtitle"))
        self.box.addStretch(1)
        status_row = QHBoxLayout()
        status = QFrame()
        status.setObjectName("InlineSwitchBox")
        self.status_box = QHBoxLayout(status)
        self.status_box.addWidget(text_label("SYSTEM STATUS", "muted"))
        self.status_label = text_label("INITIALIZING", "metricValue")
        self.status_box.addWidget(self.status_label)
        status_row.addWidget(status)
        status_row.addStretch(1)
        self.box.addLayout(status_row)
        self.box.addStretch(1)

    def set_scale(self, scale: float):
        """Size the hero while preserving layout-based text positioning."""
        self.setFixedHeight(round(234 * scale))
        self.box.setContentsMargins(round(70 * scale), 12, 12, 12)
        self.status_box.setContentsMargins(round(14 * scale), round(8 * scale), round(14 * scale), round(8 * scale))
        self.status_box.setSpacing(round(22 * scale))

    def set_status(self, text: str, color: str):
        """Reflect actual ARK readiness rather than an unconditional online badge."""
        self.status_label.setText(f'<span style="color:{color}">&#9679; &nbsp;{text}</span>')

    def paintEvent(self, event: QPaintEvent):
        """Preserve manual placement while painting artwork and border together."""
        ratio = self.devicePixelRatioF()
        key = (self.ART_HEIGHT, ratio)
        if not self.art.isNull() and self._art_height != key:
            self._scaled_art = self.art.scaledToHeight(
                round(self.ART_HEIGHT * ratio),
                Qt.TransformationMode.SmoothTransformation,
            )
            self._scaled_art.setDevicePixelRatio(ratio)
            self._art_height = key
        position = QPointF(
            self.width() - self._scaled_art.width() / ratio - self.ART_RIGHT_MARGIN,
            self.ART_TOP,
        )
        painter = QPainter(self)
        with painted_cover(
            painter,
            QRectF(self.rect()),
            11,
            self._scaled_art,
            position,
            QPen(QColor(PALETTE["cyan"]), 1),
            QColor("#03101A"),
            QRectF(self.rect()),
        ):
            painter.setPen(QPen(QColor(PALETTE["cyan"]), 2))
            painter.drawLine(20, 30, 20, self.height() - 30)
            painter.setPen(QPen(QColor("#075478"), 1))
            painter.drawLine(20, self.height() - 30, 42, self.height() - 8)


class DashboardConsole(ClickableTextEdit):
    """Incremental latest-record view preserving selection and manual scrolling."""

    def __init__(self):
        super().__init__()
        self.records = []
        self.auto_scroll = True
        self.setObjectName("Console")
        self.setReadOnly(True)
        self.setMinimumSize(0, 100)

    def set_auto_scroll(self, enabled: bool):
        """Resume following the latest output only when explicitly enabled."""
        self.auto_scroll = enabled
        if enabled:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def update_records(self, records: list[str], formatter: Callable[[list[str]], str]):
        """Append overlapping records and trim by record, including multiline logs."""
        records = list(records)
        if records == self.records:
            return
        scrollbar = self.verticalScrollBar()
        position = scrollbar.value()
        overlap = min(len(self.records), len(records))
        while overlap and self.records[-overlap:] != records[:overlap]:
            overlap -= 1
        cursor = QTextCursor(self.document())
        if not overlap:
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.removeSelectedText()
        else:
            removed_blocks = sum(max(1, len(record.rstrip("\n").split("\n"))) for record in self.records[:-overlap])
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            for _ in range(removed_blocks):
                cursor.movePosition(QTextCursor.MoveOperation.NextBlock, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for index, record in enumerate(records[overlap:]):
            if overlap or index:
                cursor.insertBlock()
            # One block per physical line allows exact trimming of multiline records.
            for line_index, line in enumerate(record.rstrip("\n").split("\n")):
                if line_index:
                    cursor.insertBlock()
                cursor.insertHtml(formatter([line]))
        self.records = records
        scrollbar.setValue(scrollbar.maximum() if self.auto_scroll else position)
