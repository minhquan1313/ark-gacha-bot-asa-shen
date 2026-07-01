try:
    import psutil
except ImportError:
    psutil = None


from PySide6.QtCore import QTimer

from source.launcher import ark_game_setup
from source.launcher.config.constants import (
    DEFAULT_SETTINGS,
    GAME_WINDOW_TITLE,
    SUPPORTED_GAME_RESOLUTIONS,
    TEMPLATE_REFERENCE_DEFAULTS,
)
from source.launcher.config.template_settings import DEFAULT_TEMPLATE_FILENAME
from source.launcher.utils.settings_store import save_settings
from source.launcher.utils.system import (
    find_window_size,
)

START_GAME_DISABLE_DELAY = 10000
RUNNER_READY_MESSAGE = "__RUNNER_READY__"


class SettingsStateGuiMixin:
    def _update_game_restore_button_visibility(self):
        button = getattr(self, "restore_game_settings_button", None)
        if button is not None:
            button.setVisible(ark_game_setup.restore_state_exists())

    def _update_start_game_button_visibility(self):
        game_size = find_window_size(GAME_WINDOW_TITLE)
        button = getattr(self, "start_game_button", None)
        if button is not None:
            button.setVisible(
                game_size is None or game_size not in SUPPORTED_GAME_RESOLUTIONS
            )

    def _unlock_start_game_button(self):
        self._set_start_game_enabled(True)
        self._update_start_game_button_visibility()

    def _set_start_game_enabled(self, enabled: bool) -> None:
        """Update and broadcast the shared START GAME enabled state."""
        button = getattr(self, "start_game_button", None)
        if button is not None:
            button.setEnabled(enabled)
        self.start_game_enabled_changed.emit(enabled)

    def _unlock_restore_game_button(self):
        button = getattr(self, "restore_game_settings_button", None)
        if button is not None:
            button.setEnabled(True)
        self._update_game_restore_button_visibility()

    def start_game(self):
        self._set_start_game_enabled(False)
        QTimer.singleShot(START_GAME_DISABLE_DELAY, self._unlock_start_game_button)

        button = getattr(self, "restore_game_settings_button", None)
        if button is not None:
            button.setEnabled(False)
        QTimer.singleShot(START_GAME_DISABLE_DELAY, self._unlock_restore_game_button)

        try:
            self.append_log("[INFO] Preparing ARK for 1920x1080 launch...\n")
            settings_path = ark_game_setup.prepare_and_launch_game()
            self.append_log(
                f"[SUCCESS] ARK launch requested through Steam. Config: {settings_path}\n"
            )
        except Exception as exc:
            self.append_log(f"[ERROR] Start game failed: {exc}\n")
            self.dialog("Start Game Failed", str(exc), "error")
        finally:
            self._update_game_restore_button_visibility()

    def restore_game_settings(self):
        if not ark_game_setup.restore_state_exists():
            self._update_game_restore_button_visibility()
            return

        try:
            self.append_log("[INFO] Restoring ARK display and config settings...\n")
            settings_path = ark_game_setup.restore_game_settings()
            self.append_log(
                f"[SUCCESS] Restored ARK display and config: {settings_path}\n"
            )
        except Exception as exc:
            self.append_log(f"[ERROR] Restore game settings failed: {exc}\n")
            self.dialog("Restore Game Settings Failed", str(exc), "error")
        finally:
            self._update_game_restore_button_visibility()

    def clear_game_restore_settings(self):
        try:
            ark_game_setup.clear_restore_state()
            self.append_log("[INFO] Cleared saved ARK restore settings.\n")
        except Exception as exc:
            self.append_log(f"[ERROR] Clear game restore settings failed: {exc}\n")
            self.dialog("Clear Restore Settings Failed", str(exc), "error")
        finally:
            self._update_game_restore_button_visibility()

    def _is_auto_start_allowed(self):
        cond = str(self.settings.get("server_number", "0")).strip() not in ("", "0")
        return cond

    def _update_auto_start_switch(self):
        allowed = self._is_auto_start_allowed()
        saved_value = bool(self.settings.get("auto_start_program", False))

        switch = getattr(self, "auto_start_switch", None)
        if switch is not None:
            switch.blockSignals(True)
            switch.setEnabled(allowed)
            switch.setChecked(saved_value if allowed else False)
            switch.blockSignals(False)

        hint = getattr(self, "auto_start_hint", None)
        if hint is not None:
            hint.setText(
                "Start program when launcher opens"
                if allowed
                else "Set server number first"
            )

    def toggle_auto_start_program(self, checked):
        if not self._is_auto_start_allowed():
            self._update_auto_start_switch()
            return

        self.settings["auto_start_program"] = bool(checked)
        self.form_values["auto_start_program"] = bool(checked)
        field = self.fields.get("auto_start_program")
        if field is not None:
            field.blockSignals(True)
            field.setChecked(bool(checked))
            field.blockSignals(False)

        save_settings(self._collect_settings())
        state = "enabled" if checked else "disabled"
        self.append_log(f"[INFO] Auto start {state}.\n")

    def persist_single_setting(self, key, show_log=True, show_error=True):
        field = self.fields.get(key)
        if field is None:
            return False
        try:
            self.form_values[key] = self._field_value(key, field)
        except ValueError as exc:
            if show_error:
                self.append_log(f"[ERROR] Invalid setting {key}: {exc}\n")
                self.dialog("Invalid Settings", str(exc), "error")
            return False
        return self.persist_settings_from_visible_fields(show_log, show_error)

    def persist_settings_from_visible_fields(self, show_log=True, show_error=True):
        try:
            self._capture_visible_fields()
            new_data = self._collect_settings()
        except ValueError as exc:
            if show_error:
                self.append_log(f"[ERROR] Invalid settings: {exc}\n")
                self.dialog("Invalid Settings", str(exc), "error")
            return False

        save_settings(new_data)
        self.settings = new_data
        self.form_values = new_data.copy()
        self._update_auto_start_switch()
        if show_log:
            self.append_log("[SUCCESS] Settings saved automatically.\n")
        return True

    def _collect_settings(self) -> dict:
        data = {}
        for key, default_value in DEFAULT_SETTINGS.items():
            value = self.form_values.get(key, default_value)
            if isinstance(default_value, bool):
                data[key] = bool(value)
            elif isinstance(default_value, int):
                data[key] = int(value)
            elif isinstance(default_value, float):
                data[key] = float(value)
            else:
                data[key] = str(value)
        data["helper_inactive_opacity"] = max(
            0.1, min(1.0, data["helper_inactive_opacity"])
        )
        data["time_to_reberry"] = max(0, int(data["time_to_reberry"]))
        for key, default in TEMPLATE_REFERENCE_DEFAULTS.items():
            data[key] = str(self.form_values.get(key, default))
        return data

    def _capture_visible_fields(self):
        for key, field in self.fields.items():
            self.form_values[key] = self._field_value(key, field)

    def _field_value(self, key, field):
        default_value = DEFAULT_SETTINGS[key]
        if isinstance(default_value, bool):
            return field.isChecked()

        raw_value = field.text()
        if isinstance(default_value, int):
            return int(raw_value)
        if isinstance(default_value, float):
            return float(raw_value)
        return raw_value

    def confirm_reset(self) -> None:
        if not self.confirm(
            "Apply Default Template",
            f"Apply {DEFAULT_TEMPLATE_FILENAME} to every template-enabled settings group? Station yaw will be preserved.",
            "RESET",
        ):
            return
        current_group = getattr(self, "current_settings_group", "SERVER")
        if not self.apply_default_template_to_all_groups():
            self._skip_visible_field_persist = True
            self._render_settings_group(current_group)
            return
        self._skip_visible_field_persist = True
        self._render_settings_group(current_group)
        self.dialog(
            "Settings Reset",
            f"{DEFAULT_TEMPLATE_FILENAME} was applied. Station yaw was preserved.",
            "info",
        )

    def reset_visible_settings(self):
        for key, field in self.fields.items():
            value = DEFAULT_SETTINGS[key]
            field.blockSignals(True)
            if isinstance(value, bool):
                field.setChecked(value)
            else:
                field.setText(str(value))
            field.blockSignals(False)
            self.form_values[key] = value
        self.persist_settings_from_visible_fields(show_log=False)
        self.append_log("[INFO] Visible settings reset to defaults and saved.\n")
        self.dialog(
            "Settings Reset",
            "Visible settings were reset and saved.",
            "info",
        )
