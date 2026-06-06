import time

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from source.launcher.constants import APP_TITLE, COLORS, HELPER_HEIGHT, HELPER_WIDTH
from source.launcher.widgets import AnimatedButton

RUNNER_OVERLAY_UPCOMING_LIMIT = 5


def format_runner_overlay(snapshot, now=None, limit=RUNNER_OVERLAY_UPCOMING_LIMIT):
    now = time.time() if now is None else now
    running = snapshot.get("running", [])
    if running:
        current = f"Running {running[0].get('name', 'unknown')}"
    else:
        current = "Waiting for running task..."

    queued = snapshot.get("active", []) + snapshot.get("waiting", [])
    queued.sort(key=lambda task: float(task.get("execution_time", now)))
    upcoming = [_format_upcoming_task(task, now) for task in queued[:limit]]
    if not upcoming:
        upcoming = ["No upcoming tasks."]
    return current, upcoming


def _format_upcoming_task(task, now):
    remaining = max(0, int(float(task.get("execution_time", now)) - now))
    if task.get("state") == "READY" or remaining == 0:
        timer = "READY"
    else:
        hours, remainder = divmod(remaining, 3600)
        minutes, seconds = divmod(remainder, 60)
        timer = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{timer:<8} {task.get('name', 'unknown')}"


class RunnerOverlay(QWidget):
    def __init__(self, owner):
        super().__init__(None)
        self.owner = owner
        self.drag_position = None
        self.upcoming_labels = []

        self.setObjectName("RunnerOverlayWindow")
        self.setWindowTitle(f"{APP_TITLE} Runner")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowOpacity(1.0)
        self.setFixedWidth(200)
        self.setMinimumHeight(HELPER_HEIGHT)
        self._build_ui()
        self._resize_to_content_height()
        self._position_set()

    def _build_ui(self):
        self.setStyleSheet(f"""
            QWidget#RunnerOverlayWindow {{
                background: #050A10;
                color: {COLORS["text"]};
                border: 1px solid rgba(0, 216, 255, 150);
            }}
            QFrame#RunnerOverlayShell {{
                background: rgba(10, 16, 25, 245);
                border: 1px solid rgba(0, 216, 255, 120);
            }}
            QLabel#RunnerOverlayTitle {{
                color: {COLORS["cyan"]};
                font-size: 15px;
                font-weight: 900;
                letter-spacing: 1px;
            }}
            QLabel#RunnerOverlayCurrent {{
                color: {COLORS["text"]};
                font-size: 13px;
                font-weight: 900;
            }}
            QLabel#RunnerOverlayHint {{
                color: {COLORS["muted"]};
                font-family: Consolas;
                font-size: 11px;
            }}
            QLabel#RunnerOverlayTask {{
                color: {COLORS["muted"]};
                font-family: Consolas;
                font-size: 11px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        shell = QFrame()
        shell.setObjectName("RunnerOverlayShell")
        root.addWidget(shell)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)

        self.header_frame = QFrame()
        self.header_frame.installEventFilter(self)
        header = QHBoxLayout(self.header_frame)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        self.header_title = QLabel(APP_TITLE)
        self.header_title.setObjectName("RunnerOverlayTitle")
        self.header_title.installEventFilter(self)
        stop = AnimatedButton("STOP", "danger")
        stop.setObjectName("RunnerOverlayStop")
        # stop.setFixedHeight(28)
        stop.setMinimumWidth(72)
        stop.clicked.connect(self.stop_program)
        header.addWidget(self.header_title)
        header.addStretch()
        header.addWidget(stop)
        layout.addWidget(self.header_frame)

        self.current_label = QLabel("Waiting for running task...")
        self.current_label.setObjectName("RunnerOverlayCurrent")
        self.current_label.setWordWrap(True)
        layout.addWidget(self.current_label)

        for _ in range(RUNNER_OVERLAY_UPCOMING_LIMIT):
            label = QLabel("")
            label.setObjectName("RunnerOverlayTask")
            label.setWordWrap(True)
            self.upcoming_labels.append(label)
            layout.addWidget(label)

    def refresh(self, snapshot):
        current, upcoming = format_runner_overlay(snapshot)
        self.current_label.setText(current)
        for index, label in enumerate(self.upcoming_labels):
            if index < len(upcoming):
                label.setText(upcoming[index])
                label.show()
            else:
                label.hide()
        self._resize_to_content_height()
        self._position_set()

    def _resize_to_content_height(self):
        layout = self.layout()
        if layout is not None:
            layout.invalidate()
            layout.activate()
        height = self.sizeHint().height()
        if layout is not None and layout.hasHeightForWidth():
            layout_height = layout.heightForWidth(self.width())
            if layout_height >= 0:
                height = max(height, layout_height)
        self.resize(self.width(), max(HELPER_HEIGHT, height))
        self.adjustSize()
        if self.height() < HELPER_HEIGHT:
            self.resize(self.width(), HELPER_HEIGHT)

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
        self.move(
            rect.right() - self.width() - 18,
            rect.top() + (rect.height() - self.height()) // 2,
        )

    def eventFilter(self, watched, event):
        if watched not in (
            getattr(self, "header_frame", None),
            getattr(self, "header_title", None),
        ):
            return super().eventFilter(watched, event)
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self.drag_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()
            return True
        if (
            event.type() == QEvent.MouseMove
            and self.drag_position is not None
            and event.buttons() & Qt.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
            return True
        if event.type() == QEvent.MouseButtonRelease:
            self.drag_position = None
            event.accept()
            return True
        return super().eventFilter(watched, event)
