import re
import time

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from source.launcher.components.widgets import (
    AnimatedButton,
    LoadingSpinner,
    RoundedShellFrame,
    sync_rounded_window_mask,
)
from source.launcher.config.constants import (
    APP_TITLE,
    COLORS,
    HELPER_HEIGHT,
    RUNNER_WIDTH,
    UI_FONTS,
    UI_METRICS,
)

RUNNER_OVERLAY_UPCOMING_LIMIT = 3
RUNNER_OVERLAY_LOG_LIMIT = 3
RUNNER_LOG_PREFIX = re.compile(
    r"^(?:\[[A-Z]+\]\s*)?(?P<timestamp>\d{2}:\d{2}:\d{2})\s+-\s+"
)


def format_runner_overlay(
    snapshot: dict,
    now: float | None = None,
    limit: int = RUNNER_OVERLAY_UPCOMING_LIMIT,
):
    now = time.time() if now is None else now
    running = snapshot.get("running", [])
    if running:
        # current = f"Running {running[0].get('name', 'unknown')}"
        current = f"{running[0].get('name', 'unknown')}"
    else:
        current = "Waiting for running task..."

    queued = snapshot.get("active", []) + snapshot.get("waiting", [])
    queued.sort(key=lambda task: float(task.get("execution_time", now)))
    upcoming = [_format_upcoming_task(task, now) for task in queued[:limit]]
    if not upcoming:
        upcoming = ["No upcoming tasks."]
    return current, upcoming


def _format_upcoming_task(task: dict, now: float):
    remaining = max(0, int(float(task.get("execution_time", now)) - now))
    if task.get("state") == "READY" or remaining == 0:
        # return f"READY {task.get('name', 'unknown')}"
        return f"{task.get('name', 'unknown')}"
    hours, remainder = divmod(remaining, 3600)
    minutes, seconds = divmod(remainder, 60)
    timer = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{timer} {task.get('name', 'unknown')}"


class _ElidedLabel(QLabel):
    """Render a single line with three-dot truncation when space is limited."""

    def __init__(self, text: str = ""):
        super().__init__("")
        self._full_text = ""
        self.setWordWrap(False)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setText(text)

    def setText(self, text: str):
        self._full_text = str(text)
        self._sync_visible_text()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._sync_visible_text()

    def _sync_visible_text(self):
        """Update the rendered text for the label's current content width."""
        available_width = self.contentsRect().width()
        visible_text = self._elide_text(self._full_text, available_width)
        if super().text() != visible_text:
            super().setText(visible_text)

    def _elide_text(self, text: str, max_width: int):
        """Return text shortened with ASCII dots to fit the requested width."""
        metrics = self.fontMetrics()
        if max_width <= 0 or metrics.horizontalAdvance(text) <= max_width:
            return text
        suffix = "..."
        suffix_width = metrics.horizontalAdvance(suffix)
        if suffix_width > max_width:
            return ""
        low = 0
        high = len(text)
        prefix_width = max_width - suffix_width
        while low < high:
            middle = (low + high + 1) // 2
            if metrics.horizontalAdvance(text[:middle]) <= prefix_width:
                low = middle
            else:
                high = middle - 1
        return f"{text[:low].rstrip()}{suffix}"


def format_runner_logs(lines: list[str], limit: int = RUNNER_OVERLAY_LOG_LIMIT):
    """Return the newest timestamped launcher log messages for the overlay."""
    if limit <= 0:
        return []
    formatted_lines = []
    for line in reversed(lines):
        formatted = _format_runner_log_line(line)
        if formatted is None:
            continue
        formatted_lines.append(formatted)
        if len(formatted_lines) == limit:
            break

    return formatted_lines


def _format_runner_log_line(line: str):
    """Remove launcher log metadata while preserving event time and message."""
    match = RUNNER_LOG_PREFIX.match(line.strip())
    if match is None:
        return None
    fields = line.strip()[match.end() :].split(" - ", 2)
    if len(fields) != 3:
        return None
    message = fields[2].strip()
    if not message:
        return None
    return f"{match.group('timestamp')[-2:]} {message}"


