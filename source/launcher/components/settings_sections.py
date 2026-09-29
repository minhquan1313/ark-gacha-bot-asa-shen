"""Approved Settings shell, fixed-height covers, and aligned field cards."""

from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from source.launcher.components.cover_painting import painted_cover
from source.launcher.components.dashboard import DashboardButton, line_icon
from source.launcher.config.constants import ASSETS
from source.launcher.dashboard_theme import asset_path
from source.launcher.settings_theme import (
    BREADCRUMB_HEIGHT,
    BREADCRUMB_LIP_DEPTH,
    BREADCRUMB_RADIUS,
    BREADCRUMB_WRAPPED_HEIGHT,
    CARD_PADDING,
    CARD_SPACING,
    CONTROL_HEIGHT,
    SECTION_CARD_RADIUS,
    SECTION_HEADER_HEIGHT,
)


def settings_icon(name: str):
    """Use the shared file-backed icon loader."""
    return line_icon(name)


def settings_label(text: str, role: str = "helper"):
    """Create a scoped label with predictable wrapping and contrast."""
    label = QLabel(text)
    label.setProperty("settingsRole", role)
    label.setWordWrap(True)
    label.setMinimumWidth(0)
    return label


class SettingsActionButton(DashboardButton):
    """Reuse button state behavior at one fixed Settings control height."""

    def __init__(self, text: str, icon: str, variant: str = "secondary", compact: bool = True):
        super().__init__(text, variant, compact=compact)
        self.setFixedHeight(CONTROL_HEIGHT)
        self.setIcon(settings_icon(icon))
        self.setIconSize(QSize(24, 24))


class SettingsUnitControl(QWidget):
    """Reserve identical unit space beside related fields, including unitless buttons."""

    def __init__(self, control: QWidget, unit: str = ""):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(control, 1)
        suffix = settings_label(unit)
        suffix.setFixedWidth(24)
        row.addWidget(suffix)


