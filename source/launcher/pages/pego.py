from functools import partial

from source.launcher.components.settings_actions import (
    SettingsEntryRow,
    SettingsHoverActions,
    SettingsRowActions,
)
from source.launcher.components.settings_sections import (
    SettingsActionButton,
    SettingsField,
    SettingsFieldGrid,
    SettingsSectionCard,
    SettingsUnitControl,
    settings_label,
)
from source.launcher.pages.common import (
    DEFAULT_PEGO_DELAY,
    DEFAULT_PEGO_SNOW_OWLS_PER_GACHA,
    DEFAULT_PEGO_STATION_SECONDS,
    DEFAULT_PEGO_TARGET_CRYSTALS,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    calculate_pego_delay,
    default_pego_entry,
    load_pego_config,
    next_pego_index,
    save_pego_config,
    set_all_pego_delays,
)
from source.launcher.settings_theme import CARD_SPACING, CONTROL_HEIGHT, ENTRY_ROW_GAP


class PegoPagesMixin:
    def _render_pego_group(self):
        """Present the existing Pego model in the approved Settings shell."""
        self._ensure_pego_config()
        self._ensure_gacha_config()
        outer, state = self._approved_settings_content("PEGO")
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(CARD_SPACING)
        outer.addWidget(content)
        self._style_template_collection(content, *state)

        controls = SettingsSectionCard(
            "Pego delays",
            "Configure global pego delay settings",
            "pego_delays",
            "clock",
        )
        self.pego_bulk_delay_field = self._deposit_line_edit(self.pego_config[-1]["delay"] if self.pego_config else DEFAULT_PEGO_DELAY)
        self.pego_bulk_delay_field.setFixedHeight(CONTROL_HEIGHT)
        set_delay = SettingsActionButton("Set all delays", "bolt")
        set_delay.ensurePolished()
        set_delay.setMinimumWidth(set_delay.sizeHint().width())
        set_delay.clicked.connect(self.apply_all_pego_delays)
        calc_toggle = SettingsActionButton("Calculator", "calculator")
        calc_toggle.ensurePolished()
        calc_toggle.setMinimumWidth(calc_toggle.sizeHint().width())
        calc_toggle.setCheckable(True)
        calc_toggle.setChecked(getattr(self, "pego_calculator_expanded", False))
        actions = QWidget()
        actions_row = QHBoxLayout(actions)
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.addWidget(set_delay, 1)
        actions_row.addWidget(calc_toggle, 1)
        controls.body.addWidget(
            SettingsFieldGrid(
                [
                    SettingsField(
                        "Set all delays",
                        SettingsUnitControl(self.pego_bulk_delay_field, "(s)"),
                    ),
                    actions,
                ]
            )
        )
        calculator = self._pego_calculator_panel()
        calculator.setVisible(calc_toggle.isChecked())
        calc_toggle.clicked.connect(lambda checked=False: self._toggle_pego_calculator(calculator, calc_toggle))
        controls.body.addWidget(calculator)
        content_layout.addWidget(controls)
        content_layout.addWidget(self._pego_section())

    def _pego_section(self):
        """Show the model count, compact entries, and existing collection actions."""
        section = SettingsSectionCard(
            f"Pego ({len(self.pego_config)})",
            "Configure individual pego teleporters.",
            "pego_list",
            "pego",
        )
        remove = SettingsActionButton("Delete all", "trash", "danger")
        remove.setEnabled(bool(self.pego_config))
        remove.clicked.connect(self.remove_pego_section)
        section.header.layout().addWidget(SettingsHoverActions(section, remove))
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(ENTRY_ROW_GAP)
        for index, entry in enumerate(self.pego_config):
            body_layout.addWidget(self._pego_card(index, entry))
        add = SettingsActionButton("Add Pego", "pego")
        add.clicked.connect(self.add_pego)
        body_layout.addWidget(add)

        section.body.addWidget(body)
        return section

    def _pego_card(self, entry_index: int, entry: dict):
        """Keep entry editors and actions aligned without nested rounded cards."""
        fields = []
        editors = {}
        for key, title in (
            ("teleporter", "Teleporter"),
            ("delay", "Delay"),
        ):
            field = self._deposit_line_edit(entry.get(key, ""))
            field.setFixedHeight(CONTROL_HEIGHT)
            field.setMinimumWidth({"teleporter": 120, "delay": 80}[key])
            field.setAccessibleName(f"Pego {entry_index + 1} {title}")
            callback = partial(self.update_station_field, "pego", entry_index, key, field)
            field.editingFinished.connect(callback)
            field.returnPressed.connect(callback)
            editors[key] = field
            control = SettingsUnitControl(field, "(s)") if key == "delay" else field
            presentation = SettingsField(title, control, icon="clock" if key == "delay" else "locator")
            presentation.label.setFixedWidth({"teleporter": 72, "delay": 42}[key])
            presentation.label.setWordWrap(False)
            fields.append(presentation)
        # copy = SettingsActionButton("", "copy")
        # copy.setToolTip("Copy teleporter name")
        # copy.clicked.connect(
        #     lambda checked=False: self.copy_text(editors["teleporter"].text())
        # )
        remove = SettingsActionButton("", "trash", "danger")
        remove.setFixedWidth(CONTROL_HEIGHT)
        remove.setToolTip("Remove pego entry")
        remove.clicked.connect(lambda checked=False: self.remove_pego(entry_index))
        # actions = SettingsRowActions([("Copy", copy), ("Delete", remove)])
        actions = SettingsRowActions([("Delete", remove)])
        return SettingsEntryRow(entry_index, fields, actions)

    def _pego_calculator_panel(self):
        """Keep the calculator's five inputs and actions in an open, flat layout."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 0)
        fields = []
        specs = [
            ("pego_calc_target_field", "Target crystals", DEFAULT_PEGO_TARGET_CRYSTALS),
            ("pego_calc_pego_count_field", "Pego amount", len(self.pego_config)),
            ("pego_calc_gacha_count_field", "Gacha amount", len(self.gacha_config)),
            (
                "pego_calc_snow_owl_field",
                "Snow owl / gacha",
                DEFAULT_PEGO_SNOW_OWLS_PER_GACHA,
            ),
            (
                "pego_calc_station_seconds_field",
                "Pego station time",
                DEFAULT_PEGO_STATION_SECONDS,
            ),
        ]
        for name, title, value in specs:
            field = self._deposit_line_edit(value)
            field.setFixedHeight(CONTROL_HEIGHT)
            setattr(self, name, field)
            control = SettingsUnitControl(field, "(s)") if name == "pego_calc_station_seconds_field" else field
            fields.append(SettingsField(title, control, stacked=True))
            field.editingFinished.connect(lambda: self.update_pego_delay_recommendation(show_error=False))
        layout.addWidget(SettingsFieldGrid(fields))
        result_row = QHBoxLayout()
        self.pego_calc_result_label = settings_label("")
        reset = SettingsActionButton("Reset", "update")
        apply = SettingsActionButton("Apply", "save")
        reset.clicked.connect(self.reset_pego_delay_calculator)
        apply.clicked.connect(self.apply_pego_delay_recommendation)
        result_row.addWidget(self.pego_calc_result_label, 1)
        result_row.addWidget(reset)
        result_row.addWidget(apply)
        layout.addLayout(result_row)
        self.update_pego_delay_recommendation(show_error=False)
        return panel

    def _pego_calculator_fields(self):
        return [
            self.pego_calc_target_field,
            self.pego_calc_pego_count_field,
            self.pego_calc_gacha_count_field,
            self.pego_calc_snow_owl_field,
            self.pego_calc_station_seconds_field,
        ]

    def _ensure_pego_config(self):
        if hasattr(self, "pego_config"):
            return
        try:
            self.pego_config = load_pego_config()
        except ValueError as exc:
            self.pego_config = [default_pego_entry()]
            self.append_log(f"[ERROR] Invalid pego config: {exc}\n")
            self.dialog("Invalid Pego Config", str(exc), "error")

    def save_pego_config(self, show_log=True):
        try:
            self.pego_config = save_pego_config(self.pego_config)
        except ValueError as exc:
            self.append_log(f"[ERROR] Invalid pego config: {exc}\n")
            self.dialog("Invalid Pego Config", str(exc), "error")
            return False
        if show_log:
            self.append_log("[SUCCESS] Pego config saved automatically.\n")
        return True

    def add_pego(self):
        self._ensure_pego_config()
        delay = self.pego_config[-1]["delay"] if self.pego_config else DEFAULT_PEGO_DELAY
        self.pego_config.append(default_pego_entry(next_pego_index(self.pego_config), delay))
        self.save_pego_config()
        self._render_settings_group("PEGO")

    def remove_pego_section(self):
        """Confirm deletion of the pego list, then save and refresh the page."""
        if not self.pego_config or not self.confirm(
            "Delete All PEGO",
            f"Delete all {len(self.pego_config)} entries in PEGO?",
            "DELETE ALL",
        ):
            return
        self.pego_config.clear()
        self.save_pego_config()
        self._render_settings_group("PEGO")

    def remove_pego(self, entry_index):
        self._ensure_pego_config()
        del self.pego_config[entry_index]
        self.save_pego_config()
        self._render_settings_group("PEGO")

    def apply_all_pego_delays(self):
        self._ensure_pego_config()
        try:
            set_all_pego_delays(self.pego_config, self.pego_bulk_delay_field.text())
        except ValueError:
            self.append_log("[ERROR] Invalid pego delay: must be an integer.\n")
            self.dialog("Invalid Pego Config", "delay must be an integer.", "error")
            return
        self.save_pego_config()
        self._render_settings_group("PEGO")

    def update_pego_delay_recommendation(self, show_error: bool = True):
        try:
            delay = self._pego_delay_recommendation()
        except ValueError as exc:
            self.pego_calc_result_label.setText("recommended delay: invalid input")
            if show_error:
                self.append_log(f"[ERROR] Invalid pego calculator input: {exc}\n")
                self.dialog("Invalid Pego Calculator", str(exc), "error")
            return None
        self.pego_calc_result_label.setText(f"recommended delay: {delay}s")
        return delay

    def apply_pego_delay_recommendation(self):
        delay = self.update_pego_delay_recommendation()
        if delay is None:
            return
        self.pego_bulk_delay_field.setText(str(delay))
        self._ensure_pego_config()
        set_all_pego_delays(self.pego_config, delay)
        self.save_pego_config()
        self._render_settings_group("PEGO")

    def reset_pego_delay_calculator(self):
        self._ensure_pego_config()
        self._ensure_gacha_config()
        defaults = [
            DEFAULT_PEGO_TARGET_CRYSTALS,
            len(self.pego_config),
            len(self.gacha_config),
            DEFAULT_PEGO_SNOW_OWLS_PER_GACHA,
            DEFAULT_PEGO_STATION_SECONDS,
        ]
        for field, value in zip(self._pego_calculator_fields(), defaults, strict=False):
            field.setText(str(value))
        self.update_pego_delay_recommendation(show_error=False)

    def _pego_delay_recommendation(self):
        return calculate_pego_delay(
            self.pego_calc_target_field.text(),
            self.pego_calc_pego_count_field.text(),
            self.pego_calc_gacha_count_field.text(),
            self.pego_calc_snow_owl_field.text(),
            self.pego_calc_station_seconds_field.text(),
        )

    def _toggle_pego_calculator(self, body: QWidget, button: QWidget):
        visible = body.isHidden()
        body.setVisible(visible)
        button.setChecked(visible)
        self.pego_calculator_expanded = visible

    def reset_pego_config(self):
        self.pego_config = [default_pego_entry()]
        self.save_pego_config(show_log=False)
        self._render_settings_group("PEGO")
        self.append_log("[INFO] Pego config reset to defaults and saved.\n")
        self.dialog("Pego Config Reset", "Pego config was reset and saved.", "info")
