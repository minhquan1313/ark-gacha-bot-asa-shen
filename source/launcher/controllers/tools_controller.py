from PySide6.QtCore import QObject, Signal, Slot


class ToolsController(QObject):
    helperRequested = Signal(str)
    messageRequested = Signal(str, str, str)

    @Slot(str)
    def openHelper(self, helper_name):
        self.helperRequested.emit(helper_name)

    @Slot()
    def checkUpdates(self):
        self.messageRequested.emit(
            "CHECK UPDATE",
            "Update check is not wired in the QML launcher yet.",
            "info",
        )
