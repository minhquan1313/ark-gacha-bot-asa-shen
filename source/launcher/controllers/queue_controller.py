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
        return running[0].get("name", "IDLE") if running else "IDLE"

    @Property("QVariantList", notify=changed)
    def upcomingTasks(self):
        return self._format_queue_snapshot()

    @Property("QVariantList", notify=changed)
    def runningLines(self):
        lines = list(self._running_history)
        running = self._snapshot.get("running", [])
        if running:
            lines.append(f"[RUNNING] CURRENT   {running[0].get('name', 'unknown')}")
        else:
            lines.append("[RUNNING] IDLE")
        return lines

    @Slot("QVariant")
    def updateSnapshot(self, snapshot):
        self._snapshot = dict(snapshot or {})
        running = self._snapshot.get("running", [])
        running_task_name = running[0].get("name", "unknown") if running else None
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
        for task in self._snapshot.get("running", []):
            lines.append(f"[QUEUE] RUNNING   {task.get('name', 'unknown')}")
        return lines or ["[QUEUE] No upcoming tasks."]
