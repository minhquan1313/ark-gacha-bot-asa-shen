from PySide6.QtCore import Property, QObject, Signal, Slot

from source.gacha_bot.deposit_config import (
    default_crystal_route,
    default_deposit_config,
    default_grindable_route,
    load_deposit_config,
    save_deposit_config,
)
from source.launcher.constants import (
    DEFAULT_SETTINGS,
    HIDDEN_SETTINGS,
    SETTINGS_GROUPS,
    setting_label,
)
from source.launcher.settings_store import load_settings, save_settings
from source.launcher.station_config import (
    DEFAULT_PEGO_DELAY,
    default_gacha_entry,
    default_gacha_pair,
    default_pego_entry,
    grouped_gacha_entries,
    load_gacha_config,
    load_pego_config,
    next_gacha_teleporter,
    next_pego_index,
    save_gacha_config,
    save_pego_config,
    set_all_pego_delays,
)


class SettingsController(QObject):
    changed = Signal()
    saved = Signal(str)
    error = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = load_settings()
        self._current_group = "GENERAL"

    @Property("QVariantList", notify=changed)
    def groups(self):
        return list(SETTINGS_GROUPS)

    @Property(str, notify=changed)
    def currentGroup(self):
        return self._current_group

    @Property("QVariantList", notify=changed)
    def fields(self):
        if self._current_group == "GACHA":
            return self._gacha_fields()
        if self._current_group == "PEGO":
            return self._pego_fields()
        if self._current_group == "STORAGE":
            return self._storage_fields()

        rows = []
        for key in SETTINGS_GROUPS[self._current_group]:
            if key in HIDDEN_SETTINGS:
                continue
            value = self._settings.get(key, DEFAULT_SETTINGS[key])
            default = DEFAULT_SETTINGS[key]
            rows.append(
                {
                    "key": key,
                    "label": setting_label(key),
                    "value": value,
                    "type": "bool" if isinstance(default, bool) else "text",
                }
            )
        return rows

    @Property("QVariantList", notify=changed)
    def groupActions(self):
        if self._current_group == "GACHA":
            return [
                {
                    "key": "add_gacha_pair",
                    "label": "ADD GACHA PAIR",
                    "variant": "secondary",
                },
                {
                    "key": "remove_last_gacha_pair",
                    "label": "REMOVE LAST PAIR",
                    "variant": "danger",
                },
                {"key": "reset_gacha", "label": "RESET GACHA", "variant": "danger"},
            ]
        if self._current_group == "PEGO":
            return [
                {"key": "add_pego", "label": "ADD PEGO", "variant": "secondary"},
                {
                    "key": "apply_pego_delay",
                    "label": "APPLY DELAY",
                    "variant": "secondary",
                    "input": "Delay",
                },
                {
                    "key": "remove_last_pego",
                    "label": "REMOVE LAST PEGO",
                    "variant": "danger",
                },
                {"key": "reset_pego", "label": "RESET PEGO", "variant": "danger"},
            ]
        if self._current_group == "STORAGE":
            return [
                {
                    "key": "add_crystal_route",
                    "label": "ADD CRYSTAL ROUTE",
                    "variant": "secondary",
                },
                {
                    "key": "add_grindable_route",
                    "label": "ADD GRINDABLE ROUTE",
                    "variant": "secondary",
                },
                {
                    "key": "remove_last_crystal_route",
                    "label": "REMOVE LAST CRYSTAL",
                    "variant": "danger",
                },
                {
                    "key": "remove_last_grindable_route",
                    "label": "REMOVE LAST GRINDABLE",
                    "variant": "danger",
                },
                {"key": "reset_storage", "label": "RESET STORAGE", "variant": "danger"},
            ]
        return []

    @Property(str, notify=changed)
    def serverNumber(self):
        return str(self._settings.get("server_number", "0"))

    @Property(bool, notify=changed)
    def autoStartProgram(self):
        return bool(self._settings.get("auto_start_program", False))

    @Property(float, notify=changed)
    def helperInactiveOpacity(self):
        return float(self._settings.get("helper_inactive_opacity", 0.3))

    @Property(int, notify=changed)
    def launcherWidth(self):
        return int(self._settings.get("launcher_width", 1200))

    @Property(int, notify=changed)
    def launcherHeight(self):
        return int(self._settings.get("launcher_height", 800))

    @Slot(str)
    def setGroup(self, group_name):
        if group_name not in SETTINGS_GROUPS:
            return
        self._current_group = group_name
        self.changed.emit()

    @Slot(str, "QVariant")
    def setValue(self, key, value):
        if key.startswith("gacha:"):
            self._set_gacha_value(key, value)
            return
        if key.startswith("pego:"):
            self._set_pego_value(key, value)
            return
        if key.startswith("storage:"):
            self._set_storage_value(key, value)
            return
        if key not in DEFAULT_SETTINGS:
            return
        try:
            self._settings[key] = self._coerce_value(key, value)
            save_settings(self._settings)
        except Exception as exc:
            self.error.emit("Invalid Settings", str(exc))
            return
        self.saved.emit("[SUCCESS] Settings saved automatically.\n")
        self.changed.emit()

    @Slot()
    def resetVisible(self):
        for key in SETTINGS_GROUPS.get(self._current_group, []):
            if key in DEFAULT_SETTINGS:
                self._settings[key] = DEFAULT_SETTINGS[key]
        try:
            save_settings(self._settings)
        except Exception as exc:
            self.error.emit("Reset Settings", str(exc))
            return
        self.saved.emit("[INFO] Visible settings reset to defaults and saved.\n")
        self.changed.emit()

    @Slot()
    def refresh(self):
        try:
            self._settings = load_settings()
        except Exception as exc:
            self.error.emit("Refresh Configs", str(exc))
            return
        self.saved.emit("[SUCCESS] JSON config files refreshed.\n")
        self.changed.emit()

    @Slot(str, "QVariant")
    def runGroupAction(self, action, value=""):
        action = str(action)
        try:
            if action == "add_gacha_pair":
                self._add_gacha_pair()
            elif action == "remove_last_gacha_pair":
                self._remove_last_gacha_pair()
            elif action == "reset_gacha":
                save_gacha_config(default_gacha_pair())
                self.saved.emit("[INFO] Gacha config reset to defaults and saved.\n")
            elif action == "add_pego":
                self._add_pego()
            elif action == "remove_last_pego":
                self._remove_last_pego()
            elif action == "apply_pego_delay":
                self._apply_pego_delay(value)
            elif action == "reset_pego":
                save_pego_config([default_pego_entry()])
                self.saved.emit("[INFO] Pego config reset to defaults and saved.\n")
            elif action == "add_crystal_route":
                config = load_deposit_config()
                config["depositCrystalData"].append(default_crystal_route())
                save_deposit_config(config)
                self.saved.emit("[SUCCESS] Crystal route added.\n")
            elif action == "add_grindable_route":
                config = load_deposit_config()
                config["depositGrindableData"].append(default_grindable_route())
                save_deposit_config(config)
                self.saved.emit("[SUCCESS] Grindable route added.\n")
            elif action == "remove_last_crystal_route":
                self._remove_last_storage_route("depositCrystalData", "crystal")
            elif action == "remove_last_grindable_route":
                self._remove_last_storage_route("depositGrindableData", "grindable")
            elif action == "reset_storage":
                save_deposit_config(default_deposit_config())
                self.saved.emit("[INFO] Deposit routes reset to defaults and saved.\n")
            else:
                return
        except Exception as exc:
            self.error.emit("Settings Action Failed", str(exc))
            return
        self.changed.emit()

    def settings(self):
        return self._settings.copy()

    def _add_gacha_pair(self):
        entries = load_gacha_config()
        teleporter = next_gacha_teleporter(entries)
        entries.extend(
            [
                default_gacha_entry(f"{teleporter}_left", teleporter, "left"),
                default_gacha_entry(f"{teleporter}_right", teleporter, "right"),
            ]
        )
        save_gacha_config(entries)
        self.saved.emit("[SUCCESS] Gacha pair added.\n")

    def _remove_last_gacha_pair(self):
        entries = load_gacha_config()
        groups = grouped_gacha_entries(entries)
        if len(groups) <= 1:
            self.saved.emit("[INFO] At least one gacha pair must remain.\n")
            return

        last_teleporter, last_group = groups[-1]
        indexes_to_remove = {index for index, _entry in last_group}
        entries = [
            entry
            for index, entry in enumerate(entries)
            if index not in indexes_to_remove
        ]
        save_gacha_config(entries)
        self.saved.emit(f"[SUCCESS] Removed gacha pair {last_teleporter}.\n")

    def _add_pego(self):
        entries = load_pego_config()
        delay = entries[-1]["delay"] if entries else DEFAULT_PEGO_DELAY
        entries.append(default_pego_entry(next_pego_index(entries), delay))
        save_pego_config(entries)
        self.saved.emit("[SUCCESS] Pego added.\n")

    def _remove_last_pego(self):
        entries = load_pego_config()
        if not entries:
            self.saved.emit("[INFO] No pego entries to remove.\n")
            return
        entries.pop()
        save_pego_config(entries)
        self.saved.emit("[SUCCESS] Last pego removed.\n")

    def _apply_pego_delay(self, value):
        entries = load_pego_config()
        set_all_pego_delays(entries, value)
        save_pego_config(entries)
        self.saved.emit("[SUCCESS] Pego delay applied to all entries.\n")

    def _remove_last_storage_route(self, key, label):
        config = load_deposit_config()
        routes = config.get(key, [])
        if len(routes) <= 1:
            self.saved.emit(f"[INFO] At least one {label} route must remain.\n")
            return
        routes.pop()
        save_deposit_config(config)
        self.saved.emit(f"[SUCCESS] Last {label} route removed.\n")

    def _coerce_value(self, key, value):
        default = DEFAULT_SETTINGS[key]
        if isinstance(default, bool):
            return bool(value)
        if isinstance(default, int):
            return int(value)
        if isinstance(default, float):
            return float(value)
        return str(value)

    @staticmethod
    def _summary_fields(title, value_func):
        try:
            value = value_func()
        except Exception as exc:
            value = f"Unable to load: {exc}"
        return [{"key": "", "label": title, "value": value, "type": "summary"}]

    @staticmethod
    def _load_count(loader):
        def count():
            data = loader()
            return f"{len(data)} entries loaded."

        return count

    @staticmethod
    def _field(key, label, value, field_type="text", options=None):
        return {
            "key": key,
            "label": label,
            "value": value,
            "type": field_type,
            "options": list(options or []),
        }

    def _gacha_fields(self):
        try:
            entries = load_gacha_config()
        except Exception as exc:
            return self._summary_fields(
                "GACHA CONFIG", lambda: f"Unable to load: {exc}"
            )
        rows = []
        for index, entry in enumerate(entries):
            prefix = f"Gacha {index + 1}"
            rows.append(
                self._field(
                    f"gacha:{index}:name", f"{prefix} name", entry.get("name", "")
                )
            )
            rows.append(
                self._field(
                    f"gacha:{index}:teleporter",
                    f"{prefix} teleporter",
                    entry.get("teleporter", ""),
                )
            )
            side = str(entry.get("side", "left")).lower()
            rows.append(
                self._field(
                    f"gacha:{index}:side",
                    f"{prefix} side",
                    side if side in {"left", "right"} else "left",
                    "options",
                    ["left", "right"],
                )
            )
        return rows

    def _pego_fields(self):
        try:
            entries = load_pego_config()
        except Exception as exc:
            return self._summary_fields("PEGO CONFIG", lambda: f"Unable to load: {exc}")
        rows = []
        for index, entry in enumerate(entries):
            prefix = f"Pego {index + 1}"
            rows.append(
                self._field(
                    f"pego:{index}:name", f"{prefix} name", entry.get("name", "")
                )
            )
            rows.append(
                self._field(
                    f"pego:{index}:teleporter",
                    f"{prefix} teleporter",
                    entry.get("teleporter", ""),
                )
            )
            rows.append(
                self._field(
                    f"pego:{index}:delay", f"{prefix} delay", entry.get("delay", "")
                )
            )
        return rows

    def _storage_fields(self):
        try:
            config = load_deposit_config()
        except Exception as exc:
            return self._summary_fields(
                "STORAGE ROUTES", lambda: f"Unable to load: {exc}"
            )
        rows = []
        for index, route in enumerate(config.get("depositCrystalData", [])):
            prefix = f"Crystal route {index + 1}"
            rows.append(
                self._field(
                    f"storage:crystal:{index}:teleport",
                    f"{prefix} teleport",
                    route.get("teleport", ""),
                )
            )
            rows.extend(
                self._object_fields(
                    "crystal",
                    index,
                    "dedi",
                    route.get("dedi", {}).get("items", []),
                    f"{prefix} dedi",
                )
            )
            rows.extend(
                self._object_fields(
                    "crystal",
                    index,
                    "vault",
                    route.get("vault", {}).get("items", []),
                    f"{prefix} vault",
                    vault=True,
                )
            )
        for index, route in enumerate(config.get("depositGrindableData", [])):
            prefix = f"Grindable route {index + 1}"
            grinder = route.get("grinder", {})
            location = grinder.get("location", {})
            rows.append(
                self._field(
                    f"storage:grindable:{index}:teleport",
                    f"{prefix} teleport",
                    route.get("teleport", ""),
                )
            )
            rows.append(
                self._field(
                    f"storage:grindable:{index}:grinder:active",
                    f"{prefix} grinder active",
                    grinder.get("active", False),
                    "bool",
                )
            )
            rows.append(
                self._field(
                    f"storage:grindable:{index}:grinder:yaw",
                    f"{prefix} grinder yaw",
                    location.get("yaw", ""),
                )
            )
            rows.append(
                self._field(
                    f"storage:grindable:{index}:grinder:pitch",
                    f"{prefix} grinder pitch",
                    location.get("pitch", ""),
                )
            )
            rows.append(
                self._field(
                    f"storage:grindable:{index}:grinder:crouched",
                    f"{prefix} grinder crouched",
                    grinder.get("crouched", False),
                    "bool",
                )
            )
            rows.extend(
                self._object_fields(
                    "grindable",
                    index,
                    "dedi",
                    route.get("dedi", {}).get("items", []),
                    f"{prefix} dedi",
                )
            )
        return rows

    def _object_fields(
        self, route_kind, route_index, object_kind, items, label, vault=False
    ):
        rows = []
        for item_index, item in enumerate(items):
            prefix = f"{label} {item_index + 1}"
            location = item.get("location", {})
            key_prefix = (
                f"storage:{route_kind}:{route_index}:{object_kind}:{item_index}"
            )
            rows.append(
                self._field(
                    f"{key_prefix}:yaw", f"{prefix} yaw", location.get("yaw", "")
                )
            )
            rows.append(
                self._field(
                    f"{key_prefix}:pitch", f"{prefix} pitch", location.get("pitch", "")
                )
            )
            rows.append(
                self._field(
                    f"{key_prefix}:crouched",
                    f"{prefix} crouched",
                    item.get("crouched", False),
                    "bool",
                )
            )
            if vault:
                rows.append(
                    self._field(
                        f"{key_prefix}:items",
                        f"{prefix} items",
                        ", ".join(item.get("items", [])),
                    )
                )
        if not items:
            rows.append(
                self._field(
                    "",
                    label,
                    "No rows configured. Use the Deposit Route Helper to add rows.",
                    "summary",
                )
            )
        return rows

    def _set_gacha_value(self, key, value):
        try:
            _prefix, index, field = key.split(":", 2)
            entries = load_gacha_config()
            index = self._coerce_config_index(index, len(entries), "gacha")
            if field not in {"name", "teleporter", "side"}:
                raise ValueError("Unknown gacha field.")
            if field == "side":
                value = str(value).lower()
                if value not in {"left", "right"}:
                    self.error.emit(
                        "Invalid Gacha Config",
                        "side must be left or right.",
                    )
                    return
            entries[index][field] = str(value)
            save_gacha_config(entries)
        except Exception as exc:
            self.error.emit("Invalid Gacha Config", str(exc))
            return
        self.saved.emit("[SUCCESS] Gacha config saved automatically.\n")
        self.changed.emit()

    def _set_pego_value(self, key, value):
        try:
            _prefix, index, field = key.split(":", 2)
            entries = load_pego_config()
            index = self._coerce_config_index(index, len(entries), "pego")
            if field not in {"name", "teleporter", "delay"}:
                raise ValueError("Unknown pego field.")
            entries[index][field] = int(value) if field == "delay" else str(value)
            save_pego_config(entries)
        except Exception as exc:
            self.error.emit("Invalid Pego Config", str(exc))
            return
        self.saved.emit("[SUCCESS] Pego config saved automatically.\n")
        self.changed.emit()

    def _set_storage_value(self, key, value):
        parts = key.split(":")
        config = load_deposit_config()
        try:
            route = self._storage_route(config, parts[1], int(parts[2]))
            self._apply_storage_value(route, parts[3:], value)
            save_deposit_config(config)
        except Exception as exc:
            self.error.emit("Invalid Storage Config", str(exc))
            return
        self.saved.emit("[SUCCESS] Storage routes saved automatically.\n")
        self.changed.emit()

    @staticmethod
    def _storage_route(config, route_kind, route_index):
        if route_kind == "crystal":
            routes = config["depositCrystalData"]
        elif route_kind == "grindable":
            routes = config["depositGrindableData"]
        else:
            raise ValueError("Unknown storage route kind.")
        if route_index < 0 or route_index >= len(routes):
            raise ValueError("Unknown storage route index.")
        return routes[route_index]

    @staticmethod
    def _apply_storage_value(route, path, value):
        if not path:
            raise ValueError("Unknown storage path.")
        if path == ["teleport"]:
            route["teleport"] = str(value)
            return
        if path[0] == "grinder":
            if len(path) != 2:
                raise ValueError("Unknown grinder path.")
            grinder = route["grinder"]
            field = path[1]
            if field == "active":
                grinder["active"] = bool(value)
            elif field == "crouched":
                grinder["crouched"] = bool(value)
            elif field in {"yaw", "pitch"}:
                grinder["location"][field] = float(value)
            else:
                raise ValueError("Unknown grinder field.")
            return

        if len(path) != 3 or path[0] not in {"dedi", "vault"}:
            raise ValueError("Unknown storage path.")
        item_index = int(path[1])
        items = route[path[0]]["items"]
        if item_index < 0 or item_index >= len(items):
            raise ValueError("Unknown storage item index.")
        container = items[item_index]
        field = path[2]
        if field == "crouched":
            container["crouched"] = bool(value)
        elif field in {"yaw", "pitch"}:
            container["location"][field] = float(value)
        elif field == "items":
            container["items"] = [
                item.strip() for item in str(value).split(",") if item.strip()
            ]
        else:
            raise ValueError("Unknown storage field.")

    def _coerce_config_index(self, index, row_count, label):
        try:
            index = int(index)
        except (TypeError, ValueError):
            raise ValueError(f"Unknown {label} index.")
        if index < 0 or index >= row_count:
            raise ValueError(f"Unknown {label} index.")
        return index
