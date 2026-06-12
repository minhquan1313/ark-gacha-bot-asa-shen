from PySide6.QtCore import Property, QObject, Signal, Slot

from source.launcher.constants import APP_VERSION


class ToolsController(QObject):
    helperRequested = Signal(str)
    messageRequested = Signal(str, str, str)
    updateChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._latest_version = APP_VERSION
        self._update_status = "Manual check required"
        self._update_detail = (
            "No update endpoint is configured for this local build. "
            "Use your release source to compare versions."
        )
        self._update_available = False

    @Property(str, notify=updateChanged)
    def latestVersion(self):
        return self._latest_version

    @Property(str, notify=updateChanged)
    def updateStatus(self):
        return self._update_status

    @Property(str, notify=updateChanged)
    def updateDetail(self):
        return self._update_detail

    @Property(bool, notify=updateChanged)
    def updateAvailable(self):
        return self._update_available

    @Slot(str)
    def openHelper(self, helper_name):
        self.helperRequested.emit(helper_name)

    @Slot()
    def checkUpdates(self):
        self._latest_version = APP_VERSION
        self._update_status = "Manual check required"
        self._update_detail = (
            "This build does not include an update endpoint. "
            "Compare the current version with your release source."
        )
        self._update_available = False
        self.updateChanged.emit()
        self.messageRequested.emit(
            "CHECK UPDATE",
            self._update_detail,
            "info",
        )

    @Slot()
    def openDownloadPage(self):
        self.messageRequested.emit(
            "DOWNLOAD",
            "Download page is not configured for this build.",
            "info",
        )

    @Slot(str, str, str)
    def showMessage(self, title, message, variant="info"):
        self.messageRequested.emit(title, message, variant)
