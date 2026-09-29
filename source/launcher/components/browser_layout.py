"""Shared cover, toolbar, and responsive layout for read-only app catalogs."""

from math import ceil
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QButtonGroup, QLabel, QLineEdit, QPushButton, QSizePolicy, QVBoxLayout

from source.launcher.components.custom_pyside_component import NoWheelComboBox, configure_settings_dropdown
from source.launcher.components.dashboard import line_icon
from source.launcher.components.gallery import CoverGallery
from source.launcher.components.settings_sections import CoverFrame
from source.launcher.config.constants import ASSETS
from source.launcher.dashboard_theme import asset_path
from source.launcher.settings_theme import BREADCRUMB_HEIGHT

# Shared logical-pixel geometry. Width is a ceiling, not a minimum column size.
TEMPLATE_CARD_MAX_WIDTH = 320
TEMPLATE_GRID_GAP = 16
TEMPLATE_LIST_ROW_HEIGHT = 84
TEMPLATE_HEADER_GAP = 12
TEMPLATE_TOOLBAR_GAP = 8

BROWSER_STYLE = """
QWidget#TemplateBrowser, QWidget#TemplateBrowser QLabel, QWidget#TemplateBrowser QLineEdit, QWidget#TemplateBrowser QComboBox, QWidget#TemplatePreviewPanel, QWidget#TemplatePreviewPanel QLabel, QWidget#TemplateBrowser QPushButton, QWidget#TemplatePreviewPanel QPushButton { color: #dbf4ff; font-family: 'Segoe UI'; font-size: 14px; }
QWidget#TemplatePreviewPanel { background: #04141f; border: 1px solid #00a2c6; border-radius: 10px; }
QWidget#TemplateBrowser QLineEdit, QWidget#TemplateBrowser QLineEdit:focus, QWidget#TemplateBrowser QComboBox:hover { border-color: #00d9ff; }
QWidget#TemplatePreviewPanel QLabel { background: transparent; border: none; color: #c3deeb; }
QWidget#TemplateBrowser QPushButton, QWidget#TemplatePreviewPanel QPushButton { background: #082637; color: #00d9ff; border: 1px solid #00a2c6; border-radius: 6px; padding: 0 14px; }
QWidget#TemplateBrowser QPushButton:checked, QWidget#TemplateBrowser QPushButton:hover, QWidget#TemplatePreviewPanel QPushButton:hover, QWidget#TemplatePreviewPanel QPushButton:focus { background: #0c3b50; border-color: #00d9ff; }
QWidget#TemplatePreviewPanel QPushButton:disabled { color: #71919f; border-color: #214351; }
"""


class BrowserHero(CoverFrame):
    """Use the Settings breadcrumb cover renderer without its lower contour."""

    def __init__(self, title: str, subtitle: str, cover: str, fallback: str):
        self.fallback = fallback
        super().__init__(cover)
        self.setFixedHeight(BREADCRUMB_HEIGHT)
        box = QVBoxLayout(self)
        box.setContentsMargins(24, 12, 24, 12)
        title = QLabel(title)
        title.setStyleSheet("color: #00d9ff; font-size: 23px; font-weight: 700; background: transparent;")
        subtitle = QLabel(subtitle)
        subtitle.setWordWrap(True)
        box.addWidget(title)
        box.addWidget(subtitle)

    def set_cover(self, cover: str):
        """Keep the replaceable construction artwork and its bundled fallback."""
        path = asset_path(ASSETS[cover])
        self.art = QPixmap(path if Path(path).is_file() else asset_path(ASSETS[self.fallback]))
        self._cache_key = None
        self._scaled = QPixmap()


def category_icon(category: str):
    """Use the existing icon family for real library categories."""
    return line_icon({"Gacha": "paw", "Transfer": "update", "QoL": "tools"}.get(category, "logs"))


