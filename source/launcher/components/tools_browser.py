"""Tool catalog cards with image previews and direct helper activation."""

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

from source.launcher.components.browser_layout import TEMPLATE_LIST_ROW_HEIGHT, BrowserGallery, category_icon
from source.launcher.components.gallery import ToolCoverCard


class ToolGalleryCard(ToolCoverCard):
    """Keep helper activation while separating artwork from readable tool information."""

    INFO_HEIGHT = 124

    def __init__(self, title: str, description: str, image_path: str, action: str, category: str):
        super().__init__(title, description, image_path, action, category)
        self.list_mode = False
        self.setFont(QFont("Segoe UI", 10))
        self.animation.setDuration(150)

    @property
    def image_rect(self):
        """Use landscape thumbnails independently of the information panel."""
        width = TEMPLATE_LIST_ROW_HEIGHT * 4 // 3 if self.list_mode else self.width()
        return QRect(0, 0, width, width * 3 // 4)

    def paintEvent(self, event: object):
        """Draw clipped artwork, compact information, and a borderless hover action."""
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
        if self._cache_size != key and not self.pixmap.isNull():
            self._cache_size = key
            self._art = self.pixmap.scaled(area.size() * ratio, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self._art.setDevicePixelRatio(ratio)
        p.save()
        p.setClipRect(area, Qt.ClipOperation.IntersectClip)
        if not self.pixmap.isNull():
            p.drawPixmap(round((area.width() - self._art.width() / ratio) / 2), round((area.height() - self._art.height() / ratio) / 2), self._art)
        p.fillRect(area, QColor(0, 8, 15, round(28 * (1 - self._progress))))
        p.restore()
        left = area.width() + 16 if self.list_mode else 12
        top = 9 if self.list_mode else area.height() + 8
        available = max(1, self.width() - left - (160 if self.list_mode else 12))
        font = p.font()
        font.setPixelSize(15)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#e5f6ff"))
        p.drawText(QRect(left, top, available, 22), Qt.AlignmentFlag.AlignVCenter, p.fontMetrics().elidedText(self.title, Qt.TextElideMode.ElideRight, available))
        font.setPixelSize(12)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor("#9bc4d5"))
        category_icon(self.category).paint(p, QRect(left, top + 25, 18, 18))
        p.drawText(QRect(left + 24, top + 23, available - 24, 22), Qt.AlignmentFlag.AlignVCenter, self.category)
        lines = self._text_lines(self.description, font, available, 1 if self.list_mode else 2)
        for index, line in enumerate(lines):
            p.drawText(QRect(left, top + 47 + index * 18, available, 18), Qt.AlignmentFlag.AlignVCenter, line)
        if self.hasFocus():
            p.fillRect(QRect(left, top + 21, 40, 2), QColor("#00d9ff"))
        if self._progress > 0:
            p.setOpacity(self._progress)
            button = QRectF(self.width() - 144, (self.height() - 44) / 2, 132, 44) if self.list_mode else QRectF((self.width() - 140) / 2, (area.height() - 44) / 2 + 8 * (1 - self._progress), 140, 44)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(5, 35, 48, 240))
            p.drawRoundedRect(button, 6, 6)
            p.setPen(QColor("#e5f6ff"))
            font.setPixelSize(14)
            font.setBold(True)
            p.setFont(font)
            p.drawText(button, Qt.AlignmentFlag.AlignCenter, "Open tool")
        if self.underMouse() and self.isEnabled():
            p.setOpacity(1)
            p.setClipping(False)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(0, 216, 255, round(255 * self._progress)), 1))
            p.drawPath(shape)


class ToolsBrowser(BrowserGallery):
    """A read-only tool browser with independently retained filters and view mode."""

    def __init__(self):
        super().__init__("Tools", "Browse and launch your automation tools.", "tools.cover", "tool.transfer_server", "Default order")
        self.empty.setText("No matching tools.")

    def add_card(self, card: ToolGalleryCard):
        """Keep existing callback connections and update the real category choices."""
        card.setParent(self.content)
        self.cards.append(card)
        self.set_categories({item.category for item in self.cards})
        self.reflow()

    def reflow(self, value: object = ""):
        """Combine name/description search, category filtering, and stable sorting."""
        if not hasattr(self, "sort"):
            return
        query = self.search.text().strip().casefold()
        category = self.category.currentText()
        visible = [card for card in self.cards if query in f"{card.title} {card.description}".casefold() and (category == "All Categories" or card.category == category)]
        if self.sort.currentIndex():
            visible.sort(key=lambda card: card.title.casefold(), reverse=self.sort.currentIndex() == 2)
        self.place_cards(visible)
