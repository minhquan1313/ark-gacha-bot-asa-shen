"""Virtualized Logs browser with stable reading anchors and progressive search."""

import itertools
import time
from bisect import bisect_left
from collections import Counter
from collections.abc import Callable
from dataclasses import replace

import psutil
from PySide6.QtCore import QAbstractTableModel, QEasingCurve, QModelIndex, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from source.launcher.components.dashboard import line_icon
from source.launcher.components.widgets import CyberSwitch
from source.launcher.logs_theme import LEVEL_COLORS, LOGS_STYLE
from source.launcher.utils.log_records import LogFileStore, LogRecord, parse_record

ROOT_INDEX = QModelIndex()

FILTERS = ("ALL", "INFO", "DEBUG", "WARN", "ERROR", "CRITICAL", "RUNNING", "QUEUE")


def copy_label(text: str, role: str = ""):
    """Build a non-wrapping label with the scoped Logs typography."""
    widget = QLabel(text)
    widget.setProperty("role", role)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


class HoverAccent:
    """Shared reversible 150 ms hover emphasis for Logs chips and metric cards."""

    def init_hover(self):
        """Allocate one reusable transition instead of animations on every entry."""
        self.hover_progress = 0.0
        self.hover_animation = QVariantAnimation(self)
        self.hover_animation.setDuration(150)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hover_animation.valueChanged.connect(self._hover_frame)

    def _hover_frame(self, value: float):
        """Schedule painting of a subtle border and glass highlight."""
        self.hover_progress = value
        self.update()

    def enterEvent(self, event: object):
        """Brighten gently without changing widget geometry."""
        self.hover_animation.stop()
        self.hover_animation.setStartValue(self.hover_progress)
        self.hover_animation.setEndValue(1.0)
        self.hover_animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event: object):
        """Reverse immediately from the current emphasis."""
        self.hover_animation.stop()
        self.hover_animation.setStartValue(self.hover_progress)
        self.hover_animation.setEndValue(0.0)
        self.hover_animation.start()
        super().leaveEvent(event)

    def paintEvent(self, event: object):
        """Overlay restrained cyan illumination on the existing dark control."""
        super().paintEvent(event)
        if self.hover_progress:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(30, 190, 220, int(90 * self.hover_progress)), 1))
            painter.setBrush(QColor(20, 160, 210, int(12 * self.hover_progress)))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 5, 5)


class LogButton(HoverAccent, QPushButton):
    """A normal accessible push button with a subtle animated hover overlay."""

    def __init__(self, text: str):
        """Initialize the reusable transition once."""
        super().__init__(text)
        self.init_hover()


class LogRowDelegate(QStyledItemDelegate):
    """Draw lightweight horizontal separators without framing every cell."""

    def paint(self, painter: QPainter, option: object, index: QModelIndex):
        """Keep Qt selection/text behavior and add a one-pixel separator."""
        super().paint(painter, option, index)
        painter.save()
        painter.setPen(QColor("#0a2431"))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.restore()


def log_button(text: str, icon: str = ""):
    """Keep toolbar controls at the shared desktop control height."""
    button = LogButton(text)
    button.setFixedHeight(44)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon:
        button.setIcon(line_icon(icon))
    return button


class LogMetricCard(HoverAccent, QFrame):
    """Compact real-value card without decorative fake trends."""

    def __init__(self, title: str, icon: str, secondary: str, color: str = "#00d9ff"):
        """Keep icon, title, value, and provenance readable in one of six columns."""
        super().__init__()
        self.init_hover()
        self.setObjectName("LogMetricCard")
        self.setMinimumWidth(0)
        self.setFixedHeight(106)
        box = QVBoxLayout(self)
        box.setContentsMargins(12, 12, 10, 10)
        box.setSpacing(5)
        row = QHBoxLayout()
        row.setSpacing(7)
        symbol = QLabel()
        symbol.setPixmap(line_icon(icon, color).pixmap(23, 23))
        symbol.setFixedSize(23, 23)
        row.addWidget(symbol)
        heading = copy_label(title.upper(), "technical")
        heading.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(heading, 1)
        box.addLayout(row)
        self.value = copy_label("0", "metric")
        box.addWidget(self.value)
        self.secondary = copy_label(secondary, "technical")
        self.secondary.setStyleSheet(f"color:{color};font-size:10px;")
        box.addWidget(self.secondary)


