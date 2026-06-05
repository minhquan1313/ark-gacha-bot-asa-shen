from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

import settings
from source.join_sim.source.auto_join import (
    normalize_server_number,
    run_auto_join_server,
)
from source.launcher.constants import HELPER_HEIGHT, HELPER_WIDTH
from source.launcher.deposit_helper_capture import (
    focus_game_window,
    register_alt_n_hotkey,
    unregister_hotkey,
)
from source.launcher.helper_window import WorkerHelperWindow
from source.launcher.widgets import AnimatedButton, WrappedStatusLabel


class AutoJoinServerHelper(WorkerHelperWindow):
    status_changed = Signal(str)
    worker_finished = Signal(str)

    def __init__(self, owner):
        super().__init__(
            owner,
            "AUTO JOIN SERVER",
            HELPER_WIDTH,
            HELPER_HEIGHT,
            route_kind="auto_join_server",
            route_index=None,
            hotkey_hint="ALT + N toggles START / STOP",
            unavailable_hotkey_hint="ALT + N toggle hotkey unavailable",
            register_hotkey_func=register_alt_n_hotkey,
            unregister_hotkey_func=unregister_hotkey,
        )
        self._build_ui()
        self._register_hotkey()
        self.status_changed.connect(self.status.setText)
        self.worker_finished.connect(self._on_worker_finished)

    def _build_ui(self):
        self.description = QLabel(
            "Enter a server number and this tool will retry the existing join flow "
            "until the player is back in-server or you stop it."
        )
        self.description.setObjectName("MutedCopy")
        self.description.setWordWrap(True)
        self.content_layout.addWidget(self.description)

        self.server_row_widget = QWidget()
        server_row = QHBoxLayout(self.server_row_widget)
        server_row.setContentsMargins(0, 0, 0, 0)
        label = QLabel("SERVER NUMBER")
        label.setObjectName("FormLabel")
        self.server_field = QLineEdit()
        self.server_field.setObjectName("SettingField")
        self.server_field.setPlaceholderText(settings.server_number)
        self.server_field.setText(settings.server_number)
        self.server_field.returnPressed.connect(self.start)
        server_row.addWidget(label)
        server_row.addWidget(self.server_field, 1)
        self.content_layout.addWidget(self.server_row_widget)

        self.start_stop_button = AnimatedButton("START", "primary")
        self.start_stop_button.clicked.connect(self.toggle)
        self.content_layout.addWidget(self.start_stop_button)

        self.status = WrappedStatusLabel("Ready.")
        self.status.setObjectName("HelperStatus")
        self.content_layout.addWidget(self.status)
        self.register_minimal_running_widgets(
            self.description,
            self.server_row_widget,
            self.start_stop_button,
            self.status,
        )

    def start(self):
        if self.is_running() or self.closing:
            return
        if self.owner.is_program_running() or self.owner.program_stopping:
            self.owner.dialog(
                "Stop Program First",
                "Stop the running automation before starting this tool.",
                "warning",
                parent=self,
            )
            self.status.setText("Cannot start while the main program is running.")
            return
        try:
            server = normalize_server_number(self.server_field.text())
        except ValueError as exc:
            self.status.setText(str(exc))
            self.owner.dialog("Invalid Server Number", str(exc), "warning", parent=self)
            return
        if not self._require_ark_window("start auto join server", "Cannot start"):
            return
        try:
            focus_game_window(center_cursor_when_switching=True)
        except RuntimeError as exc:
            self.status.setText(f"Cannot start: {exc}")
            return

        self.start_stop_button.setText("STOP")
        self.start_stop_button.set_variant("danger")
        self.start_stop_button.setEnabled(True)
        self.status.setText(f"Starting auto join for server {server}...")
        self._start_worker(self._run_worker, server)

    def stop(self):
        if not self.is_running():
            return
        super().stop()
        if self.owner.is_program_running() and not self.owner.program_stopping:
            self.owner.stop_program()
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.start_stop_button.setEnabled(False)
        self.status.setText("Stopping...")

    def _run_worker(self, server):
        error = ""
        joined = False
        try:
            joined = run_auto_join_server(
                server, self.stop_event, self.status_changed.emit
            )
        except Exception as exc:
            error = str(exc)
        if error:
            self.worker_finished.emit(f"Failed: {error}")
        elif joined:
            self.worker_finished.emit("Joined server.")
        else:
            self.worker_finished.emit("Stopped.")

    def _on_worker_finished(self, message):
        if self._finish_worker():
            return
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.start_stop_button.setEnabled(True)
        self.status.setText(message)
