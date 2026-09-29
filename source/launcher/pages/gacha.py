"""Gacha teleport groups backed by the existing flat side records."""

import copy
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap, QTransform
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLayout, QLineEdit, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from source.gacha_bot.deposit_config import collection_destination_error, deposit_destination_options, load_deposit_config
from source.launcher.components.custom_pyside_component import NoWheelComboBox
from source.launcher.components.gacha_editor import GachaSideCard
from source.launcher.components.settings_actions import SettingsHoverActions, SettingsRowIndex
from source.launcher.components.settings_sections import SettingsActionButton, SettingsField, SettingsSectionCard, SettingsSubheading, SettingsUnitControl, settings_icon, settings_label
from source.launcher.config.constants import ASSETS, TEMPLATE_GROUP_SETTING_KEYS
from source.launcher.config.station_config import (
    default_gacha_collect_entry,
    default_gacha_entry,
    grouped_gacha_entries,
    load_gacha_collect_config,
    load_gacha_config,
    risky_teleporter_names,
    save_gacha_collect_config,
    save_gacha_config,
)
from source.launcher.dashboard_theme import asset_path
from source.launcher.settings_theme import CARD_PADDING, CONTROL_HEIGHT, ENTRY_ROW_GAP
from source.launcher.utils.settings_store import save_settings


