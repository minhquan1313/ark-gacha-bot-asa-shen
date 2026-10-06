"""Shared Dedi and Craft presentation; persistence stays in the page handlers."""

from collections.abc import Callable

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPaintEvent, QResizeEvent, QTransform
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from source.launcher.components.dashboard import line_icon
from source.launcher.components.settings_actions import (
    SettingsRowActions,
    SettingsRowIndex,
)
from source.launcher.components.settings_sections import (
    SettingsActionButton,
    SettingsSubheading,
    settings_icon,
    settings_label,
)
from source.launcher.dashboard_theme import PALETTE
from source.launcher.pages.common import _deposit_route_child_count
from source.launcher.settings_theme import CONTROL_HEIGHT, ENTRY_ROW_PADDING_Y


class ElidedRouteTitle(QLabel):
    """Paint one line while retaining the full title for tooltips and accessibility."""

    def __init__(self):
        super().__init__()
        self.setProperty("settingsRole", "label")
        self.setMinimumWidth(0)
        self.setFixedHeight(CONTROL_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event: QPaintEvent):
        """Elide only the visible text; the underlying model title stays intact."""
        painter = QPainter(self)
        painter.setPen(self.palette().windowText().color())
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignVCenter,
            self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width()),
        )


class RouteMetadataChip(QWidget):
    """A fixed-height HUD segment with a caption and changing model value."""

    def __init__(self, caption: str, icon: str = ""):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        if icon:
            marker = QLabel()
            marker.setPixmap(settings_icon(icon).pixmap(24, 24))
            marker.setFixedSize(24, 24)
            row.addWidget(marker)
        text = QVBoxLayout()
        text.setSpacing(0)
        self.caption = settings_label(caption)
        self.value = settings_label("", "label")
        for label in (self.caption, self.value):
            label.setWordWrap(False)
        text.addWidget(self.caption)
        text.addWidget(self.value)
        row.addLayout(text)

    def set_value(self, value: str):
        """Size from styled text rather than allowing segment labels to wrap."""
        self.value.setText(value)
        self.updateGeometry()

    def text(self):
        """Expose a readable summary for accessibility checks."""
        return f"{self.caption.text()} {self.value.text()}"


class RoutePointSummary(RouteMetadataChip):
    """Use the same pin, numeric value, and points caption for every route type."""

    def __init__(self):
        super().__init__("points", "cube")
        text = self.layout().itemAt(1).layout()
        text.removeWidget(self.value)
        text.insertWidget(0, self.value)

    def text(self):
        """Return the full point summary without depending on its visual stacking."""
        return f"{self.value.text()} points"


