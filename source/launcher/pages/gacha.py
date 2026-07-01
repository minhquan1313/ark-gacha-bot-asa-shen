from source.launcher.pages.common import (
    TEMPLATE_GROUP_SETTING_KEYS,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    _counted_title,
    auto_fill_gacha_group,
    default_gacha_entry,
    default_gacha_pair,
    gacha_name_from_teleporter,
    grouped_gacha_entries,
    load_gacha_config,
    missing_gacha_side,
    next_gacha_teleporter,
    risky_teleporter_names,
    save_gacha_config,
)


class GachaPagesMixin:
    def _render_gacha_group(self) -> None:
        self._ensure_gacha_config()
        if not hasattr(self, "gacha_group_expanded"):
            self.gacha_group_expanded = {}

        groups = grouped_gacha_entries(self.gacha_config)
        heading = QLabel(
            _counted_title("GACHA SETTINGS", f"{len(groups)}({len(self.gacha_config)})")
        )
        heading.setObjectName("SectionHeading")
        self.settings_form_layout.addWidget(heading, 0, 0, 1, 3)
        state, template_name, template_error = self._add_template_selector("GACHA")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        next_row = self._add_setting_row(
            ("gacha_feed_delay",),
            1,
            state,
            template_name,
            template_error,
            set(TEMPLATE_GROUP_SETTING_KEYS["GACHA"]),
        )
        self.settings_form_layout.addWidget(content, next_row, 0, 1, 4)
        self._style_template_collection(content, state, template_name, template_error)

        controls, controls_layout = self._panel("GACHA GROUPS")
        hint = QLabel(
            "Groups are matched by exact teleport name. Each group supports one left and one right gacha."
        )
        hint.setObjectName("MutedCopy")
        hint.setWordWrap(True)
        controls_layout.addWidget(hint)
        expand_row = QHBoxLayout()
        expand_row.setSpacing(8)
        expand_all = self._button("EXPAND ALL", "secondary")
        collapse_all = self._button("COLLAPSE ALL", "secondary")
        expand_all.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        collapse_all.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        expand_all.clicked.connect(lambda: self.set_gacha_groups_expanded(True))
        collapse_all.clicked.connect(lambda: self.set_gacha_groups_expanded(False))
        expand_row.addWidget(expand_all)
        expand_row.addWidget(collapse_all)
        controls_layout.addLayout(expand_row)
        content_layout.addWidget(controls)

        risky = risky_teleporter_names(self.gacha_config)
        for teleporter, group in groups:
            content_layout.addWidget(self._gacha_group_card(teleporter, group, risky))
        add_group = self._button("ADD GACHA GROUP", "secondary")
        add_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        add_group.clicked.connect(self.add_gacha_group)
        content_layout.addWidget(add_group)
        content_layout.addStretch()

    def _gacha_group_card(self, teleporter, group, risky):
        card = QFrame()
        warning = teleporter in risky
        card.setObjectName(
            "StationConfigWarningCard" if warning else "DepositRouteCard"
        )
        if warning:
            card.setToolTip(
                "Teleport name may match longer teleport names in Ark search. "
                "Rename it to a unique form like GACHAPAIR_2."
            )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        expanded = self.gacha_group_expanded.get(teleporter, False)
        header = QHBoxLayout()
        toggle = self._button("v" if expanded else ">", "secondary")
        toggle.setObjectName("HelperIconButton")
        title = QLabel(
            f"{teleporter or 'NO TELEPORT'} ({len(group)}/2)"
            + ("  WARNING" if warning else "")
        )
        title.setObjectName("PanelTitle")
        copy = self._button("COPY", "secondary")
        copy.setObjectName("HelperIconButton")
        copy.setToolTip("Copy teleport name")
        copy.clicked.connect(
            lambda checked=False, value=teleporter: self.copy_text(value)
        )
        auto = self._button("AUTO FILL", "secondary")
        auto.clicked.connect(
            lambda checked=False, value=teleporter: self.auto_fill_gacha_group(value)
        )
        remove = self._icon_button("icon.trash_junk", "Remove gacha group", "danger")
        remove.clicked.connect(
            lambda checked=False, value=teleporter: self.remove_gacha_group(value)
        )
        header.addWidget(toggle)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(copy)
        header.addWidget(auto)
        header.addWidget(remove)
        layout.addLayout(header)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        body.setVisible(expanded)

        teleporter_row = QHBoxLayout()
        teleporter_label = QLabel("teleporter")
        teleporter_label.setObjectName("FormLabel")
        teleporter_field = self._deposit_line_edit(teleporter)
        teleporter_field.editingFinished.connect(
            lambda field=teleporter_field, old=teleporter: (
                self.update_gacha_group_teleporter(old, field)
            )
        )
        teleporter_row.addWidget(teleporter_label)
        teleporter_row.addWidget(teleporter_field, 1)
        body_layout.addLayout(teleporter_row)

        for entry_index, entry in group:
            body_layout.addWidget(self._gacha_row_card(entry_index, entry))

        if len(group) < 2:
            add = self._button("ADD GACHA", "secondary")
            add.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            add.setEnabled(
                missing_gacha_side([entry for _, entry in group]) is not None
            )
            add.clicked.connect(
                lambda checked=False, value=teleporter: self.add_gacha_to_group(value)
            )
            body_layout.addWidget(add)

        def toggle_body(checked=False):
            is_visible = body.isHidden()
            body.setVisible(is_visible)
            toggle.setText("v" if is_visible else ">")
            self.gacha_group_expanded[teleporter] = is_visible

        toggle.clicked.connect(toggle_body)
        layout.addWidget(body)
        return card

    def _gacha_row_card(self, entry_index, entry):
        row = QFrame()
        row.setObjectName("HelperRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self._add_station_text_field(
            layout, "name", entry.get("name", ""), entry_index, "gacha"
        )
        self._add_gacha_side_field(layout, entry.get("side", ""), entry_index)
        remove = self._icon_button(
            "icon.trash_junk", "Remove gacha from group", "danger"
        )
        remove.clicked.connect(
            lambda checked=False, index=entry_index: self.remove_gacha(index)
        )
        layout.addWidget(remove)
        return row

    def _add_station_text_field(self, row, label_text, value, entry_index, kind):
        label = QLabel(label_text)
        label.setObjectName("FormLabel")
        field = self._deposit_line_edit(value)
        field.editingFinished.connect(
            lambda field=field, index=entry_index, key=label_text, name=kind: (
                self.update_station_field(name, index, key, field)
            )
        )
        field.returnPressed.connect(
            lambda field=field, index=entry_index, key=label_text, name=kind: (
                self.update_station_field(name, index, key, field)
            )
        )
        row.addWidget(label)
        row.addWidget(field, 1)
        return field

    def _add_gacha_side_field(self, row, value, entry_index):
        label = QLabel("side")
        label.setObjectName("FormLabel")
        field = QComboBox()
        field.setObjectName("HelperCombo")
        field.addItems(["left", "right"])
        side = str(value).lower()
        field.setCurrentText(side if side in {"left", "right"} else "left")
        field.currentTextChanged.connect(
            lambda _value, combo=field, index=entry_index: self.update_gacha_side(
                index, combo
            )
        )
        row.addWidget(label)
        row.addWidget(field)
        return field

    def _ensure_gacha_config(self):
        if hasattr(self, "gacha_config"):
            return
        try:
            self.gacha_config = load_gacha_config()
        except ValueError as exc:
            self.gacha_config = default_gacha_pair()
            self.append_log(f"[ERROR] Invalid gacha config: {exc}\n")
            self.dialog("Invalid Gacha Config", str(exc), "error")

    def save_gacha_config(self, show_log=True):
        try:
            self.gacha_config = save_gacha_config(self.gacha_config)
        except ValueError as exc:
            self.append_log(f"[ERROR] Invalid gacha config: {exc}\n")
            self.dialog("Invalid Gacha Config", str(exc), "error")
            return False
        if show_log:
            self.append_log("[SUCCESS] Gacha config saved automatically.\n")
        return True

    def update_station_field(self, kind, entry_index, key, field):
        if kind == "gacha":
            self._ensure_gacha_config()
            entry = self.gacha_config[entry_index]
            value = field.text()
            entry[key] = value
            self.save_gacha_config()
            if key == "teleporter":
                self._render_settings_group("GACHA")
            return

        self._ensure_pego_config()
        entry = self.pego_config[entry_index]
        previous = entry.get(key)
        try:
            entry[key] = int(field.text()) if key == "delay" else field.text()
        except ValueError:
            field.setText(str(previous))
            self.append_log("[ERROR] Invalid pego delay: must be an integer.\n")
            self.dialog("Invalid Pego Config", "delay must be an integer.", "error")
            return
        if not self.save_pego_config():
            entry[key] = previous
            field.setText(str(previous))

    def update_gacha_side(self, entry_index, field):
        self._ensure_gacha_config()
        self.gacha_config[entry_index]["side"] = field.currentText()
        self.save_gacha_config()

    def update_gacha_group_teleporter(
        self, old_teleporter: str, field: QLineEdit
    ) -> None:
        self._ensure_gacha_config()
        if not hasattr(self, "gacha_group_expanded"):
            self.gacha_group_expanded = {}
        new_teleporter = field.text()
        if new_teleporter == old_teleporter:
            return
        existing_teleporters = {
            str(entry.get("teleporter", "")).lower()
            for entry in self.gacha_config
            if str(entry.get("teleporter", "")) != old_teleporter
        }
        if new_teleporter.lower() in existing_teleporters:
            field.setText(old_teleporter)
            self.dialog(
                "Duplicate Gacha Teleporter",
                f'A gacha group with teleport name "{new_teleporter}" already exists. '
                "Teleport names are compared case-insensitively.",
                "error",
            )
            return
        for entry in self.gacha_config:
            if entry.get("teleporter", "") == old_teleporter:
                entry["teleporter"] = new_teleporter
        self.gacha_group_expanded[new_teleporter] = self.gacha_group_expanded.pop(
            old_teleporter, True
        )
        self.save_gacha_config()
        self._render_settings_group("GACHA")

    def add_gacha_group(self):
        self._ensure_gacha_config()
        if not hasattr(self, "gacha_group_expanded"):
            self.gacha_group_expanded = {}
        teleporter = next_gacha_teleporter(self.gacha_config)
        self.gacha_config.extend(
            [
                default_gacha_entry(f"{teleporter}_left", teleporter, "left"),
                default_gacha_entry(f"{teleporter}_right", teleporter, "right"),
            ]
        )
        self.gacha_group_expanded[teleporter] = True
        self.save_gacha_config()
        self._render_settings_group("GACHA")

    def set_gacha_groups_expanded(self, expanded):
        self._ensure_gacha_config()
        if not hasattr(self, "gacha_group_expanded"):
            self.gacha_group_expanded = {}
        for teleporter, _group in grouped_gacha_entries(self.gacha_config):
            self.gacha_group_expanded[teleporter] = bool(expanded)
        self._render_settings_group("GACHA")

    def add_gacha_to_group(self, teleporter):
        self._ensure_gacha_config()
        group = [
            entry
            for entry in self.gacha_config
            if entry.get("teleporter", "") == teleporter
        ]
        if len(group) >= 2:
            self.dialog(
                "Gacha Group", "A gacha pair can only contain two gachas.", "warning"
            )
            return
        side = missing_gacha_side(group)
        if side is None:
            self.dialog(
                "Gacha Group",
                "This gacha pair already has left and right sides.",
                "warning",
            )
            return
        self.gacha_config.append(
            default_gacha_entry(
                gacha_name_from_teleporter(teleporter, side), teleporter, side
            )
        )
        self.save_gacha_config()
        self._render_settings_group("GACHA")

    def remove_gacha(self, entry_index):
        self._ensure_gacha_config()
        del self.gacha_config[entry_index]
        self.save_gacha_config()
        self._render_settings_group("GACHA")

    def remove_gacha_group(self, teleporter):
        self._ensure_gacha_config()
        if not hasattr(self, "gacha_group_expanded"):
            self.gacha_group_expanded = {}
        self.gacha_config = [
            entry
            for entry in self.gacha_config
            if entry.get("teleporter", "") != teleporter
        ]
        self.gacha_group_expanded.pop(teleporter, None)
        self.save_gacha_config()
        self._render_settings_group("GACHA")

    def auto_fill_gacha_group(self, teleporter):
        self._ensure_gacha_config()
        if not self.confirm(
            "Auto Fill Gacha Group",
            "Auto fill will assign the first available GACHAPAIR name, then overwrite this group's gacha names and sides.",
            "AUTO FILL",
        ):
            return
        group = [
            entry
            for entry in self.gacha_config
            if entry.get("teleporter", "") == teleporter
        ]
        try:
            new_teleporter = next_gacha_teleporter(
                self.gacha_config, exclude_teleporter=teleporter
            )
        except ValueError as exc:
            self.dialog("Gacha Group", str(exc), "warning")
            return
        auto_fill_gacha_group(group, new_teleporter)
        if hasattr(self, "gacha_group_expanded"):
            self.gacha_group_expanded[new_teleporter] = self.gacha_group_expanded.pop(
                teleporter, True
            )
        self.save_gacha_config()
        self._render_settings_group("GACHA")

    def reset_gacha_config(self):
        self.gacha_config = default_gacha_pair()
        self.gacha_group_expanded = {}
        self.save_gacha_config(show_log=False)
        self._render_settings_group("GACHA")
        self.append_log("[INFO] Gacha config reset to defaults and saved.\n")
        self.dialog("Gacha Config Reset", "Gacha config was reset and saved.", "info")