class GachaPagesMixin:
    def _render_gacha_group(self):
        """Mount both illustrated sections inside the established Settings shell."""
        self._ensure_gacha_config()
        self._ensure_gacha_collect_config()
        self._ensure_deposit_config()
        try:
            self.deposit_config = load_deposit_config(create_missing=False)
        except (OSError, ValueError) as exc:
            self.append_log(f"[ERROR] Unable to reload Dedi stations: {exc}\n")
        if not hasattr(self, "gacha_section_expanded"):
            self.gacha_section_expanded = {"gacha": True, "collect": True}
        outer, state = self._approved_settings_content("GACHA")
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        outer.addWidget(content)
        self._style_template_collection(content, *state)
        self._gacha_teleport_fields = {}
        self._gacha_collect_editors = {}
        for kind in ("gacha", "collect"):
            layout.addWidget(self._gacha_section(kind, state))

    def _gacha_records(self, kind: str):
        """Return the single authoritative flat list for a section."""
        return self.gacha_collect_config if kind == "collect" else self.gacha_config

    def _commit_gacha_records(self, kind: str, records: list):
        """Persist candidates before replacing live records; failures leave UI intact."""
        save = save_gacha_collect_config if kind == "collect" else save_gacha_config
        try:
            saved = save(records)
        except (OSError, ValueError) as exc:
            self.dialog("Unable to save Gacha", str(exc), "error")
            return False
        if kind == "collect":
            self.gacha_collect_config = saved
        else:
            self.gacha_config = saved
        self.append_log("[SUCCESS] Gacha settings saved automatically.\n")
        return True

    def _gacha_section(self, kind: str, state: tuple):
        """Share covers, feed delay, hover actions and collapsible entry lists."""
        groups = grouped_gacha_entries(self._gacha_records(kind))
        collect = kind == "collect"
        title = "Gacha collect" if collect else "Gacha"
        section = SettingsSectionCard(
            f"{title} ({len(groups)})",
            "Configure collection sides, items and Dedi destinations." if collect else "Configure up to two Gachas at each teleport.",
            "gacha_collect" if collect else "gacha",
            "cube" if collect else "diamond",
        )
        remove = SettingsActionButton("Delete all", "trash", "danger")
        remove.setEnabled(bool(groups))
        remove.clicked.connect(lambda checked=False: self.remove_gacha_section(kind))
        section.header.layout().addWidget(SettingsHoverActions(section, remove, "Delete all", f"{title} actions"))
        toggle = SettingsActionButton("", "chevron_down")
        toggle.setFixedWidth(CONTROL_HEIGHT)
        toggle.setCheckable(True)
        toggle.setAccessibleName(f"Expand {title}")
        section.header.layout().addWidget(toggle)
        body = QWidget()
        box = QVBoxLayout(body)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(ENTRY_ROW_GAP)
        box.addWidget(SettingsSubheading("Settings", "sliders"))
        key = "gacha_collect_feed_delay" if collect else "gacha_feed_delay"
        editor = self._setting_field(key)
        editor.setFixedHeight(CONTROL_HEIGHT)
        control = self._setting_field_container(editor, *state, key in TEMPLATE_GROUP_SETTING_KEYS["GACHA"])
        delay = SettingsField("Feed delay", SettingsUnitControl(control, "(s)"), icon="clock", natural_label=True)
        box.addWidget(delay)
        box.addWidget(SettingsSubheading("Station", "diamond"))
        risky = risky_teleporter_names(self._gacha_records(kind))
        for index, (teleport, group) in enumerate(groups):
            box.addWidget(self._gacha_teleport_entry(kind, index, teleport, group, teleport in risky))
        add = SettingsActionButton("Add collect" if collect else "Add Gacha", "plus")
        add.clicked.connect(lambda checked=False: self.add_gacha_group(kind))
        box.addWidget(add)
        section.body.addWidget(body)
        down = settings_icon("chevron_down")
        up = QIcon(down.pixmap(24, 24).transformed(QTransform().rotate(180)))

        def expand(checked: bool):
            """Synchronize the stored section state and its chevron immediately."""
            self.gacha_section_expanded[kind] = checked
            body.setVisible(checked)
            padding = CARD_PADDING if checked else 0
            section.body.setContentsMargins(padding, padding, padding, padding)
            toggle.setIcon(up if checked else down)

        toggle.toggled.connect(expand)
        toggle.setChecked(self.gacha_section_expanded.get(kind, True))
        expand(toggle.isChecked())
        return section

    def _gacha_teleport_entry(self, kind: str, index: int, teleport: str, group: list, risky: bool):
        """Keep the station row above two illustrated side controls."""
        entry = QWidget()
        entry.setObjectName("GachaTeleportEntry")
        box = QVBoxLayout(entry)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)
        row = QHBoxLayout()
        row.addWidget(SettingsRowIndex(index))
        field = self._deposit_line_edit(teleport)
        field.setFixedHeight(CONTROL_HEIGHT)
        field.setAccessibleName(f"{kind} Teleport {index + 1}")
        field.editingFinished.connect(lambda: self.update_gacha_group_teleporter(teleport, field, kind))
        self._gacha_teleport_fields[(kind, teleport)] = field
        field.setMinimumWidth(100)
        teleport_field = SettingsField("Teleport", field, icon="locator", natural_label=True)
        scroller = self._gacha_field_scroll([teleport_field])
        row.addWidget(scroller, 1)
        remove = SettingsActionButton("", "trash", "danger")
        remove.setFixedWidth(CONTROL_HEIGHT)
        remove.setToolTip("Delete teleport station")
        remove.clicked.connect(lambda checked=False: self.remove_gacha_group(teleport, kind))
        row.addWidget(remove)
        box.addLayout(row)
        sides = [record.get("side") for _, record in group]
        malformed = len(sides) != len(set(sides)) or any(side not in {"left", "right"} for side in sides)
        if malformed or risky:
            box.addWidget(
                settings_label("Repeated or invalid sides: repair the source records before editing this station." if malformed else "Teleport name may match another station in ARK search.")
            )
        scroller.setEnabled(not malformed)
        if kind == "collect":
            self._gacha_collect_fields(entry, teleport, not malformed)
        cards = QHBoxLayout()
        cards.setSpacing(8)
        for side in ("left", "right"):
            if side == "right":
                center = QLabel()
                center.setAlignment(Qt.AlignmentFlag.AlignCenter)
                candidate = asset_path(ASSETS["settings.gacha_center"])
                art = QPixmap(candidate) if Path(candidate).is_file() else settings_icon("diamond").pixmap(56, 80)
                center.setPixmap(art.scaled(48, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                center.setFixedWidth(48)
                center.setAccessibleName("Shared teleport artwork")
                cards.addWidget(center)
            record = next((record for _, record in group if record.get("side") == side), None)
            card = GachaSideCard(side, record is not None)
            card.setEnabled(not malformed)
            card.toggleRequested.connect(lambda value=side, widget=card: self.toggle_gacha_side(kind, teleport, value, widget))
            cards.addWidget(card, 1)
        box.addLayout(cards)
        return entry

    def _gacha_field_scroll(self, fields: list[QWidget]):
        """Expand inline groups, scrolling only when their styled minima cannot fit."""
        content = QWidget()
        row = QHBoxLayout(content)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        for field in fields:
            row.addWidget(field, 1)
        scroller = QScrollArea()
        scroller.setObjectName("SettingsEntryScroll")
        scroller.setFrameShape(QScrollArea.Shape.NoFrame)
        scroller.setWidgetResizable(True)
        scroller.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroller.setWidget(content)
        scroller.setMinimumWidth(0)
        content.setAutoFillBackground(False)
        scroller.viewport().setAutoFillBackground(False)
        scroller.setFixedHeight(CONTROL_HEIGHT)
        scroller.horizontalScrollBar().rangeChanged.connect(lambda _minimum, maximum: scroller.setFixedHeight(CONTROL_HEIGHT + (scroller.horizontalScrollBar().sizeHint().height() if maximum else 0)))
        return scroller

    def _gacha_collect_fields(self, entry: QWidget, teleport: str, editable: bool):
        """Mount station-wide editors without changing conflicting legacy records."""
        entry.item = self._deposit_line_edit("")
        entry.item.setFixedHeight(CONTROL_HEIGHT)
        entry.item.setMinimumWidth(80)
        entry.item.setAccessibleName(f"{teleport} Item")
        entry.destination = NoWheelComboBox()
        entry.destination.setObjectName("GachaDestination")
        entry.destination.setProperty("settingsChevron", True)
        entry.destination.setFixedHeight(CONTROL_HEIGHT)
        entry.destination.setMinimumWidth(120)
        entry.destination.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        entry.destination.setSizeAdjustPolicy(NoWheelComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        entry.destination.setAccessibleName(f"{teleport} Dedi")
        fields = [SettingsField(title, control, icon=icon, natural_label=True) for title, control, icon in (("Item", entry.item, "cube"), ("Dedi", entry.destination, "server"))]
        scroller = self._gacha_field_scroll(fields)
        scroller.setEnabled(editable)
        entry.layout().addWidget(scroller)
        entry.warning = settings_label("")
        entry.warning.setWordWrap(True)
        entry.layout().addWidget(entry.warning)
        self._gacha_collect_editors[teleport] = entry
        self._refresh_collect_fields(teleport, entry)
        # textEdited distinguishes intentional resolution from focus-only changes.
        entry.item_dirty = False
        entry.item.textEdited.connect(lambda _text: setattr(entry, "item_dirty", True))
        entry.item.editingFinished.connect(lambda: self._edit_collect_group(teleport, "item", entry.item.text(), entry))
        entry.destination.activated.connect(lambda _index: self._edit_collect_group(teleport, "dedi_teleport", entry.destination.currentData(), entry))

    def _refresh_collect_fields(self, teleport: str, entry: QWidget):
        """Display uniform values or explicit mixed states; never normalize on load."""
        records = [r for r in self.gacha_collect_config if r["teleporter"] == teleport]
        warnings = []
        for key, control in (("item", entry.item), ("dedi_teleport", entry.destination)):
            values = {r.get(key, "") for r in records}
            mixed = len(values) > 1
            value = next(iter(values), "") if not mixed else ""
            control.blockSignals(True)
            if key == "item":
                control.setText(value)
                control.setPlaceholderText("Mixed ? choose Item" if mixed else "")
                entry.item_dirty = False
            else:
                control.clear()
                if mixed:
                    control.addItem("Mixed ? choose Dedi", None)
                control.addItem("Select Dedi", "")
                for name in deposit_destination_options(self.deposit_config):
                    control.addItem(name, name)
                if value and control.findData(value) < 0:
                    control.addItem(f"Missing: {value}", value)
                control.setCurrentIndex(0 if mixed else max(0, control.findData(value)))
                error = "Choose a shared Dedi destination." if mixed else collection_destination_error(self.deposit_config, value)
                control.setToolTip(error)
                control.setProperty("invalidDestination", bool(error))
                control.style().unpolish(control)
                control.style().polish(control)
            control.blockSignals(False)
            if mixed:
                label = "Item" if key == "item" else "Dedi"
                details = "; ".join(f"{r['side'].title()}: {r.get(key, '') or '(empty)'}" for r in records)
                warnings.append(f"{label} differs ({details}). Choose a shared value to apply to both sides.")
        entry.warning.setText("\n".join(warnings))
        entry.warning.setVisible(bool(warnings))

    def _edit_collect_group(self, teleport: str, key: str, value: str, entry: QWidget):
        """Save one explicitly edited field across sides, rolling back on failure."""
        if value is None or (key == "item" and not entry.item_dirty):
            return
        records = copy.deepcopy(self.gacha_collect_config)
        group = [r for r in records if r["teleporter"] == teleport]
        if not group:
            return
        for record in group:
            record[key] = value
        self._commit_gacha_records("collect", records)
        self._refresh_collect_fields(teleport, entry)

    def toggle_gacha_side(self, kind: str, teleport: str, side: str, card: GachaSideCard):
        """Add/remove a flat record, keeping live widgets for reversible animation."""
        records = copy.deepcopy(self._gacha_records(kind))
        group = [record for record in records if record["teleporter"] == teleport]
        existing = next((record for record in group if record["side"] == side), None)
        if existing is not None:
            if len(group) == 1 and not self.confirm("Delete Gacha station", "Removing the last side deletes this teleport station. Continue?", "DELETE"):
                return
            records.remove(existing)
        else:
            record = self._new_gacha_record(kind, teleport, side)
            if kind == "collect" and group:
                record.update({key: group[0].get(key, "") for key in ("item", "dedi_teleport")})
            records.append(record)
        if not self._commit_gacha_records(kind, records):
            return
        if existing is not None and len(group) == 1:
            self._render_settings_group("GACHA")
            return
        card.set_present(existing is None)
        if kind == "collect":
            self._refresh_collect_fields(teleport, self._gacha_collect_editors[teleport])

    def _new_gacha_record(self, kind: str, teleport: str, side: str):
        """Create a flat side record; task names are generated only at runtime."""
        factory = default_gacha_collect_entry if kind == "collect" else default_gacha_entry
        return factory(teleport, side)

    def _focus_blank_gacha(self, kind: str):
        """Reveal the unfinished station without adding another blank group."""
        self.gacha_section_expanded[kind] = True
        self._render_settings_group("GACHA")

        def focus():
            """Focus after Qt has installed and laid out the replacement form."""
            field = self._gacha_teleport_fields.get((kind, ""))
            if field is not None:
                self.settings_form_area.ensureWidgetVisible(field)
                field.setFocus()

        QTimer.singleShot(0, focus)

    def add_gacha_group(self, kind: str = "gacha"):
        """Add one blank, left-only station or focus the existing unfinished one."""
        records = copy.deepcopy(self._gacha_records(kind))
        if any(record["teleporter"] == "" for record in records):
            self._focus_blank_gacha(kind)
            return
        records.append(self._new_gacha_record(kind, "", "left"))
        if self._commit_gacha_records(kind, records):
            self._focus_blank_gacha(kind)

    def update_gacha_group_teleporter(self, old_teleporter: str, field: QLineEdit, kind: str = "gacha"):
        """Rename every side together, retaining duplicate-name validation."""
        value = field.text()
        if value == old_teleporter:
            return
        records = copy.deepcopy(self._gacha_records(kind))
        if any(record["teleporter"] != old_teleporter and record["teleporter"].casefold() == value.casefold() for record in records):
            field.setText(old_teleporter)
            self.dialog("Duplicate Gacha Teleporter", "A station with this teleport name already exists.", "error")
            return
        for record in records:
            if record["teleporter"] == old_teleporter:
                record["teleporter"] = value
        if self._commit_gacha_records(kind, records):
            self._render_settings_group("GACHA")
        else:
            field.setText(old_teleporter)

    def remove_gacha_group(self, teleporter: str, kind: str = "gacha"):
        """Delete the whole station, never only one of its side records."""
        records = [record for record in self._gacha_records(kind) if record["teleporter"] != teleporter]
        if self._commit_gacha_records(kind, records):
            self._render_settings_group("GACHA")

    def remove_gacha_section(self, kind: str):
        """Confirm and atomically empty one section."""
        if self._gacha_records(kind) and self.confirm("Delete all Gacha stations", "Delete every station in this section?", "DELETE ALL") and self._commit_gacha_records(kind, []):
            self._render_settings_group("GACHA")

    def _ensure_gacha_config(self):
        if hasattr(self, "gacha_config"):
            return
        try:
            self.gacha_config = load_gacha_config()
        except ValueError as exc:
            self.gacha_config = []
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
            self.gacha_collect_config = save_gacha_collect_config(self.gacha_collect_config)
        except ValueError as exc:
            self.append_log(f"[ERROR] Invalid gacha collect config: {exc}\n")
            self.dialog("Invalid Gacha Collect Config", str(exc), "error")
            return False
        if show_log:
            self.append_log("[SUCCESS] Gacha collect config saved automatically.\n")
        return True

    def update_station_field(self, kind, entry_index, key, field):
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

    def reset_gacha_config(self):
        """Clear both lists and their profile assignment, restoring files on failure."""
        old_gacha = copy.deepcopy(self.gacha_config)
        old_collect = copy.deepcopy(self.gacha_collect_config)
        updated = self._set_group_template_references(self.settings, "GACHA", "")
        written = []
        try:
            save_gacha_config([])
            written.append((save_gacha_config, old_gacha))
            save_gacha_collect_config([])
            written.append((save_gacha_collect_config, old_collect))
            updated = save_settings(updated)
        except (OSError, ValueError) as exc:
            for save, previous in reversed(written):
                try:
                    save(previous)
                except (OSError, ValueError) as rollback_error:
                    self.append_log(f"[ERROR] Gacha reset rollback failed: {rollback_error}\n")
            self.dialog("Unable to reset Gacha", str(exc), "error")
            return
        self.gacha_config = []
        self.gacha_collect_config = []
        self.settings = updated
        self.form_values = updated.copy()
        self._skip_visible_field_persist = True
        self._render_settings_group("GACHA")
        self.append_log("[INFO] Gacha and Gacha collect station lists cleared.\n")
