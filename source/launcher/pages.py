import os

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from source.gacha_bot.deposit_config import (
    default_crystal_route,
    default_dedi_item,
    default_deposit_config,
    default_grindable_route,
    default_vault_item,
    load_deposit_config,
    save_deposit_config,
)
from source.launcher.auto_join_server_helper import AutoJoinServerHelper
from source.launcher.constants import (
    APP_NAME,
    APP_TITLE,
    APP_VERSION,
    ASSETS,
    COLORS,
    DEFAULT_SETTINGS,
    SETTINGS_GROUPS,
    setting_label,
)
from source.launcher.deposit_route_helper import DepositRouteHelper
from source.launcher.fertilizer_refresh_helper import FertilizerRefreshHelper
from source.launcher.position_render_helper import PositionRenderHelper
from source.launcher.server_transfer_helper import ServerTransferHelper
from source.launcher.settings_store import load_settings
from source.launcher.station_config import (
    DEFAULT_PEGO_DELAY,
    DEFAULT_PEGO_SNOW_OWLS_PER_GACHA,
    DEFAULT_PEGO_STATION_SECONDS,
    DEFAULT_PEGO_TARGET_CRYSTALS,
    auto_fill_gacha_group,
    calculate_pego_delay,
    default_gacha_entry,
    default_gacha_pair,
    default_pego_entry,
    gacha_name_from_teleporter,
    grouped_gacha_entries,
    load_gacha_config,
    load_pego_config,
    missing_gacha_side,
    next_gacha_teleporter,
    next_pego_index,
    risky_teleporter_names,
    save_gacha_config,
    save_pego_config,
    set_all_pego_delays,
)
from source.launcher.widgets import (
    AnimatedButton,
    ClickableTextEdit,
    CyberSwitch,
    HeroBanner,
    MeterBar,
)


