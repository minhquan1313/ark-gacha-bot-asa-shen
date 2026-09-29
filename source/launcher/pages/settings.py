import threading

from PySide6.QtCore import QObject
from shiboken6 import isValid

from source.gacha_bot.craft_config import load_craft_config, save_craft_config
from source.launcher.auto_keys import resolve_supported_keys
from source.launcher.components.settings_sections import (
    SettingsActionButton,
    SettingsBreadcrumbHeader,
    SettingsColumns,
    SettingsField,
    SettingsFieldGrid,
    SettingsSectionCard,
    SettingsUnitControl,
    settings_icon,
    settings_label,
)
from source.launcher.config.constants import SETTINGS_GROUP_LABELS
from source.launcher.config.template_settings import convert_craft_yaw
from source.launcher.pages.common import (
    AUTO_KEYS_ACTIONS,
    DEFAULT_SETTINGS,
    DEFAULT_TEMPLATE_FILENAME,
    SETTINGS_GROUPS,
    TEMPLATE_DIRECTORY,
    TEMPLATE_GROUP_REFERENCE_KEYS,
    TEMPLATE_GROUP_SETTING_KEYS,
    Counter,
    CyberCheckBox,
    CyberSwitch,
    CyberTemplateConflictDialog,
    CyberTextInputDialog,
    NoWheelComboBox,
    Path,
    QAction,
    QButtonGroup,
    QDesktopServices,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QSpacerItem,
    Qt,
    QUrl,
    QVBoxLayout,
    QWidget,
    SmoothScrollArea,
    TemplateCatalog,
    _settings_group_title,
    build_template,
    contextlib,
    convert_deposit_yaw,
    copy,
    load_deposit_config,
    load_gacha_collect_config,
    load_gacha_config,
    load_pego_config,
    load_settings,
    migrate_template_references,
    next_unique_template_filename,
    normalize_template_id,
    os,
    read_template,
    resolve_template_reference,
    safe_template_filename,
    save_deposit_config,
    save_gacha_collect_config,
    save_gacha_config,
    save_pego_config,
    save_settings,
    scan_templates,
    setting_label,
    setting_tooltip,
    subprocess,
    write_template,
)
from source.launcher.settings_theme import CONTROL_HEIGHT, settings_style


class ActivationKeyButton(SettingsActionButton):
    """Capture one non-modifier keyboard key for the Auto Keys activation gate."""

    def __init__(self, key_name: str, on_capture):
        super().__init__(f"SET KEY: {key_name}", "auto_keys", compact=False)
        self.key_name = key_name
        self.on_capture = on_capture
        self.capturing = False
        self.clicked.connect(self._begin_capture)

    def _begin_capture(self):
        self.capturing = True
        self.setText("PRESS A KEY...")
        self.setFocus()

    def keyPressEvent(self, event):
        if not self.capturing:
            return super().keyPressEvent(event)
        key = event.key()
        modifiers = {
            Qt.Key.Key_Shift,
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        }
        if key in modifiers:
            return
        name = f"F{key - Qt.Key.Key_F1 + 1}" if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24 else event.text().upper().strip()
        if not name:
            self.setText("SET KEY: INVALID")
            return
        self.key_name = name
        self.capturing = False
        self.setText(f"SET KEY: {name}")
        self.on_capture(name)


