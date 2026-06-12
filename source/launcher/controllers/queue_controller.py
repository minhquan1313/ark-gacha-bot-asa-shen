import time

from PySide6.QtCore import Property, QObject, Signal, Slot


class QueueController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snapshot = {"running": [], "active": [], "waiting": []}
        self._running_history = []
        self._running_task_name = None

    @Property(int, notify=changed)
    def activeCount(self):
        return len(self._snapshot.get("running", [])) + len(
            self._snapshot.get("active", [])
        )

    @Property(int, notify=changed)
    def waitingCount(self):
        return len(self._snapshot.get("waiting", []))

    @Property(str, notify=changed)
    def currentTask(self):
        running = self._snapshot.get("running", [])
        return self._task_name(running[0], "unknown") if running else "IDLE"

    @Property("QVariantList", notify=changed)
    def upcomingTasks(self):
        return self._format_queue_snapshot()

    @Property("QVariantList", notify=changed)
    def runnerUpcomingTasks(self):
        return self._format_runner_overlay_snapshot()

    @Property("QVariantList", notify=changed)
    def runningLines(self):
        lines = list(self._running_history)
        running = self._snapshot.get("running", [])
        if running:
            lines.append(f"[RUNNING] CURRENT   {self._task_name(running[0])}")
        else:
            lines.append("[RUNNING] IDLE")
        return lines

    @Slot("QVariant")
    def updateSnapshot(self, snapshot):
        self._snapshot = dict(snapshot or {})
        running = self._snapshot.get("running", [])
        running_task_name = self._task_name(running[0], "unknown") if running else None
        if running_task_name and running_task_name != self._running_task_name:
            self._running_history.append(f"[RUNNING] STARTED   {running_task_name}")
        self._running_task_name = running_task_name
        self.changed.emit()

    @Slot()
    def clear(self):
        self._snapshot = {"running": [], "active": [], "waiting": []}
        self._running_history = []
        self._running_task_name = None
        self.changed.emit()

    def _format_queue_snapshot(self):
        now = time.time()
        lines = []
        queued = self._snapshot.get("active", []) + self._snapshot.get("waiting", [])
        queued.sort(key=lambda task: self._task_execution_time(task, now), reverse=True)
        for task in queued:
            timer = self._format_task_timer(task, now)
            lines.append(f"[QUEUE] {timer:<9} {self._task_name(task)}")
        for task in self._snapshot.get("running", []):
            lines.append(f"[QUEUE] RUNNING   {self._task_name(task)}")
        return lines or ["[QUEUE] No upcoming tasks."]

    def _format_runner_overlay_snapshot(self):
        now = time.time()
        queued = self._snapshot.get("active", []) + self._snapshot.get("waiting", [])
        queued.sort(key=lambda task: self._task_execution_time(task, now))
        lines = [self._format_runner_overlay_task(task, now) for task in queued[:5]]
        return lines or ["No upcoming tasks."]

    def _format_runner_overlay_task(self, task, now):
        timer = self._format_task_timer(task, now)
        return f"{timer:<8} {self._task_name(task)}"

    def _format_task_timer(self, task, now):
        execution_time = self._task_execution_time(task, now)
        remaining = max(0, int(execution_time - now))
        if self._task_state(task) == "READY" or remaining == 0:
            return "READY"
        hours, remainder = divmod(remaining, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _task_execution_time(task, fallback):
        if not isinstance(task, dict):
            return fallback
        try:
            return float(task.get("execution_time", fallback))
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _task_name(task, fallback="unknown"):
        if not isinstance(task, dict):
            return fallback
        return str(task.get("name") or fallback)

    @staticmethod
    def _task_state(task):
        if not isinstance(task, dict):
            return ""
        return str(task.get("state", "")).upper()
