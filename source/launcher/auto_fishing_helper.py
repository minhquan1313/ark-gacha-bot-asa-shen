from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel

from source.launcher.components.helper_window import WorkerHelperWindow
from source.launcher.components.widgets import (
    AnimatedButton,
    CyberSwitch,
    WrappedStatusLabel,
)
from source.launcher.config.constants import HELPER_HEIGHT, HELPER_WIDTH
from source.launcher.utils.deposit_helper_capture import (
    focus_game_window,
    register_alt_n_hotkey,
    unregister_hotkey,
)


class AutoFishingHelper(WorkerHelperWindow):
    worker_ready = Signal()
    worker_finished = Signal(str)

    def __init__(self, owner: object):
        super().__init__(
            owner,
            "Auto Fishing",
            HELPER_WIDTH,
            HELPER_HEIGHT,
            route_kind="auto_fishing",
            route_index=None,
            hotkey_hint="ALT + N toggles START / STOP",
            unavailable_hotkey_hint="ALT + N toggle hotkey unavailable",
            register_hotkey_func=register_alt_n_hotkey,
            unregister_hotkey_func=unregister_hotkey,
        )
        self.starting = False
        self._build_ui()
        self._register_hotkey()
        self.worker_ready.connect(self._on_worker_ready)
        self.worker_finished.connect(self._on_worker_finished)

    def _build_ui(self):
        """Build the minimal auto-fishing controls."""
        self.description = QLabel(
            "Character should already sit on the chair.\n"
            "Require game UI scale to be 0.5.\n"
            "Movement keyboard to default mapping(WASD QE ZXC)"
        )
        self.description.setObjectName("MutedCopy")
        self.description.setWordWrap(True)
        self.content_layout.addWidget(self.description)

        self.infinite_switch = CyberSwitch("Infinite")
        self.infinite_switch.setChecked(True)
        self.content_layout.addWidget(self.infinite_switch)

        self.start_stop_button = AnimatedButton("START", "primary")
        self.start_stop_button.clicked.connect(self.toggle)
        self.content_layout.addWidget(self.start_stop_button)

        self.status = WrappedStatusLabel("Ready.")
        self.status.setObjectName("HelperStatus")
        self.content_layout.addWidget(self.status)
        self.register_minimal_running_widgets(
            self.description,
            self.infinite_switch,
        )

    def start(self):
        """Focus ARK and start the auto-fishing worker."""
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
        if not self._require_ark_window("start auto fishing", "Cannot start"):
            return
        try:
            focus_game_window(center_cursor_when_switching=True)
        except RuntimeError as exc:
            self.status.setText(f"Cannot start: {exc}")
            return

        self.starting = True
        self.start_stop_button.setText("STOP")
        self.start_stop_button.set_variant("danger")
        self.start_stop_button.setEnabled(True)
        runner_args = ["auto_fishing"]
        if self.infinite_switch.isChecked():
            runner_args.append("--infinite")
        try:
            self._start_worker(*runner_args)
        except Exception as exc:
            self.starting = False
            self.start_stop_button.setText("START")
            self.start_stop_button.set_variant("primary")
            self.start_stop_button.setEnabled(True)
            self._set_running_ui(False)
            self.status.setText(f"Cannot start: {exc}")

    def handle_hotkey(self):
        """Ignore duplicate toggles while the worker process is starting."""
        if self.starting and not self.is_running():
            return
        super().handle_hotkey()

    def stop(self):
        """Stop the auto-fishing worker and restore the idle button."""
        if not self.is_running():
            return
        self.starting = False
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.start_stop_button.setEnabled(False)
        super().stop()
        if not self.closing:
            self.status.setText("Stopped.")

    def _on_worker_ready(self):
        """Show the active state once the runtime has finished importing."""
        if not self.starting or not self.is_running():
            return
        self.starting = False
        self.start_stop_button.setText("STOP")
        self.start_stop_button.set_variant("danger")
        self.start_stop_button.setEnabled(True)

    def _on_worker_finished(self, message: str):
        """Restore the helper after its worker exits."""
        self.starting = False
        if self._finish_worker():
            return
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.start_stop_button.setEnabled(True)
        self.status.setText(message)
