"""Illustrated About and updater surfaces inside the existing application shell."""

from html import escape
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient, QTextLayout, QTextOption
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QTextBrowser, QVBoxLayout, QWidget

from source.launcher.components.browser_layout import BROWSER_STYLE
from source.launcher.components.dashboard import line_icon
from source.launcher.components.popout import POPOUT_OPEN_MS, AnimatedPopout
from source.launcher.components.settings_sections import SettingsActionButton
from source.launcher.config.constants import ASSETS
from source.launcher.dashboard_theme import PALETTE, asset_path

# Shared contour geometry, in logical pixels.
CURVE_HALF_WIDTH = 44
CURVE_DEPTH = 16
PANEL_GUTTER = 16
BORDER_SEPARATION = 12

ABOUT_STYLE = """
QWidget#CombinedAbout { background: transparent; }
QWidget#CombinedAbout QLabel { color: #b8d6e5; font-family: 'Segoe UI'; font-size: 14px; border: none; background: transparent; }
QWidget#CombinedAbout QLabel[role="title"] { color: #00d9ff; font-size: 23px; font-weight: 700; }
QWidget#CombinedAbout QLabel[role="heading"] { color: #00d9ff; font-size: 20px; font-weight: 700; }
QWidget#CombinedAbout QLabel[role="status"] { color: #f1f8ff; font-size: 24px; font-weight: 700; }
QWidget#CombinedAbout QLabel[role="brand"] { color: #f1f8ff; font-size: 30px; font-weight: 700; }
QWidget#CombinedAbout QLabel[role="muted"] { color: #8fb4c7; font-size: 12px; }
QWidget#CombinedAbout QLabel[role="badge"] { color: #27f5b0; font-weight: 700; }
QScrollArea#AboutScroll { border: none; background: transparent; }
QWidget#AboutColumns { background: transparent; }
"""


def label(text: str, role: str = "", centered: bool = False):
    """Create wrapping copy with scoped typography and optional centered alignment."""
    item = QLabel(text)
    item.setProperty("role", role)
    item.setWordWrap(True)
    item.setMinimumWidth(0)
    item.setTextFormat(Qt.TextFormat.PlainText)
    if centered:
        item.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return item


