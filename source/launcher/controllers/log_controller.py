import json
import os
from collections import deque

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

from source.launcher.constants import (
    GACHA_LOG_FILE,
    MAX_LAUNCHER_LOG_LINES,
)


class LogController(QObject):
    FILTERS = ["ALL", "INFO", "DEBUG", "WARN", "ERROR", "CRITICAL", "RUNNING", "QUEUE"]

    changed = Signal()
    activityChanged = Signal(str)
    queueSnapshotReceived = Signal("QVariant")

    def __init__(self, persistent_log_file=None, parent=None):
        super().__init__(parent)
        self._lines = []
        self._filter = "ALL"
        self._log_file_position = 0
        self._queue_controller = None
        self._persistent_log_file = persistent_log_file

    def setQueueController(self, queue_controller):
        self._queue_controller = queue_controller

    @Property("QVariantList", notify=changed)
    def lines(self):
        return self._filtered_lines()

    @Property("QVariantList", notify=changed)
    def dashboardLines(self):
        return self._filtered_lines()[-18:]

    @Property(str, notify=changed)
    def currentFilter(self):
        return self._filter

    @Property("QVariantList", constant=True)
    def filters(self):
        return self.FILTERS

    @Slot(str)
    def setFilter(self, value):
        value = str(value).upper()
        if value not in self.FILTERS:
            return
        self._filter = value
        self.changed.emit()

    @Slot(str)
    def append(self, text):
        if text.startswith("[QUEUE_STATE] "):
            try:
                snapshot = json.loads(text[len("[QUEUE_STATE] ") :])
            except json.JSONDecodeError:
                return
            self.queueSnapshotReceived.emit(snapshot)
            self.changed.emit()
            return

        text = self._normalize_runtime_line(text)
        self._append_launcher_log_file(text)
        self._lines.append(text)
        if len(self._lines) > MAX_LAUNCHER_LOG_LINES:
            self._lines = self._lines[-MAX_LAUNCHER_LOG_LINES:]
        self.activityChanged.emit("")
        self.changed.emit()

    @Slot()
    def loadPreviousLogs(self):
        if not os.path.exists(GACHA_LOG_FILE):
            return
        try:
            with open(GACHA_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                lines = deque(f, maxlen=MAX_LAUNCHER_LOG_LINES)
        except Exception as exc:
            self.append(f"[ERROR] Unable to load previous log file: {exc}\n")
            return
        self._lines = [self.normalize_file_log_line(line) for line in lines]
        self.changed.emit()

    @Slot()
    def clearLogs(self):
        self._lines = []
        self._log_file_position = 0
        try:
            with open(GACHA_LOG_FILE, "w", encoding="utf-8") as f:
                f.truncate(0)
        except Exception as exc:
            self.append(f"[ERROR] Unable to clear log file: {exc}\n")
            return
        self.changed.emit()

    @Slot()
    def copyLogs(self):
        QGuiApplication.clipboard().setText("".join(self._filtered_lines()))

    def _filtered_lines(self):
        if self._filter == "ALL":
            return self._lines
        if self._filter == "QUEUE" and self._queue_controller is not None:
            return self._queue_controller.upcomingTasks
        if self._filter == "RUNNING" and self._queue_controller is not None:
            return self._queue_controller.runningLines
        if self._filter in {"QUEUE", "RUNNING"}:
            return [line for line in self._lines if f"[{self._filter}]" in line]
        return [
            line
            for line in self._lines
            if f"[{self._filter}]" in line or self._filter in line.upper()
        ]

    def _append_launcher_log_file(self, text):
        if not self._persistent_log_file:
            return
        try:
            parent = os.path.dirname(self._persistent_log_file)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self._persistent_log_file, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass

    @staticmethod
    def normalize_file_log_line(line):
        level_map = {
            " - DEBUG - ": "DEBUG",
            " - INFO - ": "INFO",
            " - WARNING - ": "WARN",
            " - ERROR - ": "ERROR",
            " - CRITICAL - ": "CRITICAL",
            " - TEMPLATE - ": "TEMPLATE",
        }
        if line.startswith("["):
            return line
        for marker, level in level_map.items():
            if marker in line:
                return f"[{level}] {line}"
        return line

    @staticmethod
    def _normalize_runtime_line(text):
        if "Added task" in text and "[QUEUE]" not in text:
            return f"[QUEUE] {text}"
        for marker, level in (
            ("CRITICAL", "CRITICAL"),
            ("ERROR", "ERROR"),
            ("WARNING", "WARN"),
            ("DEBUG", "DEBUG"),
            ("TEMPLATE", "TEMPLATE"),
        ):
            if marker in text.upper() and f"[{level}]" not in text:
                return f"[{level}] {text}"
        return text
