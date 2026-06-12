from PySide6.QtCore import Slot

from source.launcher.controllers.helpers.base_worker_helper import (
    BaseWorkerHelperController,
)


class FertilizerHelperController(BaseWorkerHelperController):
    def __init__(self, launcher_controller, parent=None):
        super().__init__(launcher_controller, "fertilizer_refresh", parent)

    @Slot()
    def start(self):
        if self.running:
            return
        if not self._can_start("start fertilizer refresh"):
            return
        self._set_status("Aim at a crop plot to refresh fertilizer...")
        self._start_worker()
