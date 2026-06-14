from PySide6.QtCore import Property, QObject, Signal, Slot

from source.launcher.deposit_helper_capture import focus_game_window
from source.launcher.services.worker_process_service import WorkerProcessService


class BaseWorkerHelperController(QObject):
    changed = Signal()
    dialogRequested = Signal(str, str, str)

    def __init__(self, launcher_controller, worker_kind, parent=None):
        super().__init__(parent)
        self.launcher_controller = launcher_controller
        self.worker_kind = worker_kind
        self.worker = WorkerProcessService(self)
        self._status = "Ready."
        self._running_log = []
        self.worker.statusChanged.connect(self._set_status)
        self.worker.outputLine.connect(self._append_output)
        self.worker.finished.connect(self._worker_finished)
        self.worker.runningChanged.connect(self.changed)

    @Property(bool, notify=changed)
    def running(self):
        return self.worker.isRunning

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(str, notify=changed)
    def startStopText(self):
        return "STOP" if self.running else "START"

    @Property(str, notify=changed)
    def startStopVariant(self):
        return "danger" if self.running else "primary"

    @Property("QVariantList", notify=changed)
    def runningLog(self):
        return self._running_log

    @Slot()
    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    @Slot()
    def stop(self):
        if not self.running:
            return
        self._set_status("Stopping...")
        self.worker.stop()

    def _can_start(self, action):
        if (
            self.launcher_controller.is_running()
            or self.launcher_controller.program_stopping
        ):
            self._set_status("Cannot start while the main program is running.")
            self.dialogRequested.emit(
                "Stop Program First",
                "Stop the running automation before starting this tool.",
                "warning",
            )
            return False
        if not self.launcher_controller.require_ark_window(action):
            self._set_status("Cannot start: ARK window validation failed.")
            return False
        try:
            focus_game_window(center_cursor_when_switching=True)
        except RuntimeError as exc:
            self._set_status(f"Cannot start: {exc}")
            return False
        return True

    def _start_worker(self, *args):
        self.worker.start(self.worker_kind, list(args))
        self.changed.emit()

    def _set_status(self, message):
        self._status = str(message)
        self.changed.emit()

    def _append_output(self, line):
        self._running_log.append(f"{line}\n")
        self._running_log = self._running_log[-200:]
        self.changed.emit()

    def _worker_finished(self, message):
        self._set_status(message)
