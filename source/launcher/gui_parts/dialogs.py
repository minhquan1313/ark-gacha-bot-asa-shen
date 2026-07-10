from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
)

from source.launcher.components.widgets import (
    CyberDialog,
)
from source.launcher.config.constants import (
    APP_NAME,
    GAME_WINDOW_TITLE,
)
from source.launcher.utils.system import (
    validate_ark_window,
)

START_GAME_DISABLE_DELAY = 10000
RUNNER_READY_MESSAGE = "__RUNNER_READY__"


class DialogsGuiMixin:
    def check_colours(self):
        if not self.require_ark_window("check console colours"):
            return

        try:
            from source.utility.colour_checks import console_output
        except ImportError:
            self.dialog(
                "Missing Dependency",
                "Console colour check dependencies are not installed.",
                "error",
            )
            return

        colour = console_output.output_mean_colour()
        self.append_log(
            f"[INFO] Average console colour: {colour}. Set console.json lower_bound to average - 5 and upper_bound to average + 5.\n"
        )

    def require_ark_window(self, action, dialog_parent=None):
        try:
            validate_ark_window()
        except RuntimeError as exc:
            self.last_ark_window_error = str(exc)
            self.append_log(f"[ERROR] Cannot {action}: {self.last_ark_window_error}\n")
            self.dialog(
                f"{GAME_WINDOW_TITLE} Required",
                self.last_ark_window_error,
                "error",
                parent=dialog_parent,
            )
            return False
        self.last_ark_window_error = ""
        return True

    def dialog(self, title, message, variant="info", parent=None):
        dialog_parent = self if parent is None else parent
        active_dialog = getattr(dialog_parent, "_active_cyber_dialog", None)
        if active_dialog is not None:
            try:
                if active_dialog.isVisible():
                    active_dialog.show()
                    active_dialog.raise_()
                    active_dialog.activateWindow()
                    return active_dialog.result()
            except RuntimeError:
                pass

        if dialog_parent is not self:
            dialog_parent.show()
            dialog_parent.raise_()
            dialog_parent.activateWindow()

        dialog = CyberDialog(dialog_parent, title, message, variant)
        dialog_parent._active_cyber_dialog = dialog
        try:
            return dialog.exec()
        finally:
            if getattr(dialog_parent, "_active_cyber_dialog", None) is dialog:
                dialog_parent._active_cyber_dialog = None

    def toast(self, message, variant="info"):
        if variant != "success":
            self.dialog(APP_NAME, message, variant)
            return
        dialog = CyberDialog(self, APP_NAME, message, variant)
        dialog.setModal(False)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        if not hasattr(self, "_toast_dialogs"):
            self._toast_dialogs = []
        self._toast_dialogs.append(dialog)
        dialog.finished.connect(
            lambda _result, item=dialog: (
                self._toast_dialogs.remove(item)
                if item in self._toast_dialogs
                else None
            )
        )
        QTimer.singleShot(3000, dialog.accept)
        dialog.show()

    def confirm(self, title, message, confirm_text="OK"):
        return (
            CyberDialog(
                self,
                title,
                message,
                "confirm",
                confirm_text=confirm_text,
                cancel_text="CANCEL",
            ).exec()
            == QDialog.DialogCode.Accepted
        )
