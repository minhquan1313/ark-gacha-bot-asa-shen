import ctypes
import threading

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from source.gacha_bot.fertilizer_refresh import run_fertilizer_refresh
from source.launcher.deposit_helper_capture import (
    register_alt_n_hotkey,
    unregister_hotkey,
)
from source.launcher.deposit_route_helper import WM_HOTKEY
from source.launcher.native_window import WindowsMSG
from source.launcher.widgets import AnimatedButton


class FertilizerRefreshHelper(QWidget):
    status_changed = Signal(str)
    worker_finished = Signal(str)

    def __init__(self, owner):
        super().__init__(None)
        self.owner = owner
        self.route_kind = "fertilizer_refresh"
        self.route_index = None
        self.drag_position = None
        self.mouse_inside = False
        self.closing = False
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.hotkey_id = (id(self) & 0x3FFF) + 1
        self.hotkey_registered = False

        self.setObjectName("DepositHelperWindow")
        self.setStyleSheet(owner.styleSheet())
        self.setWindowTitle("FERTILIZER REFRESH")
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(440, 250)
        self._build_ui()
        self._position_top_right()
        self._register_hotkey()
        self.status_changed.connect(self.status.setText)
        self.worker_finished.connect(self._on_worker_finished)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        shell = QFrame()
        shell.setObjectName("DepositHelperWindow")
        root.addWidget(shell)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.header_frame = QFrame()
        self.header_frame.setObjectName("HelperHeader")
        self.header_frame.installEventFilter(self)
        header = QHBoxLayout(self.header_frame)
        header.setContentsMargins(0, 0, 0, 0)
        self.header_title = QLabel("FERTILIZER REFRESH")
        self.header_title.setObjectName("HelperTitle")
        self.header_title.installEventFilter(self)
        close = AnimatedButton("X", "danger")
        close.setObjectName("HelperIconButton")
        close.setToolTip("Close helper")
        close.clicked.connect(self.close)
        header.addWidget(self.header_title)
        header.addStretch()
        header.addWidget(close)
        layout.addWidget(self.header_frame)

        hint = QLabel("ALT + N toggles START / STOP")
        hint.setObjectName("HelperHint")
        self.hotkey_label = hint
        layout.addWidget(hint)

        description = QLabel(
            "Open a crop plot inventory and this tool transfers everything to your "
            "player inventory, then transfers everything back into the crop plot."
        )
        description.setObjectName("MutedCopy")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.start_stop_button = AnimatedButton("START", "primary")
        self.start_stop_button.clicked.connect(self.toggle)
        layout.addWidget(self.start_stop_button)

        self.status = QLabel("Ready.")
        self.status.setObjectName("HelperStatus")
        layout.addWidget(self.status)

    def toggle(self):
        if self.is_running():
            self.stop()
        else:
            self.start()

    def start(self):
        if self.is_running() or self.closing:
            return
        if self.owner.is_program_running() or self.owner.program_stopping:
            self.owner.dialog(
                "Stop Program First",
                "Stop the running automation before starting this tool.",
                "warning",
            )
            self.status.setText("Cannot start while the main program is running.")
            return
        if not self._require_ark_window("start fertilizer refresh"):
            return

        self.stop_event = threading.Event()
        self.start_stop_button.setText("STOP")
        self.start_stop_button.set_variant("danger")
        self.status.setText("Waiting for a crop plot inventory...")
        self.worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self.worker_thread.start()

    def _require_ark_window(self, action):
        if self.owner.require_ark_window(action):
            return True
        self.status.setText(f"Cannot start: {self.owner.last_ark_window_error}")
        return False

    def stop(self):
        if not self.is_running():
            return
        self.status.setText("Stopping...")
        self.stop_event.set()

    def is_running(self):
        return self.worker_thread is not None and self.worker_thread.is_alive()

    def _run_worker(self):
        error = ""
        try:
            run_fertilizer_refresh(self.stop_event, self.status_changed.emit)
        except Exception as exc:
            error = str(exc)
        self.worker_finished.emit(error)

    def _on_worker_finished(self, error):
        self.worker_thread = None
        if self.closing:
            return
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.status.setText(f"Failed: {error}" if error else "Stopped.")

    def _position_top_right(self):
        screen = self.screen() or self.owner.screen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        self.move(rect.right() - self.width() - 18, rect.top() + 18)

    def _register_hotkey(self):
        if not hasattr(ctypes, "windll"):
            self.hotkey_label.setText("ALT + N toggle hotkey unavailable here")
            return
        try:
            self.hotkey_registered = register_alt_n_hotkey(
                int(self.winId()), self.hotkey_id
            )
        except Exception:
            self.hotkey_registered = False
        if not self.hotkey_registered:
            self.hotkey_label.setText("ALT + N toggle hotkey unavailable")

    def nativeEvent(self, event_type, message):
        if self.hotkey_registered:
            msg = WindowsMSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                self.toggle()
                return True, 0
        return super().nativeEvent(event_type, message)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange:
            self.sync_window_opacity()

    def eventFilter(self, watched, event):
        if watched not in (
            getattr(self, "header_frame", None),
            getattr(self, "header_title", None),
        ):
            return super().eventFilter(watched, event)
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self.drag_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            return True
        if (
            event.type() == QEvent.MouseMove
            and self.drag_position is not None
            and event.buttons() & Qt.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self.drag_position)
            return True
        if event.type() == QEvent.MouseButtonRelease:
            self.drag_position = None
            return True
        return super().eventFilter(watched, event)

    def enterEvent(self, event):
        self.mouse_inside = True
        self.sync_window_opacity()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.mouse_inside = False
        self.sync_window_opacity()
        super().leaveEvent(event)

    def sync_window_opacity(self):
        owner_active = self.owner is not None and self.owner.isActiveWindow()
        keep_visible = self.mouse_inside or self.isActiveWindow() or owner_active
        opacity = float(self.owner.settings.get("helper_inactive_opacity", 0.3))
        self.setWindowOpacity(1.0 if keep_visible else max(0.1, min(1.0, opacity)))

    def closeEvent(self, event):
        self.closing = True
        self.stop_event.set()
        thread = self.worker_thread
        if thread is not None and thread.is_alive():
            thread.join()
        if self.hotkey_registered and hasattr(ctypes, "windll"):
            try:
                unregister_hotkey(int(self.winId()), self.hotkey_id)
            except Exception:
                pass
        self.hotkey_registered = False
        if self.owner is not None and hasattr(self.owner, "forget_deposit_helper"):
            self.owner.forget_deposit_helper(self)
        super().closeEvent(event)
