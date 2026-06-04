import ctypes
import threading

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

import settings
from source.join_sim.source.auto_join import (
    normalize_server_number,
    run_auto_join_server,
)
from source.launcher.deposit_helper_capture import (
    focus_game_window,
    register_alt_n_hotkey,
    unregister_hotkey,
)
from source.launcher.deposit_route_helper import WM_HOTKEY
from source.launcher.native_window import WindowsMSG
from source.launcher.widgets import AnimatedButton, WrappedStatusLabel


class AutoJoinServerHelper(QWidget):
    status_changed = Signal(str)
    worker_finished = Signal(str)

    def __init__(self, owner):
        super().__init__(None)
        self.owner = owner
        self.route_kind = "auto_join_server"
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
        self.setWindowTitle("AUTO JOIN SERVER")
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(320, 280)
        self._build_ui()
        self._position_middle_right()
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
        self.header_title = QLabel("AUTO JOIN SERVER")
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
            "Enter a server number and this tool will retry the existing join flow "
            "until the player is back in-server or you stop it."
        )
        description.setObjectName("MutedCopy")
        description.setWordWrap(True)
        layout.addWidget(description)

        server_row = QHBoxLayout()
        label = QLabel("SERVER NUMBER")
        label.setObjectName("FormLabel")
        self.server_field = QLineEdit()
        self.server_field.setObjectName("SettingField")
        self.server_field.setPlaceholderText(settings.server_number)
        self.server_field.setText(settings.server_number)
        self.server_field.returnPressed.connect(self.start)
        server_row.addWidget(label)
        server_row.addWidget(self.server_field, 1)
        layout.addLayout(server_row)

        self.start_stop_button = AnimatedButton("START", "primary")
        self.start_stop_button.clicked.connect(self.toggle)
        layout.addWidget(self.start_stop_button)

        self.status = WrappedStatusLabel("Ready.")
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
        if not self._require_ark_window("start auto join server"):
            return
        try:
            focus_game_window(center_cursor_when_switching=True)
        except RuntimeError as exc:
            self.status.setText(f"Cannot start: {exc}")
            return

        self.stop_event = threading.Event()
        self.start_stop_button.setText("STOP")
        self.start_stop_button.set_variant("danger")
        self.start_stop_button.setEnabled(True)
        self.server_field.setEnabled(False)
        self.status.setText(f"Starting auto join for server {server}...")
        self.worker_thread = threading.Thread(
            target=self._run_worker, args=(server,), daemon=True
        )
        self.worker_thread.start()

    def _require_ark_window(self, action):
        if self.owner.require_ark_window(action, dialog_parent=self):
            return True
        self.status.setText(f"Cannot start: {self.owner.last_ark_window_error}")
        return False

    def stop(self):
        if not self.is_running():
            return
        self.stop_event.set()
        if self.owner.is_program_running() and not self.owner.program_stopping:
            self.owner.stop_program()
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.start_stop_button.setEnabled(False)
        self.status.setText("Stopping...")

    def is_running(self):
        return self.worker_thread is not None and self.worker_thread.is_alive()

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
        self.worker_thread = None
        self.server_field.setEnabled(True)
        if self.closing:
            self.close()
            return
        self.start_stop_button.setText("START")
        self.start_stop_button.set_variant("primary")
        self.start_stop_button.setEnabled(True)
        self.status.setText(message)

    def _position_middle_right(self):
        screen = self.screen() or self.owner.screen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        self.move(
            rect.right() - self.width() - 18,
            rect.top() + (rect.height() - self.height()) // 2,
        )

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
            self.status.setText("Stopping...")
            self.start_stop_button.setEnabled(False)
            event.ignore()
            return
        if self.hotkey_registered and hasattr(ctypes, "windll"):
            try:
                unregister_hotkey(int(self.winId()), self.hotkey_id)
            except Exception:
                pass
        self.hotkey_registered = False
        if self.owner is not None and hasattr(self.owner, "forget_deposit_helper"):
            self.owner.forget_deposit_helper(self)
        super().closeEvent(event)
