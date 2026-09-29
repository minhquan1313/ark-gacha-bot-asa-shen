"""Read-only template catalog with an animated, in-window import preview."""

import contextlib
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QRect, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QImage, QImageReader, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from source.launcher.components.browser_layout import (
    BROWSER_STYLE,
    BrowserGallery,
    category_icon,
)
from source.launcher.components.browser_layout import (
    TEMPLATE_CARD_MAX_WIDTH as TEMPLATE_CARD_MAX_WIDTH,
)
from source.launcher.components.browser_layout import (
    TEMPLATE_GRID_GAP as TEMPLATE_GRID_GAP,
)
from source.launcher.components.browser_layout import (
    TEMPLATE_HEADER_GAP as TEMPLATE_HEADER_GAP,
)
from source.launcher.components.browser_layout import (
    TEMPLATE_LIST_ROW_HEIGHT as TEMPLATE_LIST_ROW_HEIGHT,
)
from source.launcher.components.browser_layout import (
    TEMPLATE_TOOLBAR_GAP as TEMPLATE_TOOLBAR_GAP,
)
from source.launcher.components.dashboard import line_icon
from source.launcher.components.gallery import ToolCoverCard
from source.launcher.components.popout import POPOUT_CLOSE_MS, AnimatedPopout
from source.launcher.components.popout import POPOUT_OPEN_MS as TEMPLATE_PREVIEW_OPEN_MS
from source.launcher.utils.building_templates import TEMPLATE_CATEGORIES, discover_templates, import_template

TEMPLATE_PREVIEW_CLOSE_MS = POPOUT_CLOSE_MS

# Adjustable browser presentation values (logical pixels / milliseconds).
# These are animation durations, like CSS transition-duration, not input delays.


@dataclass(frozen=True)
class TemplateModel:
    """One source file and its real filesystem metadata; no editable library state."""

    source: Path
    preview: Path | None
    name: str
    category: str
    size: int
    modified: float
    image: QImage

    @property
    def metadata(self):
        """Format actual size without claiming unsupported structure counts."""
        size = f"{self.size / 1048576:.1f} MB" if self.size >= 1048576 else f"{self.size / 1024:.1f} KB" if self.size >= 1024 else f"{self.size} B"
        return f"{self.category}  |  {size}"


@lru_cache(maxsize=64)
def read_preview(path: str, modified: int, extent: int):
    """Decode and cache bounded images off the UI thread; mtime invalidates entries."""
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and max(size.width(), size.height()) > extent:
        reader.setScaledSize(size.scaled(extent, extent, Qt.AspectRatioMode.KeepAspectRatio))
    return reader.read()


def load_template_models():
    """Discover source metadata and thumbnail images in the gallery worker."""
    models = []
    for source, preview in discover_templates():
        stat = source.stat()
        image = QImage()
        if preview:
            with contextlib.suppress(OSError):
                image = read_preview(str(preview), preview.stat().st_mtime_ns, 640)
        models.append(TemplateModel(source, preview, source.stem, TEMPLATE_CATEGORIES.get(source.stem, "Unsorted"), stat.st_size, stat.st_mtime, image))
    return models