class LogFilterBar(QWidget):
    """Fit filters into available width while retaining ALL and the active filter."""

    selected = Signal(str)

    def __init__(self):
        """Create stable chip instances and a keyboard-accessible overflow menu."""
        super().__init__()
        self.current = "ALL"
        self.setMinimumWidth(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(44)
        self.buttons = {}
        for name in FILTERS:
            button = log_button(name)
            button.setCheckable(True)
            button.setParent(self)
            button.clicked.connect(lambda checked=False, value=name: self.choose(value))
            self.buttons[name] = button
        self.more = log_button("\u2026")
        self.more.setParent(self)
        self.more.setAccessibleName("More log filters")
        self.menu = QMenu(self.more)
        self.menu.setObjectName("LogsFilterMenu")
        self.menu.setStyleSheet(LOGS_STYLE)
        self.more.setMenu(self.menu)
        self.choose("ALL", False)

    def choose(self, name: str, emit: bool = True):
        """Change filtering without losing the selected chip during resizing."""
        self.current = name
        for key, button in self.buttons.items():
            button.setChecked(key == name)
        self.arrange()
        if emit:
            self.selected.emit(name)

    def resizeEvent(self, event: object):
        """Recalculate overflow when the toolbar receives a new width."""
        self.arrange()

    def arrange(self):
        """Reserve overflow space before placing optional filter chips."""
        widths = {name: max(48, button.sizeHint().width()) for name, button in self.buttons.items()}
        all_fit = sum(widths.values()) + 7 * 8 <= self.width()
        chosen = {"ALL", self.current}
        available = self.width() - (0 if all_fit else 44 + 8)
        used = sum(widths[key] + 8 for key in chosen) - 8
        for name in FILTERS:
            if name not in chosen and (all_fit or used + 8 + widths[name] <= available):
                chosen.add(name)
                used += 8 + widths[name]
        x = 0
        self.menu.clear()
        for name, button in self.buttons.items():
            button.setVisible(name in chosen)
            if name in chosen:
                button.setGeometry(x, 0, widths[name], 44)
                x += widths[name] + 8
            else:
                action = self.menu.addAction(name)
                action.setCheckable(True)
                action.setChecked(name == self.current)
                action.triggered.connect(lambda checked=False, value=name: self.choose(value))
        self.more.setVisible(not all_fit)
        self.more.setGeometry(x, 0, 44, 44)


class LogTableModel(QAbstractTableModel):
    """Stable rows with incremental inserts instead of full-document replacement."""

    def __init__(self, parent: QWidget):
        """Maintain sorted records and indexed identities for viewport restoration."""
        super().__init__(parent)
        self.records = []
        self.positions = {}
        self.orders = []

    def rowCount(self, parent: QModelIndex = ROOT_INDEX):
        """Expose only root rows to the table."""
        return 0 if parent.isValid() else len(self.records)

    def columnCount(self, parent: QModelIndex = ROOT_INDEX):
        """Expose timestamp, level, source, and message columns."""
        return 4

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        """Show compact technical column labels."""
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return ("TIME", "LEVEL", "SOURCE", "MESSAGE")[section]

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Provide text, semantic color, and the complete unelided tooltip."""
        if not index.isValid():
            return None
        record = self.records[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return (record.timestamp, record.level, record.source, record.message.replace("\n", "  \u21b3  "))[index.column()]
        if role == Qt.ItemDataRole.ToolTipRole:
            return record.raw
        if role == Qt.ItemDataRole.ForegroundRole:
            return QColor("#a6c7da" if index.column() in (0, 2) else LEVEL_COLORS.get(record.level, "#bad8e9"))
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def replace(self, records: list[LogRecord]):
        """Reset only when the user changes the selected query or view."""
        self.beginResetModel()
        self.records = sorted(records, key=lambda r: r.order)
        self._index()
        self.endResetModel()

    def remove(self, identities: list[tuple]):
        """Remove records that no longer satisfy a filter after partial-line completion."""
        rows = sorted((self.positions[key] for key in identities if key in self.positions), reverse=True)
        for row in rows:
            self.beginRemoveRows(QModelIndex(), row, row)
            self.records.pop(row)
            self.endRemoveRows()
        if rows:
            self._index()

    def _index(self):
        """Rebuild lookup indexes once per batch, not once per painted cell."""
        self.positions = {record.identity: i for i, record in enumerate(self.records)}
        self.orders = [record.order for record in self.records]

    def merge(self, records: list[LogRecord]):
        """Insert contiguous incoming ranges without invalidating existing rows."""
        incoming = {r.identity: r for r in records}
        fresh = []
        reordered = False
        for identity, record in incoming.items():
            position = self.positions.get(identity)
            if position is None:
                fresh.append(record)
            elif self.records[position] != record:
                reordered |= self.records[position].order != record.order
                self.records[position] = record
                self.dataChanged.emit(self.index(position, 0), self.index(position, 3))
        if reordered:
            self.layoutAboutToBeChanged.emit()
            persistent = self.persistentIndexList()
            identities = [(self.records[index.row()].identity, index.column()) for index in persistent]
            self.records.sort(key=lambda r: r.order)
            self._index()
            self.changePersistentIndexList(persistent, [self.index(self.positions[key], column) for key, column in identities])
            self.layoutChanged.emit()
        fresh.sort(key=lambda r: r.order)
        groups = {}
        for record in fresh:
            position = bisect_left(self.orders, record.order)
            groups.setdefault(position, []).append(record)
        for position, batch in sorted(groups.items(), reverse=True):
            self.beginInsertRows(QModelIndex(), position, position + len(batch) - 1)
            self.records[position:position] = batch
            self.endInsertRows()
        self._index()


class LogStatusFooter(QFrame):
    """Integrated stream status, result provenance, and process-only telemetry."""

    def __init__(self):
        """Keep runtime values secondary to the event reader."""
        super().__init__()
        self.setObjectName("LogStatusFooter")
        self.setFixedHeight(42)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 4, 12, 4)
        self.state = copy_label("\u25cf LOG STREAMING", "technical")
        self.state.setStyleSheet("color:#27f5b0;")
        self.count = copy_label("0 loaded records", "technical")
        self.count.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.runtime = copy_label("", "technical")
        row.addWidget(self.state)
        row.addSpacing(12)
        row.addWidget(self.count, 1)
        row.addWidget(self.runtime)


class LogConsolePanel(QFrame):
    """The only scrolling surface on the desktop Logs page."""

    def __init__(self):
        """Create readable columns, animated switches, and an integrated footer."""
        super().__init__()
        self.setObjectName("LogConsolePanel")
        box = QVBoxLayout(self)
        box.setContentsMargins(6, 10, 6, 0)
        box.setSpacing(8)
        header = QHBoxLayout()
        header.setContentsMargins(10, 0, 10, 0)
        icon = QLabel()
        icon.setPixmap(line_icon("terminal").pixmap(30, 30))
        header.addWidget(icon)
        title = QVBoxLayout()
        title.setSpacing(2)
        title.addWidget(copy_label("LOG CONSOLE", "heading"))
        self.subtitle = copy_label("SYSTEM LOGS \u2022 REAL-TIME OUTPUT", "technical")
        title.addWidget(self.subtitle)
        header.addLayout(title, 1)
        self.switches = {}
        for name, checked in (("Auto-scroll", True), ("Errors only", False), ("Live stream", True), ("Compact mode", False)):
            switch = CyberSwitch(name)
            switch.setFixedSize(138 if name == "Compact mode" else 122, 36)
            switch.setChecked(checked)
            switch.setAccessibleName(name)
            self.switches[name] = switch
            header.addWidget(switch)
        box.addLayout(header)
        self.history = copy_label("", "technical")
        self.history.setFixedHeight(18)
        self.history.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        box.addWidget(self.history)
        self.table = QTableView()
        self.model = LogTableModel(self.table)
        self.table.setModel(self.model)
        self.table.setItemDelegate(LogRowDelegate(self.table))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.verticalHeader().setMinimumSectionSize(22)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for column, width in enumerate((105, 94, 200)):
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        box.addWidget(self.table, 1)
        self.footer = LogStatusFooter()
        box.addWidget(self.footer)


class LogsPage(QWidget):
    """Compose the browser while keeping file search independent of runtime control."""

    def __init__(self, path: str, on_clear: Callable, on_open: Callable, snapshots: Callable, parent: QWidget = None):
        """Wire stable widgets once; edits and incoming batches retain their identity."""
        super().__init__(parent)
        self.setObjectName("LogsPage")
        self.setStyleSheet(LOGS_STYLE)
        self.browsing = {}
        self.level_counts = Counter()
        self.search_matches = {}
        self.pending = {}
        self.sequence = itertools.count(1)
        self.query = ""
        self.searching = False
        self.restoring = False
        self.browse_anchor = None
        self.latest_file_time = "--:--:--"
        self.latest_arrival = 0.0
        self.started = time.monotonic()
        self.snapshots = snapshots
        self.last_snapshot = []
        self.store = LogFileStore(path, self)
        self.store.changed.connect(self._received)
        self.store.search_batch.connect(self._search_batch)
        self.store.status.connect(self._status)
        self.store.reset.connect(self._reset)
        self.store.initial.connect(lambda _: self._query_changed() if self.query else None)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 14)
        outer.setSpacing(16)
        header = QHBoxLayout()
        words = QVBoxLayout()
        words.setSpacing(2)
        words.addWidget(copy_label("SHEN GBOT - LOGS", "title"))
        words.addWidget(copy_label("REAL-TIME EVENT MONITORING & DIAGNOSTICS", "technical"))
        header.addLayout(words)
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background:#154b62;")
        header.addWidget(divider, 1)
        self.decoration = copy_label("// MONITOR  // ANALYZE  // STAY AHEAD", "technical")
        header.addWidget(self.decoration)
        outer.addLayout(header)
        metrics = QHBoxLayout()
        metrics.setSpacing(8)
        self.metrics = []
        for title, icon, detail, color in [
            ("Total Events", "btemplates", "Loaded records", "#00d9ff"),
            ("Warnings", "warning", "WARN entries", "#ffd166"),
            ("Errors", "error", "ERROR + CRITICAL", "#ff4d6d"),
            ("Active Tasks", "settings", "Running + ready", "#00d9ff"),
            ("Queue", "queue", "Waiting tasks", "#9a85ff"),
            ("Last Update", "clock", "No events yet", "#27f5b0"),
        ]:
            card = LogMetricCard(title, icon, detail, color)
            metrics.addWidget(card, 1)
            self.metrics.append(card)
        self.metrics[-1].value.setText("--:--:--")
        outer.addLayout(metrics)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.filters = LogFilterBar()
        self.filters.selected.connect(self._query_changed)
        toolbar.addWidget(self.filters, 1)
        self.search = QLineEdit()
        self.search.setFixedHeight(44)
        self.search.setMinimumWidth(175)
        self.search.setMaximumWidth(320)
        self.search.setPlaceholderText("Search logs... (Ctrl+F)")
        self.search.addAction(line_icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search entire log file")
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(200)
        self.debounce.timeout.connect(self._query_changed)
        self.search.textChanged.connect(self._search_edited)
        toolbar.addWidget(self.search, 1)
        self.clear_button = log_button("CLEAR LOGS", "trash")
        self.clear_button.setProperty("destructive", True)
        self.clear_button.clicked.connect(on_clear)
        toolbar.addWidget(self.clear_button)
        self.open_button = log_button("OPEN LOGS", "logs")
        self.open_button.clicked.connect(on_open)
        toolbar.addWidget(self.open_button)
        outer.addLayout(toolbar)
        self.console = LogConsolePanel()
        self.table, self.model = self.console.table, self.console.model
        self.switches = self.console.switches
        outer.addWidget(self.console, 1)
        self.switches["Auto-scroll"].toggled.connect(self._follow)
        self.switches["Errors only"].toggled.connect(self._query_changed)
        self.switches["Live stream"].toggled.connect(self._live)
        self.switches["Compact mode"].toggled.connect(self._compact)
        self.table.verticalScrollBar().valueChanged.connect(self._scroll_changed)
        self.table.activated.connect(self._details)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search.setFocus)
        copy_shortcut = QShortcut(QKeySequence.Copy, self.table, activated=self._copy)
        copy_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.stats_timer = QTimer(self)
        self.stats_timer.setInterval(1000)
        self.stats_timer.timeout.connect(self.tick)
        self.stats_timer.start()
        self.process = psutil.Process()
        self.process.cpu_percent(None)
        self.tick()

    def _anchor(self):
        """Remember the first visible record and its exact vertical pixel offset."""
        row = self.table.rowAt(0)
        if row < 0 or row >= len(self.model.records):
            return None
        index = self.model.index(row, 0)
        return self.model.records[row].identity, self.table.visualRect(index).top()

    def _restore(self, anchor: tuple):
        """Compensate for inserted rows without moving the reader's chosen line."""
        if not anchor:
            return
        identity, offset = anchor
        row = self.model.positions.get(identity)
        if row is not None:
            self.table.scrollTo(self.model.index(row, 0), QAbstractItemView.ScrollHint.PositionAtTop)
            self.table.verticalScrollBar().setValue(self.table.verticalScrollBar().value() - offset)

    def _merge(self, records: list[LogRecord], follow: bool = False, discard: tuple = ()):
        """Protect the viewport while Qt incrementally inserts new result rows."""
        anchor = self._anchor()
        self.restoring = True
        self.model.remove(discard)
        self.model.merge(records)
        self.table.doItemsLayout()
        if follow:
            self.table.scrollToBottom()
        else:
            self._restore(anchor)
        self.restoring = False

    def _accepted(self, record: LogRecord):
        """Apply the current literal query and visible severity controls."""
        return record.matches(self.query, self.filters.current, self.switches["Errors only"].isChecked())

    def _received(self, records: list[LogRecord], kind: str):
        """Retain browsing history while excluding search-only rows from counters."""
        if not self.switches["Live stream"].isChecked() and kind == "append":
            self.pending.update((r.identity, r) for r in records)
            return
        if kind == "initial":
            # Startup messages arrive before the asynchronous tail knows the file boundary.
            records = list(records) + [replace(record, order=(self.store.end, record.identity[1])) for record in self.browsing.values() if record.identity[0] == "local"]
        for record in records:
            previous = self.browsing.get(record.identity)
            if previous is not None:
                self.level_counts[previous.level] -= 1
            self.level_counts[record.level] += 1
            self.browsing[record.identity] = record
        if kind == "initial" and records:
            file_records = [record for record in records if record.identity[0] == "file"]
            self.latest_file_time = file_records[-1].timestamp if file_records else "--:--:--"
            self.metrics[5].value.setText(self.latest_file_time)
            self.metrics[5].secondary.setText("Latest file event")
        if kind == "append" and records:
            self.latest_arrival = time.time()
        if self.filters.current not in ("RUNNING", "QUEUE"):
            accepted = [r for r in records if self._accepted(r)]
            self._merge(accepted, kind in ("initial", "append") and not self.query and self.switches["Auto-scroll"].isChecked(), tuple(r.identity for r in records if not self._accepted(r)))
        self._metrics()

    def append_local(self, text: str):
        """Show genuine in-memory launcher messages independently of file records."""
        sequence = next(self.sequence)
        record = parse_record(text, ("local", sequence), (self.store.end, sequence), time.strftime("%H:%M:%S"))
        self._received([record], "append")

    def _search_edited(self):
        """Cancel obsolete work immediately; debounce only the replacement scan."""
        self.store.cancel_search()
        self.debounce.start()

    def _query_changed(self, ignored: object = None):
        """Show loaded matches immediately, then extend them with file-search batches."""
        was_query = self.query
        if not was_query and self.search.text().strip():
            self.browse_anchor = self._anchor()
        self.query = self.search.text().strip()
        self.store.cancel_search()
        self.search_matches.clear()
        self.searching = bool(self.query and self.filters.current not in ("RUNNING", "QUEUE"))
        anchor = self._anchor()
        self.restoring = True
        self.model.replace([r for r in self.browsing.values() if self._accepted(r)] if self.filters.current not in ("RUNNING", "QUEUE") else [])
        self.table.doItemsLayout()
        self._restore(self.browse_anchor if was_query and not self.query else anchor)
        self.restoring = False
        if self.filters.current in ("RUNNING", "QUEUE"):
            self.last_snapshot = []
            self._snapshot()
        elif self.query:
            self.store.search(self.query, self.filters.current, self.switches["Errors only"].isChecked())
        self._status("Searching file..." if self.searching else "")
        self._metrics()

    def _search_batch(self, records: list[LogRecord], done: bool):
        """Add progressive matches without following or resetting existing rows."""
        self.search_matches.update((r.identity, r) for r in records)
        self._merge(records)
        self.searching = not done
        self._status("Search complete" if done else "Searching file...")
        self._metrics()

    def _reset(self):
        """Discard old generation data and anchors after Clear or rotation."""
        self.browsing.clear()
        self.level_counts.clear()
        self.pending.clear()
        self.search_matches.clear()
        self.restoring = True
        self.model.replace([])
        self.restoring = False
        self.browse_anchor = None
        self.latest_arrival = 0
        self.latest_file_time = "--:--:--"
        self._metrics()

    def _status(self, text: str):
        """Keep failures and progress lightweight and visible above the table."""
        if not text and self.searching:
            text = "Searching file..."
        self.console.history.setText(text)
        self.console.history.setToolTip(text)
        if text.startswith(("Search failed", "Log file unavailable")):
            self.searching = False
        self._metrics()

    def _scroll_changed(self, value: int):
        """Scrolling away suspends following and reaching the top requests history."""
        if self.restoring:
            return
        scrollbar = self.table.verticalScrollBar()
        if value < scrollbar.maximum() - 2:
            self.switches["Auto-scroll"].setChecked(False)
        if value <= 28 and not self.query and self.filters.current not in ("RUNNING", "QUEUE"):
            self.store.older()

    def _follow(self, checked: bool):
        """Resume following explicitly, without coupling it to historical inserts."""
        if checked:
            self.restoring = True
            self.table.scrollToBottom()
            self.restoring = False

    def _live(self, checked: bool):
        """Resume accumulated arrivals without disturbing readers away from the end."""
        if checked:
            records = list(self.pending.values())
            self.pending.clear()
            self._received(records, "append")
            self._snapshot()
        self._metrics()

    def _compact(self, checked: bool):
        """Change density while anchoring the same visible record."""
        anchor = self._anchor()
        self.restoring = True
        self.table.verticalHeader().setDefaultSectionSize(22 if checked else 28)
        self.table.doItemsLayout()
        self._restore(anchor)
        self.restoring = False

    def _snapshot(self):
        """Preserve existing RUNNING history and QUEUE countdown views."""
        if not self.switches["Live stream"].isChecked() or self.filters.current not in ("RUNNING", "QUEUE"):
            return
        lines = self.snapshots(self.filters.current)
        if lines == self.last_snapshot:
            return
        self.last_snapshot = list(lines)
        records = [parse_record(line, ("snapshot", i), (i, 0)) for i, line in enumerate(lines)]
        anchor = self._anchor()
        self.restoring = True
        self.model.replace([r for r in records if self._accepted(r)])
        self._restore(anchor)
        self.restoring = False

    def _metrics(self):
        """Count browsing records, never inflate metrics with search-only matches."""
        if not hasattr(self, "metrics"):
            return
        counts = self.level_counts
        for card, value in zip(self.metrics[:3], (len(self.browsing), counts["WARN"], counts["ERROR"] + counts["CRITICAL"]), strict=True):
            card.value.setText(f"{value:,}")
        stream = self.switches["Live stream"].isChecked()
        notice = self.console.history.text()
        if not stream:
            state, color = "DISPLAY PAUSED", "#ffd166"
        elif notice.startswith("Log file unavailable"):
            state, color = "LOG UNAVAILABLE", "#ffd166"
        elif notice.startswith("Loading older"):
            state, color = "LOADING HISTORY", "#00d9ff"
        elif self.searching:
            state, color = "SEARCHING", "#00d9ff"
        else:
            state, color = "LOG STREAMING", "#27f5b0"
        self.console.footer.state.setText("\u25cf " + state)
        self.console.footer.state.setStyleSheet(f"color:{color};")
        count = len(self.model.records)
        if self.filters.current in ("RUNNING", "QUEUE"):
            summary = f"{count:,} scheduler " + ("matches" if self.query else "entries")
        elif self.query:
            summary = f"{count:,} matches" + (" | searching file..." if self.searching else "")
        else:
            summary = f"Showing {count:,} of {len(self.browsing):,} loaded events"
        self.console.footer.count.setText(summary)

    def tick(self):
        """Sample lightweight process telemetry once a second and update snapshots."""
        self._snapshot()
        snapshot = self.snapshots("METRICS")
        if self.switches["Live stream"].isChecked():
            self.metrics[3].value.setText(str(len(snapshot.get("running", [])) + len(snapshot.get("active", []))))
            self.metrics[4].value.setText(str(len(snapshot.get("waiting", []))))
        if self.latest_arrival:
            self.metrics[5].value.setText(time.strftime("%H:%M:%S", time.localtime(self.latest_arrival)))
            self.metrics[5].secondary.setText(f"{int(time.time() - self.latest_arrival)}s ago")
        else:
            self.metrics[5].value.setText(self.latest_file_time)
            self.metrics[5].secondary.setText("Latest file event" if self.latest_file_time != "--:--:--" else "No events yet")
        elapsed = int(time.monotonic() - self.started)
        uptime = f"{elapsed // 3600:02}:{elapsed // 60 % 60:02}:{elapsed % 60:02}"
        try:
            memory = f"{self.process.memory_info().rss / 1024**2:.0f} MB"
            cpu = f"{self.process.cpu_percent(None):.1f}%"
        except psutil.Error:
            memory = cpu = "\u2014"
        self.console.footer.runtime.setText(f"Uptime: {uptime}   |   Memory: {memory}   |   CPU: {cpu}")
        self._metrics()

    def _copy(self):
        """Copy complete selected records in their visible order."""
        rows = sorted(index.row() for index in self.table.selectionModel().selectedRows())
        QApplication.clipboard().setText("\n".join(self.model.records[row].raw for row in rows))

    def _details(self, index: QModelIndex):
        """Expose complete selectable messages in an application-styled reader."""
        if not index.isValid():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Log record")
        dialog.setStyleSheet("QDialog,QTextEdit {background:#03131e;color:#cde7f4;} QPushButton {background:#082c3e;color:#00d9ff;border:1px solid #17647d;padding:10px;}")
        dialog.resize(760, 420)
        box = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setFont(QFont("Consolas", 10))
        text.setPlainText(self.model.records[index.row()].raw)
        box.addWidget(text)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        box.addWidget(close)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.open()

    def stop(self):
        """Disconnect background work before the application closes."""
        self.store.stop()
        self.stats_timer.stop()
        self.debounce.stop()