class RouteSummaryMetadata(QFrame):
    """Inline summary information with inset dividers and no enclosing border."""

    def __init__(self):
        super().__init__()
        self.setObjectName("DediSummaryMetadata")
        self.setFixedHeight(CONTROL_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(12, 4, 12, 4)
        self.row.setSpacing(12)
        self.interval = RouteMetadataChip("Check dedi", "server")
        self.points = RoutePointSummary()
        self.divider = QWidget()
        self.divider.setFixedWidth(1)
        self.row.addWidget(self.interval)
        self.row.addWidget(self.divider)
        self.row.addWidget(self.points)
        for label in self.findChildren(QLabel):
            label.installEventFilter(self)

    def sync_width(self):
        """Measure final styled fonts, including changing multi-digit values."""
        for label in (
            self.interval.caption,
            self.interval.value,
            self.points.caption,
            self.points.value,
        ):
            label.ensurePolished()
            label.setMinimumWidth(label.fontMetrics().horizontalAdvance(label.text()) + 2)
        self.row.invalidate()
        self.setMinimumWidth(self.row.minimumSize().width())
        self.updateGeometry()

    def eventFilter(self, watched: QWidget, event: QEvent):
        """Re-measure after inheritance of the scoped Settings fonts."""
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            QTimer.singleShot(0, self.sync_width)
        return super().eventFilter(watched, event)

    def showEvent(self, event):
        """Use actual page fonts before the summary is displayed."""
        super().showEvent(event)
        self.sync_width()

    def paintEvent(self, event: QPaintEvent):
        """Keep the divider inset from the single outer frame."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QColor(PALETTE["border"]))
        painter.drawLine(0, 8, 0, self.height() - 9)
        x = self.divider.geometry().center().x()
        painter.drawLine(x, 8, x, self.height() - 9)


class DediFieldsStrip(QWidget):
    """Keep coordinates and crouch inseparable; wrap optional Items as one group."""

    def __init__(self, fields: list[QWidget]):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(8)
        self.grid.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.core = QWidget()
        row = QHBoxLayout(self.core)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for field in fields[:3]:
            row.addWidget(field, 1)
        self.grid.addWidget(self.core, 0, 0)
        self.grid.setColumnStretch(0, 3)
        self.extra = fields[3] if len(fields) > 3 else None
        if self.extra is not None:
            self.grid.addWidget(self.extra, 0, 1)
            self.grid.setColumnStretch(1, 1)
        self._wrapped = False

    def minimumSizeHint(self):
        """Let the parent offer less width before reflowing optional fields."""
        return QSize(self.core.minimumSizeHint().width(), self.grid.minimumSize().height())

    def resizeEvent(self, event: QResizeEvent):
        """Move Items as a whole while keeping the primary point fields intact."""
        super().resizeEvent(event)
        if self.extra is None:
            return
        wrapped = self.width() < self.core.minimumSizeHint().width() + self.extra.minimumSizeHint().width() + 8
        if wrapped != self._wrapped:
            self._wrapped = wrapped
            self.grid.removeWidget(self.extra)
            self.grid.addWidget(self.extra, 1, 0) if wrapped else self.grid.addWidget(self.extra, 0, 1)
            self.grid.setColumnStretch(1, 0 if wrapped else 1)
            self.updateGeometry()


class DediPointRow(QFrame):
    """Keep coordinates and crouch together, with pinned decoration and deletion."""

    def __init__(self, index: int, fields: list[QWidget], delete: QWidget):
        super().__init__()
        self.setObjectName("DediPointRow")
        self.separator = True
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(8, ENTRY_ROW_PADDING_Y, 8, ENTRY_ROW_PADDING_Y)
        self.grid.setSpacing(8)
        self.grid.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.index = SettingsRowIndex(index)
        self.grid.addWidget(self.index, 0, 0)
        self.fields = DediFieldsStrip(fields)
        self.grid.addWidget(self.fields, 0, 1)
        self.grid.addWidget(delete, 0, 2)
        self.grid.setColumnStretch(1, 1)
        self._wrapped = False

    def minimumSizeHint(self):
        """Allow the row to reflow before propagating a page-wide minimum width."""
        return QSize(0, self.grid.minimumSize().height())

    def paintEvent(self, event: QPaintEvent):
        """Draw a separator without adding stylesheet border space to the row."""
        super().paintEvent(event)
        if not self.separator:
            return
        painter = QPainter(self)
        painter.setPen(QColor(PALETTE["border"]))
        painter.drawLine(8, self.height() - 1, self.width() - 8, self.height() - 1)

    def resizeEvent(self, event: QResizeEvent):
        """Wrap the complete field area only when its actual minimum cannot fit."""
        super().resizeEvent(event)
        minimum = self.fields.minimumSizeHint().width()
        wrapped = self.width() < minimum + 34 + CONTROL_HEIGHT + 32
        if wrapped != self._wrapped:
            self._wrapped = wrapped
            self.grid.removeWidget(self.fields)
            self.grid.addWidget(self.fields, 1, 0, 1, 3) if wrapped else self.grid.addWidget(self.fields, 0, 1)
            self.updateGeometry()


class GrinderCard(QFrame):
    """A machine-position panel distinct from numbered storage points."""

    def __init__(self, available: QWidget, fields: list[QWidget]):
        super().__init__()
        self.setObjectName("DediGrinderCard")
        box = QVBoxLayout(self)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(8)
        box.addWidget(SettingsSubheading("Grinder", "settings"))
        box.addWidget(settings_label("Main grinder position used by this route."))
        self.controls = QGridLayout()
        self.controls.setHorizontalSpacing(12)
        self.controls.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.available = available
        self.fields = QWidget()
        row = QHBoxLayout(self.fields)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for field in fields:
            row.addWidget(field, 1)
        self.controls.addWidget(available, 0, 0)
        self.controls.addWidget(self.fields, 0, 1)
        self.controls.setColumnStretch(1, 1)
        box.addLayout(self.controls)
        self._wrapped = False

    def minimumSizeHint(self):
        """Permit the available toggle and fields to reflow at smaller widths."""
        return QSize(0, self.layout().minimumSize().height())

    def resizeEvent(self, event: QResizeEvent):
        """Reflow the coordinates together below availability on small panels."""
        super().resizeEvent(event)
        wrapped = self.width() < self.fields.layout().minimumSize().width() + self.available.sizeHint().width() + 36
        if wrapped != self._wrapped:
            self._wrapped = wrapped
            self.controls.removeWidget(self.fields)
            self.controls.addWidget(self.fields, 1, 0, 1, 2) if wrapped else self.controls.addWidget(self.fields, 0, 1)


class DediRouteEditor(QFrame):
    """A responsive route summary with a flat, collapsible editor body."""

    def __init__(
        self,
        route: dict,
        kind: str,
        index: int,
        expanded: bool,
        on_expand: Callable,
        on_helper: Callable,
        on_remove: Callable,
    ):
        super().__init__()
        self.route = route
        self.kind = kind
        self.route_index = index
        self.setObjectName("DediRouteEditor")
        self.setMinimumWidth(0)
        box = QVBoxLayout(self)
        box.setContentsMargins(12, 12, 12, 12)
        box.setSpacing(16)
        self.summary = QHBoxLayout()
        self.summary.setContentsMargins(0, 0, 0, 0)
        self.summary.setSpacing(8)
        self.toggle = SettingsActionButton("", "chevron_down")
        self.toggle.setFixedWidth(CONTROL_HEIGHT)
        self.toggle.setCheckable(True)
        self._collapsed_icon = settings_icon("chevron_down")
        self._expanded_icon = QIcon(self._collapsed_icon.pixmap(96, 96).transformed(QTransform().rotate(180)))
        self.toggle.setChecked(expanded)
        self.toggle.setIcon(self._expanded_icon if expanded else self._collapsed_icon)
        self.toggle.setToolTip("Expand or collapse route")
        self.title = ElidedRouteTitle()
        self.metadata = RouteSummaryMetadata()
        self.interval = self.metadata.interval
        self.points = self.metadata.points
        helper = SettingsActionButton("", "target")
        helper.setFixedWidth(CONTROL_HEIGHT)
        helper.setToolTip("Open position helper")
        helper.clicked.connect(on_helper)
        remove = SettingsActionButton("", "trash", "danger")
        remove.setIcon(line_icon("trash", PALETTE["danger"]))
        remove.setFixedWidth(CONTROL_HEIGHT)
        remove.setToolTip("Remove route")
        remove.clicked.connect(on_remove)
        self.actions = SettingsRowActions([("Open position helper", helper), ("Delete", remove)])
        self.summary.addWidget(self.toggle)
        self.summary.addWidget(self.title, 1)
        self.summary.addWidget(self.actions)
        self.summary.addWidget(self.metadata)
        box.addLayout(self.summary)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(16)
        self.body.setVisible(expanded)
        box.addWidget(self.body)

        def toggle(checked: bool):
            """Retain expansion independently of the route's editable title."""
            self.body.setVisible(checked)
            self.toggle.setIcon(self._expanded_icon if checked else self._collapsed_icon)
            on_expand(checked)

        self.toggle.toggled.connect(toggle)
        self.refresh_summary()
        self._reflow()

    def refresh_summary(self):
        """Reflect committed model values after validation, including rollback."""
        count = _deposit_route_child_count(self.route)
        if self.kind == "craft":
            count += len(self.route["crafters"])
        teleport = self.route.get("teleport", "") or "Unnamed route"
        suffix = len(self.route["dedi"]["items"]) if self.kind == "craft" else count
        self.title.setText(f"{teleport} - {suffix}")
        self.title.setToolTip(self.title.text())
        self.toggle.setAccessibleName(f"Expand route {teleport}")
        self.interval.set_value(str(self.route.get("check_on_every_dedi", 6)))
        self.points.set_value(str(count))
        self.metadata.sync_width()

    def _reflow(self):
        """Keep every summary segment on one line, reducing title space first."""
        fixed = 24 + 3 * self.summary.spacing() + CONTROL_HEIGHT
        fixed += self.metadata.minimumWidth()
        self.actions.set_compact(self.width() < fixed + self.actions.inline_width + 80)

    def resizeEvent(self, event: QResizeEvent):
        """Reflow existing widgets without interrupting edits."""
        super().resizeEvent(event)
        self._reflow()
