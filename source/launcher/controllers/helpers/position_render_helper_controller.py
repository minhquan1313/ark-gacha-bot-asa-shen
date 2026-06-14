from PySide6.QtCore import Property, QObject, Signal, Slot

from source.launcher.deposit_helper_capture import capture_ccc_yaw_pitch, view_yaw
from source.launcher.settings_store import save_settings


class PositionRenderHelperController(QObject):
    changed = Signal()
    dialogRequested = Signal(str, str, str)

    def __init__(self, launcher_controller, settings_controller, parent=None):
        super().__init__(parent)
        self.launcher_controller = launcher_controller
        self.settings_controller = settings_controller
        self._status = "Ready."
        self._busy = False

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(str, notify=changed)
    def stationYaw(self):
        return str(self.settings_controller.settings().get("station_yaw", 0.0))

    @Slot()
    def captureStationYaw(self):
        if self._busy:
            return
        if not self.launcher_controller.require_ark_window("capture render position"):
            return
        self._set_busy(True, "Capturing yaw...")
        try:
            yaw, _pitch = capture_ccc_yaw_pitch()
            settings = self.settings_controller.settings()
            settings["station_yaw"] = yaw
            save_settings(settings)
            self.settings_controller.refresh()
            self._set_status(f"Saved station_yaw: {yaw:.2f}.")
        except Exception as exc:
            self._set_status(f"Capture failed: {exc}")
            self.dialogRequested.emit("Capture Failed", str(exc), "error")
        finally:
            self._set_busy(False)
            self._refocus_helper()

    @Slot()
    def viewStationYaw(self):
        if self._busy:
            return
        if not self.launcher_controller.require_ark_window("view render position"):
            return
        self._set_busy(True, "Setting Ark view...")
        try:
            view_yaw(float(self.settings_controller.settings().get("station_yaw", 0.0)))
            self._set_status("View applied.")
        except Exception as exc:
            self._set_status(f"View failed: {exc}")
            self.dialogRequested.emit("View Failed", str(exc), "error")
        finally:
            self._set_busy(False)
            self._refocus_helper()

    def _set_status(self, message):
        self._status = str(message)
        self.changed.emit()

    def _set_busy(self, busy, message=None):
        self._busy = bool(busy)
        if message:
            self._status = message
        self.changed.emit()

    def _refocus_helper(self):
        refocus = getattr(self.launcher_controller, "refocus_active_helper", None)
        if refocus is not None:
            refocus()
