import json
import os
import threading
import time
from collections import deque

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices

from source.launcher.config.constants import (
    COLORS,
    GACHA_LOG_FILE,
    MAX_LAUNCHER_LOG_LINES,
)
from source.utility.runner_state import RUNNER_STATE_PREFIX

START_GAME_DISABLE_DELAY = 10000
RUNNER_READY_MESSAGE = "__RUNNER_READY__"


class LogsGuiMixin:
    def load_previous_logs(self):
        if not os.path.exists(GACHA_LOG_FILE):
            return
        try:
            with open(GACHA_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                lines = deque(f, maxlen=MAX_LAUNCHER_LOG_LINES)
        except Exception as exc:
            self.append_log(f"[ERROR] Unable to load previous log file: {exc}\n")
            return
        self.log_lines = [self._normalize_file_log_line(line) for line in lines]
        self._render_logs()

    def start_log_tail(self):
        self.stop_log_tail()
        self.log_tail_stop = threading.Event()
        self.log_file_position = self._log_file_size()
        self.log_tail_thread = threading.Thread(target=self.tail_log_file, daemon=True)
        self.log_tail_thread.start()

    def stop_log_tail(self):
        if self.log_tail_thread and self.log_tail_thread.is_alive():
            self.log_tail_stop.set()
            self.log_tail_thread.join(timeout=1)
        self.log_tail_thread = None

    def tail_log_file(self):
        missing_logged = False
        while not self.log_tail_stop.is_set():
            try:
                if not os.path.exists(GACHA_LOG_FILE):
                    if not missing_logged:
                        self._emit_log_line(
                            f"[WARN] Log file not found yet: {GACHA_LOG_FILE}\n"
                        )
                        missing_logged = True
                    self.log_tail_stop.wait(1)
                    continue

                missing_logged = False
                file_size = os.path.getsize(GACHA_LOG_FILE)
                if file_size < self.log_file_position:
                    self.log_file_position = 0

                with open(GACHA_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(self.log_file_position)
                    lines = f.readlines()
                    self.log_file_position = f.tell()

                for line in lines:
                    self._emit_log_line(self._normalize_file_log_line(line))
            except Exception as exc:
                self._emit_log_line(f"[ERROR] Unable to read live log file: {exc}\n")
                self.log_tail_stop.wait(2)
                continue
            self.log_tail_stop.wait(1)

    @staticmethod
    def _log_file_size():
        try:
            return os.path.getsize(GACHA_LOG_FILE)
        except OSError:
            return 0

    @staticmethod
    def _normalize_file_log_line(line):
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

    def append_log(self, text):
        if text.startswith(RUNNER_STATE_PREFIX):
            try:
                state = json.loads(text[len(RUNNER_STATE_PREFIX) :]).get("state")
            except (json.JSONDecodeError, AttributeError):
                return
            if state not in {"RUNNING", "PAUSED"}:
                return
            self.runner_state = state
            self._sync_runner_overlay()
            return
        if text.startswith("[QUEUE_STATE] "):
            try:
                snapshot = json.loads(text[len("[QUEUE_STATE] ") :])
            except json.JSONDecodeError:
                return
            self._update_queue_snapshot(snapshot)
            if not getattr(self, "runner_loading", False):
                self._render_logs()
            return
        if "Added task" in text and "[QUEUE]" not in text:
            text = f"[QUEUE] {text}"
        elif "CRITICAL" in text.upper() and "[CRITICAL]" not in text:
            text = f"[CRITICAL] {text}"
        elif "ERROR" in text.upper() and "[ERROR]" not in text:
            text = f"[ERROR] {text}"
        elif "WARNING" in text.upper() and "[WARN]" not in text:
            text = f"[WARN] {text}"
        elif "DEBUG" in text.upper() and "[DEBUG]" not in text:
            text = f"[DEBUG] {text}"
        elif "TEMPLATE" in text.upper() and "[TEMPLATE]" not in text:
            text = f"[TEMPLATE] {text}"

        self.log_lines.append(text)
        if len(self.log_lines) > MAX_LAUNCHER_LOG_LINES:
            self.log_lines = self.log_lines[-MAX_LAUNCHER_LOG_LINES:]
        self.last_activity = time.strftime("%H:%M:%S")
        if "[QUEUE]" in text:
            self.waiting_count += 1
        if "[SUCCESS]" in text:
            self.active_count = max(self.active_count, 1)
        if not getattr(self, "runner_loading", False):
            self._render_logs()
        self._sync_runner_overlay()

    def _render_logs(self):
        lines = self._filtered_logs()
        full = self._format_log_lines(lines)
        preview = self._format_log_lines(lines[-18:])
        if hasattr(self, "full_log"):
            self._set_console_html(self.full_log, full)
        if hasattr(self, "dashboard_log"):
            self._set_console_html(self.dashboard_log, preview)

    def _set_console_html(self, console, html):
        console.setHtml(html)
        console.moveCursor(console.textCursor().MoveOperation.End)
        QTimer.singleShot(
            0, lambda widget=console: self._scroll_console_to_bottom(widget)
        )

    @staticmethod
    def _scroll_console_to_bottom(console):
        scrollbar = console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _format_log_lines(self, lines):
        html = []
        for line in lines:
            color = COLORS["text"]
            if "[CRITICAL]" in line or "[ERROR]" in line:
                color = COLORS["red"]
            elif "[WARN]" in line:
                color = COLORS["yellow"]
            elif "[SUCCESS]" in line:
                color = COLORS["green"]
            elif "[INFO]" in line:
                color = COLORS["cyan"]
            elif "[DEBUG]" in line:
                color = COLORS["text"]
            elif "[TEMPLATE]" in line:
                color = COLORS["dim"]
            elif "[QUEUE]" in line:
                color = COLORS["muted"]
            html.append(
                f'<span style="color:{color}; white-space:pre;">{self._escape(line)}</span>'
            )
        return "<br>".join(html)

    @staticmethod
    def _escape(text):
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _filtered_logs(self):
        if self.current_filter == "QUEUE":
            return self._format_queue_snapshot()
        if self.current_filter == "RUNNING":
            return self._format_running_snapshot()
        if self.current_filter == "ALL":
            return self.log_lines
        return [
            line
            for line in self.log_lines
            if f"[{self.current_filter}]" in line or self.current_filter in line.upper()
        ]

    def _format_queue_snapshot(self):
        now = time.time()
        lines = []
        queued = self.queue_snapshot.get("active", []) + self.queue_snapshot.get(
            "waiting", []
        )
        queued.sort(
            key=lambda task: float(task.get("execution_time", now)), reverse=True
        )
        for task in queued:
            remaining = max(0, int(float(task.get("execution_time", now)) - now))
            if task.get("state") == "READY" or remaining == 0:
                timer = "READY"
            else:
                hours, remainder = divmod(remaining, 3600)
                minutes, seconds = divmod(remainder, 60)
                timer = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            lines.append(f"[QUEUE] {timer:<9} {task.get('name', 'unknown')}")
        for task in self.queue_snapshot.get("running", []):
            lines.append(f"[QUEUE] RUNNING   {task.get('name', 'unknown')}")
        return lines or ["[QUEUE] No upcoming tasks."]

    def _update_queue_snapshot(self, snapshot):
        self.queue_snapshot = snapshot
        running = snapshot.get("running", [])
        running_task_name = running[0].get("name", "unknown") if running else None
        if running_task_name and running_task_name != self.running_task_name:
            self.running_history.append(f"[RUNNING] STARTED   {running_task_name}")
        self.running_task_name = running_task_name
        reveal_ready = getattr(self, "_reveal_runner_overlay_if_ready", None)
        if callable(reveal_ready):
            reveal_ready()
        self._sync_runner_overlay()

    def _format_running_snapshot(self):
        lines = self.running_history.copy()
        running = self.queue_snapshot.get("running", [])
        if running:
            lines.append(f"[RUNNING] CURRENT   {running[0].get('name', 'unknown')}")
        else:
            lines.append("[RUNNING] IDLE")
        return lines

    def set_log_filter(self, value):
        self.current_filter = value
        self._render_logs()

    def clear_logs(self):
        self.log_lines.clear()
        self.running_history.clear()
        self.queue_snapshot = {"running": [], "active": [], "waiting": []}
        self.running_task_name = None
        self.active_count = 0
        self.waiting_count = 0
        self.log_file_position = 0
        self.runner_log_start_index = 0
        self._render_logs()
        try:
            with open(GACHA_LOG_FILE, "w", encoding="utf-8") as f:
                f.truncate(0)
        except Exception as exc:
            self.append_log(f"[ERROR] Unable to clear log file: {exc}\n")

    def open_logs(self):
        """Open the launcher log file with the operating system's default app."""
        log_url = QUrl.fromLocalFile(os.path.abspath(GACHA_LOG_FILE))
        if not QDesktopServices.openUrl(log_url):
            self.dialog(
                "Open Logs Failed",
                f"Unable to open the log file:\n{GACHA_LOG_FILE}",
                "error",
            )
