import ctypes
import threading

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from source.gacha_bot.server_transfer import TransferConfigError, run_transfer_helper
from source.launcher.deposit_helper_capture import (
    register_alt_n_hotkey,
    unregister_hotkey,
)
from source.launcher.deposit_route_helper import WM_HOTKEY
from source.launcher.native_window import WindowsMSG
from source.launcher.transfer_helper_config import (
    bed_name,
    load_transfer_runtime_config,
    missing_runtime_inputs,
    save_transfer_dedis,
    save_transfer_settings,
    save_transfer_ui_coords,
    suggested_loop_count,
)
from source.launcher.widgets import (
    AnimatedButton,
    ClickableTextEdit,
    CyberSwitch,
    WrappedStatusLabel,
)


class ServerTransferHelper(QWidget):
    status_changed = Signal(str)
    worker_finished = Signal(str)

    def __init__(self, owner):
        super().__init__(None)
        self.owner = owner
        self.route_kind = "server_transfer"
        self.route_index = None
        self.drag_position = None
        self.mouse_inside = False
        self.closing = False
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.hotkey_id = (id(self) & 0x3FFF) + 1
        self.hotkey_registered = False
        self.setting_fields = {}
        self.dedi_rows = []
        self.config = load_transfer_runtime_config(create_missing=True)

        self.setObjectName("DepositHelperWindow")
        self.setStyleSheet(owner.styleSheet())
        self.setWindowTitle("SERVER TRANSFER HELPER")
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(560, 700)
        self._build_ui()
        self._position_middle_right()
        self._register_hotkey()
        self.status_changed.connect(self._append_status)
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
        self.header_title = QLabel("SERVER TRANSFER HELPER")
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

        self.hotkey_label = QLabel("ALT + N toggles START / STOP")
        self.hotkey_label.setObjectName("HelperHint")
        layout.addWidget(self.hotkey_label)

        self.idle_widget = self._idle_widget()
        self.running_widget = self._running_widget()
        self.running_widget.setVisible(False)
        layout.addWidget(self.idle_widget, 1)
        layout.addWidget(self.running_widget, 1)

    def _idle_widget(self):
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        settings_card, settings_layout = self._panel("TRANSFER SETTINGS")
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        settings_layout.addLayout(grid)
        self._add_setting_fields(grid)
        content_layout.addWidget(settings_card)

        dedis_card, dedis_layout = self._panel("TRANSFER DEDIS")
        self.dedi_teleport = self._line_edit(self.config["dedis"].get("teleport", ""))
        self.dedi_teleport.editingFinished.connect(self._sync_loop_hint)
        dedis_layout.addLayout(self._labeled_row("TELEPORT", self.dedi_teleport))
        self.dedi_rows_layout = QVBoxLayout()
        self.dedi_rows_layout.setSpacing(6)
        dedis_layout.addLayout(self.dedi_rows_layout)
        for item in self.config["dedis"].get("items", []):
            self._add_dedi_row(item)
        add_dedi = AnimatedButton("ADD DEDI", "secondary")
        add_dedi.clicked.connect(lambda: self._add_dedi_row())
        dedis_layout.addWidget(add_dedi)
        content_layout.addWidget(dedis_card)

        self.loop_hint = WrappedStatusLabel("")
        self.loop_hint.setObjectName("HelperStatus")
        layout.addWidget(self.loop_hint)
        self.start_stop_button = AnimatedButton("START", "primary")
        self.start_stop_button.clicked.connect(self.toggle)
        layout.addWidget(self.start_stop_button)
        self.status = WrappedStatusLabel("Ready.")
        self.status.setObjectName("HelperStatus")
        layout.addWidget(self.status)
        self._sync_loop_hint()
        return wrapper

    def _running_widget(self):
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.running_summary = WrappedStatusLabel("Preparing transfer run...")
        self.running_summary.setObjectName("HelperStatus")
        layout.addWidget(self.running_summary)
        self.running_log = ClickableTextEdit()
        self.running_log.setObjectName("Console")
        self.running_log.setReadOnly(True)
        layout.addWidget(self.running_log, 1)
        stop = AnimatedButton("STOP", "danger")
        stop.clicked.connect(self.stop)
        self.running_stop_button = stop
        layout.addWidget(stop)
        return wrapper

    def _add_setting_fields(self, grid):
        settings = self.config["settings"]
        rows = [
            ("lag_offset", "Lag offset"),
            ("resource_station_yaw", "Resource yaw"),
            ("destination_station_yaw", "Destination yaw"),
            ("transmitter_teleport", "Transmitter teleport"),
            ("resource_server", "Resource server"),
            ("destination_server", "Destination server"),
            ("account_count", "Accounts"),
            ("loop_count", "Loops"),
            ("bed_prefix", "Bed prefix"),
            ("bed_prefix_pad_start", "Bed pad width"),
            ("structure_load_delay", "Structure delay"),
            ("transfer_retry_delay", "Retry delay"),
        ]
        for index, (key, label_text) in enumerate(rows):
            row = index // 2
            column = 0 if index % 2 == 0 else 2
            label = QLabel(label_text.upper())
            label.setObjectName("FormLabel")
            field = self._line_edit(settings.get(key, ""))
            field.editingFinished.connect(self._sync_loop_hint)
            self.setting_fields[key] = field
            grid.addWidget(label, row, column)
            grid.addWidget(field, row, column + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

    def _add_dedi_row(self, item=None):
        item = item or {
            "enabled": True,
            "location": {"yaw": 0.0, "pitch": 0.0},
            "crouched": False,
        }
        row = QFrame()
        row.setObjectName("HelperRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 6, 8, 6)
        enabled = CyberSwitch()
        enabled.setChecked(bool(item.get("enabled", True)))
        yaw = self._line_edit(item.get("location", {}).get("yaw", 0.0))
        pitch = self._line_edit(item.get("location", {}).get("pitch", 0.0))
        crouched = CyberSwitch()
        crouched.setChecked(bool(item.get("crouched", False)))
        remove = AnimatedButton("X", "danger")
        remove.setObjectName("HelperIconButton")
        layout.addWidget(QLabel("ON"))
        layout.addWidget(enabled)
        layout.addWidget(QLabel("YAW"))
        layout.addWidget(yaw, 1)
        layout.addWidget(QLabel("PITCH"))
        layout.addWidget(pitch, 1)
        layout.addWidget(QLabel("C"))
        layout.addWidget(crouched)
        layout.addWidget(remove)
        data = {
            "frame": row,
            "enabled": enabled,
            "yaw": yaw,
            "pitch": pitch,
            "crouched": crouched,
        }
        self.dedi_rows.append(data)
        remove.clicked.connect(lambda: self._remove_dedi_row(data))
        for widget in (enabled, yaw, pitch, crouched):
            if hasattr(widget, "editingFinished"):
                widget.editingFinished.connect(self._sync_loop_hint)
            if hasattr(widget, "toggled"):
                widget.toggled.connect(lambda _checked=False: self._sync_loop_hint())
        self.dedi_rows_layout.addWidget(row)
        if hasattr(self, "loop_hint"):
            self._sync_loop_hint()

    def _remove_dedi_row(self, row_data):
        if len(self.dedi_rows) <= 1:
            self.status.setText("At least one transfer dedi row is required.")
            return
        self.dedi_rows.remove(row_data)
        row_data["frame"].deleteLater()
        self._sync_loop_hint()

    def _current_config(self):
        settings = {key: field.text() for key, field in self.setting_fields.items()}
        dedis = {
            "teleport": self.dedi_teleport.text(),
            "items": [
                {
                    "enabled": row["enabled"].isChecked(),
                    "location": {
                        "yaw": row["yaw"].text(),
                        "pitch": row["pitch"].text(),
                    },
                    "crouched": row["crouched"].isChecked(),
                }
                for row in self.dedi_rows
            ],
        }
        self.config["settings"] = save_transfer_settings(settings)
        self.config["dedis"] = save_transfer_dedis(dedis)
        self.config["ui_coords"] = save_transfer_ui_coords(self.config["ui_coords"])
        return self.config

    def _sync_loop_hint(self):
        try:
            account_count = int(self.setting_fields["account_count"].text())
            active_count = sum(
                1 for row in self.dedi_rows if row["enabled"].isChecked()
            )
            suggested = suggested_loop_count(active_count, account_count)
            sample = bed_name(
                self.setting_fields["bed_prefix"].text(),
                1,
                int(self.setting_fields["bed_prefix_pad_start"].text() or 0),
            )
            self.loop_hint.setText(
                f"{active_count} dedi x {account_count} account = {suggested} suggested loop(s). "
                f"Account 1 bed: {sample}"
            )
        except Exception as exc:
            self.loop_hint.setText(f"Loop hint unavailable: {exc}")

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
            config = self._current_config()
        except ValueError as exc:
            self.status.setText(str(exc))
            self.owner.dialog(
                "Invalid Transfer Config", str(exc), "warning", parent=self
            )
            return
        missing = missing_runtime_inputs(
            config["settings"], config["dedis"], config["ui_coords"]
        )
        if missing:
            message = "Missing required transfer helper inputs:\n" + "\n".join(
                f"- {item}" for item in missing
            )
            self.status.setText("Missing required transfer helper inputs.")
            self.owner.dialog(
                "Transfer Helper Not Ready", message, "warning", parent=self
            )
            return

        self.stop_event = threading.Event()
        self.running_log.clear()
        self._set_running_ui(True)
        self.status.setText("Starting server transfer helper...")
        self.worker_thread = threading.Thread(
            target=self._run_worker, args=(config,), daemon=True
        )
        self.worker_thread.start()

    def stop(self):
        if not self.is_running():
            return
        self.stop_event.set()
        self.running_stop_button.setEnabled(False)
        self.running_summary.setText("Stopping...")
        self.status.setText("Stopping...")

    def is_running(self):
        return self.worker_thread is not None and self.worker_thread.is_alive()

    def _run_worker(self, config):
        try:
            completed = run_transfer_helper(
                config, self.stop_event, self.status_changed.emit
            )
        except TransferConfigError as exc:
            self.worker_finished.emit(f"Config blocked: {exc}")
        except Exception as exc:
            self.worker_finished.emit(f"Failed: {exc}")
        else:
            self.worker_finished.emit("Finished." if completed else "Stopped.")

    def _append_status(self, message):
        self.running_summary.setText(message)
        self.status.setText(message)
        self.running_log.append(message)

    def _on_worker_finished(self, message):
        self.worker_thread = None
        if self.closing:
            self.close()
            return
        self._set_running_ui(False)
        self.running_stop_button.setEnabled(True)
        self.status.setText(message)

    def _set_running_ui(self, running):
        self.idle_widget.setVisible(not running)
        self.running_widget.setVisible(running)
        self.start_stop_button.setText("STOP" if running else "START")
        self.start_stop_button.set_variant("danger" if running else "primary")

    def _panel(self, title):
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("PanelTitle")
        layout.addWidget(label)
        return panel, layout

    @staticmethod
    def _line_edit(value):
        field = QLineEdit(str(value))
        field.setObjectName("SettingField")
        return field

    @staticmethod
    def _labeled_row(label_text, widget):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("FormLabel")
        row.addWidget(label)
        row.addWidget(widget, 1)
        return row

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