class IllustratedPanel(QFrame):
    """One shared cyan outline around cached proportional artwork and content."""

    def __init__(self, slot: str, fallback: str):
        """Build the widgets and keep callbacks connected to existing application behavior."""
        super().__init__()
        path = asset_path(ASSETS[slot])
        self.art = QPixmap(path if Path(path).is_file() else asset_path(ASSETS[fallback]))
        self._cache = None
        self.scaled = QPixmap()
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def _prepare_art(self):
        """Rescale only when geometry or screen density changes."""
        ratio = self.devicePixelRatioF()
        key = (self.size(), ratio)
        if key != self._cache and not self.art.isNull():
            self.scaled = self.art.scaled(self.size() * ratio, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self.scaled.setDevicePixelRatio(ratio)
            self._cache = key
        return QPointF((self.width() - self.scaled.width() / ratio) / 2, (self.height() - self.scaled.height() / ratio) / 2)

    def outline(self):
        """Return the actual clipped panel contour, including its inner shoulder."""
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        if not getattr(self, "shoulder", ""):
            path.addRoundedRect(r, 10, 10)
            return path
        w, h = r.right(), r.bottom()
        path.moveTo(10, 0.5)
        if self.shoulder == "left":
            path.lineTo(w - CURVE_HALF_WIDTH, 0.5)
            path.cubicTo(w - 24, 0.5, w - 24, CURVE_DEPTH, w - 10, CURVE_DEPTH)
            path.quadTo(w, CURVE_DEPTH, w, CURVE_DEPTH + 12)
        else:
            path.lineTo(w - 10, 0.5)
            path.quadTo(w, 0.5, w, 10)
        path.lineTo(w, h - 10)
        path.quadTo(w, h, w - 10, h)
        path.lineTo(10, h)
        path.quadTo(0.5, h, 0.5, h - 10)
        if self.shoulder == "right":
            corrected = QPainterPath()
            corrected.moveTo(CURVE_HALF_WIDTH, 0.5)
            corrected.lineTo(w - 10, 0.5)
            corrected.quadTo(w, 0.5, w, 10)
            corrected.lineTo(w, h - 10)
            corrected.quadTo(w, h, w - 10, h)
            corrected.lineTo(10, h)
            corrected.quadTo(0.5, h, 0.5, h - 10)
            corrected.lineTo(0.5, CURVE_DEPTH + 12)
            corrected.quadTo(0.5, CURVE_DEPTH, 10, CURVE_DEPTH)
            corrected.cubicTo(24, CURVE_DEPTH, 24, 0.5, CURVE_HALF_WIDTH, 0.5)
            corrected.closeSubpath()
            return corrected
        path.lineTo(0.5, 10)
        path.quadTo(0.5, 0.5, 10, 0.5)
        path.closeSubpath()
        return path

    def paintEvent(self, event: QEvent):
        """Paint cached artwork or current animation progress without changing layout."""
        position = self._prepare_art()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = self.outline()
        p.setClipPath(path)
        p.fillRect(self.rect(), QColor("#03111b"))
        p.drawPixmap(position, self.scaled)
        shade = QLinearGradient(0, 0, 0, self.height())
        shade.setColorAt(0, QColor(0, 9, 16, 155))
        shade.setColorAt(1, QColor(0, 9, 16, 235))
        p.fillRect(self.rect(), shade)
        p.setClipping(False)
        p.setPen(QPen(QColor(PALETTE["cyan"]), 1))
        p.drawPath(path)


class AboutHero(IllustratedPanel):
    """An integrated curved lower extension aligned with the real panel gap."""

    def __init__(self):
        """Build the widgets and keep callbacks connected to existing application behavior."""
        super().__init__("about.hero", "settings.breadcrumb")
        self.dip_center = 0.0
        self.setFixedHeight(128)
        box = QVBoxLayout(self)
        box.setContentsMargins(24, 18, 24, 32)
        box.addWidget(label("CHECK UPDATE & ABOUT", "title"))
        box.addWidget(label("Stay up to date. Learn more about Shen GBot."))

    def outline(self):
        """Construct one closed path with an 88 by 16 pixel smooth dip."""
        left, top, right, bottom = 0.5, 0.5, self.width() - 0.5, self.height() - 0.5
        base, radius = bottom - CURVE_DEPTH, 8
        center = max(53, min(self.dip_center or self.width() / 2, right - 52))
        path = QPainterPath(QPointF(left + radius, top))
        path.lineTo(right - radius, top)
        path.quadTo(right, top, right, top + radius)
        path.lineTo(right, base - radius)
        path.quadTo(right, base, right - radius, base)
        path.lineTo(center + CURVE_HALF_WIDTH, base)
        path.cubicTo(center + 22, base, center + 20, bottom, center, bottom)
        path.cubicTo(center - 20, bottom, center - 22, base, center - CURVE_HALF_WIDTH, base)
        path.lineTo(left + radius, base)
        path.quadTo(left, base, left, base - radius)
        path.lineTo(left, top + radius)
        path.quadTo(left, top, left + radius, top)
        path.closeSubpath()
        return path

    def paintEvent(self, event: object):
        """Clip all layers to the actual curved edge, then draw its single border."""
        position = self._prepare_art()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = self.outline()
        p.setClipPath(path)
        p.fillRect(self.rect(), QColor("#03111b"))
        p.drawPixmap(position, self.scaled)
        p.fillRect(self.rect(), QColor(0, 9, 16, 155))
        p.setClipping(False)
        p.setPen(QPen(QColor(PALETTE["cyan"]), 1))
        p.drawPath(path)


BUTTON_STYLE = """QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #07516a,stop:1 #032333); color:#f0f8ff; border:1px solid #168ca5; border-radius:7px; font: bold 13px 'Segoe UI'; } QPushButton:hover,QPushButton:focus {background:#0a4258; border-color:#00c9e9;} QPushButton:disabled {color:#779aa9;}"""


def symbol(name: str, size: int = 24):
    """Create a fixed-size cyan icon from the shared asset registry."""
    widget = QLabel()
    widget.setPixmap(line_icon(name).pixmap(size, size))
    widget.setFixedSize(size, size)
    return widget


class UpdateStateIcon(QWidget):
    """Draw verification once, then pulse only while visible and verified."""

    def __init__(self, parent: QWidget = None):
        """Build the widgets and keep callbacks connected to existing application behavior."""
        super().__init__(parent)
        self.state = "idle"
        self.reveal = 0.0
        self.glow = 0.0
        self.draw_animation = QVariantAnimation(self)
        self.draw_animation.setDuration(500)
        self.draw_animation.setStartValue(0.0)
        self.draw_animation.setEndValue(1.0)
        self.draw_animation.valueChanged.connect(self._reveal)
        self.pulse = QVariantAnimation(self)
        self.pulse.setDuration(1800)
        self.pulse.setStartValue(0.0)
        self.pulse.setKeyValueAt(0.5, 1.0)
        self.pulse.setEndValue(0.0)
        self.pulse.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.pulse.setLoopCount(-1)
        self.pulse.valueChanged.connect(self._glow)
        self.draw_animation.finished.connect(self._start_pulse)

    def _reveal(self, value: float):
        """Advance the check stroke from the non-blocking reveal animation."""
        self.reveal = value
        self.update()

    def _glow(self, value: float):
        """Update the ring glow from the pulse animation."""
        self.glow = value
        self.update()

    def _start_pulse(self):
        """Start pulsing only for a visible, successfully verified state."""
        if self.isVisible() and self.state == "current":
            self.pulse.start()

    def set_state(self, state: str):
        """Apply truthful update status and manage its animation lifecycle."""
        self.draw_animation.stop()
        self.pulse.stop()
        self.state = state
        self.reveal = 0.0
        if state == "current" and self.isVisible():
            self.draw_animation.start()
        self.update()

    def showEvent(self, event: QEvent):
        """Resume verification animation when the page becomes visible."""
        super().showEvent(event)
        if self.state == "current":
            self.draw_animation.start()

    def hideEvent(self, event: QEvent):
        """Stop both animations while the status surface is hidden."""
        self.draw_animation.stop()
        self.pulse.stop()
        super().hideEvent(event)

    def paintEvent(self, event: QEvent):
        """Paint cached artwork or current animation progress without changing layout."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(self.width() / 120, self.height() / 120)
        color = QColor("#27f5b0" if self.state == "current" else "#ffd166" if self.state == "error" else "#00d9ff")
        glow = QRadialGradient(60, 60, 60)
        tint = QColor(color)
        tint.setAlpha(int(45 + self.glow * 35))
        glow.setColorAt(0.72, tint)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(0, 0, 120, 120))
        p.setPen(QPen(color, 1))
        p.setBrush(QColor(0, 24, 31, 150))
        p.drawEllipse(QRectF(9, 9, 102, 102))
        p.setPen(QPen(color, 2.5))
        p.drawEllipse(QRectF(17, 17, 86, 86))
        if self.state == "current":
            p.setPen(QPen(color, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            points = [QPointF(40, 61), QPointF(54, 74), QPointF(82, 44)]
            first = min(1.0, self.reveal * 3)
            p.drawLine(points[0], points[0] + (points[1] - points[0]) * first)
            if self.reveal > 1 / 3:
                p.drawLine(points[1], points[1] + (points[2] - points[1]) * ((self.reveal - 1 / 3) * 1.5))
        else:
            line_icon("about" if self.state == "error" else "update", color.name()).paint(p, 38, 38, 44, 44)


class ReleaseNotes(QWidget):
    """Bounded release preview; complete text stays available in the shared popout."""

    def __init__(self, parent: QWidget):
        """Build the widgets and keep callbacks connected to existing application behavior."""
        super().__init__(parent)
        self.manifest = None
        notes_font = QFont("Segoe UI")
        notes_font.setPixelSize(13)
        self.setFont(notes_font)
        self.document = symbol("btemplates", 30)
        self.heading = label("What's New", "heading")
        self.version = label("Release information unavailable", "muted")
        self.date = label("", "muted")
        self.badge = label("Current", centered=True)
        self.badge.setStyleSheet('color:#00d9ff; background:#032333; border:1px solid #146481; border-radius:13px; font:bold 12px "Segoe UI";')
        self.thanks = label("Thank you for supporting Shen GBot!", "muted")
        self.thanks.setStyleSheet("font-style:italic;")
        self.show_more = QPushButton("Show more")
        self.show_more.setStyleSheet(BUTTON_STYLE)
        self.show_more.clicked.connect(self.open_notes)
        for child in (self.document, self.heading, self.version, self.date, self.badge, self.thanks, self.show_more):
            child.setParent(self)
        self.lines = []
        self.overlay = None

    def set_manifest(self, manifest: object):
        """Retain structured release metadata and refresh the bounded preview."""
        self.manifest = manifest
        if manifest:
            self.version.setText(manifest.title or f"Shen GBot - Version {manifest.version}")
            self.date.setText(f"Released: {manifest.released_at}" if manifest.released_at else "")
        self.arrange()

    def resizeEvent(self, event: QEvent):
        """Recompute the composition after the available bounds change."""
        self.arrange()

    def arrange(self):
        """Measure wrapped bullets and reserve Show more only when content is omitted."""
        w, h = self.width(), self.height()
        self.document.setGeometry(0, 12, 30, 30)
        self.heading.setGeometry(40, 7, max(0, w - 120), 28)
        self.badge.setGeometry(max(0, w - 76), 10, 76, 26)
        self.version.setGeometry(40, 37, max(0, w - 40), 22)
        self.date.setGeometry(40, 59, max(0, w - 40), 18)
        self.thanks.setGeometry(0, max(80, h - 22), w, 22)
        self.show_more.setGeometry(max(0, w - 90), max(80, h - 50), 90, 24)
        self.lines = []
        y = 88
        full = []
        for text in self.manifest.changelog if self.manifest else ():
            layout = QTextLayout(str(text), self.font())
            option = QTextOption()
            option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            layout.setTextOption(option)
            layout.beginLayout()
            while True:
                line = layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(max(1, w - 20))
                full.append((str(text)[line.textStart() : line.textStart() + line.textLength()], line.height(), line.textStart() == 0))
            layout.endLayout()
        overflow = sum(line[1] + 3 for line in full) > max(0, h - 112)
        limit = h - (54 if overflow else 24)
        for text, height, bullet in full:
            if y + height > limit:
                break
            self.lines.append((text, y, height, bullet))
            y += height + 3
        self.show_more.setVisible(overflow)
        self.update()

    def paintEvent(self, event: QEvent):
        """Paint cached artwork or current animation progress without changing layout."""
        p = QPainter(self)
        p.setPen(QColor("#164557"))
        p.drawLine(0, 0, self.width(), 0)
        p.drawLine(40, 81, self.width(), 81)
        for text, y, height, bullet in self.lines:
            p.setPen(QColor("#00d9ff"))
            if bullet:
                p.drawText(QRectF(2, y, 14, height), "\u2022")
            p.setPen(QColor("#b8d6e5"))
            p.drawText(QRectF(20, y, self.width() - 20, height), text)

    def open_notes(self):
        """Open one focused preview containing the full release information."""
        if self.overlay is None:
            self.overlay = ReleaseNotesOverlay(self.window(), self)
        self.overlay.open_notes()


class ReleaseNotesOverlay(AnimatedPopout, QWidget):
    """Selectable complete notes using the same lifecycle as template previews."""

    def __init__(self, parent: QWidget, notes: ReleaseNotes):
        """Build the widgets and keep callbacks connected to existing application behavior."""
        super().__init__(parent)
        self.notes = notes
        self.card = notes.show_more
        self.progress = 0.0
        self.closing = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(BROWSER_STYLE)
        self.panel = QFrame(self)
        self.panel.setObjectName("TemplatePreviewPanel")
        box = QVBoxLayout(self.panel)
        box.setContentsMargins(24, 24, 24, 24)
        row = QHBoxLayout()
        title = label("What's New", "heading")
        title.setStyleSheet('color:#00d9ff; font:bold 22px "Segoe UI";')
        row.addWidget(title, 1)
        self.close_button = QPushButton("X")
        self.close_button.setFixedSize(44, 44)
        self.close_button.clicked.connect(self.close_preview)
        row.addWidget(self.close_button)
        box.addLayout(row)
        self.release_title = label("")
        self.release_title.setStyleSheet('color:#e5f2fc; font:bold 18px "Segoe UI";')
        self.release_title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(self.release_title)
        metadata = QHBoxLayout()
        self.release_metadata = label("")
        self.release_metadata.setStyleSheet('color:#a8c9db; font:13px "Segoe UI";')
        self.release_metadata.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        metadata.addWidget(self.release_metadata, 1)
        self.badge = label("", centered=True)
        self.badge.setFixedSize(76, 26)
        self.badge.setStyleSheet(notes.badge.styleSheet())
        metadata.addWidget(self.badge)
        box.addLayout(metadata)
        self.text = QTextBrowser()
        text_option = self.text.document().defaultTextOption()
        text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.text.document().setDefaultTextOption(text_option)
        self.text.setStyleSheet('QTextBrowser {background:transparent; border:none; color:#d2e7f2; font:14px "Segoe UI";}')
        box.addWidget(self.text, 1)
        self.animation = QVariantAnimation(self)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self._frame)
        self.animation.finished.connect(self._finished)
        self.hide()

    def focus_targets(self):
        """Keep keyboard focus within the close action and selectable notes."""
        return [self.close_button, self.text]

    def open_notes(self):
        """Open one focused preview containing the full release information."""
        if self.isVisible():
            return
        m = self.notes.manifest
        if m is None:
            return
        self.release_title.setText(m.title or f"Shen GBot - Version {m.version}")
        self.release_metadata.setText(f"Version {m.version}" + (f"  |  Released: {m.released_at}" if m.released_at else ""))
        self.badge.setText(self.notes.badge.text())
        self.text.setHtml("<ul>" + "".join(f'<li style="margin-bottom:12px">{escape(str(t))}</li>' for t in m.changelog) + "</ul>")
        self.text.verticalScrollBar().setValue(0)
        self.closing = False
        self.progress = 0.0
        self.setGeometry(self.parentWidget().rect())
        self._map_source()
        self._prepare_panel()
        self.show()
        self.raise_()
        QApplication.instance().installEventFilter(self)
        self.setFocus()
        self._animate(1.0, POPOUT_OPEN_MS)

    def _map_source(self):
        """Map the release region into application-overlay coordinates."""
        self.source = QRectF(self.notes.rect())
        self.source.moveTopLeft(QPointF(self.mapFromGlobal(self.notes.mapToGlobal(QPoint()))))

    def _prepare_panel(self):
        """Fit the popup to the application and snapshot its final layout."""
        w, h = min(760, self.width() - 48), min(660, self.height() - 64)
        self.target = QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)
        self.panel.setGeometry(self.target.toRect())
        self.panel.show()
        self.panel.layout().activate()
        self._capture_panel()
        if self.progress < 1 or self.closing:
            self.panel.hide()

    def _capture_panel(self):
        """Cache the panel image for animation frames."""
        self.snapshot = self.panel.grab()

    def paintEvent(self, event: QEvent):
        """Paint cached artwork or current animation progress without changing layout."""
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 5, 12, int(170 * self.progress)))
        if not self.panel.isVisible():
            t = self.progress
            r = QRectF(
                self.source.x() + (self.target.x() - self.source.x()) * t,
                self.source.y() + (self.target.y() - self.source.y()) * t,
                self.source.width() + (self.target.width() - self.source.width()) * t,
                self.source.height() + (self.target.height() - self.source.height()) * t,
            )
            p.setOpacity(t)
            p.drawPixmap(r, self.snapshot, QRectF(self.snapshot.rect()))


class CombinedAboutPage(QWidget):
    """A constrained desktop composition with a stacked small-window fallback."""

    def __init__(self, version: str, on_update: object, on_website: object):
        """Build the widgets and keep callbacks connected to existing application behavior."""
        super().__init__()
        self.setObjectName("CombinedAbout")
        self.setStyleSheet(ABOUT_STYLE)
        self.hero = AboutHero()
        self.hero.setParent(self)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("AboutScroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("AboutColumns")
        self.scroll.setWidget(self.content)
        self.scroll.viewport().installEventFilter(self)
        self.left = IllustratedPanel("about.update", "settings.render")
        self.right = IllustratedPanel("about.illustration", "settings.server")
        for panel in (self.left, self.right):
            panel.setParent(self.content)
        self.left_heading = self._heading(self.left, "update", "System Update", "Keep your Shen GBot up to date")
        self.right_heading = self._heading(self.right, "about", "About Shen GBot", "Automation tools for ARK: Survival Ascended")
        self.state_icon = UpdateStateIcon(self.left)
        self.status = label("Not checked yet", "status", True)
        self.version = label(f"Version {version}", "heading", True)
        self.version.setStyleSheet('color:#f1f8ff; font:bold 18px "Segoe UI";')
        self.support = label("Check for updates to confirm you have the latest version.", centered=True)
        self.action = SettingsActionButton("CHECK FOR UPDATE", "update", "secondary")
        self.action.setStyleSheet(BUTTON_STYLE)
        self.action.clicked.connect(on_update)
        self.timestamp = QWidget(self.left)
        clockrow = QHBoxLayout(self.timestamp)
        clockrow.setContentsMargins(0, 0, 0, 0)
        clockrow.setSpacing(6)
        clockrow.addStretch()
        clockrow.addWidget(symbol("clock", 16))
        self.last_checked = label("Last checked: Never", "muted")
        self.last_checked.setWordWrap(False)
        clockrow.addWidget(self.last_checked)
        clockrow.addStretch()
        for item in (self.status, self.version, self.support, self.action):
            item.setParent(self.left)
        self.notes = ReleaseNotes(self.left)
        self.latest_badge = self.notes.badge
        self.brand = QWidget(self.right)
        b = QVBoxLayout(self.brand)
        b.setContentsMargins(0, 0, 0, 0)
        b.setSpacing(5)
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_art = QPixmap(asset_path(ASSETS["logo"]))
        b.addStretch()
        b.addWidget(self.logo)
        for text, role in [("SHEN GBOT", "brand"), (f"v{version}", "heading"), ("DEVELOPED BY", "muted"), ("Shen", ""), ('"Code. Automate. Dominate."', "muted")]:
            b.addWidget(label(text, role, True))
        b.addStretch()
        self.website = QPushButton(self.right)
        self.website.setStyleSheet(BUTTON_STYLE.replace("#07516a", "#042c41").replace("#032333", "#021624"))
        self.website.clicked.connect(on_website)
        row = QHBoxLayout(self.website)
        row.setContentsMargins(20, 8, 16, 8)
        globe = symbol("globe", 36)
        row.addWidget(globe)
        copy = QVBoxLayout()
        copy.setSpacing(1)
        website_title = label("WEBSITE")
        website_title.setStyleSheet("color:#f1f8ff; font-weight:700;")
        copy.addWidget(website_title)
        copy.addWidget(label("Visit official website", "muted"))
        row.addLayout(copy, 1)
        row.addWidget(label("\u203a", "heading"))
        for child in self.website.findChildren(QWidget):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.website.setAccessibleName("Website: Visit official website")
        self.quote = IllustratedPanel("about.quote", "settings.breadcrumb")
        self.quote.setParent(self.right)
        q = QHBoxLayout(self.quote)
        q.setContentsMargins(22, 8, 20, 8)
        ornament = label("\u201c")
        ornament.setStyleSheet("color:#258fbc; font:bold 64px Georgia;")
        q.addWidget(ornament)
        copy = QVBoxLayout()
        quote = label("A better tomorrow for every survivor.", centered=True)
        quote.setStyleSheet('color:#e5f2fc; font:italic 14px "Segoe UI";')
        copy.addWidget(quote)
        copy.addWidget(label("\u2500\u2500\u2500    \u2014 Shen    \u2500\u2500\u2500", "muted", True))
        q.addLayout(copy, 1)
        self._stacked = False
        self.reflow()

    def _heading(self, parent: QWidget, icon: str, title: str, subtitle: str):
        """Align the shared section icon, title, and secondary copy."""
        widget = QWidget(parent)
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)
        row.addWidget(symbol(icon, 38))
        copy = QVBoxLayout()
        copy.setSpacing(2)
        copy.addWidget(label(title, "heading"))
        sub = label(subtitle, "muted")
        copy.addWidget(sub)
        row.addLayout(copy, 1)
        return widget

    def eventFilter(self, watched: object, event: QEvent):
        """Schedule reflow after the scroll viewport settles."""
        if event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.reflow)
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QEvent):
        """Recompute the composition after the available bounds change."""
        self.reflow()
        QTimer.singleShot(0, self.reflow)

    def reflow(self):
        """Fit the desktop tracks to height, or stack panels on smaller windows."""
        if not hasattr(self, "notes"):
            return
        w = max(1, self.width() - 32)
        self.hero.setGeometry(16, 14, w, 128)
        body_y = 14 + self.hero.height() - CURVE_DEPTH + BORDER_SEPARATION
        self.scroll.setGeometry(16, body_y, w, max(1, self.height() - body_y - 14))
        self._stacked = w < 900 or self.height() < 690
        h = max(580, self.scroll.height()) if self._stacked else self.scroll.height()
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if self._stacked else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cw = self.scroll.viewport().width()
        self.content.resize(cw, 2 * h + 16 if self._stacked else h)
        lw = cw if self._stacked else round((cw - PANEL_GUTTER) * 0.44)
        rw = cw if self._stacked else cw - lw - PANEL_GUTTER
        self.left.setGeometry(0, 0, lw, h)
        self.right.setGeometry(0, h + 16, rw, h) if self._stacked else self.right.setGeometry(lw + PANEL_GUTTER, 0, rw, h)
        self.left.shoulder = "" if self._stacked else "left"
        self.right.shoulder = "" if self._stacked else "right"
        self.hero.dip_center = w / 2 if self._stacked else lw + PANEL_GUTTER / 2
        self.hero.update()
        self.left.update()
        self.right.update()
        pad = 20
        inner = lw - 2 * pad
        track = (h - 2 * pad) / 3
        system = round(track * 2)
        self.left_heading.setGeometry(pad, pad, inner, 52)
        icon = min(156, max(82, system - 240))
        breathing = max(0, system - icon - 254) // 2
        self.state_icon.setGeometry((lw - icon) // 2, pad + 62 + breathing, icon, icon)
        y = pad + 66 + icon + breathing
        self.status.setGeometry(pad, y, inner, 32)
        self.status.setStyleSheet("font-size:21px;")
        self.version.setGeometry(pad, y + 34, inner, 26)
        self.support.setGeometry(pad, y + 64, inner, 36)
        bw = min(358, inner - 20)
        self.action.setGeometry((lw - bw) // 2, pad + system - 74, bw, 44)
        self.timestamp.setGeometry(pad, pad + system - 25, inner, 22)
        self.notes.setGeometry(pad, pad + system + 6, inner, h - pad - (pad + system + 6))
        self.right_heading.setGeometry(pad, pad, rw - 2 * pad, 54)
        quoteh = max(84, min(112, round(h * 0.16)))
        self.quote.setGeometry(pad, h - pad - quoteh, rw - 2 * pad, quoteh)
        self.website.setGeometry(pad, h - pad - quoteh - 76, rw - 2 * pad, 64)
        self.brand.setGeometry(pad, pad + 62, round((rw - 2 * pad) * 0.55), max(210, h - quoteh - 178))
        logo_size = min(210, max(110, self.brand.height() - 165))
        density = self.devicePixelRatioF()
        logo_pixmap = self.logo_art.scaled(round(logo_size * density), round(logo_size * density), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        logo_pixmap.setDevicePixelRatio(density)
        self.logo.setPixmap(logo_pixmap)

    def set_manifest(self, manifest: object):
        """Retain structured release metadata and refresh the bounded preview."""
        self.notes.set_manifest(manifest)

    def set_state(self, state: str, detail: str = ""):
        """Apply truthful update status and manage its animation lifecycle."""
        self.state_icon.set_state(state)
        self.state_icon.setAccessibleName(f"Update status: {state}")
        if state in {"idle", "current", "available"}:
            self.latest_badge.setText("Lastest" if state == "available" else "Current")
        self.support.setText(
            {
                "checking": "Contacting the update service...",
                "current": "You are using the latest version of Shen GBot.",
                "available": "An update is ready. Use UPDATE to install it.",
                "error": detail or "Unable to check for updates. Please try again.",
            }.get(state, "Check for updates to confirm you have the latest version.")
        )
        self.support.setToolTip(self.support.text())
