import contextlib
import json
import os
import tempfile
import time

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from source.launcher.components.custom_pyside_component import NoWheelComboBox
from source.launcher.components.helper_runner import TASK_STATE_PREFIX
from source.launcher.components.helper_window import WorkerHelperWindow
from source.launcher.components.widgets import (
    AnimatedButton,
    ClickableTextEdit,
    CyberSwitch,
    WrappedStatusLabel,
)
from source.launcher.config.transfer_helper_config import (
    MAX_TRANSFER_RUNTIME_ACCOUNTS,
    calculate_same_structure_destination_dedis,
    default_transfer_dedi_item,
    load_transfer_runtime_config,
    missing_runtime_inputs,
    normalize_transfer_dedis,
    normalize_transfer_players,
    player_bed_name_search_conflicts,
    save_transfer_dedis,
    save_transfer_players,
    save_transfer_settings,
    save_transfer_ui_coords,
    suggested_loop_count,
)
from source.launcher.runner_overlay import (
    RUNNER_OVERLAY_LOG_LIMIT,
    TransferRunnerOverlay,
)
from source.launcher.utils.deposit_helper_capture import (
    capture_ccc_yaw_pitch,
    focus_game_window,
    preload_capture_view_dependencies,
    register_alt_n_hotkey,
    unregister_hotkey,
    view_route_entry,
)
from source.launcher.utils.steam_accounts import (
    load_steam_accounts,
    most_recent_account_name,
)

DEFAULT_PANELS_EXPANDED = True
PLAYER_SEARCH_WARNING_COLOR = "#ffb020"
IGNORED_PLAYER_COLOR = "#ff4d6d"
SAME_STRUCTURE_TOOLTIP = (
    "If destinate deposit outpost has THE SAME SETUP, this will automatically "
    "calculate the yaw pitch and crouch for your destinate dedis!"
)
TRANSFER_START_MODE_DESCRIPTIONS = {
    "default": (
        "Recommended. Start from resource server -> Withdraw -> Transfer to "
        "destinate server."
    ),
    "destinate": (
        "Optional. Assume all characters are filled with resources, start transfer "
        "to destinate server."
    ),
}


