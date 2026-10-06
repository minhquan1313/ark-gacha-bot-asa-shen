from collections.abc import Callable
from functools import partial

from source.launcher.components.dashboard import line_icon
from source.launcher.components.dedi_editor import (
    DediPointRow,
    DediRouteEditor,
    GrinderCard,
)
from source.launcher.components.settings_actions import (
    SettingsHoverActions,
)
from source.launcher.components.settings_sections import (
    RouteSettingsRow,
    SettingsActionButton,
    SettingsField,
    SettingsSectionCard,
    SettingsSubheading,
    SettingsUnitControl,
    settings_label,
)
from source.launcher.components.widgets import CyberCheckBox
from source.launcher.dashboard_theme import PALETTE
from source.launcher.pages.common import (
    CyberSwitch,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
    default_crystal_route,
    default_dedi_item,
    default_deposit_config,
    default_general_route,
    default_grindable_route,
    default_vault_item,
    load_deposit_config,
    save_deposit_config,
)
from source.launcher.settings_theme import CARD_SPACING, CONTROL_HEIGHT, ENTRY_ROW_GAP


class DediPagesMixin:
    def _render_deposit_routes_group(self):
        """Build approved Dedi sections around the existing model and handlers."""
        self._ensure_deposit_config()
        if not hasattr(self, "deposit_route_card_expanded"):
            self.deposit_route_card_expanded = {}
        groups = [
            (
                "crystal",
                "depositCrystalData",
                "Crystal routes",
                "Manage dedi routes for crystal nodes.",
                "crystal",
            ),
            (
                "grindable",
                "depositGrindableData",
                "Grindable routes",
                "Manage dedi routes for grindable resources.",
                "grindable",
            ),
            (
                "general",
                "depositGeneralData",
                "General dedi",
                "Manage general storage routes.",
                "cube",
            ),
        ]
        routes = [route for _, key, *_ in groups for route in self.deposit_config[key]]
        old = getattr(self, "_dedi_expanded", {})
        self._dedi_expanded = {id(route): old.get(id(route), (route, False)) for route in routes}
        outer, state = self._approved_settings_content("DEDI")
        content = QWidget()
        box = QVBoxLayout(content)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(CARD_SPACING)
        outer.addWidget(content)
        self._style_template_collection(content, *state)
        for kind, key, title, subtitle, icon in groups:
            section = SettingsSectionCard(
                f"{title} ({len(self.deposit_config[key])})",
                subtitle,
                f"dedi_{kind}",
                icon,
            )
            add = SettingsActionButton("Add route", "plus")
            add.clicked.connect(getattr(self, f"add_{kind}_route"))
            section.header.layout().addWidget(SettingsHoverActions(section, add, "Add route", f"{title} actions"))
            for index, route in enumerate(self.deposit_config[key]):
                section.body.addWidget(self._dedi_route_editor(route, kind, index))
            if not self.deposit_config[key]:
                section.body.addWidget(settings_label("No routes configured. Use Add route to create one."))
            box.addWidget(section)

    def _dedi_route_editor(self, route: dict, kind: str, index: int):
        """Create a route's summary and appropriate editors without changing its data."""

        def retain_expansion(expanded: bool):
            """Store presentation state by route identity, never by editable labels."""
            self._dedi_expanded[id(route)] = (route, expanded)

        card = DediRouteEditor(
            route,
            kind,
            index,
            self._dedi_expanded[id(route)][1],
            retain_expansion,
            lambda checked=False: self.open_deposit_helper(kind, index),
            lambda checked=False: getattr(self, f"remove_{kind}_route")(index),
        )
        body = card.body_layout
        body.addWidget(SettingsSubheading("Route settings", "sliders"))
        teleport = self._dedi_editor_field(route, "teleport", "Teleport", self.update_deposit_text, card)
        interval = self._dedi_editor_field(
            route,
            "check_on_every_dedi",
            "Check dedi",
            self.update_deposit_int,
            card,
        )
        body.addWidget(RouteSettingsRow([teleport, interval]))
        if kind == "grindable":
            grinder = route["grinder"]
            available = CyberSwitch("Available")
            available.setFixedHeight(CONTROL_HEIGHT)
            available.setFixedWidth(available.sizeHint().width())
            available.setChecked(bool(grinder.get("active", False)))
            available.toggled.connect(lambda checked: self.update_deposit_bool(grinder, "active", checked))
            body.addWidget(GrinderCard(available, self._dedi_position_fields(grinder)))
        items = route["dedi"]["items"]
        body.addWidget(SettingsSubheading(f"Dedi points ({len(items)})", "cube"))
        point_rows = QVBoxLayout()
        point_rows.setSpacing(ENTRY_ROW_GAP)
        for item_index, item in enumerate(items):
            remove = partial(getattr(self, f"remove_{kind}_dedi"), index, item_index)
            point_rows.addWidget(self._dedi_point_editor(item, item_index, remove))
        body.addLayout(point_rows)
        add = SettingsActionButton("Add dedi", "plus")
        add.clicked.connect(lambda checked=False: getattr(self, f"add_{kind}_dedi")(index))
        body.addWidget(add)
        if kind == "crystal":
            vaults = route["vault"]["items"]
            body.addWidget(SettingsSubheading(f"Vaults ({len(vaults)})", "cube"))
            vault_rows = QVBoxLayout()
            vault_rows.setSpacing(ENTRY_ROW_GAP)
            for vault_index, vault in enumerate(vaults):
                vault_rows.addWidget(
                    self._dedi_point_editor(
                        vault,
                        vault_index,
                        partial(self.remove_crystal_vault, index, vault_index),
                        vault=True,
                    )
                )
            body.addLayout(vault_rows)
            add_vault = SettingsActionButton("Add vault", "plus")
            add_vault.clicked.connect(lambda checked=False: self.add_crystal_vault(index))
            body.addWidget(add_vault)
        return card

    def _dedi_editor_field(
        self,
        item: dict,
        key: str,
        title: str,
        update: Callable,
        card: DediRouteEditor | None = None,
    ):
        """Connect a standard editor to existing validation and successful summary updates."""
        value = ", ".join(item.get(key, [])) if key == "items" else item.get(key, "")
        editor = self._deposit_line_edit(value)
        editor.setFixedHeight(CONTROL_HEIGHT)
        editor.setMinimumWidth(90 if key in {"yaw", "pitch"} else 80)
        editor.setAccessibleName(title)
        editor.setProperty("dediField", key)

        def commit():
            """Let the existing callback handle saves and rollback before refreshing text."""
            if key == "items":
                update(item, editor)
            else:
                update(item, key, editor)
            if card is not None:
                card.refresh_summary()

        editor.editingFinished.connect(commit)
        editor.returnPressed.connect(commit)
        icons = {
            "yaw": "target",
            "pitch": "pitch",
            "teleport": "locator",
            "delay": "clock",
            "check_on_every_dedi": "server",
        }
        if key in {"delay", "check_on_every_dedi"}:
            editor.setFixedWidth(80)
        control = SettingsUnitControl(editor, "(s)") if key == "delay" else editor
        presentation = SettingsField(title, control, icon=icons.get(key, ""))
        presentation.label.setWordWrap(False)
        presentation.label.setMinimumWidth(0)
        presentation.label.setMaximumWidth(16777215)
        if key in {"yaw", "pitch", "items"}:
            presentation.label.setFixedWidth(34 if key in {"yaw", "pitch"} else 40)
        return presentation

    def _dedi_position_fields(self, item: dict):
        """Reuse existing coordinate validation and crouch persistence in all editors."""
        fields = [self._dedi_editor_field(item["location"], key, key.title(), self.update_deposit_float) for key in ("yaw", "pitch")]
        crouched = CyberCheckBox("Crouched")
        crouched.setFixedHeight(CONTROL_HEIGHT)
        crouched.setFixedWidth(crouched.sizeHint().width())
        crouched.setChecked(bool(item.get("crouched", False)))
        crouched.toggled.connect(lambda checked: self.update_deposit_bool(item, "crouched", checked))
        crouch_group = QWidget()
        crouch_group.setObjectName("CrouchedFieldGroup")
        row = QHBoxLayout(crouch_group)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(crouched)
        row.addStretch()
        fields.append(crouch_group)
        # Each group needs the same minimum before optional vault Items can reflow.
        minimum = max(field.minimumSizeHint().width() for field in fields)
        for field in fields:
            field.setMinimumWidth(minimum)
        return fields

    def _dedi_point_editor(self, item: dict, index: int, remove: Callable, vault: bool = False):
        """Place existing editors in the same compact row for all route types."""
        fields = self._dedi_position_fields(item)
        if vault:
            fields.append(self._dedi_editor_field(item, "items", "Items", self.update_deposit_items))
        delete = SettingsActionButton("", "trash", "danger")
        delete.setIcon(line_icon("trash", PALETTE["danger"]))
        delete.setFixedWidth(CONTROL_HEIGHT)
        delete.setToolTip("Remove vault" if vault else "Remove dedi")
        delete.clicked.connect(lambda checked=False: remove())
        return DediPointRow(index, fields, delete)

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
                "depositGeneralData": [default_general_route()],
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

    def save_route_item(self, item: dict):
        """Save a shared route field to the config that owns its object."""

        def contains(container: object):
            """Find the edited dictionary by identity without matching equal values."""
            if container is item:
                return True
            if isinstance(container, dict):
                return any(contains(value) for value in container.values())
            if isinstance(container, list):
                return any(contains(value) for value in container)
            return False

        if contains(getattr(self, "craft_config", {})):
            return self.save_craft_routes()
        return self.save_deposit_routes()

    def update_deposit_text(self, item, key, field):
        previous = item.get(key, "")
        item[key] = field.text()
        if not self.save_route_item(item):
            item[key] = previous
            field.setText(str(previous))

    def update_deposit_float(self, location, key, field):
        previous = location.get(key, 0.0)
        try:
            location[key] = float(field.text())
        except ValueError:
            field.setText(str(previous))
            self.append_log(f"[ERROR] Invalid deposit route {key}: must be a float.\n")
            self.dialog("Invalid Deposit Route", f"{key} must be a float number.", "error")
            return
        if not self.save_route_item(location):
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
            self.append_log(f"[ERROR] Invalid deposit route {key}: must be a positive integer.\n")
            self.dialog("Invalid Deposit Route", f"{key} must be a positive integer.", "error")
            return
        if not self.save_route_item(item):
            item[key] = previous
            field.setText(str(previous))

    def update_deposit_bool(self, item, key, checked):
        item[key] = bool(checked)
        self.save_route_item(item)

    def update_deposit_items(self, vault, field):
        vault["items"] = [item.strip() for item in field.text().split(",") if item.strip()]
        self.save_route_item(vault)

    def add_crystal_route(self):
        self.deposit_config["depositCrystalData"].append(default_crystal_route())
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def remove_crystal_route(self, route_index):
        del self.deposit_config["depositCrystalData"][route_index]
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def add_crystal_dedi(self, route_index):
        self.deposit_config["depositCrystalData"][route_index]["dedi"]["items"].append(default_dedi_item())
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def remove_crystal_dedi(self, route_index, item_index):
        del self.deposit_config["depositCrystalData"][route_index]["dedi"]["items"][item_index]
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def add_crystal_vault(self, route_index):
        self.deposit_config["depositCrystalData"][route_index]["vault"]["items"].append(default_vault_item())
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def remove_crystal_vault(self, route_index, item_index):
        del self.deposit_config["depositCrystalData"][route_index]["vault"]["items"][item_index]
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
        self.deposit_config["depositGrindableData"][route_index]["dedi"]["items"].append(default_dedi_item())
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def remove_grindable_dedi(self, route_index, item_index):
        del self.deposit_config["depositGrindableData"][route_index]["dedi"]["items"][item_index]
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def add_general_route(self):
        self.deposit_config["depositGeneralData"].append(default_general_route())
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def remove_general_route(self, route_index):
        del self.deposit_config["depositGeneralData"][route_index]
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def add_general_dedi(self, route_index: int):
        """Add a source-material dedi to a general station."""
        key = "items"
        self.deposit_config["depositGeneralData"][route_index]["dedi"][key].append(default_dedi_item())
        self.save_deposit_routes()
        self._render_settings_group("DEDI")

    def remove_general_dedi(self, route_index: int, item_index: int):
        """Remove a source-material dedi from a general station."""
        key = "items"
        del self.deposit_config["depositGeneralData"][route_index]["dedi"][key][item_index]
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
