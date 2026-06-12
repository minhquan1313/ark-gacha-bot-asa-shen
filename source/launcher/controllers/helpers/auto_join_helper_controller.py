from PySide6.QtCore import Property, Signal, Slot

from source.join_sim.source.auto_join import normalize_server_number
from source.launcher.controllers.helpers.base_worker_helper import (
    BaseWorkerHelperController,
)


class AutoJoinHelperController(BaseWorkerHelperController):
    serverNumberChanged = Signal()

    def __init__(self, launcher_controller, settings_controller, parent=None):
        super().__init__(launcher_controller, "auto_join_server", parent)
        self.settings_controller = settings_controller
        self._server_number = settings_controller.serverNumber

    @Property(str, notify=serverNumberChanged)
    def serverNumber(self):
        return self._server_number

    @Slot(str)
    def setServerNumber(self, value):
        value = str(value)
        try:
            server = normalize_server_number(value)
        except ValueError:
            self._server_number = value
            self.serverNumberChanged.emit()
            return
        self._server_number = server
        self.settings_controller.setValue("server_number", server)
        self.serverNumberChanged.emit()

    @Slot()
    def start(self):
        if self.running:
            return
        try:
            server = normalize_server_number(self._server_number)
        except ValueError as exc:
            self._set_status(str(exc))
            self.dialogRequested.emit("Invalid Server Number", str(exc), "warning")
            return
        if not self._can_start("start auto join server"):
            return
        self._set_status(f"Starting auto join for server {server}...")
        self._start_worker("--server", server)