class BrowserGallery(CoverGallery):
    """Shared controls and placement with catalog-specific filtering and actions."""

    def __init__(self, title: str, subtitle: str, cover: str, fallback: str, default_sort: str):
        super().__init__(title)
        self.list_mode = False
        self.setObjectName("TemplateBrowser")
        self.setStyleSheet(BROWSER_STYLE)
        self.layout().insertWidget(0, BrowserHero(title, subtitle, cover, fallback))
        header = self.layout().itemAt(1).layout()
        # Replace the old title/stretch row with the approved full-width filter bar.
        while header.count():
            item = header.takeAt(0)
            widget = item.widget()
            if widget and widget not in (self.search, self.category):
                widget.deleteLater()
        self.search.setMaximumWidth(16777215)
        self.search.setPlaceholderText(f"Search {title.lower()}...")
        self.category.clear()
        self.category.addItem("All Categories")
        self.sort = NoWheelComboBox()
        self.sort.addItems([default_sort, "Name A-Z", "Name Z-A"])
        for index in range(self.sort.count()):
            self.sort.setItemIcon(index, line_icon("sort"))
        self.sort.setAccessibleName(f"Sort {title.lower()}")
        for widget in (self.search, self.category, self.sort):
            widget.setFixedHeight(44)
            widget.setMinimumWidth(0)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for combo in (self.category, self.sort):
            configure_settings_dropdown(combo)
        self.search.addAction(line_icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        header.setSpacing(TEMPLATE_TOOLBAR_GAP)
        header.addWidget(self.search, 3)
        header.addWidget(self.category, 1)
        header.addWidget(self.sort, 1)
        self.view_group = QButtonGroup(self)
        for mode in ("grid", "list"):
            button = QPushButton()
            button.setIcon(line_icon(mode))
            button.setIconSize(QSize(24, 24))
            button.setFixedSize(44, 44)
            button.setCheckable(True)
            button.setChecked(mode == "grid")
            button.setAccessibleName(f"{mode.title()} view")
            button.setToolTip(f"{mode.title()} view")
            self.view_group.addButton(button)
            button.clicked.connect(lambda checked, name=mode: self.set_view_mode(name))
            header.addWidget(button)

        self.feedback = QLabel()
        self.feedback.setWordWrap(True)
        self.feedback.hide()
        self.layout().insertWidget(2, self.feedback)
        self.layout().setSpacing(TEMPLATE_HEADER_GAP)
        self.sort.currentIndexChanged.connect(self.reflow)

    def set_view_mode(self, mode: str):
        """Switch layout without recreating cards or their callbacks."""
        self.list_mode = mode == "list"
        self.reflow()

    def set_categories(self, categories: set):
        """Offer only real categories while preserving the current filter."""
        current = self.category.currentText()
        self.category.blockSignals(True)
        self.category.clear()
        for category in ["All Categories", *sorted(categories)]:
            self.category.addItem(category_icon(category), category)
        self.category.setCurrentIndex(max(0, self.category.findText(current)))
        self.category.blockSignals(False)

    def place_cards(self, visible: list):
        """Size grid images at 4:3 and preserve one vertical collection scrollbar."""
        viewport = max(4, self.scroll.viewport().width())
        columns = 1 if self.list_mode else max(1, ceil((viewport + TEMPLATE_GRID_GAP) / (TEMPLATE_CARD_MAX_WIDTH + TEMPLATE_GRID_GAP)))
        width = max(4, ((viewport - (columns - 1) * TEMPLATE_GRID_GAP) // columns) // 4 * 4)
        for card in self.cards:
            card.list_mode = self.list_mode
            card.setVisible(card in visible)
        height = TEMPLATE_LIST_ROW_HEIGHT if self.list_mode else width * 3 // 4 + (visible[0].INFO_HEIGHT if visible else 76)
        for index, card in enumerate(visible):
            row, column = divmod(index, columns)
            card.setGeometry(column * (width + TEMPLATE_GRID_GAP), row * (height + TEMPLATE_GRID_GAP), width, height)
            card.update()
        rows = (len(visible) + columns - 1) // columns
        self.content.setMinimumHeight(max(0, rows * (height + TEMPLATE_GRID_GAP) - TEMPLATE_GRID_GAP))
        self.empty.setVisible(not visible)
        self.empty.setGeometry(0, 0, viewport, 80)
