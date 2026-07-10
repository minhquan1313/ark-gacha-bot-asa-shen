from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
)

from source.launcher.components.helper_window import WorkerHelperWindow
from source.launcher.components.widgets import (
    AnimatedButton,
    LoadingSpinner,
    WrappedStatusLabel,
)
from source.launcher.config.constants import HELPER_HEIGHT, HELPER_WIDTH
from source.launcher.utils.deposit_helper_capture import (
    focus_game_window,
    register_alt_n_hotkey,
    unregister_hotkey,
)


class FertilizerRefreshHelper(WorkerHelperWindow):
    status_changed = Signal(str)
    worker_ready = Signal()
    worker_finished = Signal(str)

    def __init__(self, owner: object):
        super().__init__(
            owner,
            "Fertilizer Refresh",
            HELPER_WIDTH,
            HELPER_HEIGHT,
            route_kind="fertilizer_refresh",
            route_index=None,
            hotkey_hint="ALT + N toggles START / STOP",
            unavailable_hotkey_hint="ALT + N toggle hotkey unavailable",
            register_hotkey_func=register_alt_n_hotkey,
            unregister_hotkey_func=unregister_hotkey,
        )
        self.starting = False
        self._build_ui()
        self._register_hotkey()
        self.status_changed.connect(self.status.setText)
        self.worker_ready.connect(self._on_worker_ready)
        self.worker_finished.connect(self._on_worker_finished)

    def _build_ui(self):
        self.description = QLabel(
            "Aim at a crop plot and this tool opens its inventory, transfers everything "
            "to your player inventory, then transfers everything back into the crop plot."
        )
        self.description.setObjectName("MutedCopy")
        self.description.setWordWrap(True)
        self.content_layout.addWidget(self.description)

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
        self.register_minimal_running_widgets(self.description)

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
        if not self._require_ark_window("start fertilizer refresh", "Cannot start"):
            return
        try:
            focus_game_window(center_cursor_when_switching=True)
        except RuntimeError as exc:
            self.status.setText(f"Cannot start: {exc}")
            return

        self.starting = True
        self.status_spinner.start()
        self.start_stop_button.setText("STOP")
        self.start_stop_button.set_variant("danger")
        self.start_stop_button.setEnabled(True)
        self.status.setText("Loading fertilizer modules...")
        try:
            self._start_worker("fertilizer_refresh")
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
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.start_stop_button.setEnabled(False)
        super().stop()
        if not self.closing:
            self.status.setText("Stopped.")

    def _on_worker_ready(self):
        if not self.starting or not self.is_running():
            return
        self.starting = False
        self.status_spinner.stop()
        self.start_stop_button.setText("STOP")
        self.start_stop_button.set_variant("danger")
        self.start_stop_button.setEnabled(True)
        self.status.setText("Aim at a crop plot to refresh fertilizer...")

    def _on_worker_finished(self, message: str):
        self.starting = False
        self.status_spinner.stop()
        if self._finish_worker():
            return
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.start_stop_button.setEnabled(True)
        self.status.setText(message)
