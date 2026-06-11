from PySide6.QtCore import Property, QObject, Signal, Slot

from source.launcher.constants import DEFAULT_SETTINGS, HIDDEN_SETTINGS, SETTINGS_GROUPS
from source.launcher.settings_store import load_settings, save_settings
from source.launcher.station_config import load_gacha_config, load_pego_config


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
            return self._summary_fields(
                "GACHA CONFIG", self._load_count(load_gacha_config)
            )
        if self._current_group == "PEGO":
            return self._summary_fields(
                "PEGO CONFIG", self._load_count(load_pego_config)
            )
        if self._current_group == "STORAGE":
            return self._summary_fields(
                "STORAGE ROUTES", lambda: "Use helper windows for route editing."
            )

        rows = []
        for key in SETTINGS_GROUPS[self._current_group]:
            if key in HIDDEN_SETTINGS:
                continue
            value = self._settings.get(key, DEFAULT_SETTINGS[key])
            default = DEFAULT_SETTINGS[key]
            rows.append(
                {
                    "key": key,
                    "label": key.replace("_", " ").capitalize(),
                    "value": value,
                    "type": "bool" if isinstance(default, bool) else "text",
                }
            )
        return rows

    @Property(str, notify=changed)
    def serverNumber(self):
        return str(self._settings.get("server_number", "0"))

    @Property(bool, notify=changed)
    def autoStartProgram(self):
        return bool(self._settings.get("auto_start_program", False))

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

    def settings(self):
        return self._settings.copy()

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