class RunnerOverlay(QWidget):
    def __init__(self, owner: object):
        super().__init__(None)
        self.owner = owner
        self.drag_position = None
        self.upcoming_labels = []
        self.log_labels = []
        self.loading_active = False

        self.setObjectName("RunnerOverlayWindow")
        self.setWindowTitle(f"{APP_TITLE} Runner")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowOpacity(1.0)
        self.setFixedWidth(RUNNER_WIDTH)
        self.setMinimumHeight(HELPER_HEIGHT)
        self._build_ui()
        self._resize_to_content_height()
        self._position_set()

    def _build_ui(self):
        self.setStyleSheet(f"""
            QWidget#RunnerOverlayWindow {{
                background: #050A10;
                color: {COLORS["text"]};
                border-radius: {UI_METRICS["radius_lg"]}px;
            }}
            QFrame#RunnerOverlayShell {{
                background: transparent;
                border: none;
                border-radius: {UI_METRICS["radius_lg"]}px;
            }}
            QLabel#RunnerOverlayTitle {{
                color: {COLORS["cyan"]};
                font-size: 15px;
                font-weight: 900;
                letter-spacing: 1px;
            }}
            QLabel#RunnerOverlayClock {{
                color: {COLORS["muted"]};
                font-family: {UI_FONTS["mono"]};
                font-size: 11px;
            }}
            QLabel#RunnerOverlayCurrent {{
                color: {COLORS["text"]};
                font-size: 13px;
                font-weight: 900;
            }}
            QLabel#RunnerOverlayHint {{
                color: {COLORS["muted"]};
                font-family: {UI_FONTS["mono"]};
                font-size: 11px;
            }}
            QLabel#RunnerOverlayTask {{
                color: {COLORS["muted"]};
                font-family: {UI_FONTS["mono"]};
                font-size: 11px;
            }}
            QFrame#RunnerOverlayDivider {{
                background: rgba(0, 216, 255, 70);
                border: none;
            }}
            QLabel#RunnerOverlayLog {{
                color: {COLORS["dim"]};
                font-family: {UI_FONTS["mono"]};
                font-size: 11px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        shell = RoundedShellFrame()
        shell.setObjectName("RunnerOverlayShell")
        root.addWidget(shell)

        layout = QVBoxLayout(shell)
        self.content_layout = layout
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(2)

        self.header_frame = QFrame()
        self.header_frame.installEventFilter(self)
        header = QHBoxLayout(self.header_frame)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        self.header_title = QLabel(APP_TITLE)
        self.header_title.setObjectName("RunnerOverlayTitle")
        self.header_title.installEventFilter(self)
        self.clock_label = QLabel(time.strftime("%H:%M:%S"))
        self.clock_label.setObjectName("RunnerOverlayClock")
        self.clock_label.installEventFilter(self)
        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(0)
        title_stack.addWidget(self.header_title)
        title_stack.addWidget(self.clock_label)
        stop = AnimatedButton("STOP", "danger")
        stop.setObjectName("RunnerOverlayStop")
        # stop.setFixedHeight(28)
        stop.setMinimumWidth(72)
        stop.clicked.connect(self.stop_program)
        self.stop_button = stop
        header.addLayout(title_stack)
        header.addStretch()
        header.addWidget(stop)
        layout.addWidget(self.header_frame)

        self.current_label = _ElidedLabel("Waiting for running task...")
        self.current_label.setObjectName("RunnerOverlayCurrent")
        self.loading_spinner = LoadingSpinner()
        loading_row = QHBoxLayout()
        loading_row.setContentsMargins(0, 0, 0, 0)
        loading_row.setSpacing(8)
        loading_row.addWidget(self.loading_spinner)
        loading_row.addWidget(self.current_label, 1)
        layout.addLayout(loading_row)

        for _ in range(RUNNER_OVERLAY_UPCOMING_LIMIT):
            label = _ElidedLabel()
            label.setObjectName("RunnerOverlayTask")
            self.upcoming_labels.append(label)
            layout.addWidget(label)

        self.log_divider = QFrame()
        self.log_divider.setObjectName("RunnerOverlayDivider")
        self.log_divider.setFixedHeight(1)
        self.log_divider.hide()
        layout.addWidget(self.log_divider)

        for _ in range(RUNNER_OVERLAY_LOG_LIMIT):
            label = _ElidedLabel()
            label.setObjectName("RunnerOverlayLog")
            label.hide()
            self.log_labels.append(label)
            layout.addWidget(label)

    def refresh(self, snapshot: dict, log_lines: list[str] | None = None):
        self.loading_active = False
        self.loading_spinner.stop()
        self.clock_label.setText(time.strftime("%H:%M:%S"))
        current, upcoming = format_runner_overlay(snapshot)
        self.current_label.setText(current)
        for index, label in enumerate(self.upcoming_labels):
            if index < len(upcoming):
                label.setText(upcoming[index])
                label.show()
            else:
                label.hide()
        logs = format_runner_logs(log_lines or [])
        self.log_divider.setVisible(bool(logs))
        for index, label in enumerate(self.log_labels):
            if index < len(logs):
                label.setText(logs[index])
                label.show()
            else:
                label.hide()
        self._resize_to_content_height()
        self._position_set()

    def refresh_loading(self, log_lines: list[str] | None = None):
        if self.loading_active:
            return
        self.loading_active = True
        self.clock_label.setText(time.strftime("%H:%M:%S"))
        self.current_label.setText("Loading runner...")
        self.loading_spinner.start()
        for label in self.upcoming_labels:
            label.hide()
        self.log_divider.hide()
        for label in self.log_labels:
            label.hide()
        self._resize_to_content_height()
        self._position_set()

    def _resize_to_content_height(self):
        layout = self.layout()
        if layout is None:
            return
        self.content_layout.invalidate()
        self.content_layout.activate()
        layout.invalidate()
        layout.activate()
        height = layout.sizeHint().height()
        if layout.hasHeightForWidth():
            layout_height = layout.heightForWidth(self.width())
            if layout_height >= 0:
                height = max(height, layout_height)
        target_height = max(HELPER_HEIGHT, height)
        if self.height() != target_height:
            self.setFixedHeight(target_height)
        sync_rounded_window_mask(self, UI_METRICS["window_radius"])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        sync_rounded_window_mask(self, UI_METRICS["window_radius"])

    def stop_program(self):
        if self.owner is not None:
            self.owner.stop_program()
        self.close()

    def _position_set(self):
        screen = self.screen()
        if screen is None and self.owner is not None:
            screen = self.owner.screen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        target_x = rect.right() - self.width() - 18
        target_y = rect.top() + (rect.height() - self.height()) // 2
        if self.x() != target_x or self.y() != target_y:
            self.move(target_x, target_y)

    def eventFilter(self, watched: QObject, event: QEvent):
        if watched not in (
            getattr(self, "header_frame", None),
            getattr(self, "header_title", None),
            getattr(self, "clock_label", None),
        ):
            return super().eventFilter(watched, event)
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.drag_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()
            return True
        if (
            event.type() == QEvent.Type.MouseMove
            and self.drag_position is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
            return True
        if event.type() == QEvent.Type.MouseButtonRelease:
            self.drag_position = None
            event.accept()
            return True
        return super().eventFilter(watched, event)


class TransferRunnerOverlay(RunnerOverlay):
    """Run the server-transfer worker inside the standard compact overlay UI."""

    def __init__(self, owner: object):
        super().__init__(owner)
        self.setWindowTitle("Transfer GBot")
        self.header_title.setText("Transfer GBot")
        header_layout = self.header_frame.layout()
        if header_layout is not None:
            header_layout.setSpacing(4)
        self._resize_to_content_height()
        self._position_set()

    def stop_program(self):
        """Delegate STOP to the transfer helper that owns the worker process."""
        stop = getattr(self.owner, "stop", None)
        if callable(stop):
            stop()