class ServerTransferHelper(WorkerHelperWindow):
    status_changed = Signal(str)
    task_state_changed = Signal(dict)
    worker_ready = Signal()
    worker_finished = Signal(str)

    def __init__(self, owner: object) -> None:
        self.setting_fields = {}
        self.dedi_rows = []
        self.resource_dedi_rows = self.dedi_rows
        self.destination_dedi_rows = []
        self.player_rows = []
        self.collapsible_panels = []
        self.transfer_overlay = None
        self.starting = False
        self.transfer_log_lines = []
        self.transfer_task_snapshot = {
            "running": [{"name": "Preparing transfer"}],
            "active": [],
            "waiting": [],
        }
        self.config = load_transfer_runtime_config(create_missing=True)
        self.config["dedis"] = normalize_transfer_dedis(self.config.get("dedis", {}))
        try:
            self.steam_accounts = load_steam_accounts()
            self.steam_accounts_error = ""
        except Exception as exc:
            self.steam_accounts = []
            self.steam_accounts_error = str(exc)
        self.config["steam_accounts"] = self.steam_accounts

        super().__init__(
            owner,
            "SERVER TRANSFER HELPER",
            360,
            520,
            route_kind="server_transfer",
            route_index=None,
            hotkey_hint="ALT + N toggles START / STOP",
            unavailable_hotkey_hint="ALT + N toggle hotkey unavailable",
            register_hotkey_func=register_alt_n_hotkey,
            unregister_hotkey_func=unregister_hotkey,
        )
        self._build_ui()
        self._register_hotkey()
        self._preload_capture_view()
        self.status_changed.connect(self._append_status)
        self.task_state_changed.connect(self._update_transfer_task_snapshot)
        self.worker_ready.connect(self._on_worker_ready)
        self.worker_finished.connect(self._on_worker_finished)
        self.transfer_refresh_timer = QTimer(self)
        self.transfer_refresh_timer.timeout.connect(self._refresh_transfer_overlay)
        self.runtime_config_path = None

    def _build_ui(self) -> None:
        self.idle_widget = self._idle_widget()
        self.running_widget = self._running_widget()
        self.running_widget.setVisible(False)
        self.content_layout.addWidget(self.idle_widget, 1)
        self.content_layout.addWidget(self.running_widget, 1)
        self.register_minimal_running_widgets(self.idle_widget)

    def _idle_content_height(self):
        return self.idle_min_height

    def _idle_widget(self):
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
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

        players_card, players_layout = self._panel("PLAYER SETTINGS")
        self.players_layout = QVBoxLayout()
        self.players_layout.setSpacing(6)
        players_layout.addLayout(self.players_layout)
        self._refresh_player_rows()
        add_player = AnimatedButton("ADD PLAYER", "secondary")
        add_player.clicked.connect(self._add_player_row_from_button)
        players_layout.addWidget(add_player)
        content_layout.addWidget(players_card)

        resource_card = self._build_dedi_section("resource", "RESOURCE")
        content_layout.addWidget(resource_card)
        destination_card = self._build_dedi_section("destination", "DESTINATE")
        content_layout.addWidget(destination_card)
        content_layout.addStretch(1)

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
        mode_label = QLabel("Start mode")
        mode_label.setObjectName("FormLabel")
        mode_field = NoWheelComboBox()
        mode_field.setObjectName("HelperCombo")
        mode_field.addItem("Default", "default")
        mode_field.addItem("Destinate", "destinate")
        mode_index = mode_field.findData(settings.get("transfer_start_mode", "default"))
        mode_field.setCurrentIndex(max(0, mode_index))
        mode_field.currentIndexChanged.connect(lambda _index: self._persist_settings())
        mode_field.currentIndexChanged.connect(
            self._sync_transfer_start_mode_description
        )
        self.setting_fields["transfer_start_mode"] = mode_field
        grid.addWidget(mode_label, 0, 0)
        grid.addWidget(mode_field, 0, 1)
        self.transfer_start_mode_label = mode_label
        self.transfer_start_mode_description = WrappedStatusLabel("")
        self.transfer_start_mode_description.setObjectName("HelperStatus")
        grid.addWidget(self.transfer_start_mode_description, 1, 0, 1, 2)

        rows = [
            ("lag_offset", "Lag offset"),
            ("transmitter_teleport", "Transmitter"),
            ("structure_load_delay", "Wait structures"),
            ("steam_restart_interval", "Steam restart interval"),
        ]
        for index, (key, label_text) in enumerate(rows):
            row = index + 2
            column = 0
            label, field = self._setting_field(key, label_text)
            grid.addWidget(label, row, column)
            grid.addWidget(field, row, column + 1)
        loop_row = len(rows) + 3
        loop_label = QLabel("Transfer")
        loop_label.setObjectName("FormLabel")
        loop_field = self._line_edit(settings.get("loop_count", ""))
        loop_field.editingFinished.connect(self._persist_settings)
        loop_field.returnPressed.connect(self._persist_settings)
        self.setting_fields["loop_count"] = loop_field
        grid.addWidget(loop_label, loop_row, 0)
        grid.addWidget(loop_field, loop_row, 1)
        self.loop_hint = WrappedStatusLabel("")
        self.loop_hint.setObjectName("HelperStatus")
        grid.addWidget(self.loop_hint, loop_row + 1, 0, 1, 2)
        grid.setColumnStretch(1, 1)
        self._sync_transfer_start_mode_description()

    def _build_dedi_section(self, side, title):
        card, layout = self._panel(title)
        route = self.config["dedis"].get(side, {})
        server_key = f"{side if side == 'resource' else 'destination'}_server"
        server_label_text = (
            "Resource server" if side == "resource" else "Destination server"
        )
        server_label, server_field = self._setting_field(server_key, server_label_text)
        layout.addLayout(self._labeled_row_widget(server_label, server_field))
        yaw_key = f"{side}_station_yaw"
        station_yaw = self._line_edit(self.config["settings"].get(yaw_key, 0.0))
        station_yaw.editingFinished.connect(self._persist_settings)
        station_yaw.returnPressed.connect(self._persist_settings)
        self.setting_fields[yaw_key] = station_yaw
        setattr(self, f"{side}_station_yaw", station_yaw)
        yaw_row = QHBoxLayout()
        yaw_row.setSpacing(4)
        yaw_row.setContentsMargins(0, 0, 0, 0)
        yaw_row.addWidget(station_yaw, 1)
        capture_yaw = self._helper_button("C", f"Capture {side} yaw")
        capture_yaw.clicked.connect(
            lambda checked=False, target=station_yaw: self._capture_station_yaw(target)
        )
        yaw_row.addWidget(capture_yaw)
        yaw_widget = QWidget()
        yaw_widget.setLayout(yaw_row)
        layout.addLayout(self._labeled_row("YAW", yaw_widget))
        teleport = self._line_edit(route.get("teleport", ""))
        teleport.editingFinished.connect(self._persist_dedis)
        teleport.returnPressed.connect(self._persist_dedis)
        setattr(self, f"{side}_dedi_teleport", teleport)
        if side == "resource":
            self.dedi_teleport = teleport
        layout.addLayout(self._labeled_row("TELEPORT", teleport))
        if side == "destination":
            calculate = AnimatedButton("CAL", "secondary")
            calculate.setToolTip(SAME_STRUCTURE_TOOLTIP)
            calculate.clicked.connect(self._calculate_destination_dedis)
            self.destination_same_structure_calculate = calculate
            layout.addWidget(calculate)
            calculate_description = WrappedStatusLabel(SAME_STRUCTURE_TOOLTIP)
            calculate_description.setObjectName("HelperStatus")
            self.destination_same_structure_description = calculate_description
            layout.addWidget(calculate_description)
        rows_layout = QVBoxLayout()
        rows_layout.setSpacing(6)
        setattr(self, f"{side}_dedi_rows_layout", rows_layout)
        if side == "resource":
            self.dedi_rows_layout = rows_layout
        layout.addLayout(rows_layout)
        for item in route.get("items", []):
            self._add_dedi_row(item, side=side)
        add_dedi = AnimatedButton("ADD DEDI", "secondary")
        add_dedi.clicked.connect(
            lambda checked=False, target_side=side: self._add_synced_dedi_pair(
                target_side
            )
        )
        layout.addWidget(add_dedi)
        return card

    def _dedi_rows_for_side(self, side):
        return (
            self.destination_dedi_rows
            if side == "destination"
            else self.resource_dedi_rows
        )

    @staticmethod
    def _opposite_dedi_side(side):
        return "resource" if side == "destination" else "destination"

    def _add_synced_dedi_pair(self, side="resource"):
        self._add_dedi_row(side=side)
        self._add_dedi_row(side=self._opposite_dedi_side(side))
        self._autosync_transfer_count(persist=True)
        self._persist_dedis()

    def _add_dedi_row(self, item=None, persist=False, side="resource"):
        item = item or default_transfer_dedi_item()
        row = QFrame()
        row.setObjectName("HelperRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(6)
        toggle = self._helper_button(">", "Expand or collapse dedi row")
        index_label = QLabel("")
        index_label.setObjectName("FormLabel")
        summary = QLabel("")
        summary.setObjectName("HelperRowSummary")
        summary.setWordWrap(True)
        header.addWidget(toggle)
        header.addWidget(index_label)
        header.addWidget(summary, 1)
        layout.addLayout(header)

        details = QWidget()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(6)
        details.setVisible(False)
        info = QHBoxLayout()
        info.setSpacing(8)
        yaw = self._line_edit(item.get("location", {}).get("yaw", 0.0))
        pitch = self._line_edit(item.get("location", {}).get("pitch", 0.0))
        crouched = CyberSwitch("Crouch")
        crouched.setChecked(bool(item.get("crouched", False)))
        capture = self._helper_button("C", "Capture yaw and pitch")
        view = self._helper_button("V", "View saved yaw and pitch in Ark")
        remove = AnimatedButton("X", "danger")
        remove.setObjectName("HelperIconButton")
        info.addWidget(QLabel("YAW"))
        info.addWidget(yaw, 1)
        info.addWidget(QLabel("PITCH"))
        info.addWidget(pitch, 1)
        actions = QHBoxLayout()
        actions.setSpacing(6)
        actions.addWidget(crouched)
        actions.addWidget(capture, 1)
        actions.addWidget(view)
        actions.addWidget(remove)
        details_layout.addLayout(info)
        details_layout.addLayout(actions)
        layout.addWidget(details)
        data = {
            "frame": row,
            "toggle": toggle,
            "index_label": index_label,
            "summary": summary,
            "details": details,
            "yaw": yaw,
            "pitch": pitch,
            "crouched": crouched,
            "side": side,
        }
        rows = self._dedi_rows_for_side(side)
        rows.append(data)
        toggle.clicked.connect(
            lambda checked=False, target=data: self._toggle_dedi_row(target)
        )
        remove.clicked.connect(lambda: self._remove_dedi_row(data))
        capture.clicked.connect(
            lambda checked=False, target=data: self._capture_dedi(target)
        )
        view.clicked.connect(lambda checked=False, target=data: self._view_dedi(target))
        for widget in (yaw, pitch, crouched):
            if hasattr(widget, "editingFinished"):
                widget.editingFinished.connect(
                    lambda target=data: self._autosync_transfer_count(persist=True)
                )
                widget.editingFinished.connect(
                    lambda target=data: self._sync_dedi_summary(target)
                )
                widget.editingFinished.connect(self._persist_dedis)
            if hasattr(widget, "toggled"):
                widget.toggled.connect(
                    lambda _checked=False: self._autosync_transfer_count(persist=True)
                )
                widget.toggled.connect(
                    lambda _checked=False, target=data: self._sync_dedi_summary(target)
                )
                widget.toggled.connect(lambda _checked=False: self._persist_dedis())
        rows_layout = getattr(self, f"{side}_dedi_rows_layout")
        rows_layout.addWidget(row)
        self._renumber_dedi_rows(side)
        if hasattr(self, "loop_hint"):
            self._sync_loop_hint()
        if persist:
            self._persist_dedis()

    def _remove_dedi_row(self, row_data):
        side = row_data.get("side", "resource")
        rows = self._dedi_rows_for_side(side)
        if len(rows) <= 1:
            self.status.setText("At least one transfer dedi row is required.")
            return
        index = rows.index(row_data)
        self._remove_dedi_row_at("resource", index)
        self._remove_dedi_row_at("destination", index)
        self._autosync_transfer_count(persist=True)
        self._persist_dedis()

    def _remove_dedi_row_at(self, side, index):
        rows = self._dedi_rows_for_side(side)
        if index >= len(rows):
            return
        row_data = rows.pop(index)
        row_data["frame"].deleteLater()
        self._renumber_dedi_rows(side)

    def _toggle_dedi_row(self, row_data):
        visible = row_data["details"].isHidden()
        row_data["details"].setVisible(visible)
        row_data["toggle"].setText("v" if visible else ">")

    def _renumber_dedi_rows(self, side="resource"):
        for index, row in enumerate(self._dedi_rows_for_side(side), 1):
            row["index_label"].setText(f"D{index}")
            self._sync_dedi_summary(row)

    def _sync_dedi_summary(self, row_data):
        crouch_text = "Crouch on" if row_data["crouched"].isChecked() else "Crouch off"
        row_data["summary"].setText(
            f"Yaw {row_data['yaw'].text()} | "
            f"Pitch {row_data['pitch'].text()} | {crouch_text}"
        )

    def _current_config(self):
        self._sync_loop_hint()
        self.config["settings"] = save_transfer_settings(self._settings_from_fields())
        self.config["dedis"] = save_transfer_dedis(self._dedis_from_rows())
        self.config["players"] = self._save_players_from_rows(autosync=False)
        self.config["ui_coords"] = save_transfer_ui_coords(self.config["ui_coords"])
        self.config["steam_accounts"] = self.steam_accounts
        return self.config

    def _sync_loop_hint(self):
        if not hasattr(self, "loop_hint"):
            return
        try:
            self.loop_hint.setText(self._loop_count_hint_text())
        except Exception as exc:
            self.loop_hint.setText(f"Loop hint unavailable: {exc}")

    def _autosync_transfer_count(self, persist=False):
        if not hasattr(self, "loop_hint") or "loop_count" not in self.setting_fields:
            return
        try:
            suggested = self._suggested_loop_count()
            self.setting_fields["loop_count"].setText(str(suggested))
            self.loop_hint.setText(self._loop_count_hint_text())
            if persist:
                self._persist_settings()
        except Exception as exc:
            self.loop_hint.setText(f"Loop hint unavailable: {exc}")

    def _suggested_loop_count(self):
        account_count = len(self.player_rows)
        active_count = len(self.resource_dedi_rows)
        if account_count == 0 or active_count == 0:
            return 1
        effective_accounts = min(account_count, MAX_TRANSFER_RUNTIME_ACCOUNTS)
        return suggested_loop_count(active_count, effective_accounts)

    def _loop_count_hint_text(self):
        account_count = len(self.player_rows)
        active_count = len(self.resource_dedi_rows)
        if account_count == 0:
            return f"{active_count} dedi x 0 account = no runnable accounts."
        if active_count == 0:
            return f"0 dedi x {account_count} account = no transfer dedis."
        effective_accounts = min(account_count, MAX_TRANSFER_RUNTIME_ACCOUNTS)
        suggested = suggested_loop_count(active_count, effective_accounts)
        suffix = (
            f" Only first {effective_accounts} account(s) run."
            if account_count > effective_accounts
            else ""
        )
        return (
            f"{active_count} dedi x {effective_accounts} account = "
            f"{suggested} transfer(s).{suffix}"
        )

    def start(self) -> None:
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
        if not self.player_rows:
            self.status.setText("Add at least one player before starting.")
            self.owner.dialog(
                "Transfer Helper Not Ready",
                "Add at least one player before starting.",
                "warning",
                parent=self,
            )
            return
        player_conflicts = self._runtime_player_search_conflicts(
            self._players_from_rows()
        )
        if player_conflicts:
            conflict_lines = self._format_player_search_conflicts(
                player_conflicts, self._players_from_rows()
            )
            message = "Player bed/teleport names are not search-safe:\n" + "\n".join(
                f"- {line}" for line in conflict_lines
            )
            self.status.setText("Player bed/teleport names are not search-safe.")
            self.owner.dialog(
                "Transfer Helper Not Ready", message, "warning", parent=self
            )
            return
        steam_issues = self._player_steam_issue_map(self._players_from_rows())
        if steam_issues:
            lines = []
            for index in sorted(steam_issues):
                lines.append(f"Player {index + 1}: {' '.join(steam_issues[index])}")
            message = "Player Steam accounts are not ready:\n" + "\n".join(
                f"- {line}" for line in lines
            )
            self.status.setText("Player Steam accounts are not ready.")
            self.owner.dialog(
                "Transfer Helper Not Ready", message, "warning", parent=self
            )
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
            config["settings"],
            config["dedis"],
            config["players"],
            steam_accounts=config.get("steam_accounts"),
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

        if not self._require_ark_window("start server transfer", "Cannot start"):
            return
        try:
            focus_game_window(center_cursor_when_switching=True)
        except RuntimeError as exc:
            self.status.setText(f"Cannot start: {exc}")
            return

        self.running_log.clear()
        self.transfer_log_lines.clear()
        self.transfer_task_snapshot = {
            "running": [{"name": "Loading server transfer modules"}],
            "active": [],
            "waiting": [],
        }
        self.starting = True
        self.status.setText("Loading server transfer modules...")
        try:
            self.runtime_config_path = self._write_runtime_config(config)
            self._start_worker("server_transfer", "--config", self.runtime_config_path)
        except Exception as exc:
            self.starting = False
            self._set_running_ui(False)
            self._cleanup_runtime_config()
            self.status.setText(f"Cannot start transfer helper: {exc}")
            self.owner.dialog(
                "Transfer Helper Start Failed", str(exc), "error", parent=self
            )

    def stop(self) -> None:
        if not self.is_running():
            return
        self.starting = False
        super().stop()
        self.running_stop_button.setEnabled(False)
        self.running_summary.setText("Stopping...")
        self.status.setText("Stopping...")

    def handle_hotkey(self) -> None:
        if self.starting and not self.is_running():
            return
        super().handle_hotkey()

    def _on_worker_ready(self) -> None:
        if not self.starting or not self.is_running():
            return
        self.starting = False
        self.transfer_task_snapshot = {
            "running": [{"name": "Preparing transfer"}],
            "active": [],
            "waiting": [],
        }
        if self.transfer_overlay is not None:
            self.transfer_overlay.stop_button.setText("STOP")
            self.transfer_overlay.stop_button.set_variant("danger")
            self.transfer_overlay.stop_button.setEnabled(True)
        self._refresh_transfer_overlay()

    def _append_status(self, message: str) -> None:
        self.running_summary.setText(message)
        self.status.setText(message)
        self.running_log.append(message)
        self.transfer_log_lines.append(
            f"{time.strftime('%H:%M:%S')} - INFO - transfer - {message}"
        )
        self.transfer_log_lines = self.transfer_log_lines[-RUNNER_OVERLAY_LOG_LIMIT:]
        self._refresh_transfer_overlay()

    def _on_worker_finished(self, message: str) -> None:
        self.starting = False
        if self._finish_worker():
            self._close_transfer_overlay()
            self._cleanup_runtime_config()
            return
        self._cleanup_runtime_config()
        self.running_stop_button.setEnabled(True)
        self.status.setText(message)

    def _handle_worker_output(self, line: str) -> None:
        if line.startswith(TASK_STATE_PREFIX):
            try:
                snapshot = json.loads(line[len(TASK_STATE_PREFIX) :])
            except json.JSONDecodeError:
                return
            if isinstance(snapshot, dict):
                self.task_state_changed.emit(snapshot)
            return
        super()._handle_worker_output(line)

    def _update_transfer_task_snapshot(self, snapshot: dict) -> None:
        """Store a worker task snapshot and refresh the compact transfer UI."""
        self.transfer_task_snapshot = snapshot
        self._refresh_transfer_overlay()

    def _refresh_transfer_overlay(self) -> None:
        """Refresh transfer tasks, status logs, and the overlay clock."""
        overlay = self.transfer_overlay
        if overlay is None:
            return
        try:
            if self.starting:
                overlay.refresh_loading()
                return
            overlay.refresh(self.transfer_task_snapshot, self.transfer_log_lines)
        except RuntimeError:
            self.transfer_overlay = None
            self.transfer_refresh_timer.stop()

    def _close_transfer_overlay(self) -> None:
        """Stop transfer UI refreshes and close the compact overlay safely."""
        self.transfer_refresh_timer.stop()
        overlay = self.transfer_overlay
        self.transfer_overlay = None
        if overlay is None:
            return
        with contextlib.suppress(RuntimeError):
            overlay.close()

    def _set_running_ui(self, running: bool) -> None:
        if running:
            self.running_ui_active = True
            self.idle_widget.setVisible(False)
            self.running_widget.setVisible(True)
            self.hotkey_label.setText(self.running_hotkey_hint)
            if self.transfer_overlay is None:
                self.transfer_overlay = TransferRunnerOverlay(self)
            if self.starting:
                self.transfer_overlay.stop_button.setText("STOP")
                self.transfer_overlay.stop_button.set_variant("danger")
                self.transfer_overlay.stop_button.setEnabled(True)
            self.hide()
            self._refresh_transfer_overlay()
            self.transfer_overlay.show()
            self.transfer_overlay.raise_()
            self.transfer_refresh_timer.start(1000)
        else:
            self._close_transfer_overlay()
            self.setMaximumHeight(16777215)
            self.setFixedWidth(self.idle_width)
            self.setMinimumHeight(self.idle_min_height)
            self.running_widget.setVisible(False)
            self.idle_widget.setVisible(True)
            self.hotkey_label.setText(self.hotkey_hint)
            self.resize(self.idle_width, self._idle_content_height())
            self.running_ui_active = False
            self.show()
            self.raise_()
            self.activateWindow()
            self._position_middle_right()
        self.start_stop_button.setText("STOP" if running else "START")
        self.start_stop_button.set_variant("danger" if running else "primary")

    def _before_close(self) -> None:
        self._close_transfer_overlay()
        self._cleanup_runtime_config()
        super()._before_close()

    def _preload_capture_view(self):
        try:
            preload_capture_view_dependencies()
        except Exception as exc:
            self.status.setText(f"Capture preload skipped: {exc}")

    def _refresh_player_rows(self, persist=False):
        if not hasattr(self, "players_layout"):
            return
        if self.player_rows:
            source_players = self._players_from_rows()
        else:
            source_players = self.config.get("players", {})
        account_count = max(1, len(source_players.get("players", [])))
        try:
            self.config["players"] = normalize_transfer_players(
                source_players, account_count
            )
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        while self.players_layout.count():
            item = self.players_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.player_rows = []
        for account in range(1, account_count + 1):
            self._add_player_row(account)
        self._sync_player_search_warnings()
        if persist:
            try:
                self.config["players"] = save_transfer_players(
                    self.config["players"],
                )
            except ValueError as exc:
                self.status.setText(str(exc))
                return
            self.status.setText("Player settings saved.")
        if persist:
            self._autosync_transfer_count(persist=True)
        else:
            self._sync_loop_hint()

    def _add_player_row(self, account):
        row = QFrame()
        row.setObjectName("HelperRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(8, 6, 8, 6)

        label = QLabel(f"P{account}")
        label.setObjectName("FormLabel")

        name = self._line_edit(
            self.config["players"]["players"][account - 1]["bed_name"]
        )
        name.editingFinished.connect(self._save_players_from_rows)
        name.editingFinished.connect(self._sync_player_search_warnings)
        copy = self._helper_button("C", "Copy Bed/teleport name")
        copy.clicked.connect(
            lambda checked=False, field=name: self._copy_name(field.text())
        )
        remove = AnimatedButton("X", "danger")
        remove.setObjectName("HelperIconButton")
        info = QHBoxLayout()
        info.addWidget(label)
        info.addWidget(QLabel("Bed/Teleport"))
        info.addWidget(name, 1)
        info.addWidget(copy)
        info.addWidget(remove)

        layout.addLayout(info)
        steam_row = QHBoxLayout()
        steam_row.setSpacing(6)
        steam_label = QLabel("Steam")
        steam_label.setObjectName("FormLabel")
        steam = NoWheelComboBox()
        steam.setObjectName("HelperCombo")
        steam.addItem("")
        for steam_account in self.steam_accounts:
            account_name = str(steam_account.get("account_name", "")).strip()
            if account_name:
                steam.addItem(account_name)
        current_steam = str(
            self.config["players"]["players"][account - 1].get("steam_account", "")
        ).strip()
        if current_steam and steam.findText(current_steam) == -1:
            steam.addItem(current_steam)
        steam.setCurrentText(current_steam)
        steam.currentTextChanged.connect(self._save_players_from_rows)
        steam.currentTextChanged.connect(self._sync_player_search_warnings)
        steam_row.addWidget(steam_label)
        steam_row.addWidget(steam, 1)
        layout.addLayout(steam_row)
        self.players_layout.addWidget(row)
        row_data = {
            "frame": row,
            "label": label,
            "name": name,
            "steam": steam,
            "account": account,
        }
        self.player_rows.append(row_data)
        remove.clicked.connect(
            lambda checked=False, target=row_data: self._remove_player_row(target)
        )

    def _add_player_row_from_button(self):
        players = self._players_from_rows().get("players", [])
        next_account = len(players) + 1
        players.append({"bed_name": "", "steam_account": ""})
        self.config["players"] = normalize_transfer_players(
            {"players": players}, next_account
        )
        self.player_rows = []
        self._refresh_player_rows(persist=True)

    def _remove_player_row(self, row_data):
        if len(self.player_rows) <= 1:
            self.status.setText("At least one player row is required.")
            return
        self.player_rows.remove(row_data)
        row_data["frame"].deleteLater()
        for index, row in enumerate(self.player_rows, 1):
            row["account"] = index
            row["label"].setText(f"P{index}")
        self._save_players_from_rows()
        self._sync_player_search_warnings()

    def _players_from_rows(self):
        if self.player_rows:
            return {
                "players": [
                    {
                        "bed_name": row["name"].text(),
                        "steam_account": row["steam"].currentText().strip(),
                    }
                    for row in self.player_rows
                ]
            }
        return self.config.get("players", {})

    def _save_players_from_rows(self, *_args: object, autosync: bool = True):
        try:
            players = save_transfer_players(
                self._players_from_rows(),
            )
        except ValueError as exc:
            self.status.setText(str(exc))
            return self.config.get("players", {})
        self.config["players"] = players
        self.status.setText("Player settings saved.")
        self._sync_player_search_warnings()
        if autosync:
            self._autosync_transfer_count(persist=True)
        return players

    def _sync_player_search_warnings(self):
        conflicts = player_bed_name_search_conflicts(self._players_from_rows())
        steam_issues = self._player_steam_issue_map(self._players_from_rows())
        for index, row in enumerate(self.player_rows):
            account = row["account"]
            messages = []
            if account > MAX_TRANSFER_RUNTIME_ACCOUNTS:
                row["frame"].setStyleSheet(
                    f"QFrame#HelperRow {{ border-color: {IGNORED_PLAYER_COLOR}; }}"
                )
                messages.append(
                    f"Account {account} is ignored. Runtime support is currently "
                    f"limited to {MAX_TRANSFER_RUNTIME_ACCOUNTS} accounts."
                )
            elif index in steam_issues:
                row["frame"].setStyleSheet(
                    f"QFrame#HelperRow {{ border-color: {IGNORED_PLAYER_COLOR}; }}"
                )
            elif index in conflicts:
                row["frame"].setStyleSheet(
                    "QFrame#HelperRow { "
                    f"border-color: {PLAYER_SEARCH_WARNING_COLOR}; "
                    "}"
                )
            else:
                row["frame"].setStyleSheet("")

            if index in conflicts:
                name = row["name"].text().strip()
                if name:
                    matches = ", ".join(conflicts[index])
                    messages.append(f'Searching "{name}" may also match: {matches}.')
                else:
                    messages.append("Bed/teleport name cannot be empty.")
            messages.extend(steam_issues.get(index, []))
            row["frame"].setToolTip(" ".join(messages))

    def _player_steam_issue_map(self, players):
        rows = players.get("players", []) if isinstance(players, dict) else []
        issues = {index: [] for index in range(len(rows))}
        account_names = {
            str(account.get("account_name", "")).strip()
            for account in self.steam_accounts
            if isinstance(account, dict)
        }
        most_recent = most_recent_account_name(self.steam_accounts)
        seen = {}
        for index, player in enumerate(rows):
            if not isinstance(player, dict):
                player = {}
            account_name = str(player.get("steam_account", "")).strip()
            if not account_name:
                issues[index].append("Steam account is required.")
                continue
            if account_names and account_name not in account_names:
                issues[index].append(
                    "Steam account is not available in loginusers.vdf."
                )
            if account_name in seen:
                issues[index].append(
                    f"Steam account duplicates player {seen[account_name] + 1}."
                )
            else:
                seen[account_name] = index
            if index == 0 and most_recent and account_name != most_recent:
                issues[index].append(
                    "Relog Steam with this account before starting; ARK is currently controlled by another Steam user."
                )
        if self.steam_accounts_error:
            for index in issues:
                issues[index].append(
                    f"Steam accounts unavailable: {self.steam_accounts_error}"
                )
        return {index: values for index, values in issues.items() if values}

    def _runtime_player_search_conflicts(self, players):
        conflicts = player_bed_name_search_conflicts(players)
        return {
            index: matches
            for index, matches in conflicts.items()
            if index < MAX_TRANSFER_RUNTIME_ACCOUNTS
        }

    def _format_player_search_conflicts(self, conflicts, players):
        rows = players.get("players", [])
        lines = []
        for index in sorted(conflicts):
            try:
                name = str(rows[index].get("bed_name", "")).strip()
            except (IndexError, AttributeError):
                name = ""
            label = name or f"Player {index + 1}"
            lines.append(f"{label}: {', '.join(conflicts[index])}")
        return lines

    def _settings_from_fields(self):
        return {
            key: self._setting_field_value(field)
            for key, field in self.setting_fields.items()
            if key != "account_count"
        }

    def _setting_field_value(self, field: object):
        if isinstance(field, NoWheelComboBox):
            data = field.currentData()
            return field.currentText() if data is None else data
        return field.text()

    def _sync_transfer_start_mode_description(self, *_args: object):
        field = self.setting_fields["transfer_start_mode"]
        mode = str(self._setting_field_value(field)).strip()
        description = TRANSFER_START_MODE_DESCRIPTIONS.get(
            mode, TRANSFER_START_MODE_DESCRIPTIONS["default"]
        )
        field.setToolTip(description)
        if hasattr(self, "transfer_start_mode_label"):
            self.transfer_start_mode_label.setToolTip(description)
        if hasattr(self, "transfer_start_mode_description"):
            self.transfer_start_mode_description.setText(description)

    def _dedis_from_rows(self):
        return {
            "resource": self._dedi_route_from_rows("resource"),
            "destination": self._dedi_route_from_rows("destination"),
        }

    def _dedi_route_from_rows(self, side):
        teleport = getattr(self, f"{side}_dedi_teleport")
        return {
            "teleport": teleport.text(),
            "items": [
                {
                    "location": {
                        "yaw": row["yaw"].text(),
                        "pitch": row["pitch"].text(),
                    },
                    "crouched": row["crouched"].isChecked(),
                }
                for row in self._dedi_rows_for_side(side)
            ],
        }

    def _calculate_destination_dedis(self):
        try:
            settings = self._settings_from_fields()
            dedis = calculate_same_structure_destination_dedis(
                self._dedis_from_rows(),
                settings["resource_station_yaw"],
                settings["destination_station_yaw"],
            )
        except ValueError as exc:
            self.status.setText(str(exc))
            return

        self._apply_destination_dedi_route(dedis["destination"])
        if self._persist_dedis():
            self.status.setText("Destination dedis calculated from resource structure.")

    def _apply_destination_dedi_route(self, route):
        for row, item in zip(
            self.destination_dedi_rows, route.get("items", []), strict=False
        ):
            location = item.get("location", {})
            row["yaw"].setText(str(location.get("yaw", 0.0)))
            row["pitch"].setText(str(location.get("pitch", 0.0)))
            previous_blocked = row["crouched"].blockSignals(True)
            row["crouched"].setChecked(bool(item.get("crouched", False)))
            row["crouched"].blockSignals(previous_blocked)
            self._sync_dedi_summary(row)

    def _persist_settings(self):
        try:
            self.config["settings"] = save_transfer_settings(
                self._settings_from_fields()
            )
        except ValueError as exc:
            self.status.setText(str(exc))
            return False
        self.status.setText("Transfer settings saved.")
        return True

    def _persist_dedis(self):
        try:
            self.config["dedis"] = save_transfer_dedis(self._dedis_from_rows())
        except ValueError as exc:
            self.status.setText(str(exc))
            return False
        self.status.setText("Transfer dedis saved.")
        return True

    def _copy_name(self, value):
        QApplication.clipboard().setText(str(value))
        self.status.setText("Bed/teleport name copied.")

    def _capture_station_yaw(self, field):
        if not self._require_ark_window("capture yaw"):
            return
        cursor_position = QCursor.pos()
        try:
            yaw, _pitch = capture_ccc_yaw_pitch()
            field.setText(f"{yaw:.2f}")
            self._persist_settings()
            self.status.setText(f"Captured yaw {yaw:.2f}.")
        except Exception as exc:
            self.status.setText(f"Capture failed: {exc}")
        finally:
            self.refocus_helper(cursor_position)

    def _capture_dedi(self, row):
        if not self._require_ark_window("capture transfer dedi"):
            return
        cursor_position = QCursor.pos()
        try:
            yaw, pitch = capture_ccc_yaw_pitch()
            row["yaw"].setText(f"{yaw:.2f}")
            row["pitch"].setText(f"{pitch:.2f}")
            self.status.setText(f"Captured yaw {yaw:.2f}, pitch {pitch:.2f}.")
            self._autosync_transfer_count(persist=True)
            self._sync_dedi_summary(row)
            self._persist_dedis()
        except Exception as exc:
            self.status.setText(f"Capture failed: {exc}")
        finally:
            self.refocus_helper(cursor_position)

    def _view_dedi(self, row):
        if not self._require_ark_window("view transfer dedi"):
            return
        cursor_position = QCursor.pos()
        try:
            view_route_entry(
                float(row["yaw"].text()),
                float(row["pitch"].text()),
                row["crouched"].isChecked(),
            )
            self.status.setText("View applied.")
        except Exception as exc:
            self.status.setText(f"View failed: {exc}")
        finally:
            self.refocus_helper(cursor_position)

    def _panel(self, title):
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        header = QHBoxLayout()
        expanded = DEFAULT_PANELS_EXPANDED
        toggle = self._helper_button(
            "v" if expanded else ">", f"Expand or collapse {title.lower()}"
        )
        label = QLabel(title)
        label.setObjectName("PanelTitle")
        header.addWidget(toggle)
        header.addWidget(label)
        header.addStretch()
        layout.addLayout(header)
        body = QWidget()
        body.setObjectName("DepositRouteCardBody")
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        body.setVisible(expanded)
        toggle.clicked.connect(
            lambda checked=False, target=body, button=toggle: self._toggle_panel(
                target, button
            )
        )
        layout.addWidget(body)
        panel.body_widget = body
        panel.toggle_button = toggle
        self.collapsible_panels.append(panel)
        return panel, body_layout

    def set_all_collapsible_expanded(self, expanded):
        for panel in self.collapsible_panels:
            panel.body_widget.setVisible(bool(expanded))
            panel.toggle_button.setText("v" if expanded else ">")
        for row in self.resource_dedi_rows + self.destination_dedi_rows:
            row["details"].setVisible(bool(expanded))
            row["toggle"].setText("v" if expanded else ">")

    @staticmethod
    def _toggle_panel(body, button):
        visible = body.isHidden()
        body.setVisible(visible)
        button.setText("v" if visible else ">")

    @staticmethod
    def _line_edit(value):
        field = QLineEdit(str(value))
        field.setObjectName("SettingField")
        return field

    def _setting_field(self, key: str, label_text: str):
        """Create a persisted transfer setting row field."""
        label = QLabel(label_text)
        label.setObjectName("FormLabel")
        field = self._line_edit(self.config["settings"].get(key, ""))
        field.editingFinished.connect(self._persist_settings)
        field.returnPressed.connect(self._persist_settings)
        self.setting_fields[key] = field
        return label, field

    def _write_runtime_config(self, config):
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            prefix="ark_gacha_transfer_",
            suffix=".json",
        ) as handle:
            json.dump(config, handle)
        return handle.name

    def _cleanup_runtime_config(self):
        path = self.runtime_config_path
        self.runtime_config_path = None
        if not path:
            return
        with contextlib.suppress(OSError):
            os.unlink(path)

    @staticmethod
    def _labeled_row(label_text, widget):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("FormLabel")
        row.addWidget(label)
        row.addWidget(widget, 1)
        return row

    @staticmethod
    def _labeled_row_widget(label: QLabel, widget: QWidget):
        row = QHBoxLayout()
        row.addWidget(label)
        row.addWidget(widget, 1)
        return row
