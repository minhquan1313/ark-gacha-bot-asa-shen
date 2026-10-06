from functools import partial

from PySide6.QtWidgets import QFrame, QLineEdit, QPushButton

from source.gacha_bot.craft_config import (
    default_craft_route,
    default_crafter,
    load_craft_config,
    save_craft_config,
)
from source.launcher.components.dedi_editor import DediRouteEditor
from source.launcher.components.settings_actions import SettingsHoverActions
from source.launcher.components.settings_sections import (
    RouteSettingsRow,
    SettingsActionButton,
    SettingsSectionCard,
    SettingsSubheading,
    settings_icon,
    settings_label,
)
from source.launcher.pages.common import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    default_dedi_item,
)
from source.launcher.settings_theme import ENTRY_ROW_GAP, ENTRY_ROW_PADDING_Y


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
        """Present Craft as one approved cover section with independently timed entries."""
        self._ensure_craft_config()
        routes = self.craft_config["generalCraftData"]
        previous = getattr(self, "_craft_expanded", {})
        self._craft_expanded = {id(route): previous.get(id(route), (route, False)) for route in routes}
        outer, state = self._approved_settings_content("CRAFT")
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(content)
        self._style_template_collection(content, *state)
        section = SettingsSectionCard(
            f"Craft settings ({len(routes)})",
            "Manage your crafting automation settings.",
            "craft",
            "craft",
        )
        add = SettingsActionButton("Add craft", "plus")
        add.clicked.connect(self.add_craft_route)
        section.header.layout().addWidget(SettingsHoverActions(section, add, "Add craft", "Craft actions"))
        for index, route in enumerate(routes):
            section.body.addWidget(self._craft_route_card(route, index))
        if not routes:
            section.body.addWidget(settings_label("No craft entries configured. Use Add craft to create one."))
        layout.addWidget(section)

    def _craft_route_card(self, route: dict, index: int):
        """Reuse summary, coordinate editors and existing Craft callbacks."""

        def expanded(checked: bool):
            """Retain expansion without depending on an editable teleport name."""
            self._craft_expanded[id(route)] = (route, checked)

        card = DediRouteEditor(
            route,
            "craft",
            index,
            self._craft_expanded[id(route)][1],
            expanded,
            lambda checked=False: self.open_deposit_helper("craft", index),
            lambda checked=False: self.remove_craft_route(index),
        )
        body = card.body_layout
        body.addWidget(SettingsSubheading("Settings", "sliders"))
        settings = RouteSettingsRow(
            [
                self._dedi_editor_field(route, "teleport", "Teleport", self.update_deposit_text, card),
                self._dedi_editor_field(route, "delay", "Delay", self.update_craft_delay, card),
                self._dedi_editor_field(
                    route,
                    "check_on_every_dedi",
                    "Check dedi",
                    self.update_deposit_int,
                    card,
                ),
            ]
        )
        settings.setObjectName("CraftEntrySettings")
        body.addWidget(settings)
        crafter_panel = QFrame()
        crafter_panel.setObjectName("DediGrinderCard")
        crafters = QVBoxLayout(crafter_panel)
        crafters.setContentsMargins(12, 10, 12, 10)
        crafters.setSpacing(ENTRY_ROW_GAP)
        crafters.addWidget(SettingsSubheading(f"Crafters ({len(route['crafters'])})", "craft"))
        for crafter_index, crafter in enumerate(route["crafters"]):
            wrapper = QFrame()
            wrapper.setObjectName("CraftCrafter")
            rows = QVBoxLayout(wrapper)
            rows.setContentsMargins(0, 0, 0, ENTRY_ROW_PADDING_Y)
            rows.setSpacing(0)
            aim = self._dedi_point_editor(
                crafter,
                crafter_index,
                partial(self.remove_crafter, index, crafter_index),
            )
            aim.separator = False
            for button in aim.findChildren(QPushButton):
                button.setToolTip("Remove crafter")
            rows.addWidget(aim)
            item_row = QHBoxLayout()
            item_row.setContentsMargins(28, 0, 8, 0)
            item_row.setSpacing(8)
            symbol = QLabel()
            symbol.setPixmap(settings_icon("cube").pixmap(24, 24))
            symbol.setFixedSize(34, 24)
            item_row.addWidget(symbol)
            item_field = self._dedi_editor_field(crafter, "item", "Craft", self.update_deposit_text)
            item_field.label.setFixedWidth(40)
            item_row.addWidget(item_field, 1)
            rows.addLayout(item_row)
            if crafter_index:
                separator = QFrame()
                separator.setFixedHeight(1)
                separator.setStyleSheet("background: #14516A; border: none;")
                crafters.addWidget(separator)
            crafters.addWidget(wrapper)
        add_crafter = SettingsActionButton("Add crafter", "plus")
        add_crafter.clicked.connect(lambda checked=False: self.add_crafter(index))
        crafters.addWidget(add_crafter)
        body.addWidget(crafter_panel)
        body.addWidget(SettingsSubheading("Dedi", "cube"))
        dedis = QVBoxLayout()
        dedis.setSpacing(ENTRY_ROW_GAP)
        for item_index, item in enumerate(route["dedi"]["items"]):
            dedis.addWidget(self._dedi_point_editor(item, item_index, partial(self.remove_craft_dedi, index, item_index)))
        body.addLayout(dedis)
        add = SettingsActionButton("Add dedi", "plus")
        add.clicked.connect(lambda checked=False: self.add_craft_dedi(index))
        body.addWidget(add)
        return card

    def update_craft_delay(self, route: dict, key: str, field: QLineEdit):
        """Validate a non-negative interval and restore the editor on save failure."""
        previous = route[key]
        try:
            value = int(field.text())
            if value < 0:
                raise ValueError
        except ValueError:
            field.setText(str(previous))
            self.dialog(
                "Invalid Craft Delay",
                "Delay must be a non-negative integer in seconds.",
                "error",
            )
            return
        route[key] = value
        if not self.save_craft_routes():
            route[key] = previous
            field.setText(str(previous))

    def add_crafter(self, index: int):
        """Add another crafter at the entry's shared teleport."""
        self.craft_config["generalCraftData"][index]["crafters"].append(default_crafter())
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
        self.craft_config["generalCraftData"][index]["dedi"]["items"].append(default_dedi_item())
        self.save_craft_routes()
        self._render_settings_group("CRAFT")

    def remove_craft_dedi(self, index: int, item_index: int):
        """Remove an output dedi from one crafter."""
        del self.craft_config["generalCraftData"][index]["dedi"]["items"][item_index]
        self.save_craft_routes()
        self._render_settings_group("CRAFT")
