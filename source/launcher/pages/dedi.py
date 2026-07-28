from source.launcher.pages.common import (
    CyberSwitch,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    _counted_title,
    _deposit_route_child_count,
    default_crystal_route,
    default_dedi_item,
    default_deposit_config,
    default_grindable_route,
    default_vault_item,
    load_deposit_config,
    save_deposit_config,
    setting_label,
)


class DediPagesMixin:
    def _render_deposit_routes_group(self):
        self._ensure_deposit_config()
        if not hasattr(self, "deposit_route_card_expanded"):
            self.deposit_route_card_expanded = {}
        crystal_routes = self.deposit_config["depositCrystalData"]
        grindable_routes = self.deposit_config["depositGrindableData"]
        heading = QLabel(
            _counted_title("DEDI SETTINGS", len(crystal_routes) + len(grindable_routes))
        )
        heading.setObjectName("SectionHeading")
        self.settings_form_layout.addWidget(heading, 0, 0, 1, 3)
        state, template_name, template_error = self._add_template_selector("DEDI")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        self.settings_form_layout.addWidget(content, 1, 0, 1, 4)
        self._style_template_collection(content, state, template_name, template_error)

        storage_settings, storage_layout = self._panel("DEDI")
        expand_row = QHBoxLayout()
        expand_row.setSpacing(8)
        expand_all = self._button("EXPAND ALL", "secondary")
        collapse_all = self._button("COLLAPSE ALL", "secondary")
        expand_all.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        collapse_all.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        expand_all.clicked.connect(lambda: self.set_storage_routes_expanded(True))
        collapse_all.clicked.connect(lambda: self.set_storage_routes_expanded(False))
        expand_row.addWidget(expand_all)
        expand_row.addWidget(collapse_all)
        storage_layout.addLayout(expand_row)
        content_layout.addWidget(storage_settings)

        crystal_heading = QLabel(
            _counted_title("CRYSTAL DEPOSIT ROUTES", len(crystal_routes))
        )
        crystal_heading.setObjectName("PanelTitle")
        content_layout.addWidget(crystal_heading)
        for route_index, route in enumerate(crystal_routes):
            content_layout.addWidget(self._crystal_route_card(route, route_index))
        add_crystal = self._button("ADD CRYSTAL ROUTE", "secondary")
        add_crystal.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        add_crystal.clicked.connect(self.add_crystal_route)
        content_layout.addWidget(add_crystal)

        grindable_heading = QLabel(
            _counted_title("GRINDABLE ROUTES", len(grindable_routes))
        )
        grindable_heading.setObjectName("PanelTitle")
        content_layout.addWidget(grindable_heading)
        for route_index, route in enumerate(grindable_routes):
            content_layout.addWidget(self._grindable_route_card(route, route_index))
        add_grindable = self._button("ADD GRINDABLE ROUTE", "secondary")
        add_grindable.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        add_grindable.clicked.connect(self.add_grindable_route)
        content_layout.addWidget(add_grindable)
        content_layout.addStretch()

    def _crystal_route_card(self, route: dict, route_index: int):
        dedi_count = len(route["dedi"]["items"])
        vault_count = len(route["vault"]["items"])
        card, layout = self._deposit_route_card(
            _counted_title(
                f"CRYSTAL ROUTE {route_index + 1}",
                _deposit_route_child_count(route),
            ),
            lambda checked=False, index=route_index: self.remove_crystal_route(index),
            lambda checked=False, index=route_index: self.open_deposit_helper(
                "crystal", index
            ),
        )
        self._add_route_teleport_field(layout, route)
        self._add_route_check_interval_field(layout, route)

        self._add_deposit_subheading(layout, "DEDIS", dedi_count)
        for item_index, item in enumerate(route["dedi"]["items"]):
            layout.addLayout(
                self._dedi_row(
                    item,
                    lambda checked=False, r=route_index, i=item_index: (
                        self.remove_crystal_dedi(r, i)
                    ),
                )
            )
        add_dedi = self._button("ADD DEDI", "secondary")
        add_dedi.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add_dedi.clicked.connect(
            lambda checked=False, index=route_index: self.add_crystal_dedi(index)
        )
        layout.addWidget(add_dedi)

        self._add_deposit_subheading(layout, "VAULTS", vault_count)
        for vault_index, vault in enumerate(route["vault"]["items"]):
            layout.addLayout(
                self._vault_row(
                    vault,
                    lambda checked=False, r=route_index, i=vault_index: (
                        self.remove_crystal_vault(r, i)
                    ),
                )
            )
        add_vault = self._button("ADD VAULT", "secondary")
        add_vault.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add_vault.clicked.connect(
            lambda checked=False, index=route_index: self.add_crystal_vault(index)
        )
        layout.addWidget(add_vault)
        return card

    def _grindable_route_card(self, route: dict, route_index: int):
        dedi_count = len(route["dedi"]["items"])
        card, layout = self._deposit_route_card(
            _counted_title(
                f"GRINDABLE ROUTE {route_index + 1}",
                _deposit_route_child_count(route),
            ),
            lambda checked=False, index=route_index: self.remove_grindable_route(index),
            lambda checked=False, index=route_index: self.open_deposit_helper(
                "grindable", index
            ),
        )
        self._add_route_teleport_field(layout, route)
        self._add_route_check_interval_field(layout, route)

        self._add_deposit_subheading(layout, "GRINDER", 1)
        grinder = route["grinder"]
        grinder_row = QHBoxLayout()
        grinder_row.setSpacing(8)
        active = CyberSwitch("ACTIVE")
        active.blockSignals(True)
        active.setChecked(bool(grinder.get("active", False)))
        active.blockSignals(False)
        active.toggled.connect(
            lambda checked, route_grinder=grinder: self.update_deposit_bool(
                route_grinder, "active", checked
            )
        )
        grinder_row.addWidget(active)
        self._add_yaw_pitch_fields(grinder_row, grinder)
        crouched = self._crouch_switch(grinder)
        grinder_row.addWidget(crouched)
        grinder_row.addStretch()
        layout.addLayout(grinder_row)

        self._add_deposit_subheading(layout, "DEDIS", dedi_count)
        for item_index, item in enumerate(route["dedi"]["items"]):
            layout.addLayout(
                self._dedi_row(
                    item,
                    lambda checked=False, r=route_index, i=item_index: (
                        self.remove_grindable_dedi(r, i)
                    ),
                )
            )
        add_dedi = self._button("ADD DEDI", "secondary")
        add_dedi.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add_dedi.clicked.connect(
            lambda checked=False, index=route_index: self.add_grindable_dedi(index)
        )
        layout.addWidget(add_dedi)
        return card

    def _deposit_route_card(self, title, remove_handler, helper_handler):
        card = QFrame()
        card.setObjectName("DepositRouteCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        header = QHBoxLayout()
        expanded_key = title
        expanded = self.deposit_route_card_expanded.get(expanded_key, False)
        toggle = self._button("v" if expanded else ">", "secondary")
        toggle.setObjectName("HelperIconButton")
        label = QLabel(title)
        label.setObjectName("PanelTitle")
        helper = self._button("[B]", "secondary")
        helper.setObjectName("HelperIconButton")
        helper.setToolTip(
            "Open helper to add dedi and vault locations the easiest way."
        )
        # helper.setFixedSize(38, 30)
        helper.clicked.connect(helper_handler)
        remove = self._icon_button("icon.trash_junk", "Remove route", "danger")
        remove.clicked.connect(remove_handler)
        header.addWidget(toggle)
        header.addWidget(label)
        header.addStretch()
        header.addWidget(helper)
        header.addWidget(remove)
        layout.addLayout(header)
        body = QWidget()
        body.setObjectName("DepositRouteCardBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)
        body.setVisible(expanded)

        def toggle_body(checked=False):
            is_visible = body.isHidden()
            body.setVisible(is_visible)
            toggle.setText("v" if is_visible else ">")
            self.deposit_route_card_expanded[expanded_key] = is_visible

        toggle.clicked.connect(toggle_body)
        layout.addWidget(body)
        return card, body_layout

    def _add_route_teleport_field(self, layout, route):
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(setting_label("teleport"))
        label.setObjectName("FormLabel")
        field = self._deposit_line_edit(route.get("teleport", ""))
        field.editingFinished.connect(
            lambda field=field, item=route: self.update_deposit_text(
                item, "teleport", field
            )
        )
        field.returnPressed.connect(
            lambda field=field, item=route: self.update_deposit_text(
                item, "teleport", field
            )
        )
        row.addWidget(label)
        row.addWidget(field, 1)
        layout.addLayout(row)

    def _add_route_check_interval_field(self, layout, route):
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(setting_label("check_on_every_dedi"))
        label.setObjectName("FormLabel")
        field = self._deposit_line_edit(route.get("check_on_every_dedi", 6))
        field.editingFinished.connect(
            lambda field=field, item=route: self.update_deposit_int(
                item, "check_on_every_dedi", field
            )
        )
        field.returnPressed.connect(
            lambda field=field, item=route: self.update_deposit_int(
                item, "check_on_every_dedi", field
            )
        )
        row.addWidget(label)
        row.addWidget(field, 1)
        layout.addLayout(row)
        hint = QLabel(
            "Set this max 2 - if your server ping is more than 200 to help prevent "
            "resource loss."
        )
        hint.setObjectName("MutedCopy")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def _add_deposit_subheading(self, layout: QVBoxLayout, text: str, count: int):
        label = QLabel(_counted_title(text, count))
        label.setObjectName("FormLabel")
        layout.addWidget(label)

    def _dedi_row(self, item, remove_handler):
        row = QHBoxLayout()
        row.setSpacing(8)
        self._add_yaw_pitch_fields(row, item)
        row.addWidget(self._crouch_switch(item))
        remove = self._icon_button("icon.trash_junk", "Remove dedi entry", "danger")
        remove.clicked.connect(remove_handler)
        row.addWidget(remove)
        return row

    def _vault_row(self, vault, remove_handler):
        row = QVBoxLayout()
        row.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        self._add_yaw_pitch_fields(top, vault)
        top.addWidget(self._crouch_switch(vault))
        remove = self._icon_button("icon.trash_junk", "Remove vault entry", "danger")
        remove.clicked.connect(remove_handler)
        top.addWidget(remove)
        row.addLayout(top)

        items_row = QHBoxLayout()
        items_row.setSpacing(8)
        items_label = QLabel(setting_label("items"))
        items_label.setObjectName("FormLabel")
        items = self._deposit_line_edit(", ".join(vault.get("items", [])))
        items.editingFinished.connect(
            lambda field=items, item=vault: self.update_deposit_items(item, field)
        )
        items.returnPressed.connect(
            lambda field=items, item=vault: self.update_deposit_items(item, field)
        )
        items_row.addWidget(items_label)
        items_row.addWidget(items, 1)
        row.addLayout(items_row)
        return row

    def _add_yaw_pitch_fields(self, row, item):
        location = item["location"]
        for key in ("yaw", "pitch"):
            label = QLabel(setting_label(key))
            label.setObjectName("FormLabel")
            field = self._deposit_line_edit(str(location.get(key, 0.0)))
            field.editingFinished.connect(
                lambda field=field, loc=location, name=key: self.update_deposit_float(
                    loc, name, field
                )
            )
            field.returnPressed.connect(
                lambda field=field, loc=location, name=key: self.update_deposit_float(
                    loc, name, field
                )
            )
            row.addWidget(label)
            row.addWidget(field)

    def _crouch_switch(self, item):
        checkbox = QCheckBox("Crouched")
        checkbox.blockSignals(True)
        checkbox.setChecked(bool(item.get("crouched", False)))
        checkbox.blockSignals(False)
        checkbox.toggled.connect(
            lambda checked, route_item=item: self.update_deposit_bool(
                route_item, "crouched", checked
            )
        )
        return checkbox

    def _deposit_line_edit(self, value):
        field = QLineEdit(str(value))
        field.setObjectName("SettingField")
        return field

    def _ensure_deposit_config(self):
        if hasattr(self, "deposit_config"):
            return
        try:
            self.deposit_config = load_deposit_config()
        except ValueError as exc:
            self.deposit_config = {
                "depositCrystalData": [default_crystal_route()],
                "depositGrindableData": [default_grindable_route()],
            }
            self.append_log(f"[ERROR] Invalid deposit route config: {exc}\n")
            self.dialog("Invalid Deposit Routes", str(exc), "error")

    def save_deposit_routes(self, show_log=True):
        try:
            save_deposit_config(self.deposit_config)
        except ValueError as exc:
            self.append_log(f"[ERROR] Invalid deposit route config: {exc}\n")
            self.dialog("Invalid Deposit Routes", str(exc), "error")
            return False
        if show_log:
            self.append_log("[SUCCESS] Deposit routes saved automatically.\n")
        return True

    def update_deposit_text(self, item, key, field):
        item[key] = field.text()
        self.save_deposit_routes()

    def update_deposit_float(self, location, key, field):
        previous = location.get(key, 0.0)
        try:
            location[key] = float(field.text())
        except ValueError:
            field.setText(str(previous))
            self.append_log(f"[ERROR] Invalid deposit route {key}: must be a float.\n")
            self.dialog(
                "Invalid Deposit Route", f"{key} must be a float number.", "error"
            )
            return
        if not self.save_deposit_routes():
            location[key] = previous
            field.setText(str(previous))

    def update_deposit_int(self, item, key, field):
        previous = item.get(key, 6)
        try:
            value = int(field.text())
            if value <= 0:
                raise ValueError
            item[key] = value
        except ValueError:
            field.setText(str(previous))
            self.append_log(
                f"[ERROR] Invalid deposit route {key}: must be a positive integer.\n"
            )
            self.dialog(
                "Invalid Deposit Route", f"{key} must be a positive integer.", "error"
            )
            return
        if not self.save_deposit_routes():
            item[key] = previous
            field.setText(str(previous))

    def update_deposit_bool(self, item, key, checked):
        item[key] = bool(checked)
        self.save_deposit_routes()

    def update_deposit_items(self, vault, field):
        vault["items"] = [
            item.strip() for item in field.text().split(",") if item.strip()
        ]
        self.save_deposit_routes()

    def add_crystal_route(self):
        self.deposit_config["depositCrystalData"].append(default_crystal_route())
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def remove_crystal_route(self, route_index):
        del self.deposit_config["depositCrystalData"][route_index]
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def add_crystal_dedi(self, route_index):
        self.deposit_config["depositCrystalData"][route_index]["dedi"]["items"].append(
            default_dedi_item()
        )
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def remove_crystal_dedi(self, route_index, item_index):
        del self.deposit_config["depositCrystalData"][route_index]["dedi"]["items"][
            item_index
        ]
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def add_crystal_vault(self, route_index):
        self.deposit_config["depositCrystalData"][route_index]["vault"]["items"].append(
            default_vault_item()
        )
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def remove_crystal_vault(self, route_index, item_index):
        del self.deposit_config["depositCrystalData"][route_index]["vault"]["items"][
            item_index
        ]
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def add_grindable_route(self):
        self.deposit_config["depositGrindableData"].append(default_grindable_route())
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def remove_grindable_route(self, route_index):
        del self.deposit_config["depositGrindableData"][route_index]
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def add_grindable_dedi(self, route_index):
        self.deposit_config["depositGrindableData"][route_index]["dedi"][
            "items"
        ].append(default_dedi_item())
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def remove_grindable_dedi(self, route_index, item_index):
        del self.deposit_config["depositGrindableData"][route_index]["dedi"]["items"][
            item_index
        ]
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def reset_deposit_routes(self):
        self.deposit_config = default_deposit_config()
        self.save_deposit_routes(show_log=False)
        self._render_settings_group("DEDI")
        self.append_log("[INFO] Deposit routes reset to defaults and saved.\n")
        self.dialog(
            "Deposit Routes Reset",
            "Deposit routes were reset and saved.",
            "info",
        )

    def set_storage_routes_expanded(self, expanded):
        self._ensure_deposit_config()
        if not hasattr(self, "deposit_route_card_expanded"):
            self.deposit_route_card_expanded = {}
        for index, _route in enumerate(self.deposit_config["depositCrystalData"], 1):
            self.deposit_route_card_expanded[f"CRYSTAL ROUTE {index}"] = bool(expanded)
        for index, _route in enumerate(self.deposit_config["depositGrindableData"], 1):
            self.deposit_route_card_expanded[f"GRINDABLE ROUTE {index}"] = bool(
                expanded
            )
        self._render_settings_group("DEDI")
