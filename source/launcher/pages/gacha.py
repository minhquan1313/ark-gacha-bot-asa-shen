from source.gacha_bot.deposit_config import (
    collection_destination_error,
    deposit_destination_options,
    load_deposit_config,
)
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
    default_gacha_collect_entry,
    default_gacha_entry,
    default_gacha_pair,
    gacha_name_from_teleporter,
    grouped_gacha_entries,
    load_gacha_collect_config,
    load_gacha_config,
    missing_gacha_side,
    next_gacha_teleporter,
    risky_teleporter_names,
    save_gacha_collect_config,
    save_gacha_config,
    setting_label,
)


class GachaPagesMixin:
    def _render_gacha_group(self):
        self._ensure_gacha_config()
        self._ensure_gacha_collect_config()
        self._ensure_deposit_config()
        try:
            self.deposit_config = load_deposit_config(create_missing=False)
        except (OSError, ValueError) as exc:
            self.append_log(f"[ERROR] Unable to reload Dedi stations: {exc}\n")
            self.deposit_config = {
                "depositCrystalData": [],
                "depositGrindableData": [],
                "depositGeneralData": [],
            }
        if not hasattr(self, "gacha_group_expanded"):
            self.gacha_group_expanded = {}
        if not hasattr(self, "gacha_section_expanded"):
            self.gacha_section_expanded = {"gacha": False, "collect": False}

        groups = grouped_gacha_entries(self.gacha_config)
        collect_groups = grouped_gacha_entries(self.gacha_collect_config)
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
        self.settings_form_layout.addWidget(content, 1, 0, 1, 4)
        self._style_template_collection(content, state, template_name, template_error)

        risky = risky_teleporter_names(self.gacha_config)
        collect_risky = risky_teleporter_names(self.gacha_collect_config)
        content_layout.addWidget(
            self._gacha_section(
                "GACHA",
                "gacha",
                groups,
                risky,
                "gacha_feed_delay",
                state,
                template_name,
                template_error,
            )
        )
        content_layout.addWidget(
            self._gacha_section(
                "GACHA COLLECT",
                "collect",
                collect_groups,
                collect_risky,
                "gacha_collect_feed_delay",
                state,
                template_name,
                template_error,
            )
        )
        content_layout.addStretch()

    def _gacha_section(
        self,
        title,
        kind,
        groups,
        risky,
        delay_key,
        state,
        template_name,
        template_error,
    ):
        """Build one collapsible gacha configuration section."""
        section = QFrame()
        section.setObjectName("DepositRouteCard")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        expanded = self.gacha_section_expanded.get(kind, False)
        header = QHBoxLayout()
        toggle = self._button("v" if expanded else ">", "secondary")
        toggle.setObjectName("HelperIconButton")
        label = QLabel(
            _counted_title(
                title, f"{len(groups)}({sum(len(group) for _, group in groups)})"
            )
        )
        label.setObjectName("PanelTitle")
        header.addWidget(toggle)
        header.addWidget(label)
        header.addStretch()
        remove = self._icon_button(
            "icon.trash_junk", f"Remove all {title} entries", "danger"
        )
        remove.setEnabled(any(group for _, group in groups))
        remove.clicked.connect(
            lambda checked=False, value=kind: self.remove_gacha_section(value)
        )
        header.addWidget(remove)
        layout.addLayout(header)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        body.setVisible(expanded)
        delay_keys = [delay_key]
        for key in delay_keys:
            delay_row = QHBoxLayout()
            delay_label = QLabel(setting_label(key))
            delay_label.setObjectName("FormLabel")
            delay_row.addWidget(delay_label)
            delay_row.addWidget(
                self._setting_field_container(
                    self._setting_field(key),
                    state,
                    template_name,
                    template_error,
                    key in TEMPLATE_GROUP_SETTING_KEYS["GACHA"],
                ),
                1,
            )
            body_layout.addLayout(delay_row)
        for teleporter, group in groups:
            body_layout.addWidget(
                self._gacha_group_card(teleporter, group, risky, kind)
            )
        add = self._button(f"ADD {title} GROUP", "secondary")
        add.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add.clicked.connect(
            lambda checked=False, value=kind: self.add_gacha_group(value)
        )
        body_layout.addWidget(add)

        def toggle_body(checked=False):
            is_visible = body.isHidden()
            body.setVisible(is_visible)
            toggle.setText("v" if is_visible else ">")
            self.gacha_section_expanded[kind] = is_visible

        toggle.clicked.connect(toggle_body)
        layout.addWidget(body)
        return section

    def _gacha_group_card(self, teleporter, group, risky, kind="gacha"):
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

        expanded_key = teleporter if kind == "gacha" else f"collect:{teleporter}"
        expanded = self.gacha_group_expanded.get(expanded_key, True)
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
            lambda checked=False, value=teleporter, config_kind=kind: (
                self.auto_fill_gacha_group(value, config_kind)
            )
        )
        remove = self._icon_button("icon.trash_junk", "Remove gacha group", "danger")
        remove.clicked.connect(
            lambda checked=False, value=teleporter, config_kind=kind: (
                self.remove_gacha_group(value, config_kind)
            )
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
                self.update_gacha_group_teleporter(old, field, kind)
            )
        )
        teleporter_row.addWidget(teleporter_label)
        teleporter_row.addWidget(teleporter_field, 1)
        body_layout.addLayout(teleporter_row)
        if kind == "collect":
            body_layout.addWidget(self._collection_dedi_selector(teleporter, group))

        for entry_index, entry in group:
            body_layout.addWidget(self._gacha_row_card(entry_index, entry, kind))

        if len(group) < 2:
            add = self._button("ADD GACHA", "secondary")
            add.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            add.setEnabled(
                missing_gacha_side([entry for _, entry in group]) is not None
            )
            add.clicked.connect(
                lambda checked=False, value=teleporter, config_kind=kind: (
                    self.add_gacha_to_group(value, config_kind)
                )
            )
            body_layout.addWidget(add)

        def toggle_body(checked=False):
            is_visible = body.isHidden()
            body.setVisible(is_visible)
            toggle.setText("v" if is_visible else ">")
            self.gacha_group_expanded[expanded_key] = is_visible

        toggle.clicked.connect(toggle_body)
        layout.addWidget(body)
        return card

    def _gacha_row_card(self, entry_index, entry, kind="gacha"):
        row = QWidget()
        outer = QVBoxLayout(row)
        outer.setContentsMargins(0, 0, 0, 0)
        layout = QHBoxLayout()
        outer.addLayout(layout)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self._add_station_text_field(
            layout, "name", entry.get("name", ""), entry_index, kind
        )
        self._add_gacha_side_field(layout, entry.get("side", ""), entry_index, kind)
        if kind == "collect":
            self._add_station_text_field(
                layout, "item", entry.get("item", ""), entry_index, kind
            )
        remove = self._icon_button(
            "icon.trash_junk", "Remove gacha from group", "danger"
        )
        remove.clicked.connect(
            lambda checked=False, index=entry_index, config_kind=kind: (
                self.remove_gacha(index, config_kind)
            )
        )
        layout.addWidget(remove)
        return row

    def _collection_dedi_selector(self, teleporter: str, group: list):
        """Build one shared destination selector and validation hint for a pair."""
        wrapper = QWidget()
        wrapper.setObjectName("PairDediSelector")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        label = QLabel("Dedi")
        label.setObjectName("FormLabel")
        row.addWidget(label)
        field = QComboBox()
        field.addItem("Select Dedi...", "")
        for name in deposit_destination_options(self.deposit_config):
            field.addItem(name, name)
        selections = {entry.get("dedi_teleport", "") for _, entry in group}
        conflict = len(selections) > 1
        selected = next(iter(selections), "") if not conflict else None
        index = field.findData(selected)
        if index < 0:
            field.addItem(
                "Conflicting selections - reselect Dedi"
                if conflict
                else f"Missing: {selected}",
                selected,
            )
            index = field.count() - 1
        field.setCurrentIndex(index)
        row.addWidget(field, 1)
        layout.addLayout(row)
        hint = QLabel()
        hint.setObjectName("FormLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self._style_collection_dedi(field, hint, conflict)
        field.currentIndexChanged.connect(
            lambda _index, pair=teleporter, combo=field, message=hint: (
                self.update_collection_dedi(pair, combo, message)
            )
        )
        return wrapper

    def _style_collection_dedi(
        self, field: QComboBox, hint: QLabel, conflict: bool = False
    ):
        """Mark destinations requiring selection with the existing red combo style."""
        error = (
            "Pair destinations conflict. Reselect Dedi."
            if conflict
            else collection_destination_error(
                self.deposit_config, field.currentData() or ""
            )
        )
        field.setObjectName("MissingTemplateSelector" if error else "HelperCombo")
        field.setToolTip(error)
        field.style().unpolish(field)
        field.style().polish(field)
        hint.setText(error)
        hint.setVisible(bool(error))

    def update_collection_dedi(self, teleporter: str, combo: QComboBox, hint: QLabel):
        """Save the same destination on both flat collection entries in a pair."""
        selected = combo.currentData()
        if selected is None:
            return
        for entry in self.gacha_collect_config:
            if entry.get("teleporter", "") == teleporter:
                entry["dedi_teleport"] = selected
        self.save_gacha_collect_config()
        self._style_collection_dedi(combo, hint)

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

    def _add_gacha_side_field(self, row, value, entry_index, kind="gacha"):
        label = QLabel("side")
        label.setObjectName("FormLabel")
        field = QComboBox()
        field.setObjectName("HelperCombo")
        field.addItems(["left", "right"])
        side = str(value).lower()
        field.setCurrentText(side if side in {"left", "right"} else "left")
        field.currentTextChanged.connect(
            lambda _value, combo=field, index=entry_index, config_kind=kind: (
                self.update_gacha_side(index, combo, config_kind)
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

    def _ensure_gacha_collect_config(self):
        if hasattr(self, "gacha_collect_config"):
            return
        try:
            self.gacha_collect_config = load_gacha_collect_config()
        except ValueError as exc:
            self.gacha_collect_config = []
            self.append_log(f"[ERROR] Invalid gacha collect config: {exc}\n")
            self.dialog("Invalid Gacha Collect Config", str(exc), "error")

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

    def save_gacha_collect_config(self, show_log=True):
        try:
            self.gacha_collect_config = save_gacha_collect_config(
                self.gacha_collect_config
            )
        except ValueError as exc:
            self.append_log(f"[ERROR] Invalid gacha collect config: {exc}\n")
            self.dialog("Invalid Gacha Collect Config", str(exc), "error")
            return False
        if show_log:
            self.append_log("[SUCCESS] Gacha collect config saved automatically.\n")
        return True

    def update_station_field(self, kind, entry_index, key, field):
        if kind in {"gacha", "collect"}:
            self._ensure_gacha_config()
            if kind == "collect":
                self._ensure_gacha_collect_config()
                entry = self.gacha_collect_config[entry_index]
            else:
                entry = self.gacha_config[entry_index]
            value = field.text()
            entry[key] = value
            (
                self.save_gacha_collect_config()
                if kind == "collect"
                else self.save_gacha_config()
            )
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

    def update_gacha_side(self, entry_index, field, kind="gacha"):
        config = self.gacha_collect_config if kind == "collect" else self.gacha_config
        config[entry_index]["side"] = field.currentText()
        (
            self.save_gacha_collect_config()
            if kind == "collect"
            else self.save_gacha_config()
        )

    def update_gacha_group_teleporter(
        self, old_teleporter: str, field: QLineEdit, kind="gacha"
    ):
        self._ensure_gacha_config()
        if not hasattr(self, "gacha_group_expanded"):
            self.gacha_group_expanded = {}
        new_teleporter = field.text()
        if new_teleporter == old_teleporter:
            return
        config = self.gacha_collect_config if kind == "collect" else self.gacha_config
        existing_teleporters = {
            str(entry.get("teleporter", "")).lower()
            for entry in config
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
        for entry in config:
            if entry.get("teleporter", "") == old_teleporter:
                entry["teleporter"] = new_teleporter
        new_expanded_key = (
            new_teleporter if kind == "gacha" else f"collect:{new_teleporter}"
        )
        old_expanded_key = (
            old_teleporter if kind == "gacha" else f"collect:{old_teleporter}"
        )
        self.gacha_group_expanded[new_expanded_key] = self.gacha_group_expanded.pop(
            old_expanded_key, True
        )
        (
            self.save_gacha_collect_config()
            if kind == "collect"
            else self.save_gacha_config()
        )
        self._render_settings_group("GACHA")

    def add_gacha_group(self, kind="gacha"):
        self._ensure_gacha_config()
        if not hasattr(self, "gacha_group_expanded"):
            self.gacha_group_expanded = {}
        config = self.gacha_collect_config if kind == "collect" else self.gacha_config
        teleporter = next_gacha_teleporter(config)
        factory = (
            default_gacha_collect_entry if kind == "collect" else default_gacha_entry
        )
        config.extend(
            [
                factory(f"{teleporter}_left", teleporter, "left"),
                factory(f"{teleporter}_right", teleporter, "right"),
            ]
        )
        expanded_key = teleporter if kind == "gacha" else f"collect:{teleporter}"
        self.gacha_group_expanded[expanded_key] = True
        (
            self.save_gacha_collect_config()
            if kind == "collect"
            else self.save_gacha_config()
        )
        self._render_settings_group("GACHA")

    def add_gacha_to_group(self, teleporter, kind="gacha"):
        self._ensure_gacha_config()
        if kind == "collect":
            self._ensure_gacha_collect_config()
        config = self.gacha_collect_config if kind == "collect" else self.gacha_config
        group = [entry for entry in config if entry.get("teleporter", "") == teleporter]
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
        factory = (
            default_gacha_collect_entry if kind == "collect" else default_gacha_entry
        )
        entry = factory(gacha_name_from_teleporter(teleporter, side), teleporter, side)
        if kind == "collect" and group:
            entry["dedi_teleport"] = group[0].get("dedi_teleport", "")
        config.append(entry)
        (
            self.save_gacha_collect_config()
            if kind == "collect"
            else self.save_gacha_config()
        )
        self._render_settings_group("GACHA")

    def remove_gacha(self, entry_index, kind="gacha"):
        config = self.gacha_collect_config if kind == "collect" else self.gacha_config
        del config[entry_index]
        (
            self.save_gacha_collect_config()
            if kind == "collect"
            else self.save_gacha_config()
        )
        self._render_settings_group("GACHA")

    def remove_gacha_section(self, kind: str):
        """Empty one gacha section, save it, and refresh its displayed counts."""
        config = self.gacha_collect_config if kind == "collect" else self.gacha_config
        title = "GACHA COLLECT" if kind == "collect" else "GACHA"
        if not config or not self.confirm(
            f"Delete All {title}",
            f"Delete all {len(config)} entries in {title}?",
            "DELETE ALL",
        ):
            return
        expanded = getattr(self, "gacha_group_expanded", {})
        for entry in config:
            teleporter = entry.get("teleporter", "")
            key = f"collect:{teleporter}" if kind == "collect" else teleporter
            expanded.pop(key, None)
        config.clear()
        (
            self.save_gacha_collect_config()
            if kind == "collect"
            else self.save_gacha_config()
        )
        self._render_settings_group("GACHA")

    def remove_gacha_group(self, teleporter, kind="gacha"):
        config = self.gacha_collect_config if kind == "collect" else self.gacha_config
        if not hasattr(self, "gacha_group_expanded"):
            self.gacha_group_expanded = {}
        filtered = [
            entry for entry in config if entry.get("teleporter", "") != teleporter
        ]
        if kind == "collect":
            self.gacha_collect_config = filtered
        else:
            self.gacha_config = filtered
        expanded_key = teleporter if kind == "gacha" else f"collect:{teleporter}"
        self.gacha_group_expanded.pop(expanded_key, None)
        (
            self.save_gacha_collect_config()
            if kind == "collect"
            else self.save_gacha_config()
        )
        self._render_settings_group("GACHA")

    def auto_fill_gacha_group(self, teleporter, kind="gacha"):
        config = self.gacha_collect_config if kind == "collect" else self.gacha_config
        if not self.confirm(
            "Auto Fill Gacha Group",
            "Auto fill will assign the first available GACHAPAIR name, then overwrite this group's gacha names and sides.",
            "AUTO FILL",
        ):
            return
        group = [entry for entry in config if entry.get("teleporter", "") == teleporter]
        try:
            new_teleporter = next_gacha_teleporter(
                config, exclude_teleporter=teleporter
            )
        except ValueError as exc:
            self.dialog("Gacha Group", str(exc), "warning")
            return
        auto_fill_gacha_group(group, new_teleporter)
        if hasattr(self, "gacha_group_expanded"):
            new_expanded_key = (
                new_teleporter if kind == "gacha" else f"collect:{new_teleporter}"
            )
            old_expanded_key = (
                teleporter if kind == "gacha" else f"collect:{teleporter}"
            )
            self.gacha_group_expanded[new_expanded_key] = self.gacha_group_expanded.pop(
                old_expanded_key, True
            )
        (
            self.save_gacha_collect_config()
            if kind == "collect"
            else self.save_gacha_config()
        )
        self._render_settings_group("GACHA")

    def reset_gacha_config(self):
        self.gacha_config = default_gacha_pair()
        self.gacha_group_expanded = {}
        self.save_gacha_config(show_log=False)
        self._render_settings_group("GACHA")
        self.append_log("[INFO] Gacha config reset to defaults and saved.\n")
        self.dialog("Gacha Config Reset", "Gacha config was reset and saved.", "info")