class LauncherPagesMixin:
    def _icon_button(
        self, icon_key, tooltip="", variant="secondary", width=36, icon_size=32
    ):
        button = self._button("", variant)
        button.setObjectName("HelperIconButton")
        button.setIcon(QIcon(ASSETS[icon_key]))
        button.setIconSize(QSize(icon_size, icon_size))
        button.setMinimumWidth(width)
        # button.setFixedWidth(width)
        if tooltip:
            button.setToolTip(tooltip)
        return button

    def _welcome_page(self):
        page, layout = self._page("WelcomePage")
        row = QHBoxLayout()
        row.setSpacing(22)
        layout.addLayout(row, 1)

        left = QVBoxLayout()
        left.setSpacing(16)
        row.addLayout(left, 1)
        title = QLabel(f"WELCOME TO\n{APP_TITLE}")
        title.setObjectName("WelcomeTitle")
        copy = QLabel(
            "AUTOMATE. MANAGE. DOMINATE.\n\n"
            f"{APP_NAME} is your compact companion for managing automation tasks, "
            "queues, and local offline runs with style."
        )
        copy.setObjectName("MutedCopy")
        copy.setWordWrap(True)
        checklist, checklist_layout = self._panel("BEFORE YOU START:")
        for item in [
            "Configure your settings",
            "Review your station data",
            "Review the setup guide",
            "Save settings before starting",
        ]:
            checklist_layout.addWidget(QLabel(f"- {item}"))
        checkbox = CyberSwitch("Do not show again")
        start = self._button("GET STARTED  >", "primary")
        start.clicked.connect(lambda: self.show_page("dashboard"))
        left.addStretch()
        left.addWidget(title)
        left.addWidget(copy)
        left.addWidget(checklist)
        left.addWidget(checkbox)
        left.addWidget(start, alignment=Qt.AlignRight)
        left.addStretch()

        art = QLabel()
        art.setObjectName("HeroArt")
        art.setAlignment(Qt.AlignCenter)
        if os.path.exists(ASSETS["welcome"]):
            art.setPixmap(
                QPixmap(ASSETS["welcome"]).scaled(
                    430, 430, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        row.addWidget(art, 1)
        return page

    def _dashboard_page(self):
        page, layout = self._page("DashboardPage")
        layout.setContentsMargins(16, 0, 16, 14)
        layout.addWidget(HeroBanner(self))

        dashboard_gutter = 10
        stats = QGridLayout()
        stats.setSpacing(dashboard_gutter)
        layout.addLayout(stats)
        self.server_value = self._stat_card(stats, 0, "SERVER NUMBER", "ID")
        self.dashboard_server_card = stats.itemAtPosition(0, 0).widget()
        self.active_value = self._stat_card(stats, 1, "ACTIVE QUEUE", "TASKS")
        self.waiting_value = self._stat_card(stats, 2, "WAITING QUEUE", "TASKS")
        self.uptime_value = self._stat_card(stats, 3, "UPTIME", "HH:MM:SS")

        middle = QHBoxLayout()
        middle.setSpacing(dashboard_gutter)
        layout.addLayout(middle, 1)

        actions, action_layout = self._panel("QUICK ACTIONS")
        self.dashboard_actions_card = actions
        self.start_stop_button = self._button("START PROGRAM", "primary")
        self.start_stop_button.setToolTip("Hotkey: Shift + Alt + N")
        self.start_stop_button.clicked.connect(self.toggle_program)
        action_layout.addWidget(self.start_stop_button)

        start_game_row = QHBoxLayout()
        start_game_row.setSpacing(8)
        self.start_game_button = self._button("START GAME", "secondary")
        self.start_game_button.setToolTip(
            "Set display to 1920x1080 and start ARK through Steam."
        )
        self.start_game_button.clicked.connect(
            getattr(self, "start_game", lambda: None)
        )
        start_game_row.addWidget(self.start_game_button, 1)
        if hasattr(self, "_update_start_game_button_visibility"):
            self._update_start_game_button_visibility()

        self.restore_game_settings_button = self._icon_button(
            "icon.restore_settings",
            "Restore the original display mode and ARK config. "
            "Right-click to clear saved restore data.",
            "danger",
        )
        self.restore_game_settings_button.clicked.connect(
            getattr(self, "restore_game_settings", lambda: None)
        )
        self.restore_game_settings_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.restore_game_settings_button.customContextMenuRequested.connect(
            lambda _pos: getattr(self, "clear_game_restore_settings", lambda: None)()
        )
        start_game_row.addWidget(self.restore_game_settings_button)
        action_layout.addLayout(start_game_row)
        if hasattr(self, "_update_game_restore_button_visibility"):
            self._update_game_restore_button_visibility()

        auto_start_box = QFrame()
        auto_start_box.setObjectName("InlineSwitchBox")
        auto_layout = QVBoxLayout(auto_start_box)
        auto_layout.setContentsMargins(10, 8, 10, 8)
        auto_layout.setSpacing(4)
        self.auto_start_switch = CyberSwitch("AUTO START")
        self.auto_start_switch.toggled.connect(self.toggle_auto_start_program)
        self.auto_start_hint = QLabel("Start program when launcher opens")
        self.auto_start_hint.setObjectName("MutedCopy")
        auto_layout.addWidget(self.auto_start_switch)
        auto_layout.addWidget(self.auto_start_hint)
        action_layout.addWidget(auto_start_box)
        action_layout.addStretch()
        middle.addWidget(actions)

        console, console_layout = self._panel("LIVE CONSOLE (LATEST)")
        self.dashboard_log = self._console_widget()
        console_layout.addWidget(self.dashboard_log)
        open_logs = self._button("OPEN FULL LOGS", "secondary")
        open_logs.clicked.connect(lambda: self.show_page("logs"))
        console_layout.addWidget(open_logs, alignment=Qt.AlignRight)
        middle.addWidget(console, 1)

        footer = QGridLayout()
        footer.setSpacing(8)
        layout.addLayout(footer)
        self.memory_value, self.memory_meter = self._footer_stat(
            footer, 0, "MEMORY USAGE", True, COLORS["green"]
        )
        self.cpu_value, self.cpu_meter = self._footer_stat(
            footer, 1, "CPU USAGE", True, COLORS["cyan"]
        )
        self.runner_value = self._footer_stat(footer, 2, "RUNNER")
        self.activity_value = self._footer_stat(footer, 3, "LAST ACTIVITY")
        self.clock_value = self._footer_stat(footer, 4, "SYSTEM TIME")
        self._update_start_stop_button()
        self._update_auto_start_switch()
        QTimer.singleShot(0, self._sync_dashboard_actions_width)
        return page

    def _sync_dashboard_actions_width(self):
        if hasattr(self, "dashboard_actions_card"):
            self.dashboard_actions_card.setFixedWidth(
                self.dashboard_server_card.width()
            )

    def _stat_card(self, layout, column, label, sublabel):
        panel, panel_layout = self._panel()
        title = QLabel(label)
        title.setObjectName("StatLabel")
        value = QLabel("0")
        value.setObjectName("StatValue")
        sub = QLabel(sublabel)
        sub.setObjectName("StatSubLabel")
        panel_layout.addWidget(title, alignment=Qt.AlignCenter)
        panel_layout.addWidget(value, alignment=Qt.AlignCenter)
        panel_layout.addWidget(sub, alignment=Qt.AlignCenter)
        layout.addWidget(panel, 0, column)
        return value

    def _footer_stat(self, layout, column, label, meter=False, accent=None):
        panel, panel_layout = self._panel()
        panel_layout.setContentsMargins(12, 8, 12, 8)
        title = QLabel(label)
        title.setObjectName("FooterLabel")
        value = QLabel("--")
        value.setObjectName("FooterValue")
        panel_layout.addWidget(title)
        if meter:
            row = QHBoxLayout()
            row.setSpacing(8)
            bar = MeterBar(accent)
            row.addWidget(bar, 1)
            row.addWidget(value)
            panel_layout.addLayout(row)
        else:
            bar = None
            panel_layout.addWidget(value)
        layout.addWidget(panel, 0, column)
        return (value, bar) if meter else value

    def _setup_page(self):
        page, layout = self._page("SetupPage")
        layout.addWidget(self._page_title("SETUP GUIDE"))
        row = QHBoxLayout()
        row.setSpacing(14)
        layout.addLayout(row, 1)

        steps, steps_layout = self._panel()
        steps_layout.setSpacing(8)
        for number, text, state in [
            ("01", "Configure Local Settings", "DONE"),
            ("02", "Set Server Number", "DONE"),
            ("03", "Configure Gacha Names", "INCOMPLETE"),
            ("04", "Review Queue Data", "PENDING"),
            ("05", "Save Settings", "PENDING"),
            ("06", "Start Program", "PENDING"),
        ]:
            steps_layout.addWidget(self._setup_step(number, text, state))
        row.addWidget(steps, 1)

        detail, detail_layout = self._panel("STEP 03")
        heading = QLabel("CONFIGURE GACHA NAMES")
        heading.setObjectName("SectionHeading")
        body = QLabel(
            "Set your gacha station names below. These names will be used for "
            "text automation and queue processing."
        )
        body.setObjectName("MutedCopy")
        body.setWordWrap(True)
        go = self._button("GO TO SETTINGS  >", "primary")
        go.clicked.connect(lambda: self.show_page("settings"))
        tip, tip_layout = self._panel("TIP")
        tip_text = QLabel(
            "Make sure the names match exactly with your in-game stations to avoid errors."
        )
        tip_text.setWordWrap(True)
        tip_layout.addWidget(tip_text)
        detail_layout.addWidget(heading)
        detail_layout.addWidget(body)
        detail_layout.addWidget(go)
        detail_layout.addWidget(tip)
        detail_layout.addStretch()
        row.addWidget(detail, 1)
        return page

    def _setup_step(self, number, text, state):
        item = QFrame()
        item.setObjectName("StepItem")
        layout = QHBoxLayout(item)
        layout.setContentsMargins(12, 9, 12, 9)
        label = QLabel(number)
        label.setObjectName("StepNumber")
        title = QLabel(text)
        badge = QLabel(state)
        badge.setObjectName(
            "BadgeDone"
            if state == "DONE"
            else "BadgeWarn" if state == "INCOMPLETE" else "BadgePending"
        )
        layout.addWidget(label)
        layout.addWidget(title, 1)
        layout.addWidget(badge)
        return item

    def _settings_page(self):
        page, layout = self._page("SettingsPage")
        layout.addWidget(self._page_title("SETTINGS"))

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
        tab_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        tab_frame.setLayout(tabs)
        content.addWidget(tab_frame)

        form_area = QScrollArea()
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
            if group_name == "GENERAL":
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
        self._render_settings_group("GENERAL")
        return page

    def _render_settings_group(self, group_name):
        self.current_settings_group = group_name
        if getattr(self, "_skip_visible_field_persist", False):
            self._skip_visible_field_persist = False
        else:
            self.persist_settings_from_visible_fields(show_log=False, show_error=False)
        while self.settings_form_layout.count():
            item = self.settings_form_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.fields = {}

        if group_name == "STORAGE":
            self._render_deposit_routes_group()
            return
        if group_name == "GACHA":
            self._render_gacha_group()
            return
        if group_name == "PEGO":
            self._render_pego_group()
            return

        heading = QLabel("HELPER" if group_name == "UI" else f"{group_name} SETTINGS")
        heading.setObjectName("SectionHeading")
        self.settings_form_layout.addWidget(heading, 0, 0, 1, 4)
        if group_name == "POSITION / RENDER":
            helper = self._button("[B]", "secondary")
            helper.setObjectName("HelperIconButton")
            helper.setToolTip("Open helper to capture and view render yaw settings.")
            helper.clicked.connect(self.open_position_render_helper)
            self.settings_form_layout.addWidget(helper, 0, 3, alignment=Qt.AlignRight)

        keys = SETTINGS_GROUPS[group_name]
        for index, key in enumerate(keys, start=1):
            default_value = DEFAULT_SETTINGS[key]
            label = QLabel(setting_label(key))
            label.setObjectName("FormLabel")
            row = 1 + ((index - 1) // 2)
            col = 0 if index % 2 else 2
            self.settings_form_layout.addWidget(label, row, col)
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
            self.fields[key] = field
            self.settings_form_layout.addWidget(field, row, col + 1)

        self.settings_form_layout.setColumnStretch(1, 1)
        self.settings_form_layout.setColumnStretch(3, 1)
        spacer_row = 1 + ((len(keys) + 1) // 2)
        self.settings_form_layout.addItem(
            QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding),
            spacer_row,
            0,
            1,
            4,
        )

    def _render_deposit_routes_group(self):
        self._ensure_deposit_config()
        if not hasattr(self, "deposit_route_card_expanded"):
            self.deposit_route_card_expanded = {}
        heading = QLabel("STORAGE SETTINGS")
        heading.setObjectName("SectionHeading")
        self.settings_form_layout.addWidget(heading, 0, 0, 1, 4)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        self.settings_form_layout.addWidget(content, 1, 0, 1, 4)

        storage_settings, storage_layout = self._panel("STORAGE")
        expand_row = QHBoxLayout()
        expand_row.setSpacing(8)
        expand_all = self._button("EXPAND ALL", "secondary")
        collapse_all = self._button("COLLAPSE ALL", "secondary")
        expand_all.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        collapse_all.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        expand_all.clicked.connect(lambda: self.set_storage_routes_expanded(True))
        collapse_all.clicked.connect(lambda: self.set_storage_routes_expanded(False))
        expand_row.addWidget(expand_all)
        expand_row.addWidget(collapse_all)
        storage_layout.addLayout(expand_row)
        timeout_row = QHBoxLayout()
        timeout_label = QLabel(setting_label("dedi_handshake_timeout"))
        timeout_label.setObjectName("FormLabel")
        timeout = QLineEdit(str(self.form_values.get("dedi_handshake_timeout", 30)))
        timeout.setObjectName("SettingField")
        timeout.editingFinished.connect(
            lambda: self.persist_single_setting("dedi_handshake_timeout")
        )
        timeout.returnPressed.connect(
            lambda: self.persist_single_setting("dedi_handshake_timeout")
        )
        self.fields["dedi_handshake_timeout"] = timeout
        timeout_row.addWidget(timeout_label)
        timeout_row.addWidget(timeout, 1)
        storage_layout.addLayout(timeout_row)
        content_layout.addWidget(storage_settings)

        crystal_heading = QLabel("CRYSTAL DEPOSIT ROUTES")
        crystal_heading.setObjectName("PanelTitle")
        content_layout.addWidget(crystal_heading)
        for route_index, route in enumerate(self.deposit_config["depositCrystalData"]):
            content_layout.addWidget(self._crystal_route_card(route, route_index))
        add_crystal = self._button("ADD CRYSTAL ROUTE", "secondary")
        add_crystal.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        add_crystal.clicked.connect(self.add_crystal_route)
        content_layout.addWidget(add_crystal)

        grindable_heading = QLabel("GRINDABLE ROUTES")
        grindable_heading.setObjectName("PanelTitle")
        content_layout.addWidget(grindable_heading)
        for route_index, route in enumerate(
            self.deposit_config["depositGrindableData"]
        ):
            content_layout.addWidget(self._grindable_route_card(route, route_index))
        add_grindable = self._button("ADD GRINDABLE ROUTE", "secondary")
        add_grindable.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        add_grindable.clicked.connect(self.add_grindable_route)
        content_layout.addWidget(add_grindable)
        content_layout.addStretch()

    def _render_gacha_group(self):
        self._ensure_gacha_config()
        if not hasattr(self, "gacha_group_expanded"):
            self.gacha_group_expanded = {}

        heading = QLabel("GACHA SETTINGS")
        heading.setObjectName("SectionHeading")
        self.settings_form_layout.addWidget(heading, 0, 0, 1, 4)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        self.settings_form_layout.addWidget(content, 1, 0, 1, 4)

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
        for teleporter, group in grouped_gacha_entries(self.gacha_config):
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
            lambda field=teleporter_field, old=teleporter: self.update_gacha_group_teleporter(
                old, field
            )
        )
        teleporter_field.returnPressed.connect(
            lambda field=teleporter_field, old=teleporter: self.update_gacha_group_teleporter(
                old, field
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

    def _render_pego_group(self):
        self._ensure_pego_config()
        self._ensure_gacha_config()

        heading = QLabel("PEGO SETTINGS")
        heading.setObjectName("SectionHeading")
        self.settings_form_layout.addWidget(heading, 0, 0, 1, 4)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        self.settings_form_layout.addWidget(content, 1, 0, 1, 4)

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
            lambda checked=False, target=calculator, button=calc_toggle: self._toggle_pego_calculator(
                target, button
            )
        )
        controls_layout.addWidget(calculator)
        content_layout.addWidget(controls)

        for index, entry in enumerate(self.pego_config):
            content_layout.addWidget(self._pego_card(index, entry))
        add = self._button("ADD PEGO", "secondary")
        add.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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
        copy.clicked.connect(
            lambda checked=False, value=entry.get("teleporter", ""): self.copy_text(
                value
            )
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

    def _pego_calculator_panel(self) -> QFrame:
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
    ) -> QLineEdit:
        group = QVBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("FormLabel")
        field = self._deposit_line_edit(value)
        group.addWidget(label)
        group.addWidget(field)
        layout.addLayout(group)
        return field

    def _pego_calculator_fields(self) -> list[QLineEdit]:
        return [
            self.pego_calc_target_field,
            self.pego_calc_pego_count_field,
            self.pego_calc_gacha_count_field,
            self.pego_calc_snow_owl_field,
            self.pego_calc_station_seconds_field,
        ]

    def _crystal_route_card(self, route, route_index):
        card, layout = self._deposit_route_card(
            f"CRYSTAL ROUTE {route_index + 1}",
            lambda checked=False, index=route_index: self.remove_crystal_route(index),
            lambda checked=False, index=route_index: self.open_deposit_helper(
                "crystal", index
            ),
        )
        self._add_route_teleport_field(layout, route)

        self._add_deposit_subheading(layout, "DEDIS")
        for item_index, item in enumerate(route["dedi"]["items"]):
            layout.addLayout(
                self._dedi_row(
                    item,
                    lambda checked=False, r=route_index, i=item_index: self.remove_crystal_dedi(
                        r, i
                    ),
                )
            )
        add_dedi = self._button("ADD DEDI", "secondary")
        add_dedi.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        add_dedi.clicked.connect(
            lambda checked=False, index=route_index: self.add_crystal_dedi(index)
        )
        layout.addWidget(add_dedi)

        self._add_deposit_subheading(layout, "VAULTS")
        for vault_index, vault in enumerate(route["vault"]["items"]):
            layout.addLayout(
                self._vault_row(
                    vault,
                    lambda checked=False, r=route_index, i=vault_index: self.remove_crystal_vault(
                        r, i
                    ),
                )
            )
        add_vault = self._button("ADD VAULT", "secondary")
        add_vault.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        add_vault.clicked.connect(
            lambda checked=False, index=route_index: self.add_crystal_vault(index)
        )
        layout.addWidget(add_vault)
        return card

    def _grindable_route_card(self, route, route_index):
        card, layout = self._deposit_route_card(
            f"GRINDABLE ROUTE {route_index + 1}",
            lambda checked=False, index=route_index: self.remove_grindable_route(index),
            lambda checked=False, index=route_index: self.open_deposit_helper(
                "grindable", index
            ),
        )
        self._add_route_teleport_field(layout, route)

        self._add_deposit_subheading(layout, "GRINDER")
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

        self._add_deposit_subheading(layout, "DEDIS")
        for item_index, item in enumerate(route["dedi"]["items"]):
            layout.addLayout(
                self._dedi_row(
                    item,
                    lambda checked=False, r=route_index, i=item_index: self.remove_grindable_dedi(
                        r, i
                    ),
                )
            )
        add_dedi = self._button("ADD DEDI", "secondary")
        add_dedi.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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

    def open_deposit_helper(self, route_kind, route_index):
        if not self._can_open_setup_helper():
            return
        self._ensure_deposit_config()
        existing = self.find_deposit_helper(route_kind, route_index)
        if existing is not None:
            existing.show()
            existing.raise_()
            existing.activateWindow()
            self.deposit_helper = existing
            return

        self.close_external_helpers()
        helper = DepositRouteHelper(self, route_kind, route_index)
        self.register_deposit_helper(helper)
        helper.show()
        helper.raise_()
        helper.activateWindow()
        self.deposit_helper = helper

    def open_position_render_helper(self):
        if not self._can_open_setup_helper():
            return
        helper = self.find_deposit_helper("position_render", None)
        if helper is not None:
            helper.show()
            helper.raise_()
            helper.activateWindow()
            self.deposit_helper = helper
            return

        self.close_external_helpers()
        helper = PositionRenderHelper(self)
        helper.route_kind = "position_render"
        helper.route_index = None
        self.register_deposit_helper(helper)
        helper.show()
        helper.raise_()
        helper.activateWindow()
        self.deposit_helper = helper

    def open_fertilizer_refresh_helper(self):
        if not self._can_open_setup_helper():
            return
        helper = self.find_deposit_helper("fertilizer_refresh", None)
        if helper is not None:
            helper.show()
            helper.raise_()
            helper.activateWindow()
            self.deposit_helper = helper
            return

        self.close_external_helpers()
        helper = FertilizerRefreshHelper(self)
        self.register_deposit_helper(helper)
        helper.show()
        helper.raise_()
        helper.activateWindow()
        self.deposit_helper = helper

    def open_auto_join_server_helper(self):
        if not self._can_open_setup_helper():
            return
        helper = self.find_deposit_helper("auto_join_server", None)
        if helper is not None:
            helper.show()
            helper.raise_()
            helper.activateWindow()
            self.deposit_helper = helper
            return

        self.close_external_helpers()
        helper = AutoJoinServerHelper(self)
        self.register_deposit_helper(helper)
        helper.show()
        helper.raise_()
        helper.activateWindow()
        self.deposit_helper = helper

    def open_server_transfer_helper(self):
        if not self._can_open_setup_helper():
            return
        helper = self.find_deposit_helper("server_transfer", None)
        if helper is not None:
            helper.show()
            helper.raise_()
            helper.activateWindow()
            self.deposit_helper = helper
            return

        self.close_external_helpers()
        helper = ServerTransferHelper(self)
        self.register_deposit_helper(helper)
        helper.show()
        helper.raise_()
        helper.activateWindow()
        self.deposit_helper = helper

    def _can_open_setup_helper(self):
        if self.is_program_running() or getattr(self, "program_stopping", False):
            self.dialog(
                "Stop Program First",
                "Stop the running automation before opening a setup helper.",
                "warning",
            )
            return False
        return True

    def find_deposit_helper(self, route_kind, route_index):
        for helper in list(getattr(self, "external_helpers", [])):
            try:
                if (
                    helper.route_kind == route_kind
                    and helper.route_index == route_index
                ):
                    return helper
            except RuntimeError:
                self.forget_deposit_helper(helper)
        return None

    def register_deposit_helper(self, helper):
        if not hasattr(self, "external_helpers"):
            self.external_helpers = []
        if helper not in self.external_helpers:
            self.external_helpers.append(helper)
        helper.destroyed.connect(
            lambda _=None, tracked=helper: self.forget_deposit_helper(tracked)
        )

    def forget_deposit_helper(self, helper):
        helpers = getattr(self, "external_helpers", [])
        if helper in helpers:
            helpers.remove(helper)

    def close_external_helpers(self):
        for helper in list(getattr(self, "external_helpers", [])):
            try:
                helper.close()
            except RuntimeError:
                pass
        self.external_helpers.clear()

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
        self._skip_visible_field_persist = True
        self._render_settings_group(getattr(self, "current_settings_group", "GENERAL"))
        self._update_auto_start_switch()
        self._tick()
        self.append_log("[SUCCESS] JSON config files refreshed.\n")

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

    def _add_deposit_subheading(self, layout, text):
        label = QLabel(text)
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
        switch = CyberSwitch("CROUCHED")
        switch.blockSignals(True)
        switch.setChecked(bool(item.get("crouched", False)))
        switch.blockSignals(False)
        switch.toggled.connect(
            lambda checked, route_item=item: self.update_deposit_bool(
                route_item, "crouched", checked
            )
        )
        return switch

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
        self._render_settings_group("STORAGE")

    def remove_crystal_route(self, route_index):
        if len(self.deposit_config["depositCrystalData"]) <= 1:
            self.dialog(
                "Deposit Routes",
                "At least one crystal deposit route is required.",
                "warning",
            )
            return
        del self.deposit_config["depositCrystalData"][route_index]
        self.save_deposit_routes()
        self._render_settings_group("STORAGE")

    def add_crystal_dedi(self, route_index):
        self.deposit_config["depositCrystalData"][route_index]["dedi"]["items"].append(
            default_dedi_item()
        )
        self.save_deposit_routes()
        self._render_settings_group("STORAGE")

    def remove_crystal_dedi(self, route_index, item_index):
        del self.deposit_config["depositCrystalData"][route_index]["dedi"]["items"][
            item_index
        ]
        self.save_deposit_routes()
        self._render_settings_group("STORAGE")

    def add_crystal_vault(self, route_index):
        self.deposit_config["depositCrystalData"][route_index]["vault"]["items"].append(
            default_vault_item()
        )
        self.save_deposit_routes()
        self._render_settings_group("STORAGE")

    def remove_crystal_vault(self, route_index, item_index):
        del self.deposit_config["depositCrystalData"][route_index]["vault"]["items"][
            item_index
        ]
        self.save_deposit_routes()
        self._render_settings_group("STORAGE")

    def add_grindable_route(self):
        self.deposit_config["depositGrindableData"].append(default_grindable_route())
        self.save_deposit_routes()
        self._render_settings_group("STORAGE")

    def remove_grindable_route(self, route_index):
        if len(self.deposit_config["depositGrindableData"]) <= 1:
            self.dialog(
                "Deposit Routes",
                "At least one grindable route is required.",
                "warning",
            )
            return
        del self.deposit_config["depositGrindableData"][route_index]
        self.save_deposit_routes()
        self._render_settings_group("STORAGE")

    def add_grindable_dedi(self, route_index):
        self.deposit_config["depositGrindableData"][route_index]["dedi"][
            "items"
        ].append(default_dedi_item())
        self.save_deposit_routes()
        self._render_settings_group("STORAGE")

    def remove_grindable_dedi(self, route_index, item_index):
        del self.deposit_config["depositGrindableData"][route_index]["dedi"]["items"][
            item_index
        ]
        self.save_deposit_routes()
        self._render_settings_group("STORAGE")

    def reset_deposit_routes(self):
        self.deposit_config = default_deposit_config()
        self.save_deposit_routes(show_log=False)
        self._render_settings_group("STORAGE")
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
        self._render_settings_group("STORAGE")

    def _add_station_text_field(self, row, label_text, value, entry_index, kind):
        label = QLabel(label_text)
        label.setObjectName("FormLabel")
        field = self._deposit_line_edit(value)
        field.editingFinished.connect(
            lambda field=field, index=entry_index, key=label_text, name=kind: self.update_station_field(
                name, index, key, field
            )
        )
        field.returnPressed.connect(
            lambda field=field, index=entry_index, key=label_text, name=kind: self.update_station_field(
                name, index, key, field
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

    def _ensure_pego_config(self):
        if hasattr(self, "pego_config"):
            return
        try:
            self.pego_config = load_pego_config()
        except ValueError as exc:
            self.pego_config = [default_pego_entry()]
            self.append_log(f"[ERROR] Invalid pego config: {exc}\n")
            self.dialog("Invalid Pego Config", str(exc), "error")

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

    def update_gacha_group_teleporter(self, old_teleporter, field):
        self._ensure_gacha_config()
        if not hasattr(self, "gacha_group_expanded"):
            self.gacha_group_expanded = {}
        new_teleporter = field.text()
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

    def update_pego_delay_recommendation(self, show_error: bool = True) -> int | None:
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

    def apply_pego_delay_recommendation(self) -> None:
        delay = self.update_pego_delay_recommendation()
        if delay is None:
            return
        self.pego_bulk_delay_field.setText(str(delay))
        self._ensure_pego_config()
        set_all_pego_delays(self.pego_config, delay)
        self.save_pego_config()
        self._render_settings_group("PEGO")

    def reset_pego_delay_calculator(self) -> None:
        self._ensure_pego_config()
        self._ensure_gacha_config()
        defaults = [
            DEFAULT_PEGO_TARGET_CRYSTALS,
            len(self.pego_config),
            len(self.gacha_config),
            DEFAULT_PEGO_SNOW_OWLS_PER_GACHA,
            DEFAULT_PEGO_STATION_SECONDS,
        ]
        for field, value in zip(self._pego_calculator_fields(), defaults):
            field.setText(str(value))
        self.update_pego_delay_recommendation(show_error=False)

    def _pego_delay_recommendation(self) -> int:
        return calculate_pego_delay(
            self.pego_calc_target_field.text(),
            self.pego_calc_pego_count_field.text(),
            self.pego_calc_gacha_count_field.text(),
            self.pego_calc_snow_owl_field.text(),
            self.pego_calc_station_seconds_field.text(),
        )

    def _toggle_pego_calculator(self, body: QWidget, button: QWidget) -> None:
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

    def copy_text(self, value):
        QApplication.clipboard().setText(str(value))
        self.toast("Teleport name copied to clipboard.", "success")

    def _logs_page(self):
        # DEBUG ONLY
        # def debug_only():
        #     print("Starting debugging...")
        #     import psutil

        #     for proc in psutil.process_iter(attrs=["name", "exe"]):
        #         if proc.info["name"] == "CrashReportClient.exe":
        #             print("Found target process!")

        # QTimer.singleShot(300, debug_only)

        page, layout = self._page("LogsPage")
        layout.addWidget(self._page_title("LOGS"))
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        layout.addLayout(filter_row)
        for name in [
            "ALL",
            "INFO",
            "DEBUG",
            "WARN",
            "ERROR",
            "CRITICAL",
            "RUNNING",
            "QUEUE",
        ]:
            button = self._button(name, "secondary")
            button.clicked.connect(
                lambda checked=False, value=name: self.set_log_filter(value)
            )
            filter_row.addWidget(button)
        filter_row.addStretch()
        clear = self._button("CLEAR LOGS", "danger")
        export = self._button("EXPORT", "secondary")
        clear.clicked.connect(self.clear_logs)
        export.clicked.connect(self.copy_logs)
        filter_row.addWidget(clear)
        filter_row.addWidget(export)

        console, console_layout = self._panel()
        self.full_log = self._console_widget()
        console_layout.addWidget(self.full_log)
        layout.addWidget(console, 1)
        bottom = QHBoxLayout()
        test = self._button("TEST CONSOLE COLOURS  >", "secondary")
        copy = self._button("COPY LOGS", "primary")
        test.clicked.connect(self.check_colours)
        copy.clicked.connect(self.copy_logs)
        bottom.addWidget(test)
        bottom.addStretch()
        bottom.addWidget(copy)
        layout.addLayout(bottom)
        return page

    def _tools_page(self):
        # QTimer.singleShot(300, self.open_server_transfer_helper)
        page, layout = self._page("ToolsPage")
        layout.addWidget(self._page_title("TOOLS"))
        tools_grid = QGridLayout()
        tools_grid.setContentsMargins(0, 0, 0, 0)
        tools_grid.setHorizontalSpacing(14)
        tools_grid.setVerticalSpacing(14)
        tools_grid.setColumnStretch(0, 1)
        tools_grid.setColumnStretch(1, 1)

        auto_join_card, auto_join_layout = self._panel("AUTO JOIN SERVER")
        auto_join_description = QLabel(
            "Enter a server number and retry the existing join flow until the "
            "character is detected back in-server."
        )
        auto_join_description.setObjectName("MutedCopy")
        auto_join_description.setWordWrap(True)
        open_auto_join = self._button("OPEN TOOL", "primary")
        open_auto_join.clicked.connect(self.open_auto_join_server_helper)
        auto_join_layout.addWidget(auto_join_description)
        auto_join_layout.addWidget(open_auto_join)

        transfer_card, transfer_layout = self._panel("SERVER TRANSFER HELPER")
        transfer_description = QLabel(
            "Move resources between two servers across multiple Steam accounts. "
            "The helper saves its own settings and blocks start until required "
            "Steam and transfer UI inputs are configured."
        )
        transfer_description.setObjectName("MutedCopy")
        transfer_description.setWordWrap(True)
        open_transfer = self._button("OPEN TOOL", "primary")
        open_transfer.clicked.connect(self.open_server_transfer_helper)
        transfer_layout.addWidget(transfer_description)
        transfer_layout.addWidget(open_transfer)

        fertilizer_card, card_layout = self._panel("CROP PLOT FERTILIZER REFRESH")
        description = QLabel(
            "Refresh crop plot fertilizer with one quick helper. Start the tool, "
            "and it will open a crop plot inventory, transfer everything to your "
            "player inventory and back into the crop plot."
        )
        description.setObjectName("MutedCopy")
        description.setWordWrap(True)
        open_tool = self._button("OPEN TOOL", "primary")
        open_tool.clicked.connect(self.open_fertilizer_refresh_helper)
        card_layout.addWidget(description)
        card_layout.addWidget(open_tool)

        tools_grid.addWidget(auto_join_card, 0, 0)
        tools_grid.addWidget(transfer_card, 0, 1)
        tools_grid.addWidget(fertilizer_card, 1, 0)
        layout.addLayout(tools_grid)
        layout.addStretch()
        return page

    def _console_widget(self):
        console = ClickableTextEdit()
        console.setObjectName("Console")
        console.setReadOnly(True)
        console.copied.connect(lambda: self.toast("Logs copied", "success"))
        return console

    def _update_page(self):
        page, layout = self._page("UpdatePage")
        layout.addWidget(self._page_title("CHECK UPDATE"))
        layout.addStretch()
        card, card_layout = self._panel()
        card.setMaximumWidth(420)
        icon = QLabel("[CLOUD]")
        icon.setObjectName("UpdateIcon")
        icon.setAlignment(Qt.AlignCenter)
        current = QLabel("CURRENT VERSION\nv1.0.0")
        current.setAlignment(Qt.AlignCenter)
        latest = QLabel("LATEST VERSION\nv1.1.0\nUpdate available!")
        latest.setObjectName("UpdateLatest")
        latest.setAlignment(Qt.AlignCenter)
        changelog, changelog_layout = self._panel("CHANGELOG")
        changelog_layout.addWidget(QLabel("- Added new queue management"))
        changelog_layout.addWidget(QLabel("- Improved stability and performance"))
        changelog_layout.addWidget(QLabel("- Fixed minor bugs"))
        row = QHBoxLayout()
        check = self._button("CHECK UPDATE  >", "primary")
        download = self._button("OPEN DOWNLOAD PAGE", "secondary")
        check.clicked.connect(
            lambda: self.toast("Update check is not wired yet.", "info")
        )
        download.clicked.connect(
            lambda: self.toast("Download page is not configured yet.", "info")
        )
        row.addWidget(check)
        row.addWidget(download)
        card_layout.addWidget(icon)
        card_layout.addWidget(current)
        card_layout.addWidget(latest)
        card_layout.addWidget(changelog)
        card_layout.addLayout(row)
        layout.addWidget(card, alignment=Qt.AlignCenter)
        layout.addStretch()
        return page

    def _about_page(self):
        page, layout = self._page("AboutPage")
        layout.addWidget(self._page_title("ABOUT ME"))
        layout.addStretch()
        card, card_layout = self._panel()
        card.setMaximumWidth(420)
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        if os.path.exists(ASSETS["logo"]):
            logo.setPixmap(
                QPixmap(ASSETS["logo"]).scaled(
                    110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        title = QLabel(f"{APP_TITLE}\n{APP_VERSION}")
        title.setObjectName("AboutTitle")
        title.setAlignment(Qt.AlignCenter)
        author = QLabel('DEVELOPED BY\nShen\n\n"Code. Automate. Dominate."')
        author.setAlignment(Qt.AlignCenter)
        connect = QHBoxLayout()
        for text in ["GITHUB", "WEBSITE"]:
            button = self._button(text, "secondary")
            button.clicked.connect(
                lambda checked=False, name=text: self.toast(
                    f"{name} link is not configured yet.", "info"
                )
            )
            connect.addWidget(button)
        thanks = QLabel(f"SPECIAL THANKS TO\nYou, for using {APP_NAME}")
        thanks.setObjectName("MutedCopy")
        thanks.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(logo)
        card_layout.addWidget(title)
        card_layout.addWidget(author)
        card_layout.addLayout(connect)
        card_layout.addWidget(thanks)
        layout.addWidget(card, alignment=Qt.AlignCenter)
        layout.addStretch()
        return page
