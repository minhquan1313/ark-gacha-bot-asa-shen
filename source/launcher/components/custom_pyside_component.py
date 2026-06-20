from PySide6.QtWidgets import (
    QComboBox,
)


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()
