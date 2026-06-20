import json
import os
import tempfile

from PySide6.QtCore import Signal
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
from source.launcher.deposit_helper_capture import (
    capture_ccc_yaw_pitch,
    focus_game_window,
    preload_capture_view_dependencies,
    register_alt_n_hotkey,
    unregister_hotkey,
    view_route_entry,
)
from source.launcher.helper_window import WorkerHelperWindow
from source.launcher.steam_accounts import load_steam_accounts, most_recent_account_name
from source.launcher.transfer_helper_config import (
    MAX_TRANSFER_RUNTIME_ACCOUNTS,
    load_transfer_runtime_config,
    missing_runtime_inputs,
    normalize_transfer_dedis,
    normalize_transfer_players,
    player_account_count,
    player_bed_name_search_conflicts,
    save_transfer_dedis,
    save_transfer_players,
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

DEFAULT_PANELS_EXPANDED = True
PLAYER_SEARCH_WARNING_COLOR = "#ffb020"
IGNORED_PLAYER_COLOR = "#ff4d6d"


class ServerTransferHelper(WorkerHelperWindow):
    status_changed = Signal(str)
    worker_finished = Signal(str)

    def __init__(self, owner):
        self.setting_fields = {}
        self.dedi_rows = []
        self.resource_dedi_rows = self.dedi_rows
        self.destination_dedi_rows = []
        self.player_rows = []
        self.collapsible_panels = []
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
        self.worker_finished.connect(self._on_worker_finished)
        self.runtime_config_path = None

    def _build_ui(self):
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

        controls = QHBoxLayout()
        controls.setSpacing(8)
        expand_all = AnimatedButton("EXPAND ALL", "secondary")
        collapse_all = AnimatedButton("COLLAPSE ALL", "secondary")
        expand_all.clicked.connect(lambda: self.set_all_collapsible_expanded(True))
        collapse_all.clicked.connect(lambda: self.set_all_collapsible_expanded(False))
        controls.addWidget(expand_all)
        controls.addWidget(collapse_all)
        content_layout.addLayout(controls)

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
        content_layout.addWidget(players_card)

        resource_card = self._build_dedi_section("resource", "RESOURCE DEDIS")
        content_layout.addWidget(resource_card)
        destination_card = self._build_dedi_section("destination", "DESTINATION DEDIS")
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
        rows = [
            ("lag_offset", "Lag offset"),
            ("resource_station_yaw", "Resource yaw"),
            ("destination_station_yaw", "Destination yaw"),
            ("transmitter_teleport", "Transmitter teleport"),
            ("resource_server", "Resource server"),
            ("destination_server", "Destination server"),
            ("account_count", "Accounts"),
            ("structure_load_delay", "Delay on logged in"),
            ("transfer_retry_delay", "Retry transfer delay"),
        ]
        for index, (key, label_text) in enumerate(rows):
            row = index
            column = 0
            label = QLabel(label_text)
            label.setObjectName("FormLabel")
            value = (
                player_account_count(self.config.get("players", {}))
                if key == "account_count"
                else settings.get(key, "")
            )
            field = self._line_edit(value)
            if key in {"resource_station_yaw", "destination_station_yaw"}:
                row_layout = QHBoxLayout()
                row_layout.setSpacing(4)
                row_layout.setContentsMargins(0, 0, 0, 0)
                capture = self._helper_button("C", f"Capture {label_text.lower()}")
                capture.clicked.connect(
                    lambda checked=False, target=field: self._capture_yaw(target)
                )
                row_layout.addWidget(field, 1)
                row_layout.addWidget(capture)
                value_widget = QWidget()
                value_widget.setLayout(row_layout)
            else:
                value_widget = field
            if key == "account_count":
                field.editingFinished.connect(
                    lambda: self._refresh_player_rows(persist=True)
                )
                field.returnPressed.connect(
                    lambda: self._refresh_player_rows(persist=True)
                )
            else:
                field.editingFinished.connect(self._persist_settings)
                field.returnPressed.connect(self._persist_settings)
            field.editingFinished.connect(self._sync_loop_hint)
            self.setting_fields[key] = field
            grid.addWidget(label, row, column)
            grid.addWidget(value_widget, row, column + 1)
        loop_row = len(rows) + 1
        loop_label = QLabel("LOOPS")
        loop_label.setObjectName("FormLabel")
        loop_field = self._line_edit(settings.get("loop_count", ""))
        loop_field.editingFinished.connect(self._sync_loop_hint)
        loop_field.editingFinished.connect(self._persist_settings)
        loop_field.returnPressed.connect(self._persist_settings)
        self.setting_fields["loop_count"] = loop_field
        grid.addWidget(loop_label, loop_row, 0)
        grid.addWidget(loop_field, loop_row, 1)
        self.loop_hint = WrappedStatusLabel("")
        self.loop_hint.setObjectName("HelperStatus")
        grid.addWidget(self.loop_hint, loop_row + 1, 0, 1, 2)
        grid.setColumnStretch(1, 1)

    def _build_dedi_section(self, side, title):
        card, layout = self._panel(title)
        route = self.config["dedis"].get(side, {})
        teleport = self._line_edit(route.get("teleport", ""))
        teleport.editingFinished.connect(self._sync_loop_hint)
        teleport.editingFinished.connect(self._persist_dedis)
        teleport.returnPressed.connect(self._persist_dedis)
        setattr(self, f"{side}_dedi_teleport", teleport)
        if side == "resource":
            self.dedi_teleport = teleport
        layout.addLayout(self._labeled_row("TELEPORT", teleport))
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
            lambda checked=False, target_side=side: self._add_dedi_row(
                side=target_side, persist=True
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

    def _add_dedi_row(self, item=None, persist=False, side="resource"):
        item = item or {
            "location": {"yaw": 0.0, "pitch": 0.0},
            "crouched": False,
        }
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
                widget.editingFinished.connect(self._sync_loop_hint)
                widget.editingFinished.connect(
                    lambda target=data: self._sync_dedi_summary(target)
                )
                widget.editingFinished.connect(self._persist_dedis)
            if hasattr(widget, "toggled"):
                widget.toggled.connect(lambda _checked=False: self._sync_loop_hint())
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
        rows.remove(row_data)
        row_data["frame"].deleteLater()
        self._renumber_dedi_rows(side)
        self._sync_loop_hint()
        self._persist_dedis()

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
        self.config["settings"] = save_transfer_settings(self._settings_from_fields())
        self.config["dedis"] = save_transfer_dedis(self._dedis_from_rows())
        self.config["players"] = self._save_players_from_rows()
        self.config["ui_coords"] = save_transfer_ui_coords(self.config["ui_coords"])
        self.config["steam_accounts"] = self.steam_accounts
        return self.config

    def _sync_loop_hint(self):
        try:
            account_count = int(self.setting_fields["account_count"].text())
            active_count = len(self.resource_dedi_rows)
            if account_count == 0:
                self.loop_hint.setText(
                    f"{active_count} dedi x 0 account = no runnable accounts."
                )
                return
            effective_accounts = min(account_count, MAX_TRANSFER_RUNTIME_ACCOUNTS)
            suggested = suggested_loop_count(active_count, effective_accounts)
            suffix = (
                f" Only first {effective_accounts} account(s) run."
                if account_count > effective_accounts
                else ""
            )
            self.loop_hint.setText(
                f"{active_count} dedi x {effective_accounts} account = "
                f"{suggested} suggested loop(s).{suffix}"
            )
        except Exception as exc:
            self.loop_hint.setText(f"Loop hint unavailable: {exc}")

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
            config["ui_coords"],
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
        self.status.setText("Starting server transfer helper...")
        self.runtime_config_path = self._write_runtime_config(config)
        self._start_worker("server_transfer", "--config", self.runtime_config_path)

    def stop(self):
        if not self.is_running():
            return
        super().stop()
        self.running_stop_button.setEnabled(False)
        self.running_summary.setText("Stopping...")
        self.status.setText("Stopping...")

    def _append_status(self, message):
        self.running_summary.setText(message)
        self.status.setText(message)
        self.running_log.append(message)

    def _on_worker_finished(self, message):
        if self._finish_worker():
            return
        self._cleanup_runtime_config()
        self.running_stop_button.setEnabled(True)
        self.status.setText(message)

    def _set_running_ui(self, running):
        if running:
            self.running_ui_active = True
            self.idle_widget.setVisible(False)
            self.running_widget.setVisible(True)
            self.hotkey_label.setText(self.running_hotkey_hint)
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            self.setFixedWidth(self.idle_width)
            running_height = self._height_for_width(self.idle_width)
            self.setFixedHeight(running_height)
            self.resize(self.idle_width, running_height)
        else:
            self.setMaximumHeight(16777215)
            self.setFixedWidth(self.idle_width)
            self.setMinimumHeight(self.idle_min_height)
            self.running_widget.setVisible(False)
            self.idle_widget.setVisible(True)
            self.hotkey_label.setText(self.hotkey_hint)
            self.resize(self.idle_width, self._idle_content_height())
            self.running_ui_active = False
        self._position_middle_right()
        self.start_stop_button.setText("STOP" if running else "START")
        self.start_stop_button.set_variant("danger" if running else "primary")

    def _preload_capture_view(self):
        try:
            preload_capture_view_dependencies()
        except Exception as exc:
            self.status.setText(f"Capture preload skipped: {exc}")

    def _refresh_player_rows(self, persist=False):
        if not hasattr(self, "players_layout"):
            return
        try:
            account_count = self._account_count_from_field()
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        if self.player_rows:
            source_players = self._players_from_rows()
        else:
            source_players = self.config.get("players", {})
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
                    account_count=account_count,
                )
            except ValueError as exc:
                self.status.setText(str(exc))
                return
            self.status.setText("Player settings saved.")
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
        info = QHBoxLayout()
        info.addWidget(label)
        info.addWidget(QLabel("Bed/Teleport"))
        info.addWidget(name, 1)
        info.addWidget(copy)

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
        self.player_rows.append(
            {"frame": row, "name": name, "steam": steam, "account": account}
        )

    def _account_count_from_field(self):
        try:
            account_count = int(self.setting_fields["account_count"].text())
        except KeyError as exc:
            raise ValueError("account_count field is missing.") from exc
        except ValueError as exc:
            raise ValueError("account_count must be an integer.") from exc
        if account_count < 0:
            raise ValueError("account_count must be at least 0.")
        return account_count

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

    def _save_players_from_rows(self):
        try:
            players = save_transfer_players(
                self._players_from_rows(),
                account_count=self._account_count_from_field(),
            )
        except ValueError as exc:
            self.status.setText(str(exc))
            return self.config.get("players", {})
        self.config["players"] = players
        self.status.setText("Player settings saved.")
        self._sync_player_search_warnings()
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
            lines.append(f'{label}: {", ".join(conflicts[index])}')
        return lines

    def _settings_from_fields(self):
        return {
            key: field.text()
            for key, field in self.setting_fields.items()
            if key != "account_count"
        }

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

    def _capture_yaw(self, field):
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
            self._sync_loop_hint()
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

    def _write_runtime_config(self, config):
        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            prefix="ark_gacha_transfer_",
            suffix=".json",
        )
        with handle:
            json.dump(config, handle)
        return handle.name

    def _cleanup_runtime_config(self):
        path = self.runtime_config_path
        self.runtime_config_path = None
        if not path:
            return
        try:
            os.unlink(path)
        except OSError:
            pass

    @staticmethod
    def _labeled_row(label_text, widget):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("FormLabel")
        row.addWidget(label)
        row.addWidget(widget, 1)
        return row
