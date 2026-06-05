from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
)

from source.gacha_bot.fertilizer_refresh import run_fertilizer_refresh
from source.launcher.constants import HELPER_HEIGHT, HELPER_WIDTH
from source.launcher.deposit_helper_capture import (
    focus_game_window,
    register_alt_n_hotkey,
    unregister_hotkey,
)
from source.launcher.helper_window import WorkerHelperWindow
from source.launcher.widgets import AnimatedButton, WrappedStatusLabel


class FertilizerRefreshHelper(WorkerHelperWindow):
    status_changed = Signal(str)
    worker_finished = Signal(str)

    def __init__(self, owner):
        super().__init__(
            owner,
            "FERTILIZER REFRESH",
            HELPER_WIDTH,
            HELPER_HEIGHT,
            route_kind="fertilizer_refresh",
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
            "Aim at a crop plot and this tool opens its inventory, transfers everything "
            "to your player inventory, then transfers everything back into the crop plot."
        )
        self.description.setObjectName("MutedCopy")
        self.description.setWordWrap(True)
        self.content_layout.addWidget(self.description)

        self.start_stop_button = AnimatedButton("START", "primary")
        self.start_stop_button.clicked.connect(self.toggle)
        self.content_layout.addWidget(self.start_stop_button)

        self.status = WrappedStatusLabel("Ready.")
        self.status.setObjectName("HelperStatus")
        self.content_layout.addWidget(self.status)
        self.register_minimal_running_widgets(
            self.description,
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
        if not self._require_ark_window("start fertilizer refresh", "Cannot start"):
            return
        try:
            focus_game_window(center_cursor_when_switching=True)
        except RuntimeError as exc:
            self.status.setText(f"Cannot start: {exc}")
            return

        self.start_stop_button.setText("STOP")
        self.start_stop_button.set_variant("danger")
        self.start_stop_button.setEnabled(True)
        self.status.setText("Aim at a crop plot to refresh fertilizer...")
        self._start_worker(self._run_worker)

    def stop(self):
        if not self.is_running():
            return
        super().stop()
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.start_stop_button.setEnabled(False)
        self.status.setText("Stopped.")

    def _run_worker(self):
        error = ""
        try:
            run_fertilizer_refresh(self.stop_event, self.status_changed.emit)
        except Exception as exc:
            error = str(exc)
        self.worker_finished.emit(error)

    def _on_worker_finished(self, error):
        if self._finish_worker():
            return
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.start_stop_button.setEnabled(True)
        self.status.setText(f"Failed: {error}" if error else "Stopped.")
