import json
import os
import tempfile

from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from source.launcher.controllers.helpers.base_worker_helper import (
    BaseWorkerHelperController,
)
from source.launcher.deposit_helper_capture import (
    capture_ccc_yaw_pitch,
    preload_capture_view_dependencies,
    view_route_entry,
)
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
    suggested_loop_count,
)


class TransferHelperController(BaseWorkerHelperController):
    configChanged = Signal()

    def __init__(self, launcher_controller, parent=None):
        super().__init__(launcher_controller, "server_transfer", parent)
        self.config = load_transfer_runtime_config(create_missing=True)
        self.config["dedis"] = normalize_transfer_dedis(self.config.get("dedis", {}))
        self.runtime_config_path = None
        self._preload_capture_view()

    @Property("QVariantList", notify=configChanged)
    def settingRows(self):
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
            ("loop_count", "Loops"),
        ]
        result = []
        for key, label in rows:
            value = (
                player_account_count(self.config.get("players", {}))
                if key == "account_count"
                else settings.get(key, "")
            )
            result.append(
                {
                    "key": key,
                    "label": label,
                    "value": str(value),
                    "capture": key
                    in {"resource_station_yaw", "destination_station_yaw"},
                }
            )
        return result

    @Property("QVariantList", notify=configChanged)
    def playerRows(self):
        conflicts = player_bed_name_search_conflicts(
            self.config.get("players", {}), limit=MAX_TRANSFER_RUNTIME_ACCOUNTS
        )
        rows = []
        for index, player in enumerate(
            self.config.get("players", {}).get("players", [])
        ):
            warning = ", ".join(conflicts.get(index, []))
            if index >= MAX_TRANSFER_RUNTIME_ACCOUNTS:
                warning = (
                    f"Account {index + 1} is ignored. Runtime support is limited "
                    f"to {MAX_TRANSFER_RUNTIME_ACCOUNTS} accounts."
                )
            rows.append(
                {
                    "index": index,
                    "label": f"P{index + 1}",
                    "bedName": player.get("bed_name", ""),
                    "warning": warning,
                }
            )
        return rows

    @Property("QVariantList", notify=configChanged)
    def resourceDedis(self):
        return self._dedi_rows("resource")

    @Property("QVariantList", notify=configChanged)
    def destinationDedis(self):
        return self._dedi_rows("destination")

    @Property(str, notify=configChanged)
    def resourceTeleport(self):
        return self.config["dedis"]["resource"].get("teleport", "")

    @Property(str, notify=configChanged)
    def destinationTeleport(self):
        return self.config["dedis"]["destination"].get("teleport", "")

    @Property(str, notify=configChanged)
    def loopHint(self):
        resource_count = len(self.config["dedis"]["resource"].get("items", []))
        account_count = player_account_count(self.config.get("players", {}))
        if account_count <= 0:
            return f"{resource_count} dedi x 0 account = no runnable accounts."
        effective_accounts = min(account_count, MAX_TRANSFER_RUNTIME_ACCOUNTS)
        suffix = (
            f" Only first {effective_accounts} account(s) run."
            if account_count > effective_accounts
            else ""
        )
        return (
            f"{resource_count} dedi x {effective_accounts} account = "
            f"{suggested_loop_count(resource_count, effective_accounts)} "
            f"suggested loop(s).{suffix}"
        )

    @Slot(str, str)
    def updateSetting(self, key, value):
        if key == "account_count":
            self.resizePlayers(value)
            return
        proposed = dict(self.config["settings"])
        proposed[str(key)] = value
        try:
            self.config["settings"] = save_transfer_settings(proposed)
            self._set_status("Settings saved.")
        except Exception as exc:
            self._set_status(f"Settings save failed: {exc}")
            self.dialogRequested.emit("Invalid Transfer Settings", str(exc), "error")
        self.configChanged.emit()

    @Slot(str, int, str)
    def updatePlayer(self, key, index, value):
        if key != "bed_name":
            return
        index = self._coerce_player_index(index, allow_append=True)
        if index is None:
            return
        players = self.config["players"].setdefault("players", [])
        while len(players) <= index:
            players.append({"bed_name": f"BBedPlayer{len(players) + 1}"})
        players[index]["bed_name"] = str(value)
        self._persist_players()

    @Slot()
    def addPlayer(self):
        players = self.config["players"].setdefault("players", [])
        players.append({"bed_name": f"BBedPlayer{len(players) + 1}"})
        self._persist_players()

    @Slot("QVariant")
    def resizePlayers(self, account_count):
        try:
            account_count = int(account_count)
            if account_count < 0:
                raise ValueError("account_count must be at least 0.")
        except (TypeError, ValueError) as exc:
            self.dialogRequested.emit("Invalid Transfer Players", str(exc), "error")
            return
        players = self.config["players"].get("players", [])
        if not isinstance(players, list):
            players = []
        merged = [
            dict(player) if isinstance(player, dict) else {} for player in players
        ]
        for account in range(len(merged) + 1, account_count + 1):
            merged.append({"bed_name": f"BBedPlayer{account}"})
        self.config["players"] = normalize_transfer_players(
            {"players": merged}, account_count
        )
        self._persist_players()

    @Slot(int)
    def removePlayer(self, index):
        players = self.config["players"].setdefault("players", [])
        index = self._coerce_player_index(index, len(players))
        if index is None:
            return
        del players[index]
        self._persist_players()

    @Slot(int)
    def copyPlayerName(self, index):
        players = self.config.get("players", {}).get("players", [])
        index = self._coerce_player_index(index, len(players))
        if index is None:
            return
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(str(players[index].get("bed_name", "")))
            self._set_status("Player name copied.")

    @Slot(str)
    def captureSettingYaw(self, key):
        key = str(key)
        if key not in {"resource_station_yaw", "destination_station_yaw"}:
            return
        if not self.launcher_controller.require_ark_window("capture transfer yaw"):
            return
        try:
            yaw, _pitch = capture_ccc_yaw_pitch()
            self.config["settings"][key] = yaw
            self._persist_settings()
            self._set_status(f"Captured yaw {yaw:.2f}.")
        except Exception as exc:
            self._set_status(f"Capture failed: {exc}")
            self.dialogRequested.emit("Capture Failed", str(exc), "error")
        finally:
            self._refocus_helper()

    @Slot(str, str)
    def setTeleport(self, side, value):
        route = self._dedi_route(side)
        if route is None:
            return
        route["teleport"] = str(value)
        self._persist_dedis()

    @Slot(str)
    def addDedi(self, side):
        route = self._dedi_route(side)
        if route is None:
            return
        route.setdefault("items", []).append(
            {"location": {"yaw": 0.0, "pitch": 0.0}, "crouched": False}
        )
        self._persist_dedis()

    @Slot(str, int)
    def removeDedi(self, side, index):
        route = self._dedi_route(side)
        if route is None:
            return
        items = route.setdefault("items", [])
        index = self._coerce_dedi_index(index, len(items))
        if index is None:
            return
        if len(items) <= 1:
            self._set_status("At least one transfer dedi row is required.")
            return
        del items[index]
        self._persist_dedis()

    @Slot(str, int, str, "QVariant")
    def updateDedi(self, side, index, key, value):
        item = self._dedi_item(side, index)
        if item is None:
            return
        try:
            if key in {"yaw", "pitch"}:
                item["location"][str(key)] = float(value)
            elif key == "crouched":
                item["crouched"] = bool(value)
        except ValueError as exc:
            self.dialogRequested.emit("Invalid Transfer Dedi", str(exc), "error")
            return
        self._persist_dedis()

    @Slot(str, int)
    def captureDedi(self, side, index):
        item = self._dedi_item(side, index)
        if item is None:
            return
        if not self.launcher_controller.require_ark_window("capture transfer dedi"):
            return
        try:
            yaw, pitch = capture_ccc_yaw_pitch()
            item["location"]["yaw"] = yaw
            item["location"]["pitch"] = pitch
            self._persist_dedis()
            self._set_status(f"Captured yaw {yaw:.2f}, pitch {pitch:.2f}.")
        except Exception as exc:
            self._set_status(f"Capture failed: {exc}")
            self.dialogRequested.emit("Capture Failed", str(exc), "error")
        finally:
            self._refocus_helper()

    @Slot(str, int)
    def viewDedi(self, side, index):
        item = self._dedi_item(side, index)
        if item is None:
            return
        if not self.launcher_controller.require_ark_window("view transfer dedi"):
            return
        try:
            location = item["location"]
            view_route_entry(
                location["yaw"], location["pitch"], item.get("crouched", False)
            )
            self._set_status("View applied.")
        except Exception as exc:
            self._set_status(f"View failed: {exc}")
            self.dialogRequested.emit("View Failed", str(exc), "error")
        finally:
            self._refocus_helper()

    @Slot()
    def start(self):
        if self.running:
            return
        if (
            self.launcher_controller.is_running()
            or self.launcher_controller.program_stopping
        ):
            self._set_status("Cannot start while the main program is running.")
            self.dialogRequested.emit(
                "Stop Program First",
                "Stop the running automation before starting this tool.",
                "warning",
            )
            return
        conflicts = player_bed_name_search_conflicts(
            self.config.get("players", {}), limit=MAX_TRANSFER_RUNTIME_ACCOUNTS
        )
        if conflicts:
            conflict_lines = self._format_player_search_conflicts(
                conflicts, self.config.get("players", {})
            )
            message = "Player bed/teleport names are not search-safe:\n" + "\n".join(
                f"- {line}" for line in conflict_lines
            )
            self._set_status("Player bed/teleport names are not search-safe.")
            self.dialogRequested.emit("Transfer Helper Not Ready", message, "warning")
            return
        missing = missing_runtime_inputs(
            self.config["settings"],
            self.config["dedis"],
            self.config["ui_coords"],
            self.config["players"],
        )
        if missing:
            message = "\n".join(missing)
            self._set_status("Transfer config is incomplete.")
            self.dialogRequested.emit("Transfer Config Blocked", message, "warning")
            return
        if not self._can_start("start server transfer"):
            return
        temp = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, suffix=".json"
        )
        json.dump(self.config, temp, indent=2)
        temp.close()
        self.runtime_config_path = temp.name
        self._set_status("Starting server transfer...")
        self._start_worker("--config", self.runtime_config_path)

    def _worker_finished(self, message):
        super()._worker_finished(message)
        if self.runtime_config_path and os.path.exists(self.runtime_config_path):
            try:
                os.remove(self.runtime_config_path)
            except OSError:
                pass
        self.runtime_config_path = None

    def _format_player_search_conflicts(self, conflicts, players):
        rows = players.get("players", []) if isinstance(players, dict) else []
        lines = []
        for index in sorted(conflicts):
            try:
                name = str(rows[index].get("bed_name", "")).strip()
            except (IndexError, AttributeError):
                name = ""
            label = name or f"Player {index + 1}"
            lines.append(f'{label}: {", ".join(conflicts[index])}')
        return lines

    def _dedi_rows(self, side):
        rows = []
        for index, item in enumerate(self.config["dedis"][side].get("items", [])):
            location = item.get("location", {})
            rows.append(
                {
                    "index": index,
                    "label": f"D{index + 1}",
                    "yaw": str(location.get("yaw", 0.0)),
                    "pitch": str(location.get("pitch", 0.0)),
                    "crouched": bool(item.get("crouched", False)),
                }
            )
        return rows

    def _dedi_route(self, side):
        side = str(side)
        if side not in {"resource", "destination"}:
            self._set_status("Unknown transfer dedi side.")
            return None
        return self.config["dedis"][side]

    def _coerce_dedi_index(self, index, row_count):
        try:
            index = int(index)
        except (TypeError, ValueError):
            self._set_status("Unknown transfer dedi index.")
            return None
        if not 0 <= index < row_count:
            self._set_status("Unknown transfer dedi index.")
            return None
        return index

    def _dedi_item(self, side, index):
        route = self._dedi_route(side)
        if route is None:
            return None
        items = route.setdefault("items", [])
        index = self._coerce_dedi_index(index, len(items))
        if index is None:
            return None
        return items[index]

    def _coerce_player_index(self, index, row_count=None, allow_append=False):
        try:
            index = int(index)
        except (TypeError, ValueError):
            self._set_status("Unknown transfer player index.")
            return None
        if index < 0:
            self._set_status("Unknown transfer player index.")
            return None
        if row_count is not None and not allow_append and index >= row_count:
            self._set_status("Unknown transfer player index.")
            return None
        return index

    def _persist_settings(self):
        try:
            self.config["settings"] = save_transfer_settings(self.config["settings"])
            self._set_status("Settings saved.")
        except Exception as exc:
            self.dialogRequested.emit("Invalid Transfer Settings", str(exc), "error")
        self.configChanged.emit()

    def _persist_players(self):
        count = len(self.config.get("players", {}).get("players", []))
        try:
            self.config["players"] = save_transfer_players(
                self.config["players"], account_count=count
            )
            self._set_status("Players saved.")
        except Exception as exc:
            self.dialogRequested.emit("Invalid Transfer Players", str(exc), "error")
        self.configChanged.emit()

    def _persist_dedis(self):
        try:
            self.config["dedis"] = save_transfer_dedis(self.config["dedis"])
            self._set_status("Dedis saved.")
        except Exception as exc:
            self.dialogRequested.emit("Invalid Transfer Dedis", str(exc), "error")
        self.configChanged.emit()

    def _refocus_helper(self):
        refocus = getattr(self.launcher_controller, "refocus_active_helper", None)
        if refocus is not None:
            refocus()

    def _preload_capture_view(self):
        try:
            preload_capture_view_dependencies()
        except Exception as exc:
            self._set_status(f"Capture preload skipped: {exc}")
