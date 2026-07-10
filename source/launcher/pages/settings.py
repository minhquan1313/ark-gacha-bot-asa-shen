from source.launcher.pages.common import (
    DEFAULT_SETTINGS,
    DEFAULT_TEMPLATE_FILENAME,
    SETTINGS_GROUPS,
    TEMPLATE_DIRECTORY,
    TEMPLATE_GROUP_REFERENCE_KEYS,
    TEMPLATE_GROUP_SETTING_KEYS,
    AnimatedButton,
    Counter,
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
    QMenu,
    QSizePolicy,
    QSpacerItem,
    Qt,
    QToolButton,
    QUrl,
    QVBoxLayout,
    QWidget,
    SmoothScrollArea,
    TemplateCatalog,
    build_template,
    contextlib,
    convert_deposit_yaw,
    copy,
    load_deposit_config,
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
    save_gacha_config,
    save_pego_config,
    save_settings,
    scan_templates,
    setting_label,
    setting_tooltip,
    subprocess,
    write_template,
)


class SettingsPagesMixin:
    def _settings_page(self):
        page, layout = self._page("SettingsPage")
        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self._page_title("SETTINGS"), 1)
        header.addWidget(self._template_action_split_button())
        layout.addLayout(header)

        shell, shell_layout = self._panel()
        shell.setObjectName("SettingsShell")
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        shell_layout.addLayout(content, 1)
        layout.addWidget(shell, 1)

        self.settings_tabs = QButtonGroup(self)
        self.settings_tabs.setExclusive(True)
        tabs = QVBoxLayout()
        tabs.setContentsMargins(8, 10, 8, 10)
        tabs.setSpacing(6)
        tab_frame = QFrame()
        tab_frame.setObjectName("SettingsTabs")
        tab_frame.setMinimumWidth(0)
        tab_frame.setMaximumWidth(340)
        tab_frame.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        tab_frame.setLayout(tabs)
        content.addWidget(tab_frame)

        form_area = SmoothScrollArea()
        form_area.setWidgetResizable(True)
        form_area.setObjectName("SettingsScroll")
        self.settings_form = QWidget()
        self.settings_form.setObjectName("SettingsForm")
        self.settings_form_layout = QGridLayout(self.settings_form)
        self.settings_form_layout.setContentsMargins(28, 20, 28, 20)
        self.settings_form_layout.setHorizontalSpacing(18)
        self.settings_form_layout.setVerticalSpacing(10)
        form_area.setWidget(self.settings_form)
        content.addWidget(form_area, 1)

        for group_name in SETTINGS_GROUPS:
            button = AnimatedButton(group_name, "nav")
            button.setObjectName("SettingsTab")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, name=group_name: self._render_settings_group(name)
            )
            self.settings_tabs.addButton(button)
            tabs.addWidget(button)
            if group_name == "SERVER":
                button.setChecked(True)
        tabs.addStretch()

        footer = QFrame()
        footer.setObjectName("SettingsFooter")
        action_bar = QHBoxLayout(footer)
        action_bar.setContentsMargins(12, 8, 12, 8)
        action_bar.setSpacing(8)
        footer_hint = QLabel("CHANGES SAVE AUTOMATICALLY")
        footer_hint.setObjectName("SettingsFooterHint")
        action_bar.addWidget(footer_hint)
        action_bar.addStretch()
        refresh_button = self._button("REFRESH", "secondary")
        refresh_button.clicked.connect(self.refresh_json_configs)
        action_bar.addWidget(refresh_button)
        reset_button = self._button("RESET", "danger")
        reset_button.clicked.connect(self.confirm_reset)
        action_bar.addWidget(reset_button)
        shell_layout.addWidget(footer)
        self._render_settings_group("SERVER")
        return page

    def _template_action_split_button(self):
        """Build the fixed IMPORT action with an EXPORT/BROWSE popup menu."""
        button = QToolButton()
        button.setObjectName("TemplateActionSplitButton")
        button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.setArrowType(Qt.ArrowType.DownArrow)

        import_action = QAction("IMPORT", button)
        import_action.triggered.connect(self.import_template_setting)
        button.setDefaultAction(import_action)

        menu = QMenu(button)
        menu.setObjectName("TemplateActionMenu")
        export_action = menu.addAction("EXPORT TEMPLATE")
        export_action.triggered.connect(self.export_template_setting)
        browse_action = menu.addAction("BROWSE TEMPLATE FOLDER")
        browse_action.triggered.connect(self.browse_template_settings)
        button.setMenu(menu)

        self.template_action_button = button
        self.template_import_action = import_action
        self.template_export_action = export_action
        self.template_browse_action = browse_action
        return button

    def _template_catalog(self):
        """Rescan versioned template files for the settings UI."""
        self.template_catalog = scan_templates()
        return self.template_catalog

    def _template_group_state(self, group_name: str):
        """Resolve a settings group to manual, active, or missing template state."""
        reference_keys = TEMPLATE_GROUP_REFERENCE_KEYS.get(group_name, ())
        reference_values = {
            str(self.form_values.get(key, "")) for key in reference_keys
        }
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

    def _add_template_selector(self, group_name: str):
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
        display_counts = Counter(
            str(template["name"]) for template in catalog.templates.values()
        )
        sorted_templates = sorted(
            catalog.templates.items(),
            key=lambda item: (str(item[1]["name"]).casefold(), item[0].casefold()),
        )
        for template_id, template in sorted_templates:
            display_name = str(template["name"])
            label = (
                f"{display_name} — {template_id}"
                if display_counts[display_name] > 1
                else display_name
            )
            selector.addItem(
                f"V  {label}"
                if state == "active" and template_id == selected_name
                else label,
                template_id,
            )
            selector.setItemData(
                selector.count() - 1, template_id, Qt.ItemDataRole.ToolTipRole
            )
        if selected_name and selector.findData(selected_name) < 0:
            selector.addItem(f"MISSING: {selected_name}", selected_name)
        if state == "missing" and not selected_name:
            selector.addItem("MIXED ASSIGNMENTS", "__mixed__")
        current_index = selector.findData(
            selected_name or ("__mixed__" if state == "missing" else "")
        )
        selector.setCurrentIndex(max(0, current_index))
        if error:
            selector.setToolTip(error)
        selector.currentIndexChanged.connect(
            lambda _index, combo=selector, group=group_name: self.change_template_group(
                group, str(combo.currentData())
            )
        )
        action_column = getattr(self, "_settings_form_action_column", 3)
        self.settings_form_layout.addWidget(
            selector, 0, action_column, alignment=Qt.AlignmentFlag.AlignRight
        )
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
        frame.setObjectName(
            "TemplateFieldActive" if state == "active" else "TemplateFieldMissing"
        )
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
        content.setObjectName(
            "TemplateGroupActive" if state == "active" else "TemplateGroupMissing"
        )
        content.setToolTip(f"Using {template_name}" if state == "active" else error)
        content.setEnabled(state != "active")
        content.style().unpolish(content)
        content.style().polish(content)

    def _set_group_template_references(
        self, settings: dict, group_name: str, template_name: str
    ):
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
        new_settings = self._set_group_template_references(
            old_settings, group_name, template_name
        )
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
                catalog.errors.get(
                    template_name, f'Template "{template_name}" cannot be found.'
                ),
                "error",
            )
            return False

        old_deposit = copy.deepcopy(getattr(self, "deposit_config", None))
        old_gacha = copy.deepcopy(getattr(self, "gacha_config", None))
        old_pego = copy.deepcopy(getattr(self, "pego_config", None))
        new_deposit = old_deposit
        new_gacha = old_gacha
        new_pego = old_pego
        if group_name == "DEDI" and old_deposit is None:
            old_deposit = load_deposit_config()
            new_deposit = old_deposit
        elif group_name == "GACHA" and old_gacha is None:
            old_gacha = load_gacha_config()
            new_gacha = old_gacha
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
            elif group_name == "PEGO":
                self._ensure_pego_config()
                new_pego = save_pego_config(template["data"]["pego"])
            new_settings = save_settings(new_settings)
        except (OSError, TypeError, ValueError) as exc:
            self._rollback_template_group(
                group_name, old_settings, old_deposit, old_gacha, old_pego
            )
            self.dialog("Template Apply Failed", str(exc), "error")
            return False

        self.settings = new_settings
        self.form_values = new_settings.copy()
        if group_name == "DEDI":
            self.deposit_config = new_deposit
        elif group_name == "GACHA":
            self.gacha_config = new_gacha
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
        old_pego: list[dict] | None,
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
        elif group_name == "PEGO" and old_pego is not None:
            with contextlib.suppress(OSError, TypeError, ValueError):
                save_pego_config(old_pego)

    def apply_default_template_to_all_groups(self):
        """Apply the bundled default as one rollback-protected reset operation."""
        old_settings = copy.deepcopy(self.settings)
        old_deposit = load_deposit_config()
        old_gacha = load_gacha_config()
        old_pego = load_pego_config()
        for group_name in (
            "SERVER",
            "STATIONS",
            "PEGO",
            "DEDI",
            "GACHA",
            "LAUNCHER",
        ):
            if self.change_template_group(group_name, DEFAULT_TEMPLATE_FILENAME):
                continue
            try:
                self.settings = save_settings(old_settings)
                self.form_values = self.settings.copy()
                self.deposit_config = save_deposit_config(old_deposit)
                self.gacha_config = save_gacha_config(old_gacha)
                self.pego_config = save_pego_config(old_pego)
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
        migrated_settings, migration_errors = migrate_template_references(
            self.settings, catalog
        )
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
            )
            destination = self._store_template_with_conflict(
                template, safe_template_filename(str(template["name"]))
            )
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
        collision_id, collision_path = self._find_template_collision(
            template_id, catalog
        )
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
                candidate_id, candidate_path = self._find_template_collision(
                    candidate, catalog
                )
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
            field.toggled.connect(
                lambda checked=False, setting_key=key: self.persist_single_setting(
                    setting_key
                )
            )
        else:
            field = QLineEdit(str(self.form_values.get(key, default_value)))
            field.setObjectName("SettingField")
            field.editingFinished.connect(
                lambda setting_key=key: self.persist_single_setting(setting_key)
            )
            field.returnPressed.connect(
                lambda setting_key=key: self.persist_single_setting(setting_key)
            )
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
            return self._template_field_widget(
                field, state, template_name, template_error
            )
        return field

    def _station_yaw_field_container(self, field: QWidget):
        """Place the Station yaw capture helper directly beside the field."""
        frame = QFrame()
        row = QHBoxLayout(frame)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(field, 1)
        helper = self._button("[B]", "secondary")
        helper.setObjectName("HelperIconButton")
        helper.setToolTip("Open helper to capture and view render yaw settings.")
        helper.clicked.connect(self.open_position_render_helper)
        row.addWidget(helper)
        return frame

    def _start_settings_section(
        self,
        group_name: str,
        max_fields: int,
    ):
        """Add a settings heading and template selector for one simple section."""
        heading = QLabel("HELPER" if group_name == "UI" else f"{group_name} SETTINGS")
        heading.setObjectName("SectionHeading")
        self._settings_form_action_column = max((max_fields * 2) - 1, 3)
        self.settings_form_layout.addWidget(
            heading, 0, 0, 1, self._settings_form_action_column
        )
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
            content = (
                self._station_yaw_field_container(field)
                if key == "station_yaw"
                else field
            )
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

    def _render_server_settings(self):
        state, template_name, template_error = self._start_settings_section("SERVER", 2)
        templated_keys = set(TEMPLATE_GROUP_SETTING_KEYS["SERVER"])
        row = 1
        row = self._add_setting_row(
            ("server_number", "ping"),
            row,
            state,
            template_name,
            template_error,
            templated_keys,
        )
        row = self._add_setting_row(
            ("singleplayer",),
            row,
            state,
            template_name,
            template_error,
            templated_keys,
        )
        self._add_settings_spacer(row)

    def _render_stations_settings(self):
        state, template_name, template_error = self._start_settings_section(
            "STATIONS", 2
        )
        templated_keys = set(TEMPLATE_GROUP_SETTING_KEYS["STATIONS"])
        row = 1
        row = self._add_settings_divider(row, "RENDER STATION")
        row = self._add_setting_row(
            ("bed_spawn", "station_yaw"),
            row,
            state,
            template_name,
            template_error,
            templated_keys,
        )
        row = self._add_settings_divider(row, "IGUANODON STATION")
        row = self._add_setting_row(
            ("iguanadon", "iguanadon_seed_throw_amount"),
            row,
            state,
            template_name,
            template_error,
            templated_keys,
        )
        row = self._add_settings_divider(row, "BERRY STATION")
        row = self._add_setting_row(
            ("berry_station", "berry_type"),
            row,
            state,
            template_name,
            template_error,
            templated_keys,
        )
        row = self._add_setting_row(
            ("time_to_reberry", "external_berry"),
            row,
            state,
            template_name,
            template_error,
            templated_keys,
        )
        self._add_settings_spacer(row)

    def _render_launcher_settings(self):
        state, template_name, template_error = self._start_settings_section(
            "LAUNCHER", 2
        )
        templated_keys = set(TEMPLATE_GROUP_SETTING_KEYS["LAUNCHER"])
        row = 1
        row = self._add_setting_row(
            ("auto_start_program", "helper_inactive_opacity"),
            row,
            state,
            template_name,
            template_error,
            templated_keys,
        )
        row = self._add_setting_row(
            ("allow_focus_ark_window", "focus_ark_window_interval"),
            row,
            state,
            template_name,
            template_error,
            templated_keys,
        )
        row = self._add_setting_row(
            ("launcher_width", "launcher_height"),
            row,
            state,
            template_name,
            template_error,
            templated_keys,
        )
        self._add_settings_spacer(row)

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

        self._settings_form_action_column = 3
        if group_name == "DEDI":
            self._render_deposit_routes_group()
            return
        if group_name == "GACHA":
            self._render_gacha_group()
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
            pego_config = load_pego_config()
        except Exception as exc:
            self.append_log(f"[ERROR] Unable to refresh JSON config files: {exc}\n")
            self.dialog("Refresh Configs", str(exc), "error")
            return

        self.close_external_helpers()
        self.settings = settings
        self.form_values = settings.copy()
        self.deposit_config = deposit_config
        self.gacha_config = gacha_config
        self.pego_config = pego_config
        self.fields = {}
        self.sync_configured_templates()
        self._skip_visible_field_persist = True
        self._render_settings_group(getattr(self, "current_settings_group", "SERVER"))
        self._update_auto_start_switch()
        self._tick()
        self.append_log("[SUCCESS] JSON config files refreshed.\n")