class CoverFrame(QFrame):
    """Render a subdued crop inside a frame whose layout determines its size."""

    def __init__(self, cover: str):
        super().__init__()
        self.bottom_lip = 0
        self.set_cover(cover)
        self.setMinimumWidth(0)

    def set_cover(self, cover: str):
        """Load a registered artwork slot, falling back without changing geometry."""
        slot = ASSETS[f"settings.{cover}"]
        fallback = ASSETS["dashboard"]
        if cover in {"launcher", "auto_keys"} and Path(asset_path(ASSETS["settings.server"])).is_file():
            fallback = ASSETS["settings.server"]
        if cover.startswith(("breadcrumb.", "pego_", "dedi_", "craft", "gacha")):
            fallback = ASSETS["settings.breadcrumb"]
        if cover in {"gacha", "gacha_collect"}:
            fallback = ASSETS["settings.render" if cover == "gacha" else "settings.server"]
        selected = slot if Path(asset_path(slot)).is_file() else fallback
        if not Path(asset_path(selected)).is_file():
            selected = ASSETS["dashboard"]
        self.cover_asset = selected
        self.art = QPixmap(asset_path(selected))
        if selected == ASSETS["dashboard"] and not self.art.isNull():
            # Use a quiet city crop without the tool covers' baked-in titles.
            self.art = self.art.copy(20, 20, round(self.art.width() * 0.48), self.art.height() - 40)
        self._cache_key = None
        self._scaled = QPixmap()

    def paintEvent(self, event: QPaintEvent):
        """Paint the entire card and header artwork with one outer rounded path."""
        bounds = QRectF(self.rect())
        header = getattr(self, "header", None)
        art_bounds = QRectF(bounds)
        if header is not None:
            art_bounds.setHeight(header.geometry().bottom() + 1)
        ratio = self.devicePixelRatioF()
        key = (art_bounds.width(), art_bounds.height(), ratio)
        if key != self._cache_key and not self.art.isNull():
            self._scaled = self.art.scaled(
                round(art_bounds.width() * ratio),
                round(art_bounds.height() * ratio),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._scaled.setDevicePixelRatio(ratio)
            self._cache_key = key
        position = QPointF(
            art_bounds.right() - self._scaled.width() / ratio,
            (art_bounds.height() - self._scaled.height() / ratio) / 2,
        )
        painter = QPainter(self)
        with painted_cover(
            painter,
            bounds,
            SECTION_CARD_RADIUS if header is not None else BREADCRUMB_RADIUS,
            self._scaled,
            position,
            QPen(QColor("#00D9FF"), 1),
            QColor("#06131C"),
            art_bounds,
            bottom_lip=self.bottom_lip,
            drop_start=self.cover_drop_start(),
        ):
            pass

    def cover_drop_start(self):
        """Regular section cards have no decorative lower contour."""
        return 0.0


class SettingsSectionHeader(QWidget):
    """A 104-pixel illustrated cover shared by every approved section."""

    def __init__(self, title: str, subtitle: str, icon: str):
        super().__init__()
        self.setFixedHeight(SECTION_HEADER_HEIGHT)
        row = QHBoxLayout(self)
        row.setContentsMargins(24, 12, 24, 12)
        row.setSpacing(20)
        symbol = QLabel()
        symbol.setPixmap(settings_icon(icon).pixmap(44, 44))
        symbol.setFixedSize(44, 44)
        row.addWidget(symbol)
        text = QVBoxLayout()
        text.setSpacing(4)
        text.addStretch()
        text.addWidget(settings_label(title, "title"))
        text.addWidget(settings_label(subtitle, "subtitle"))
        text.addStretch()
        row.addLayout(text, 1)


class SettingsSectionCard(CoverFrame):
    """Identical section cover and body spacing for Server and all stations."""

    def __init__(self, title: str, subtitle: str, cover: str, icon: str):
        super().__init__(cover)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        box = QVBoxLayout(self)
        box.setContentsMargins(2, 2, 2, 2)
        box.setSpacing(0)
        self.header = SettingsSectionHeader(title, subtitle, icon)
        box.addWidget(self.header)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        self.body.setSpacing(CARD_SPACING)
        box.addLayout(self.body)


class SettingsField(QWidget):
    """One aligned label/control pair with optional secondary helper text."""

    def __init__(
        self,
        title: str,
        control: QWidget,
        description: str = "",
        stacked: bool = False,
        icon: str = "",
        natural_label: bool = False,
    ):
        super().__init__()
        self.setMinimumWidth(0)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        self.label = settings_label(title, "label")
        if stacked:
            box.addWidget(self.label)
            box.addWidget(control)
        else:
            row = QHBoxLayout()
            row.setSpacing(12)
            if natural_label:
                # Qt updates the natural hint after polish, font and style changes.
                self.label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
            else:
                self.label.setFixedWidth(108)
            if icon:
                marker = QLabel()
                marker.setPixmap(settings_icon(icon).pixmap(20, 20))
                marker.setFixedSize(20, 20)
                row.addWidget(marker)
                row.setSpacing(6)
            row.addWidget(self.label)
            row.addWidget(control, 1)
            box.addLayout(row)
        if description:
            box.addWidget(settings_label(description))


class SettingsFieldGrid(QWidget):
    """Keep field pairs aligned and stack them when the form is narrow."""

    def __init__(self, fields: list[QWidget], columns: int = 2, column_width: int = 335):
        super().__init__()
        self.fields = fields
        self.max_columns = columns
        self.column_width = column_width
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(28)
        self.grid.setVerticalSpacing(18)
        self._columns = 0
        self._reflow()

    def _reflow(self):
        """Choose columns from available content width without rebuilding fields."""
        columns = max(1, min(self.max_columns, self.width() // self.column_width))
        if columns == self._columns:
            return
        self._columns = columns
        for index, field in enumerate(self.fields):
            self.grid.removeWidget(field)
            self.grid.addWidget(
                field,
                index // columns,
                index % columns,
                alignment=Qt.AlignmentFlag.AlignTop,
            )
        for column in range(self.max_columns):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)

    def resizeEvent(self, event: QResizeEvent):
        """Respond to form resizing with a stable two-column grid."""
        super().resizeEvent(event)
        self._reflow()


class SettingsColumns(QWidget):
    """Position the sidebar below the raised edge without moving the content column."""

    def __init__(self, header: CoverFrame, sidebar: QWidget, content: QWidget, gap: int):
        super().__init__()
        self.header = header
        self.gap = gap
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(0)
        self.grid.setColumnStretch(1, 1)
        self.grid.setRowStretch(2, 1)
        self.grid.addWidget(header, 0, 0, 2, 2, Qt.AlignmentFlag.AlignTop)
        sidebar_column = QWidget()
        sidebar_column.setFixedWidth(sidebar.width())
        sidebar_layout = QVBoxLayout(sidebar_column)
        sidebar_layout.setContentsMargins(0, gap, 0, 0)
        sidebar_layout.setSpacing(0)
        sidebar_layout.addWidget(sidebar)
        self.grid.addWidget(sidebar_column, 1, 0, 2, 1)
        self.grid.addWidget(content, 2, 1)
        header.installEventFilter(self)
        self._sync_header_rows()

    def _sync_header_rows(self):
        """Keep the content baseline fixed as the breadcrumb controls wrap."""
        self.grid.setRowMinimumHeight(0, self.header.height() - self.header.bottom_lip)
        self.grid.setRowMinimumHeight(1, self.header.bottom_lip + self.gap)

    def eventFilter(self, watched: QWidget, event: QEvent):
        """Track the real header height through normal and compact layouts."""
        if watched is self.header and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self._sync_header_rows)
        return super().eventFilter(watched, event)


class SettingsBreadcrumbHeader(CoverFrame):
    """Breadcrumb banner with the single group-profile selector and file menu."""

    def __init__(self, import_export: QWidget):
        super().__init__("breadcrumb")
        self.sidebar = None
        self.bottom_lip = BREADCRUMB_LIP_DEPTH
        self.setObjectName("SettingsBreadcrumb")
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(24, 12, 12, 12 + BREADCRUMB_LIP_DEPTH)
        self.grid.setSpacing(12)
        self.copy = QWidget()
        text = QVBoxLayout(self.copy)
        text.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel()
        self.title.setObjectName("SettingsBreadcrumbTitle")
        self.subtitle = QLabel()
        self.subtitle.setWordWrap(True)
        text.addWidget(self.title)
        text.addWidget(self.subtitle)
        self.profile = QWidget()
        self.profile.setFixedWidth(218)
        self.profile_layout = QVBoxLayout(self.profile)
        self.profile_layout.setContentsMargins(0, 0, 0, 0)
        self.profile_layout.setSpacing(4)
        caption = QLabel("SETTINGS PROFILE")
        caption.setObjectName("SettingsProfileCaption")
        self.profile_layout.addWidget(caption)
        self.selector = None
        self.import_export = import_export
        import_export.setFixedWidth(218)
        self._compact = None
        self.set_group("SERVER")
        self._reflow()

    def set_sidebar(self, sidebar: QWidget):
        """Bind the contour to the live sidebar geometry instead of a width ratio."""
        self.sidebar = sidebar
        sidebar.installEventFilter(self)
        self.update()

    def cover_drop_start(self):
        """Map the sidebar's right edge to the breadcrumb's local coordinates."""
        if self.sidebar is None:
            return 0.0
        return float(self.mapFromGlobal(self.sidebar.mapToGlobal(QPoint(self.sidebar.width(), 0))).x())

    def eventFilter(self, watched: QWidget, event: QEvent):
        """Repaint when layout changes move or resize the sidebar boundary."""
        if watched is self.sidebar and event.type() in (
            QEvent.Type.Move,
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            self.update()
        return super().eventFilter(watched, event)

    def set_group(self, group: str):
        """Update breadcrumb and reserve the profile only for approved groups."""
        self.set_cover(f"breadcrumb.{group.lower()}")
        self.update()
        self.title.setText(f"SETTINGS  >  {group}")
        self.subtitle.setText(
            {
                "PEGO": "Configure pego teleporters and delays",
                "SERVER": "Configure main server connection and general options",
                "STATIONS": "Configure positions for different resource stations",
            }.get(group, "Configure your automation settings")
        )
        self.profile.setVisible(group in {"SERVER", "STATIONS", "LAUNCHER", "PEGO", "DEDI", "CRAFT", "GACHA"})
        if self.selector is not None:
            self.profile_layout.removeWidget(self.selector)
            self.selector.hide()
            self.selector.deleteLater()
            self.selector = None

    def set_profile(self, selector: QWidget):
        """Host the existing selector without duplicating its apply logic."""
        self.selector = selector
        from source.launcher.components.custom_pyside_component import configure_settings_dropdown

        configure_settings_dropdown(selector)
        selector.setFixedHeight(CONTROL_HEIGHT)
        selector.setMinimumWidth(0)
        selector.setAccessibleName("Settings profile for current group")
        self.profile_layout.addWidget(selector)

    def _reflow(self):
        """Wrap top controls below the breadcrumb on smaller windows."""
        compact = self.width() < 960
        if compact == self._compact:
            return
        self._compact = compact
        for widget in (self.copy, self.profile, self.import_export):
            self.grid.removeWidget(widget)
        self.grid.addWidget(self.copy, 0, 0, 1, 3 if compact else 1)
        self.grid.addWidget(self.profile, 1 if compact else 0, 1)
        self.grid.addWidget(
            self.import_export,
            1 if compact else 0,
            2,
            alignment=Qt.AlignmentFlag.AlignBottom,
        )
        self.grid.setColumnStretch(0, 1)
        self.setFixedHeight(BREADCRUMB_WRAPPED_HEIGHT if compact else BREADCRUMB_HEIGHT)

    def resizeEvent(self, event: QResizeEvent):
        """Keep header controls usable without shrinking their typography."""
        super().resizeEvent(event)
        self._reflow()


class SettingsSubheading(QWidget):
    """Shared bold heading and icon for sections inside an entry."""

    def __init__(self, title: str, icon: str):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        marker = QLabel()
        marker.setPixmap(settings_icon(icon).pixmap(24, 24))
        marker.setFixedSize(24, 24)
        row.addWidget(marker)
        row.addWidget(settings_label(title, "dediSection"), 1)


class RouteSettingsRow(QWidget):
    """One horizontal strip of existing editors with inset field separators."""

    def __init__(self, fields: list[QWidget]):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for index, field in enumerate(fields):
            if index:
                divider = QFrame()
                divider.setObjectName("CraftSettingsDivider")
                divider.setFixedWidth(1)
                row.addWidget(divider)
            row.addWidget(field, 1 if index == 0 else 0)