class TemplateCard(ToolCoverCard):
    """A 4:3 image followed by a separate information panel; click means preview."""

    INFO_HEIGHT = 76

    def __init__(self, model: TemplateModel):
        super().__init__(model.name, model.metadata, "", "Preview", model.category)
        self.setFont(QFont("Segoe UI", 10))
        self.list_mode = False
        self.model = model
        self.pixmap = QPixmap.fromImage(model.image)
        self.animation.setDuration(150)

    @property
    def image_rect(self):
        """The information panel is excluded from the image aspect ratio."""
        return QRect(0, 0, TEMPLATE_LIST_ROW_HEIGHT * 4 // 3, TEMPLATE_LIST_ROW_HEIGHT) if self.list_mode else QRect(0, 0, self.width(), self.width() * 3 // 4)

    def paintEvent(self, event: object):
        """Cache landscape cropping once per size/DPR and paint subtle hover emphasis."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        p.setClipPath(shape)
        p.fillRect(self.rect(), QColor("#04141f"))
        area = self.image_rect
        ratio = self.devicePixelRatioF()
        key = (area.size(), ratio, self.pixmap.cacheKey())
        if key != self._cache_size and not self.pixmap.isNull():
            self._cache_size = key
            self._art = self.pixmap.scaled(round(area.width() * ratio), round(area.height() * ratio), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self._art.setDevicePixelRatio(ratio)
        if not self.pixmap.isNull():
            p.save()
            p.setClipRect(area, Qt.ClipOperation.IntersectClip)
            p.drawPixmap(round((area.width() - self._art.width() / ratio) / 2), round((area.height() - self._art.height() / ratio) / 2), self._art)
            p.fillRect(area, QColor(0, 8, 15, round(22 * (1 - self._progress))))
            p.restore()
        else:
            p.setPen(QPen(QColor("#123c50"), 1))
            for x in range(0, area.width(), 24):
                p.drawLine(x, 0, x, area.height())
            for y in range(0, area.height(), 24):
                p.drawLine(0, y, area.width(), y)
            p.setPen(QColor("#8baebf"))
            p.drawText(area, Qt.AlignmentFlag.AlignCenter, "Preview unavailable")
        font = p.font()
        font.setPixelSize(15)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#e5f6ff"))
        left = area.width() + 20 if self.list_mode else 12
        top = (self.height() - 52) // 2 if self.list_mode else area.height() + 10
        available = self.width() - left - 12
        name = p.fontMetrics().elidedText(self.model.name, Qt.TextElideMode.ElideRight, available)
        p.drawText(QRect(left, top, available, 24), Qt.AlignmentFlag.AlignVCenter, name)
        font.setPixelSize(12)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor("#9bc4d5"))
        category_icon(self.model.category).paint(p, QRect(left, top + 30, 20, 20))
        category_width = p.fontMetrics().horizontalAdvance(self.model.category)
        p.drawText(QRect(left + 28, top + 28, category_width, 24), Qt.AlignmentFlag.AlignVCenter, self.model.category)
        size_x = left + 28 + category_width + 20
        line_icon("cube").paint(p, QRect(size_x, top + 30, 20, 20))
        p.drawText(QRect(size_x + 28, top + 28, available - (size_x - left) - 28, 24), Qt.AlignmentFlag.AlignVCenter, self.model.metadata.split("|")[-1].strip())
        if self.hasFocus():
            # Keyboard focus stays visible without restoring a card outline.
            p.fillRect(QRect(left, top + 24, min(available, 48), 2), QColor("#00d9ff"))
        if self.underMouse() and self.isEnabled():
            p.setClipping(False)
            p.setPen(QPen(QColor(0, 216, 255, round(255 * self._progress)), 1))
            p.drawPath(shape)


class TemplatePreviewOverlay(AnimatedPopout, QWidget):
    """One reusable in-window focused preview with reversible geometry animation."""

    def __init__(self, browser: QWidget):
        super().__init__(browser.window())
        self.browser = browser
        self.card = None
        self.progress = 0.0
        self.closing = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.panel = QWidget(self)
        self.panel.setObjectName("TemplatePreviewPanel")
        self.setStyleSheet(BROWSER_STYLE)
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        top = QHBoxLayout()
        caption = QLabel("TEMPLATE PREVIEW")
        caption.setStyleSheet("color: #8ebdcc; font-size: 12px; font-weight: 600; letter-spacing: 2px;")
        top.addWidget(caption)
        top.addStretch()
        self.close_button = QPushButton("×")
        self.close_button.setAccessibleName("Close template preview")
        self.close_button.setFixedSize(44, 44)
        self.close_button.clicked.connect(self.close_preview)
        top.addWidget(self.close_button)
        layout.addLayout(top)
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image, 0, Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setFixedHeight(44)
        self.title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00d9ff;")
        layout.addWidget(self.title)
        self.metadata = QLabel()
        self.metadata.setFixedHeight(24)
        metadata_row = QHBoxLayout()
        self.category_symbol = QLabel()
        self.category_symbol.setFixedSize(24, 24)
        metadata_row.addWidget(self.category_symbol)
        metadata_row.addWidget(self.metadata)
        metadata_row.addStretch()
        self.size_symbol = QLabel()
        self.size_symbol.setPixmap(line_icon("cube").pixmap(24, 24))
        metadata_row.addWidget(self.size_symbol)
        self.file_size = QLabel()
        metadata_row.addWidget(self.file_size)
        layout.addLayout(metadata_row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setFixedHeight(36)
        footer = QHBoxLayout()
        footer.addWidget(self.status, 1)
        self.import_button = QPushButton("Import")
        self.import_button.setIcon(line_icon("save"))
        self.import_button.setIconSize(QSize(24, 24))
        self.import_button.setFixedSize(160, 44)
        self.import_button.clicked.connect(lambda: browser.import_selected(self.card.model))
        footer.addWidget(self.import_button)
        layout.addLayout(footer)
        self.animation = QVariantAnimation(self)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self._frame)
        self.animation.finished.connect(self._finished)
        self.hide()

    def open_card(self, card: TemplateCard):
        """Map the source card into the application and animate forward."""
        if self.isVisible():
            return
        self.card = card
        self.original = card.pixmap
        self.title.setText(card.model.name)
        self.metadata.setText(card.model.category)
        self.category_symbol.setPixmap(category_icon(card.model.category).pixmap(24, 24))
        self.file_size.setText(card.model.metadata.split("|")[-1].strip())
        self.status.clear()
        self.import_button.setText("Import")
        self.import_button.setEnabled(not self.browser._busy)
        self.closing = False
        self.progress = 0.0
        self.setGeometry(self.parentWidget().rect())
        self._map_source()
        self._prepare_panel()
        self.show()
        self.raise_()
        QApplication.instance().installEventFilter(self)
        self.setFocus()
        self._animate(1.0, TEMPLATE_PREVIEW_OPEN_MS)

    def _map_source(self):
        """Measure the actual image after layout in overlay-local logical pixels."""
        self.source = QRect(self.mapFromGlobal(self.card.mapToGlobal(QPoint())), self.card.size())
        self.image_source = QRect(self.mapFromGlobal(self.card.mapToGlobal(self.card.image_rect.topLeft())), self.card.image_rect.size())
        viewport = self.browser.scroll.viewport()
        self.source_clip = QRect(self.mapFromGlobal(viewport.mapToGlobal(QPoint())), viewport.size())

    def _prepare_panel(self):
        """Fit the complete source image, preserving its native aspect ratio."""
        bounds = QSize(min(900, max(160, self.width() - 112)), max(120, self.height() - 260))
        native = self.original.size() if not self.original.isNull() else QSize(640, 480)
        fitted = native.scaled(bounds, Qt.AspectRatioMode.KeepAspectRatio)
        width, height = max(460, fitted.width() + 32), fitted.height() + 212
        width = min(width, self.width() - 48)
        self.target = QRect((self.width() - width) // 2, (self.height() - height) // 2, width, height)
        self.image.setFixedSize(fitted)
        self.panel.setGeometry(self.target)
        self._set_image()
        self.panel.show()
        self.panel.layout().activate()
        self._capture_panel()
        self.panel.setVisible(self.progress == 1 and not self.closing)

    def _capture_panel(self):
        """Separate the portrait from the panel snapshot to keep its ratio in motion."""
        self.snapshot = self.panel.grab()
        self.portrait = self.image.pixmap()
        self.image_target = QRect(self.image.mapTo(self, QPoint()), self.image.size())
        if self.portrait and not self.portrait.isNull():
            painter = QPainter(self.snapshot)
            painter.fillRect(QRect(self.image.mapTo(self.panel, QPoint()), self.image.size()), QColor("#04141f"))
            painter.end()

    def _set_image(self):
        """Prepare the final image once; animation draws its snapshot directly."""
        if self.original.isNull():
            self.image.setPixmap(QPixmap())
            self.image.setText("Preview unavailable")
            self.image.setStyleSheet("background: #082333; color: #9bc4d5; border: 1px solid #164759;")
            return
        self.image.setStyleSheet("background: transparent;")
        ratio = self.devicePixelRatioF()
        size = self.image.size() * ratio
        art = self.original.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        art.setDevicePixelRatio(ratio)
        self.image.setPixmap(art)

    def paintEvent(self, event: object):
        """Interpolate actual image bounds and crop, with a separately fading panel."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        t = self.progress
        p.fillRect(self.rect(), QColor(0, 5, 12, round(160 * t)))
        if self.panel.isVisible():
            return
        p.setOpacity(t * t)
        p.drawPixmap(self.target, self.snapshot)
        p.setOpacity(1)
        start, end = QRectF(self.image_source), QRectF(self.image_target)
        rect = QRectF(
            start.x() + (end.x() - start.x()) * t, start.y() + (end.y() - start.y()) * t, start.width() + (end.width() - start.width()) * t, start.height() + (end.height() - start.height()) * t
        )
        clip = QRectF(self.source_clip)
        final_clip = QRectF(self.rect())
        p.setClipRect(QRectF(clip.x() * (1 - t), clip.y() * (1 - t), clip.width() + (final_clip.width() - clip.width()) * t, clip.height() + (final_clip.height() - clip.height()) * t))
        if not self.original.isNull():
            full = QRectF(self.original.rect())
            ratio = rect.width() / rect.height()
            crop_width = min(full.width(), full.height() * ratio)
            crop_height = min(full.height(), full.width() / ratio)
            crop = QRectF((full.width() - crop_width) / 2, (full.height() - crop_height) / 2, crop_width, crop_height)
            p.drawPixmap(rect, self.original, crop)
        else:
            p.fillRect(rect, QColor("#082333"))
            p.setPen(QColor("#9bc4d5"))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Preview unavailable")


class TemplateBrowser(BrowserGallery):
    """Dedicated template presentation while the Tools gallery remains unchanged."""

    image_ready = Signal(object, object)

    def __init__(self, notify: object):
        super().__init__("Building templates", "Manage and import your structure templates for automated building.", "btemplates.cover", "btemplates.blueprint", "Last modified")
        self.search.setPlaceholderText("Search templates...")
        self.notify = notify
        self.overlay = None
        self.image_ready.connect(self._image_loaded)

    def load(self):
        """Discover metadata and thumbnails without blocking startup."""
        self.empty.setText("Loading templates...")
        self.run_work(load_template_models, self._loaded)

    def _loaded(self, models: list, error: str):
        """Install the catalog and category options once worker discovery finishes."""
        if error:
            self.empty.setText(f"Unable to load templates: {error}")
            return
        self.models = models
        self.set_categories({m.category for m in models})
        for model in models:
            card = TemplateCard(model)
            card.setParent(self.content)
            card.activated.connect(lambda selected=card: self.open_preview(selected))
            self.cards.append(card)
        self.empty.setText("No matching templates.")
        self.reflow()

    def reflow(self, value: object = ""):
        """Fit as many columns as needed to keep grid cards below the width limit."""
        if not hasattr(self, "sort"):
            return
        query, category = self.search.text().strip().casefold(), self.category.currentText()
        visible = [c for c in self.cards if query in c.model.name.casefold() and (category == "All Categories" or c.category == category)]
        order = self.sort.currentIndex()
        visible.sort(key=lambda c: c.model.name.casefold(), reverse=order == 2)
        if order == 0:
            visible.sort(key=lambda c: c.model.modified, reverse=True)
        self.place_cards(visible)

    def open_preview(self, card: TemplateCard):
        """Open exactly one preview and asynchronously request its full image."""
        if self.overlay is None:
            self.overlay = TemplatePreviewOverlay(self)
        if self.overlay.isVisible():
            return
        self.overlay.open_card(card)
        model = card.model
        if model.preview:

            def decode():
                """Deliver high-resolution image data; never create pixmaps in workers."""
                image = QImage()
                with contextlib.suppress(OSError):
                    image = read_preview(str(model.preview), model.preview.stat().st_mtime_ns, 1600)
                with contextlib.suppress(RuntimeError):
                    self.image_ready.emit(model, image)

            threading.Thread(target=decode, daemon=True).start()

    def _image_loaded(self, model: TemplateModel, image: QImage):
        """Apply only to the still-selected preview and cache its final rendering."""
        if self.overlay and self.overlay.isVisible() and self.overlay.card.model.source == model.source and not image.isNull():
            self.overlay.original = QPixmap.fromImage(image)
            self.overlay._prepare_panel()

    def import_selected(self, model: TemplateModel):
        """Copy the selected existing template once; source data stays read-only."""
        if self._busy:
            return
        self.overlay.status.setText("Importing...")
        self.overlay.import_button.setEnabled(False)
        self.feedback.hide()

        def complete(destination: object, error: str):
            """Report completion safely even when the focused preview has closed."""
            message = f"Import failed: {error}" if error else f"Imported {model.name}"
            if self.overlay and self.overlay.card.model.source == model.source:
                self.overlay.status.setText(message)
                self.overlay.status.setToolTip(message)
                self.overlay.import_button.setText("Import" if error else "Imported")
                self.overlay.import_button.setEnabled(bool(error))
            self.feedback.setText(message)
            self.feedback.setVisible(bool(error) and not self.overlay.isVisible())
            if not error:
                self.notify(message, "success")

        self.run_work(lambda: import_template(model.source), complete)
