from source.launcher.pages.common import (
    DEFAULT_PEGO_DELAY,
    DEFAULT_PEGO_SNOW_OWLS_PER_GACHA,
    DEFAULT_PEGO_STATION_SECONDS,
    DEFAULT_PEGO_TARGET_CRYSTALS,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    _counted_title,
    calculate_pego_delay,
    default_pego_entry,
    load_pego_config,
    next_pego_index,
    save_pego_config,
    set_all_pego_delays,
)


class PegoPagesMixin:
    def _render_pego_group(self):
        self._ensure_pego_config()
        self._ensure_gacha_config()

        heading = QLabel(_counted_title("PEGO SETTINGS", len(self.pego_config)))
        heading.setObjectName("SectionHeading")
        self.settings_form_layout.addWidget(heading, 0, 0, 1, 3)
        state, template_name, template_error = self._add_template_selector("PEGO")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        self.settings_form_layout.addWidget(content, 1, 0, 1, 4)
        self._style_template_collection(content, state, template_name, template_error)

        controls, controls_layout = self._panel("PEGO DELAYS")
        delay_row = QHBoxLayout()
        delay_label = QLabel("set all delays")
        delay_label.setObjectName("FormLabel")
        self.pego_bulk_delay_field = self._deposit_line_edit(
            self.pego_config[-1]["delay"] if self.pego_config else DEFAULT_PEGO_DELAY
        )
        set_delay = self._button("SET ALL DELAYS", "secondary")
        set_delay.clicked.connect(self.apply_all_pego_delays)
        delay_row.addWidget(delay_label)
        delay_row.addWidget(self.pego_bulk_delay_field, 1)
        delay_row.addWidget(set_delay)
        expanded = getattr(self, "pego_calculator_expanded", False)
        calc_toggle = self._button(
            "v CALCULATOR" if expanded else "> CALCULATOR", "secondary"
        )
        delay_row.addWidget(calc_toggle)
        controls_layout.addLayout(delay_row)
        calculator = self._pego_calculator_panel()
        calculator.setVisible(getattr(self, "pego_calculator_expanded", False))
        calc_toggle.clicked.connect(
            lambda checked=False, target=calculator, button=calc_toggle: (
                self._toggle_pego_calculator(target, button)
            )
        )
        controls_layout.addWidget(calculator)
        content_layout.addWidget(controls)

        for index, entry in enumerate(self.pego_config):
            content_layout.addWidget(self._pego_card(index, entry))
        add = self._button("ADD PEGO", "secondary")
        add.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add.clicked.connect(self.add_pego)
        content_layout.addWidget(add)
        content_layout.addStretch()

    def _pego_card(self, entry_index, entry):
        card = QFrame()
        card.setObjectName("DepositRouteCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel(entry.get("name", f"PEGO {entry_index + 1}"))
        title.setObjectName("PanelTitle")
        copy = self._button("COPY", "secondary")
        copy.setObjectName("HelperIconButton")
        copy.setToolTip("Copy teleport name")

        teleporter = entry.get("teleporter", "")
        copy.clicked.connect(
            lambda checked=False, value=teleporter: self.copy_text(value)
        )
        remove = self._icon_button("icon.trash_junk", "Remove pego entry", "danger")
        remove.clicked.connect(
            lambda checked=False, index=entry_index: self.remove_pego(index)
        )
        header.addWidget(title)
        header.addStretch()
        header.addWidget(copy)
        header.addWidget(remove)
        layout.addLayout(header)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._add_station_text_field(
            row, "name", entry.get("name", ""), entry_index, "pego"
        )
        self._add_station_text_field(
            row, "teleporter", entry.get("teleporter", ""), entry_index, "pego"
        )
        self._add_station_text_field(
            row, "delay", entry.get("delay", ""), entry_index, "pego"
        )
        layout.addLayout(row)
        return card

    def _pego_calculator_panel(self):
        panel = QFrame()
        panel.setObjectName("HelperRow")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        fields = QHBoxLayout()
        fields.setSpacing(8)
        self.pego_calc_target_field = self._pego_calculator_field(
            fields, "target crystals", DEFAULT_PEGO_TARGET_CRYSTALS
        )
        self.pego_calc_pego_count_field = self._pego_calculator_field(
            fields, "pego amount", len(self.pego_config)
        )
        self.pego_calc_gacha_count_field = self._pego_calculator_field(
            fields, "gacha amount", len(self.gacha_config)
        )
        self.pego_calc_snow_owl_field = self._pego_calculator_field(
            fields, "snow owl / gacha", DEFAULT_PEGO_SNOW_OWLS_PER_GACHA
        )
        self.pego_calc_station_seconds_field = self._pego_calculator_field(
            fields, "pego station seconds", DEFAULT_PEGO_STATION_SECONDS
        )
        layout.addLayout(fields)

        result_row = QHBoxLayout()
        result_row.setSpacing(8)
        self.pego_calc_result_label = QLabel("recommended delay: 1767s")
        self.pego_calc_result_label.setObjectName("HelperRowSummary")
        reset = self._button("RESET", "secondary")
        apply = self._button("APPLY", "secondary")
        reset.clicked.connect(self.reset_pego_delay_calculator)
        apply.clicked.connect(self.apply_pego_delay_recommendation)
        result_row.addWidget(self.pego_calc_result_label, 1)
        result_row.addWidget(reset)
        result_row.addWidget(apply)
        layout.addLayout(result_row)

        for field in self._pego_calculator_fields():
            field.editingFinished.connect(
                lambda: self.update_pego_delay_recommendation(show_error=False)
            )
        self.update_pego_delay_recommendation(show_error=False)
        return panel

    def _pego_calculator_field(
        self, layout: QHBoxLayout, label_text: str, value: object
    ):
        group = QVBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("FormLabel")
        field = self._deposit_line_edit(value)
        group.addWidget(label)
        group.addWidget(field)
        layout.addLayout(group)
        return field

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
        delay = (
            self.pego_config[-1]["delay"] if self.pego_config else DEFAULT_PEGO_DELAY
        )
        self.pego_config.append(
            default_pego_entry(next_pego_index(self.pego_config), delay)
        )
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
        button.setText("v CALCULATOR" if visible else "> CALCULATOR")
        self.pego_calculator_expanded = visible

    def reset_pego_config(self):
        self.pego_config = [default_pego_entry()]
        self.save_pego_config(show_log=False)
        self._render_settings_group("PEGO")
        self.append_log("[INFO] Pego config reset to defaults and saved.\n")
        self.dialog("Pego Config Reset", "Pego config was reset and saved.", "info")