class SettingsPagesMixin:
    def _settings_page(self):
        page, layout = self._page("SettingsPage")
        page.setStyleSheet(settings_style())
        self.settings_breadcrumb = SettingsBreadcrumbHeader(self._settings_import_export_button())

        shell, shell_layout = self._panel()
        shell.setObjectName("SettingsShell")
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        shell_layout.addLayout(content, 1)

        self.settings_tabs = QButtonGroup(self)
        self.settings_tabs.setExclusive(True)
        tabs = QVBoxLayout()
        tabs.setContentsMargins(8, 10, 8, 10)
        tabs.setSpacing(6)
        tab_frame = QFrame()
        tab_frame.setObjectName("SettingsTabs")
        tab_frame.setFixedWidth(164)
        tab_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        tab_frame.setLayout(tabs)
        self.settings_breadcrumb.set_sidebar(tab_frame)
        layout.addWidget(
            SettingsColumns(self.settings_breadcrumb, tab_frame, shell, layout.spacing()),
            1,
        )

        form_area = SmoothScrollArea()
        form_area.setWidgetResizable(True)
        form_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_area.setObjectName("SettingsScroll")
        self.settings_form_area = form_area
        self.settings_form = QWidget()
        self.settings_form.setObjectName("SettingsForm")
        self.settings_form_layout = QGridLayout(self.settings_form)
        self.settings_form_layout.setContentsMargins(28, 20, 28, 20)
        self.settings_form_layout.setHorizontalSpacing(18)
        self.settings_form_layout.setVerticalSpacing(10)
        form_area.setWidget(self.settings_form)
        content.addWidget(form_area, 1)

        for group_name in SETTINGS_GROUPS:
            label = SETTINGS_GROUP_LABELS.get(group_name, group_name)
            icon = {
                "SERVER": "server",
                "STATIONS": "antenna",
                "PEGO": "paw",
                "DEDI": "cube",
                "GACHA": "paw",
                "CRAFT": "tools",
                "LAUNCHER": "rocket",
            }[group_name]
            button = SettingsActionButton("  " + label, icon, "nav")
            button.setFixedHeight(56)
            button.setObjectName("SettingsTab")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, name=group_name: self._render_settings_group(name))
            self.settings_tabs.addButton(button)
            tabs.addWidget(button)
            if group_name == "SERVER":
                button.setChecked(True)
        tabs.addStretch()

        footer = QFrame()
        footer.setObjectName("SettingsBottomBar")
        action_bar = QHBoxLayout(footer)
        action_bar.setContentsMargins(12, 8, 12, 8)
        action_bar.setSpacing(8)
        footer_hint = QLabel("CHANGES WILL BE SAVED AUTOMATICALLY")
        footer_hint.setWordWrap(True)
        footer_hint.setObjectName("SettingsSaveHint")
        action_bar.addWidget(footer_hint, 1)
        refresh_button = SettingsActionButton("REFRESH", "update")
        refresh_button.setFixedWidth(150)
        self.settings_refresh_button = refresh_button
        refresh_button.clicked.connect(self.refresh_json_configs)
        action_bar.addWidget(refresh_button)
        reset_button = SettingsActionButton("RESET", "trash", "danger")
        reset_button.setFixedWidth(128)
        self.settings_reset_button = reset_button
        reset_button.clicked.connect(self.confirm_reset)
        action_bar.addWidget(reset_button)
        layout.addWidget(footer)
        self._render_settings_group("SERVER")
        return page

    def _settings_import_export_button(self):
        """Use the profile's native combo popup to dispatch existing file actions."""
        selector = NoWheelComboBox()
        selector.setObjectName("SettingsImportExport")
        selector.setProperty("settingsChevron", True)
        selector.setAccessibleName("Import / Export")
        selector.setPlaceholderText("IMPORT / EXPORT")
        selector.setFixedHeight(CONTROL_HEIGHT)
        actions = []
        for caption, callback, attribute in (
            ("Import Settings", self.import_template_setting, "template_import_action"),
            ("Export Settings", self.export_template_setting, "template_export_action"),
            (
                "Browse Template Folder",
                self.browse_template_settings,
                "template_browse_action",
            ),
        ):
            action = QAction(caption, selector)
            action.triggered.connect(callback)
            setattr(self, attribute, action)
            actions.append(action)
            selector.addItem(caption)
        selector.setCurrentIndex(-1)

        def activate(index: int):
            """Restore the caption before opening dialogs; allow repeated actions."""
            selector.setCurrentIndex(-1)
            if 0 <= index < len(actions):
                actions[index].trigger()

        selector.activated.connect(activate)
        self.template_action_button = selector
        return selector

    def _template_catalog(self):
        """Rescan versioned template files for the settings UI."""
        self.template_catalog = scan_templates()
        return self.template_catalog

    def _template_group_state(self, group_name: str):
        """Resolve a settings group to manual, active, or missing template state."""
        reference_keys = TEMPLATE_GROUP_REFERENCE_KEYS.get(group_name, ())
        reference_values = {str(self.form_values.get(key, "")) for key in reference_keys}
        if reference_values == {""} or not reference_values:
            return "manual", "", ""
        if len(reference_values) != 1:
            return "missing", "", "Template assignments are mixed for this group."
        name = next(iter(reference_values))
        catalog = self._template_catalog()
        resolved, resolve_error = resolve_template_reference(name, catalog)
        if resolved in catalog.templates:
            return "active", str(resolved), ""
        error = catalog.errors.get(str(resolved), resolve_error)
        return "missing", str(resolved or name), error

    def _add_template_selector(self, group_name: str, in_header: bool = False):
        """Add the no-wheel template selector beside a settings group heading."""
        state, selected_name, error = self._template_group_state(group_name)
        catalog = self._template_catalog()
        selector = NoWheelComboBox()
        selector_name = {
            "active": "ActiveTemplateSelector",
            "missing": "MissingTemplateSelector",
        }.get(state, "TemplateSelector")
        selector.setObjectName(selector_name)
        selector.setMinimumWidth(190)
        selector.addItem("Manual", "")
        display_counts = Counter(str(template["name"]) for template in catalog.templates.values())
        sorted_templates = sorted(
            catalog.templates.items(),
            key=lambda item: (str(item[1]["name"]).casefold(), item[0].casefold()),
        )
        for template_id, template in sorted_templates:
            display_name = str(template["name"])
            label = f"{display_name} — {template_id}" if display_counts[display_name] > 1 else display_name
            selector.addItem(
                f"V  {label}" if state == "active" and template_id == selected_name else label,
                template_id,
            )
            selector.setItemData(selector.count() - 1, template_id, Qt.ItemDataRole.ToolTipRole)
        if selected_name and selector.findData(selected_name) < 0:
            selector.addItem(f"MISSING: {selected_name}", selected_name)
        if state == "missing" and not selected_name:
            selector.addItem("MIXED ASSIGNMENTS", "__mixed__")
        current_index = selector.findData(selected_name or ("__mixed__" if state == "missing" else ""))
        selector.setCurrentIndex(max(0, current_index))
        if error:
            selector.setToolTip(error)
        selector.currentIndexChanged.connect(lambda _index, combo=selector, group=group_name: self.change_template_group(group, str(combo.currentData())))
        if in_header:
            self.settings_breadcrumb.set_profile(selector)
        else:
            action_column = getattr(self, "_settings_form_action_column", 3)
            self.settings_form_layout.addWidget(selector, 0, action_column, alignment=Qt.AlignmentFlag.AlignRight)
        self.template_selector = selector
        return state, selected_name, error

    def _template_field_widget(
        self,
        field: QWidget,
        state: str,
        template_name: str,
        error: str,
    ):
        """Wrap a normal setting with template status styling and a compact marker."""
        if state == "manual":
            return field
        frame = QFrame()
        frame.setObjectName("TemplateFieldActive" if state == "active" else "TemplateFieldMissing")
        row = QHBoxLayout(frame)
        row.setContentsMargins(4, 1, 4, 1)
        row.setSpacing(5)
        row.addWidget(field, 1)
        marker = QLabel("V" if state == "active" else "!")
        marker.setObjectName("TemplateTick" if state == "active" else "TemplateWarning")
        row.addWidget(marker)
        tooltip = f"Using {template_name}" if state == "active" else error
        frame.setToolTip(tooltip)
        field.setToolTip(tooltip)
        field.setEnabled(state != "active")
        return frame

    def _style_template_collection(
        self,
        content: QWidget,
        state: str,
        template_name: str,
        error: str,
    ):
        """Style and lock a collection editor when a template is active."""
        if state == "manual":
            return
        content.setObjectName("TemplateGroupActive" if state == "active" else "TemplateGroupMissing")
        content.setToolTip(f"Using {template_name}" if state == "active" else error)
        content.setEnabled(state != "active")
        content.style().unpolish(content)
        content.style().polish(content)

    def _set_group_template_references(self, settings: dict, group_name: str, template_name: str):
        """Return settings with every reference for a group assigned together."""
        updated = copy.deepcopy(settings)
        for key in TEMPLATE_GROUP_REFERENCE_KEYS[group_name]:
            updated[key] = template_name
        return updated

    def change_template_group(self, group_name: str, template_name: str):
        """Switch one settings group between Manual and a selected template."""
        if template_name == "__mixed__":
            return False
        old_settings = copy.deepcopy(self.settings)
        new_settings = self._set_group_template_references(old_settings, group_name, template_name)
        if not template_name:
            try:
                new_settings = save_settings(new_settings)
            except OSError as exc:
                self.dialog("Template Settings", str(exc), "error")
                return False
            self.settings = new_settings
            self.form_values = new_settings.copy()
            self._skip_visible_field_persist = True
            self._render_settings_group(group_name)
            self.append_log(f"[INFO] {group_name} settings switched to Manual.\n")
            return True

        catalog = self._template_catalog()
        template = catalog.templates.get(template_name)
        if template is None:
            self._skip_visible_field_persist = True
            self._render_settings_group(group_name)
            self.dialog(
                "Template Unavailable",
                catalog.errors.get(template_name, f'Template "{template_name}" cannot be found.'),
                "error",
            )
            return False

        old_deposit = copy.deepcopy(getattr(self, "deposit_config", None))
        old_gacha = copy.deepcopy(getattr(self, "gacha_config", None))
        old_gacha_collect = copy.deepcopy(getattr(self, "gacha_collect_config", None))
        old_pego = copy.deepcopy(getattr(self, "pego_config", None))
        old_craft = copy.deepcopy(getattr(self, "craft_config", None))
        new_deposit = old_deposit
        new_gacha = old_gacha
        new_gacha_collect = old_gacha_collect
        new_pego = old_pego
        new_craft = old_craft
        if group_name == "DEDI" and old_deposit is None:
            old_deposit = load_deposit_config()
            new_deposit = old_deposit
        elif group_name == "GACHA" and old_gacha is None:
            old_gacha = load_gacha_config()
            new_gacha = old_gacha
            old_gacha_collect = load_gacha_collect_config()
            new_gacha_collect = old_gacha_collect
        elif group_name == "CRAFT" and old_craft is None:
            old_craft = load_craft_config()
            new_craft = old_craft
        elif group_name == "PEGO" and old_pego is None:
            old_pego = load_pego_config()
            new_pego = old_pego
        try:
            if group_name in TEMPLATE_GROUP_SETTING_KEYS:
                for key in TEMPLATE_GROUP_SETTING_KEYS[group_name]:
                    new_settings[key] = template["data"]["settings"][key]
            if group_name == "DEDI":
                self._ensure_deposit_config()
                new_deposit = convert_deposit_yaw(
                    template["data"]["dedis"],
                    float(old_settings["station_yaw"]),
                    False,
                )
                save_deposit_config(new_deposit)
            elif group_name == "GACHA":
                self._ensure_gacha_config()
                new_gacha = save_gacha_config(template["data"]["gacha"])
                new_gacha_collect = save_gacha_collect_config(template["data"]["gacha_collect"])
            elif group_name == "CRAFT":
                new_craft = save_craft_config(
                    convert_craft_yaw(
                        template["data"]["craft"],
                        float(old_settings["station_yaw"]),
                        False,
                    )
                )
            elif group_name == "PEGO":
                self._ensure_pego_config()
                new_pego = save_pego_config(template["data"]["pego"])
            new_settings = save_settings(new_settings)
        except (OSError, TypeError, ValueError) as exc:
            self._rollback_template_group(
                group_name,
                old_settings,
                old_deposit,
                old_gacha,
                old_gacha_collect,
                old_pego,
                old_craft,
            )
            self.dialog("Template Apply Failed", str(exc), "error")
            return False

        self.settings = new_settings
        self.form_values = new_settings.copy()
        if group_name == "DEDI":
            self.deposit_config = new_deposit
        elif group_name == "GACHA":
            self.gacha_config = new_gacha
            self.gacha_collect_config = new_gacha_collect
        elif group_name == "CRAFT":
            self.craft_config = new_craft
        elif group_name == "PEGO":
            self.pego_config = new_pego
        self._skip_visible_field_persist = True
        self._render_settings_group(group_name)
        self._update_auto_start_switch()
        self.append_log(f"[SUCCESS] Applied {template_name} to {group_name}.\n")
        return True

    def _rollback_template_group(
        self,
        group_name: str,
        old_settings: dict,
        old_deposit: dict | None,
        old_gacha: list[dict] | None,
        old_gacha_collect: list[dict] | None,
        old_pego: list[dict] | None,
        old_craft: dict | None = None,
    ):
        """Best-effort restore canonical files after a partial template write."""
        with contextlib.suppress(OSError, TypeError, ValueError):
            save_settings(old_settings)
        if group_name == "DEDI" and old_deposit is not None:
            with contextlib.suppress(OSError, TypeError, ValueError):
                save_deposit_config(old_deposit)
        elif group_name == "GACHA" and old_gacha is not None:
            with contextlib.suppress(OSError, TypeError, ValueError):
                save_gacha_config(old_gacha)
            if old_gacha_collect is not None:
                with contextlib.suppress(OSError, TypeError, ValueError):
                    save_gacha_collect_config(old_gacha_collect)
        elif group_name == "CRAFT" and old_craft is not None:
            with contextlib.suppress(OSError, TypeError, ValueError):
                save_craft_config(old_craft)
        elif group_name == "PEGO" and old_pego is not None:
            with contextlib.suppress(OSError, TypeError, ValueError):
                save_pego_config(old_pego)

    def apply_default_template_to_all_groups(self):
        """Apply the bundled default as one rollback-protected reset operation."""
        old_settings = copy.deepcopy(self.settings)
        old_deposit = load_deposit_config()
        old_gacha = load_gacha_config()
        old_gacha_collect = load_gacha_collect_config()
        old_pego = load_pego_config()
        old_craft = load_craft_config()
        for group_name in (
            "SERVER",
            "STATIONS",
            "PEGO",
            "DEDI",
            "GACHA",
            "CRAFT",
            "LAUNCHER",
        ):
            if self.change_template_group(group_name, DEFAULT_TEMPLATE_FILENAME):
                continue
            try:
                self.settings = save_settings(old_settings)
                self.form_values = self.settings.copy()
                self.deposit_config = save_deposit_config(old_deposit)
                self.gacha_config = save_gacha_config(old_gacha)
                self.gacha_collect_config = save_gacha_collect_config(old_gacha_collect)
                self.pego_config = save_pego_config(old_pego)
                self.craft_config = save_craft_config(old_craft)
            except (OSError, TypeError, ValueError) as exc:
                self.dialog(
                    "Reset Rollback Failed",
                    f"Unable to fully restore the previous configuration: {exc}",
                    "error",
                )
            return False
        return True

    def sync_configured_templates(self):
        """Re-materialize valid configured templates after startup or refresh."""
        catalog = self._template_catalog()
        migrated_settings, migration_errors = migrate_template_references(self.settings, catalog)
        self.template_reference_errors = migration_errors
        if migrated_settings != self.settings:
            self.settings = save_settings(migrated_settings)
            self.form_values = self.settings.copy()
        current_group = getattr(self, "current_settings_group", "SERVER")
        for group_name, reference_keys in TEMPLATE_GROUP_REFERENCE_KEYS.items():
            references = {str(self.settings.get(key, "")) for key in reference_keys}
            if len(references) != 1:
                continue
            template_name = next(iter(references))
            if not template_name or template_name not in catalog.templates:
                continue
            self.change_template_group(group_name, template_name)
        if hasattr(self, "settings_form_layout"):
            self._skip_visible_field_persist = True
            self._render_settings_group(current_group)

    def import_template_setting(self):
        """Import one validated template selected through a file picker."""
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Import Template Setting",
            str(Path.cwd()),
            "JSON files (*.json)",
        )
        if not path:
            return
        try:
            template, warnings = read_template(path)
            destination = self._store_template_with_conflict(template, Path(path).name)
        except (OSError, ValueError) as exc:
            self.dialog("Template Import Failed", str(exc), "error")
            return
        if destination is None:
            return
        warning_text = f"\n\n{' '.join(warnings)}" if warnings else ""
        self.dialog(
            "Template Imported",
            f'Imported "{template["name"]}" as {destination.name}.{warning_text}',
            "success",
        )
        self._refresh_current_settings_group()

    def export_template_setting(self):
        """Export the complete current effective main-bot configuration."""
        self.persist_settings_from_visible_fields(show_log=False, show_error=False)
        dialog = CyberTextInputDialog(
            self,
            "Export Template",
            "Enter the template display name. A Windows-safe JSON filename will be derived automatically.",
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            template = build_template(
                dialog.text_value(),
                self.settings,
                load_deposit_config(),
                load_gacha_config(),
                load_pego_config(),
                load_gacha_collect_config(),
                load_craft_config(),
            )
            destination = self._store_template_with_conflict(template, safe_template_filename(str(template["name"])))
        except (OSError, TypeError, ValueError) as exc:
            self.dialog("Template Export Failed", str(exc), "error")
            return
        if destination is None:
            return
        self.dialog(
            "Template Exported",
            f'Exported "{template["name"]}" as {destination.name}.',
            "success",
        )
        self._show_exported_template(destination)
        self._refresh_current_settings_group()

    def _store_template_with_conflict(self, template: dict, template_id: str):
        """Store a template after resolving name or safe-filename collisions."""
        catalog = self._template_catalog()
        template_id = normalize_template_id(template_id)
        collision_id, collision_path = self._find_template_collision(template_id, catalog)
        if collision_path is None:
            return write_template(template, template_id)

        conflict = CyberTemplateConflictDialog(self, collision_id or template_id)
        result = conflict.exec()
        if result == QDialog.DialogCode.Rejected:
            return None
        if result == CyberTemplateConflictDialog.KEEP_BOTH_RESULT:
            unique_filename = next_unique_template_filename(template_id, catalog)
            while True:
                rename = CyberTextInputDialog(
                    self,
                    "Keep Both Templates",
                    "Enter a unique filename for the incoming template.",
                    unique_filename,
                    "KEEP BOTH",
                )
                if rename.exec() != QDialog.DialogCode.Accepted:
                    return None
                candidate = safe_template_filename(rename.text_value())
                candidate_id, candidate_path = self._find_template_collision(candidate, catalog)
                if candidate_path is None:
                    return write_template(template, candidate)
                self.dialog(
                    "Template Name In Use",
                    f'"{candidate_id or candidate}" still conflicts with an existing template.',
                    "warning",
                )
                unique_filename = next_unique_template_filename(candidate, catalog)

        return write_template(
            template,
            collision_id or template_id,
            replaced_path=collision_path,
        )

    def _find_template_collision(self, template_id: str, catalog: TemplateCatalog):
        """Find an existing template with the same identity or safe filename."""
        template_id = normalize_template_id(template_id)
        target_name = template_id.casefold()
        for existing_name, path in catalog.paths.items():
            if existing_name.casefold() == target_name:
                return existing_name, path
        for existing_name, path in catalog.error_paths.items():
            if existing_name.casefold() == target_name:
                return existing_name, path
        destination = TEMPLATE_DIRECTORY / template_id
        if destination.exists():
            return destination.name, destination
        return "", None

    def browse_template_settings(self):
        """Open the managed template settings directory."""
        TEMPLATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(TEMPLATE_DIRECTORY.resolve())))

    def _show_exported_template(self, path: Path):
        """Reveal an exported file in Explorer or open its parent directory."""
        resolved = path.resolve()
        if os.name == "nt":
            try:
                subprocess.Popen(["explorer.exe", f"/select,{resolved}"])
                return
            except OSError:
                pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved.parent)))

    def _refresh_current_settings_group(self):
        """Rerender the active settings group after template catalog changes."""
        if not hasattr(self, "settings_form_layout"):
            return
        self.sync_configured_templates()

    def _setting_field(self, key: str):
        """Build one setting editor and connect automatic persistence."""
        default_value = DEFAULT_SETTINGS[key]
        if isinstance(default_value, bool):
            field = CyberSwitch()
            field.blockSignals(True)
            field.setChecked(bool(self.form_values.get(key, default_value)))
            field.blockSignals(False)
            field.toggled.connect(lambda checked=False, setting_key=key: self.persist_single_setting(setting_key))
        else:
            field = QLineEdit(str(self.form_values.get(key, default_value)))
            field.setObjectName("SettingField")
            field.editingFinished.connect(lambda setting_key=key: self.persist_single_setting(setting_key))
            field.returnPressed.connect(lambda setting_key=key: self.persist_single_setting(setting_key))
        tooltip = setting_tooltip(key)
        if tooltip:
            field.setToolTip(tooltip)
        self.fields[key] = field
        return field

    def _setting_field_container(
        self,
        field: QWidget,
        state: str,
        template_name: str,
        template_error: str,
        templated: bool,
    ):
        """Wrap a setting editor with template state when needed."""
        if templated:
            return self._template_field_widget(field, state, template_name, template_error)
        return field

    def _station_yaw_field_container(self, field: QWidget):
        """Place the Station yaw capture helper directly beside the field."""
        frame = QFrame()
        row = QHBoxLayout(frame)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(field, 1)
        helper = SettingsActionButton("", "target")
        helper.setObjectName("PositionCaptureButton")
        helper.setFixedSize(CONTROL_HEIGHT, CONTROL_HEIGHT)
        helper.setToolTip("Open position helper")
        helper.setAccessibleName("Open position helper")
        self.station_yaw_capture_button = helper
        helper.clicked.connect(self.open_position_render_helper)
        row.addWidget(helper)
        return frame

    def _start_settings_section(
        self,
        group_name: str,
        max_fields: int,
    ):
        """Add a settings heading and template selector for one simple section."""
        heading = QLabel(_settings_group_title(group_name))
        heading.setObjectName("SectionHeading")
        self._settings_form_action_column = max((max_fields * 2) - 1, 3)
        self.settings_form_layout.addWidget(heading, 0, 0, 1, self._settings_form_action_column)
        if group_name in TEMPLATE_GROUP_REFERENCE_KEYS:
            return self._add_template_selector(group_name)
        return "manual", "", ""

    def _add_setting_row(
        self,
        keys: tuple[str, ...],
        row_number: int,
        state: str,
        template_name: str,
        template_error: str,
        templated_keys: set[str],
    ):
        """Add one explicit settings row and return the next grid row."""
        for index in range(len(keys)):
            self.settings_form_layout.setColumnStretch(index * 2 + 1, 1)
        for field_index, key in enumerate(keys):
            label = QLabel(setting_label(key))
            label.setObjectName("FormLabel")
            tooltip = setting_tooltip(key)
            if tooltip:
                label.setToolTip(tooltip)
            col = field_index * 2
            field = self._setting_field(key)
            content = self._station_yaw_field_container(field) if key == "station_yaw" else field
            self.settings_form_layout.addWidget(label, row_number, col)
            self.settings_form_layout.addWidget(
                self._setting_field_container(
                    content,
                    state,
                    template_name,
                    template_error,
                    key in templated_keys,
                ),
                row_number,
                col + 1,
            )
        return row_number + 1

    def _add_settings_divider(self, row_number: int, text: str):
        """Add a reusable labeled divider row between settings groups."""
        frame = QFrame()
        frame.setObjectName("SettingsDivider")
        row = QHBoxLayout(frame)
        row.setContentsMargins(0, 6, 0, 6)
        row.setSpacing(10)

        left_line = QFrame()
        left_line.setObjectName("SettingsDividerLine")
        left_line.setFixedHeight(1)
        right_line = QFrame()
        right_line.setObjectName("SettingsDividerLine")
        right_line.setFixedHeight(1)

        label = QLabel(text)
        label.setObjectName("SettingsDividerLabel")

        row.addWidget(left_line, 1)
        row.addWidget(label)
        row.addWidget(right_line, 1)
        self.settings_form_layout.addWidget(
            frame,
            row_number,
            0,
            1,
            self._settings_form_action_column + 1,
        )
        return row_number + 1

    def _add_settings_spacer(self, row_number: int):
        """Add the final expanding spacer below a settings section."""
        self.settings_form_layout.addItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding),
            row_number,
            0,
            1,
            self._settings_form_action_column + 1,
        )

    def _approved_settings_content(self, group: str):
        """Mount the scoped content without changing the shared field registry."""
        state = self._add_template_selector(group, in_header=True)
        content = QWidget()
        content.setObjectName("ApprovedSettingsContent")
        box = QVBoxLayout(content)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(16)
        self.settings_form_layout.addWidget(content, 0, 0, 1, 4)
        self.settings_form_layout.setContentsMargins(14, 0, 0, 0)
        self.settings_form_layout.setRowStretch(0, 0)
        self.settings_form_layout.setRowStretch(1, 1)
        self.settings_form_layout.addItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding),
            1,
            0,
            1,
            4,
        )
        return box, state

    def _approved_setting_field(
        self,
        key: str,
        title: str,
        state: tuple[str, str, str],
        description: str = "",
        stacked: bool = False,
        unit: str = "",
    ):
        """Adapt the existing editor, template lock, and autosave connections."""
        field = self._setting_field(key)
        field.setFixedHeight(CONTROL_HEIGHT)
        field.setMinimumWidth(0)
        control = self._station_yaw_field_container(field) if key == "station_yaw" else field
        if key in TEMPLATE_GROUP_SETTING_KEYS[self.current_settings_group]:
            control = self._template_field_widget(control, *state)
            if control is not field and control.layout() is not None:
                control.layout().setContentsMargins(0, 0, 0, 0)
                control.setFixedHeight(CONTROL_HEIGHT)
        if unit:
            wrapper = QWidget()
            row = QHBoxLayout(wrapper)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(10)
            row.addWidget(control, 1)
            row.addWidget(settings_label(unit))
            control = wrapper
        return SettingsField(title, control, description, stacked)

    def _render_server_settings(self):
        """Render the approved Server card with the existing three editors."""
        box, state = self._approved_settings_content("SERVER")
        card = SettingsSectionCard(
            "Server settings",
            "Set the server information for the bot to connect to",
            "server",
            "server",
        )
        grid = SettingsFieldGrid(
            [
                self._approved_setting_field(
                    "server_number",
                    "Server",
                    state,
                    "ARK server number or ID",
                    stacked=True,
                ),
                self._approved_setting_field(
                    "ping",
                    "Server ping (ms)",
                    state,
                    "Server ping in milliseconds",
                    stacked=True,
                ),
                self._approved_setting_field(
                    "singleplayer",
                    "Singleplayer mode",
                    state,
                    "Enable if running a singleplayer/local game",
                    stacked=True,
                ),
            ]
        )
        card.body.addWidget(grid)
        info = QFrame()
        info.setObjectName("ServerInformation")
        row = QHBoxLayout(info)
        row.setContentsMargins(18, 18, 18, 18)
        symbol = QLabel()
        symbol.setPixmap(settings_icon("about").pixmap(38, 38))
        row.addWidget(symbol)
        text = QVBoxLayout()
        text.addWidget(settings_label("Server Information", "title"))
        text.addWidget(settings_label("Make sure the server number matches the server where your automation stations are located."))
        row.addLayout(text, 1)
        card.body.addWidget(info)
        box.addWidget(card)

    def _render_stations_settings(self):
        """Render consistent station cards without changing their saved fields."""
        box, state = self._approved_settings_content("STATIONS")
        render = SettingsSectionCard(
            "RENDER STATION",
            "Set the render base location for automation.",
            "render",
            "bed",
        )
        render.body.addWidget(
            SettingsFieldGrid(
                [
                    self._approved_setting_field("bed_spawn", "Bed spawn", state),
                    self._approved_setting_field("station_yaw", "Station yaw", state),
                ]
            )
        )
        box.addWidget(render)
        iguanodon = SettingsSectionCard(
            "IGUANODON STATION",
            "Set the iguanodon location and seed drop settings.",
            "iguanodon",
            "iguanodon",
        )
        iguanodon.body.addWidget(
            SettingsFieldGrid(
                [
                    self._approved_setting_field("iguanadon", "Iguanodon", state),
                    self._approved_setting_field("iguanadon_seed_throw_amount", "Seed drop", state),
                ]
            )
        )
        box.addWidget(iguanodon)
        berry = SettingsSectionCard(
            "BERRY STATION",
            "Set the berry collection station settings.",
            "berry",
            "berry",
        )
        berry.body.addWidget(
            SettingsFieldGrid(
                [
                    self._approved_setting_field("berry_station", "Berry station", state),
                    self._approved_setting_field("berry_type", "Berry name", state),
                    self._approved_setting_field("time_to_reberry", "Reberry after", state, unit="(s)"),
                    self._approved_setting_field(
                        "external_berry",
                        "Troughs away?",
                        state,
                        "True if trough is not in render, but far away",
                    ),
                ]
            )
        )
        box.addWidget(berry)

    def _render_launcher_settings(self):
        """Render Launcher settings using existing editors and local Auto Keys."""
        box, state = self._approved_settings_content("LAUNCHER")
        card = SettingsSectionCard(
            "Launcher settings",
            "Configure ARK launcher behavior and window options.",
            "launcher",
            "launcher_settings",
        )
        fields = []
        for key, title in (
            ("auto_start_program", "Auto start program"),
            ("helper_inactive_opacity", "Helper inactive opacity"),
            ("allow_focus_ark_window", "Allow Ark window focus"),
            ("focus_ark_window_interval", "Ark window focus interval"),
            ("launcher_width", "Launcher startup width"),
            ("launcher_height", "Launcher startup height"),
        ):
            field = self._approved_setting_field(key, title, state)
            field.label.setFixedWidth(190)
            fields.append(field)
        card.body.addWidget(SettingsFieldGrid(fields))
        box.addWidget(card)
        box.addWidget(self._add_auto_keys_settings())

    def _add_auto_keys_settings(self):
        """Lay out existing Auto Keys controls without altering runtime semantics."""
        card = SettingsSectionCard(
            "AUTO KEYS",
            "Configure automatic key presses for launcher flow.",
            "auto_keys",
            "auto_keys",
        )
        card.header.setObjectName("AutoKeysHeader")
        auto_keys = self.form_values.get("auto_keys", {})
        enabled = CyberSwitch("ENABLED")
        enabled.setChecked(bool(auto_keys.get("enabled", False)))
        enabled.toggled.connect(self.persist_auto_keys_settings)
        enabled_box = QVBoxLayout()
        enabled_box.setSpacing(3)
        enabled_box.addWidget(enabled, alignment=Qt.AlignmentFlag.AlignRight)
        emergency_hint = settings_label("Press Shift+F1 to deactivate")
        emergency_hint.setWordWrap(False)
        enabled_box.addWidget(emergency_hint)
        card.header.layout().addLayout(enabled_box)
        self.auto_keys_enabled_field = enabled

        interval = QLineEdit(str(auto_keys.get("interval", 0.25)))
        hold_duration = QLineEdit(str(auto_keys.get("hold_duration", 1.0)))
        for field in (interval, hold_duration):
            field.setObjectName("SettingField")
            field.setFixedHeight(CONTROL_HEIGHT)
            field.setMinimumWidth(0)
            field.editingFinished.connect(self.persist_auto_keys_settings)
        self.auto_keys_interval_field = interval
        self.auto_keys_hold_field = hold_duration
        activation_key_button = ActivationKeyButton(
            str(auto_keys.get("activation_key", "F1")),
            self._capture_auto_keys_activation_key,
        )
        activation_key_button.setObjectName("AutoKeysActivationKey")
        self.auto_keys_activation_key_field = activation_key_button
        sync_suspension_ui = getattr(self, "_sync_auto_keys_suspension_ui", None)
        if callable(sync_suspension_ui):
            sync_suspension_ui()

        activation = SettingsField("Activation key", SettingsUnitControl(activation_key_button))
        activation.label.setFixedWidth(180)
        card.body.addWidget(SettingsFieldGrid([activation, QWidget()]))
        for title, field, description, object_name in (
            (
                "Interval",
                interval,
                "Delay between repeated presses.\nExample: press E → wait X seconds → press E again.",
                "AutoKeysIntervalDescription",
            ),
            (
                "Trigger",
                hold_duration,
                "How long a key must be held before Auto Keys starts.\nExample: with a 1-second trigger, holding Left Mouse Button for 1 second starts repeating it until pressed again.",
                "AutoKeysTriggerDescription",
            ),
        ):
            unit_control = SettingsUnitControl(field, "(s)")
            entry = SettingsField(title, unit_control)
            entry.label.setFixedWidth(180)
            copy = QWidget()
            copy_layout = QVBoxLayout(copy)
            copy_layout.setContentsMargins(0, 0, 0, 0)
            label = settings_label(description)
            label.setObjectName(object_name)
            copy_layout.addWidget(label)
            if field is interval:
                warning = settings_label("Intervals below 0.15 seconds may increase the risk of being banned under ARK's anti-macro Code of Conduct.")
                warning.setObjectName("AutoKeysWarning")
                self.auto_keys_interval_warning = warning
                copy_layout.addWidget(warning)
                interval.textChanged.connect(self._refresh_auto_keys_interval_warning)
                self._refresh_auto_keys_interval_warning()
            card.body.addWidget(SettingsFieldGrid([entry, copy]))

        divider = QFrame()
        divider.setObjectName("SettingsDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        card.body.addWidget(divider)
        supported_grid = QWidget()
        supported_grid.setObjectName("AutoKeysSupportedGrid")
        supported_layout = QGridLayout(supported_grid)
        supported_layout.setContentsMargins(0, 0, 0, 0)
        supported_layout.setHorizontalSpacing(18)
        supported_layout.setVerticalSpacing(6)
        supported_layout.setColumnStretch(1, 1)
        supported_layout.setColumnStretch(3, 1)
        action_settings = auto_keys.get("actions", {})
        if not isinstance(action_settings, dict):
            action_settings = {}
        action_fields, binding_labels = {}, {}
        positions = {
            "Fire": (0, 0),
            "Use": (0, 2),
            "DropItem": (1, 0),
            "Crouch": (1, 2),
            "Jump": (2, 0),
            "MoveForward": (3, 0),
        }
        for index, action in enumerate(AUTO_KEYS_ACTIONS):
            action_field = CyberCheckBox(action)
            action_field.setObjectName("AutoKeysSupportedAction")
            action_field.setChecked(bool(action_settings.get(action, True)))
            action_field.toggled.connect(self.persist_auto_keys_settings)
            binding_label = settings_label("?")
            binding_label.setObjectName("AutoKeysSupportedBinding")
            row, column = positions.get(action, (4 + index, 0))
            supported_layout.addWidget(action_field, row, column)
            supported_layout.addWidget(binding_label, row, column + 1)
            action_fields[action] = action_field
            binding_labels[action] = binding_label
        self.auto_keys_supported_grid = supported_grid
        self.auto_keys_supported_grid_layout = supported_layout
        self.auto_keys_action_fields = action_fields
        self.auto_keys_supported_binding_labels = binding_labels
        self.auto_keys_input_path = None
        self.auto_keys_input_mtime = None
        repeat = SettingsField("Repeat keys", supported_grid)
        repeat.label.setFixedWidth(180)
        repeat.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        card.body.addWidget(repeat)
        self._refresh_auto_keys_supported_keys(force=True)
        hold_duration.textChanged.connect(self._refresh_auto_keys_instruction)
        self._refresh_auto_keys_instruction()
        return card

    def _refresh_auto_keys_interval_warning(self, _text: str = ""):
        """Show the advisory warning only for parsed intervals below 0.15 seconds."""
        warning = getattr(self, "auto_keys_interval_warning", None)
        field = getattr(self, "auto_keys_interval_field", None)
        if warning is None or field is None:
            return
        try:
            show_warning = float(field.text()) < 0.15
        except ValueError:
            show_warning = False
        warning.setVisible(show_warning)

    def _refresh_auto_keys_instruction(self, _text: str = ""):
        """Show the current hold duration in the Auto Keys usage instruction."""
        label = getattr(self, "auto_keys_hold_field", None)
        field = getattr(self, "auto_keys_hold_field", None)
        if label is None or field is None:
            return
        try:
            duration = float(field.text())
        except ValueError:
            return
        if duration <= 0:
            return
        unit = "second" if duration == 1 else "seconds"
        label.setToolTip(
            f"Hold the activation key and a supported button for {duration:g} {unit} to start. Repeat keys press automatically; Key Hold keeps its key down. Press the same button again to stop."
        )

    def _capture_auto_keys_activation_key(self, key_name: str):
        """Persist a key captured by the Auto Keys activation control."""
        self.persist_auto_keys_settings()

    def _refresh_auto_keys_supported_keys(self, force: bool = False):
        """Request binding discovery without filesystem work on Qt's thread."""
        labels = getattr(self, "auto_keys_supported_binding_labels", None)
        if not labels or getattr(self, "supported_keys_busy", False):
            return
        if getattr(self, "shutdown_started", False):
            return
        self.supported_keys_busy = True
        token = id(labels)
        path = getattr(self, "auto_keys_input_path", None)
        previous_mtime = getattr(self, "auto_keys_input_mtime", None)
        signal = self.supported_keys_finished

        def resolve():
            """Read file metadata and bindings on the refresh worker."""
            resolved = None
            mtime = None
            try:
                if path is not None:
                    with contextlib.suppress(OSError):
                        mtime = path.stat().st_mtime_ns
                resolved_path = path
                if force or path is None or mtime != previous_mtime:
                    resolved, resolved_path = resolve_supported_keys()
                    try:
                        mtime = resolved_path.stat().st_mtime_ns
                    except (AttributeError, OSError):
                        mtime = None
                result = (token, resolved, resolved_path, mtime)
            except Exception:
                result = (token, {}, None, None)
            # ruff: disable[SIM105]
            try:
                signal.emit(result)
            except RuntimeError:
                pass  # The launcher was deleted during discovery.

        threading.Thread(target=resolve, name="auto-keys-display", daemon=True).start()

    def _on_supported_keys_finished(self, result: tuple):
        """Apply discovery only to the controls that requested it."""
        self.supported_keys_busy = False
        token, resolved, input_path, mtime = result
        labels = getattr(self, "auto_keys_supported_binding_labels", {})
        if getattr(self, "shutdown_started", False) or token != id(labels):
            return
        if resolved is None:
            return
        tooltip = str(input_path) if input_path is not None else ""
        for action, label in labels.items():
            if isinstance(label, QObject) and not isValid(label):
                continue
            binding = resolved.get(action)
            label.setText(f"[{binding}]" if binding else "—")
            label.setToolTip(tooltip)
        self.auto_keys_input_path = input_path
        self.auto_keys_input_mtime = mtime
        grid = getattr(self, "auto_keys_supported_grid", None)
        if grid is not None and (not isinstance(grid, QObject) or isValid(grid)):
            grid.setToolTip(tooltip)

    def persist_auto_keys_settings(self, _checked=False):
        """Validate, save, and apply the Auto keys settings immediately."""
        try:
            is_suspended = getattr(self, "_auto_keys_are_suspended", lambda: False)()
            enabled = bool(self.settings.get("auto_keys", {}).get("enabled", False)) if is_suspended else self.auto_keys_enabled_field.isChecked()
            auto_keys = {
                "enabled": enabled,
                "activation_key": getattr(
                    getattr(self, "auto_keys_activation_key_field", None),
                    "key_name",
                    self.settings.get("auto_keys", {}).get("activation_key", "F1"),
                ),
                "interval": float(self.auto_keys_interval_field.text()),
                "hold_duration": float(self.auto_keys_hold_field.text()),
                "actions": {action: field.isChecked() for action, field in getattr(self, "auto_keys_action_fields", {}).items()},
            }
            if not auto_keys["actions"]:
                current_actions = self.settings.get("auto_keys", {}).get("actions", {})
                auto_keys["actions"] = {action: bool(current_actions.get(action, True)) for action in AUTO_KEYS_ACTIONS}
            if auto_keys["interval"] <= 0 or auto_keys["hold_duration"] <= 0:
                raise ValueError
            self.form_values["auto_keys"] = auto_keys
            self.settings = save_settings(self._collect_settings())
            self.form_values = self.settings.copy()
            runtime = getattr(self, "auto_keys_runtime", None)
            if runtime is not None and getattr(self, "startup_complete", True):
                runtime.configure(self.settings, allow_enable=not is_suspended)
            sync_suspension_ui = getattr(self, "_sync_auto_keys_suspension_ui", None)
            if callable(sync_suspension_ui):
                sync_suspension_ui()
        except (TypeError, ValueError):
            self.dialog(
                "Invalid Auto keys Settings",
                "Interval and hold duration must be positive numbers.",
                "error",
            )

    def _render_settings_group(self, group_name: str):
        if group_name not in SETTINGS_GROUPS:
            group_name = "SERVER"
        self.current_settings_group = group_name
        if getattr(self, "_skip_visible_field_persist", False):
            self._skip_visible_field_persist = False
        else:
            self.persist_settings_from_visible_fields(show_log=False, show_error=False)
        while self.settings_form_layout.count():
            item = self.settings_form_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.fields = {}
        if hasattr(self, "settings_breadcrumb"):
            self.settings_breadcrumb.set_group(group_name)
            for button in self.settings_tabs.buttons():
                button.setChecked(button.text().strip() == SETTINGS_GROUP_LABELS[group_name])
        self.settings_form_layout.setContentsMargins(28, 20, 28, 20)
        for index in range(self.settings_form_layout.rowCount()):
            self.settings_form_layout.setRowStretch(index, 0)
        for index in range(self.settings_form_layout.columnCount()):
            self.settings_form_layout.setColumnStretch(index, 0)

        self._settings_form_action_column = 3
        if group_name == "DEDI":
            self._render_deposit_routes_group()
            return
        if group_name == "GACHA":
            self._render_gacha_group()
            return
        if group_name == "CRAFT":
            self._render_craft_group()
            return
        if group_name == "PEGO":
            self._render_pego_group()
            return
        if group_name == "SERVER":
            self._render_server_settings()
            return
        if group_name == "STATIONS":
            self._render_stations_settings()
            return
        if group_name == "LAUNCHER":
            self._render_launcher_settings()
            return

    def refresh_json_configs(self):
        try:
            settings = load_settings()
            deposit_config = load_deposit_config()
            gacha_config = load_gacha_config()
            gacha_collect_config = load_gacha_collect_config()
            pego_config = load_pego_config()
            craft_config = load_craft_config()
        except Exception as exc:
            self.append_log(f"[ERROR] Unable to refresh JSON config files: {exc}\n")
            self.dialog("Refresh Configs", str(exc), "error")
            return

        self.close_external_helpers()
        self.settings = settings
        self.form_values = settings.copy()
        runtime = getattr(self, "auto_keys_runtime", None)
        if runtime is not None:
            is_suspended = getattr(self, "_auto_keys_are_suspended", lambda: False)()
            runtime.configure(settings, allow_enable=not is_suspended)
        self.deposit_config = deposit_config
        self.gacha_config = gacha_config
        self.gacha_collect_config = gacha_collect_config
        self.pego_config = pego_config
        self.craft_config = craft_config
        self.fields = {}
        self.sync_configured_templates()
        self._skip_visible_field_persist = True
        self._render_settings_group(getattr(self, "current_settings_group", "SERVER"))
        self._update_auto_start_switch()
        self._tick()
        self.append_log("[SUCCESS] JSON config files refreshed.\n")
