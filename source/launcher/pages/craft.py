from source.gacha_bot.craft_config import (
    default_craft_route,
    default_crafter,
    load_craft_config,
    save_craft_config,
)
from source.launcher.pages.common import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    _counted_title,
    default_dedi_item,
    setting_label,
)


class CraftPagesMixin:
    def _ensure_craft_config(self):
        """Load the independent craft configuration on first use."""
        if hasattr(self, "craft_config"):
            return
        try:
            self.craft_config = load_craft_config()
        except (OSError, ValueError) as exc:
            self.craft_config = {"generalCraftData": []}
            self.append_log(f"[ERROR] Invalid craft config: {exc}\n")
            self.dialog("Invalid Craft Config", str(exc), "error")

    def _render_craft_group(self):
        """Build the Craft settings page using the existing route controls."""
        self._ensure_craft_config()
        if not hasattr(self, "deposit_route_card_expanded"):
            self.deposit_route_card_expanded = {}
        routes = self.craft_config["generalCraftData"]
        heading = QLabel(_counted_title("CRAFT SETTINGS", len(routes)))
        heading.setObjectName("SectionHeading")
        self.settings_form_layout.addWidget(heading, 0, 0, 1, 3)
        state, template_name, error = self._add_template_selector("CRAFT")
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.settings_form_layout.addWidget(content, 1, 0, 1, 4)
        self._style_template_collection(content, state, template_name, error)
        title = QLabel(_counted_title("GENERAL CRAFT", len(routes)))
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        delay = QHBoxLayout()
        delay_label = QLabel(setting_label("craft_delay"))
        delay_label.setObjectName("FormLabel")
        delay.addWidget(delay_label)
        delay.addWidget(
            self._setting_field_container(
                self._setting_field("craft_delay"),
                state,
                template_name,
                error,
                True,
            ),
            1,
        )
        layout.addLayout(delay)
        for index, route in enumerate(routes):
            layout.addWidget(self._craft_route_card(route, index))
        add = self._button("ADD CRAFT", "secondary")
        add.clicked.connect(self.add_craft_route)
        layout.addWidget(add)
        layout.addStretch()

    def _craft_route_card(self, route: dict, index: int):
        """Edit crafters sharing a teleport and crafted-item dedicated storage."""
        card, layout = self._deposit_route_card(
            _counted_title(
                f"CRAFT {index + 1}",
                len(route["dedi"]["items"]) + len(route["crafters"]),
            ),
            lambda checked=False, i=index: self.remove_craft_route(i),
            lambda checked=False, i=index: self.open_deposit_helper("craft", i),
        )
        self._add_route_teleport_field(layout, route)
        self._add_route_check_interval_field(layout, route)
        self._add_deposit_subheading(layout, "CRAFTERS", len(route["crafters"]))
        for crafter_index, crafter in enumerate(route["crafters"]):
            crafter_label = QLabel(f"CRAFTER {crafter_index + 1}")
            crafter_label.setObjectName("FormLabel")
            layout.addWidget(crafter_label)
            aim = QHBoxLayout()
            self._add_yaw_pitch_fields(aim, crafter)
            aim.addWidget(self._crouch_switch(crafter))
            remove = self._icon_button("icon.trash_junk", "Remove crafter", "danger")
            remove.clicked.connect(
                lambda checked=False, r=index, i=crafter_index: self.remove_crafter(
                    r, i
                )
            )
            aim.addWidget(remove)
            layout.addLayout(aim)
            item_row = QHBoxLayout()
            item_label = QLabel("Craft:")
            item_label.setObjectName("FormLabel")
            item_row.addWidget(item_label)
            field = self._deposit_line_edit(crafter["item"])
            field.editingFinished.connect(
                lambda value=crafter, editor=field: self.update_deposit_text(
                    value, "item", editor
                )
            )
            item_row.addWidget(field, 1)
            layout.addLayout(item_row)
        add_crafter = self._button("ADD CRAFTER", "secondary")
        add_crafter.clicked.connect(lambda checked=False, i=index: self.add_crafter(i))
        layout.addWidget(add_crafter)
        self._add_deposit_subheading(
            layout, "CRAFTED ITEMS DEDIS", len(route["dedi"]["items"])
        )
        for item_index, item in enumerate(route["dedi"]["items"]):
            layout.addLayout(
                self._dedi_row(
                    item,
                    lambda checked=False, r=index, i=item_index: self.remove_craft_dedi(
                        r, i
                    ),
                )
            )
        add = self._button("ADD DEDI", "secondary")
        add.clicked.connect(lambda checked=False, i=index: self.add_craft_dedi(i))
        layout.addWidget(add)
        return card

    def add_crafter(self, index: int):
        """Add another crafter at the entry's shared teleport."""
        self.craft_config["generalCraftData"][index]["crafters"].append(
            default_crafter()
        )
        self.save_craft_routes()
        self._render_settings_group("CRAFT")

    def remove_crafter(self, index: int, crafter_index: int):
        """Remove one crafter while retaining the shared station and output dedis."""
        del self.craft_config["generalCraftData"][index]["crafters"][crafter_index]
        self.save_craft_routes()
        self._render_settings_group("CRAFT")

    def save_craft_routes(self, show_log: bool = True):
        """Save craft data while retaining objects referenced by visible editors."""
        try:
            save_craft_config(self.craft_config)
        except (OSError, ValueError) as exc:
            self.dialog("Invalid Craft Config", str(exc), "error")
            return False
        if show_log:
            self.append_log("[SUCCESS] Craft routes saved automatically.\n")
        return True

    def add_craft_route(self):
        """Add one independently scheduled craft station."""
        self.craft_config["generalCraftData"].append(default_craft_route())
        self.save_craft_routes()
        self._render_settings_group("CRAFT")

    def remove_craft_route(self, index: int):
        """Remove a craft entry and its output storage configuration."""
        del self.craft_config["generalCraftData"][index]
        self.save_craft_routes()
        self._render_settings_group("CRAFT")

    def add_craft_dedi(self, index: int):
        """Append an output dedi to one crafter."""
        self.craft_config["generalCraftData"][index]["dedi"]["items"].append(
            default_dedi_item()
        )
        self.save_craft_routes()
        self._render_settings_group("CRAFT")

    def remove_craft_dedi(self, index: int, item_index: int):
        """Remove an output dedi from one crafter."""
        del self.craft_config["generalCraftData"][index]["dedi"]["items"][item_index]
        self.save_craft_routes()
        self._render_settings_group("CRAFT")
