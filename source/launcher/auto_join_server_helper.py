from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QWidget,
)

import settings
from source.join_sim.source.server_number import normalize_server_number
from source.launcher.components.custom_pyside_component import RemovableComboBox
from source.launcher.components.helper_window import WorkerHelperWindow
from source.launcher.components.widgets import (
    AnimatedButton,
    LoadingSpinner,
    WrappedStatusLabel,
)
from source.launcher.config.constants import HELPER_HEIGHT, HELPER_WIDTH
from source.launcher.utils.auto_join_server_store import (
    forget_auto_join_server,
    load_auto_join_servers,
    remember_auto_join_server,
)
from source.launcher.utils.deposit_helper_capture import (
    focus_game_window,
    register_alt_n_hotkey,
    unregister_hotkey,
)


class AutoJoinServerHelper(WorkerHelperWindow):
    status_changed = Signal(str)
    worker_ready = Signal()
    worker_finished = Signal(str)

    def __init__(self, owner: object):
        super().__init__(
            owner,
            "Auto Join Server",
            HELPER_WIDTH,
            HELPER_HEIGHT,
            route_kind="auto_join_server",
            route_index=None,
            hotkey_hint="ALT + N toggles START / STOP",
            unavailable_hotkey_hint="ALT + N toggle hotkey unavailable",
            register_hotkey_func=register_alt_n_hotkey,
            unregister_hotkey_func=unregister_hotkey,
        )
        self.starting = False
        self.active_server = ""
        self._build_ui()
        self._register_hotkey()
        self.status_changed.connect(self.status.setText)
        self.worker_ready.connect(self._on_worker_ready)
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
        label = QLabel("Server")
        label.setObjectName("FormLabel")
        self.server_field = RemovableComboBox()
        self.server_field.setObjectName("HelperCombo")
        self.server_field.setEditable(True)
        self.server_field.setPlaceholderText(settings.server_number)
        self.server_field.addItems(load_auto_join_servers())
        initial_server = (
            self.server_field.itemText(self.server_field.count() - 1)
            if self.server_field.count()
            else settings.server_number
        )
        self.server_field.setCurrentText(initial_server)
        self.server_field.item_remove_requested.connect(self._delete_saved_server)
        line_edit = self.server_field.lineEdit()
        if line_edit is not None:
            line_edit.returnPressed.connect(self.start)
        server_row.addWidget(label)
        server_row.addWidget(self.server_field, 1)
        self.content_layout.addWidget(self.server_row_widget)

        self.start_stop_button = AnimatedButton("START", "primary")
        self.start_stop_button.clicked.connect(self.toggle)
        self.content_layout.addWidget(self.start_stop_button)

        self.status_spinner = LoadingSpinner()
        self.status = WrappedStatusLabel("Ready.")
        self.status.setObjectName("HelperStatus")
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(8)
        status_row.addWidget(self.status_spinner)
        status_row.addWidget(self.status, 1)
        self.content_layout.addLayout(status_row)
        self.register_minimal_running_widgets(
            self.description,
            self.server_row_widget,
        )

    def _delete_saved_server(self, index: int):
        """Delete one saved server and keep the editable selection useful."""
        server = self.server_field.itemText(index)
        current_server = self.server_field.currentText()
        servers = forget_auto_join_server(server)
        self.server_field.clear()
        self.server_field.addItems(servers)
        if current_server != server:
            self.server_field.setEditText(current_server)
        elif servers:
            self.server_field.setCurrentText(servers[-1])
        else:
            self.server_field.setEditText(settings.server_number)

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
            server = normalize_server_number(self.server_field.currentText())
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

        servers = remember_auto_join_server(server)
        self.server_field.clear()
        self.server_field.addItems(servers)
        self.server_field.setCurrentText(server)

        self.starting = True
        self.active_server = server
        self.status_spinner.start()
        self.start_stop_button.setText("STOP")
        self.start_stop_button.set_variant("danger")
        self.start_stop_button.setEnabled(True)
        self.status.setText("Loading auto join modules...")
        try:
            self._start_worker("auto_join_server", "--server", server)
        except Exception as exc:
            self.starting = False
            self.status_spinner.stop()
            self.start_stop_button.setText("START")
            self.start_stop_button.set_variant("primary")
            self.start_stop_button.setEnabled(True)
            self._set_running_ui(False)
            self.status.setText(f"Cannot start: {exc}")

    def handle_hotkey(self):
        if self.starting and not self.is_running():
            return
        super().handle_hotkey()

    def stop(self):
        if not self.is_running():
            return
        self.starting = False
        self.status_spinner.stop()
        if self.owner.is_program_running() and not self.owner.program_stopping:
            self.owner.stop_program()
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.start_stop_button.setEnabled(False)
        super().stop()
        self.status.setText("Stopping...")

    def _on_worker_ready(self):
        if not self.starting or not self.is_running():
            return
        self.starting = False
        self.status_spinner.stop()
        self.start_stop_button.setText("STOP")
        self.start_stop_button.set_variant("danger")
        self.start_stop_button.setEnabled(True)
        self.status.setText(f"Starting auto join for server {self.active_server}...")

    def _on_worker_finished(self, message: str):
        self.starting = False
        self.status_spinner.stop()
        if self._finish_worker():
            return
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.start_stop_button.setEnabled(True)
        self.status.setText(message)
