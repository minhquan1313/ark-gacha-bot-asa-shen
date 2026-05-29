import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from source.launcher.constants import (
    APP_NAME,
    APP_TITLE,
    APP_VERSION,
    ASSETS,
    COLORS,
    DEFAULT_SETTINGS,
    SETTINGS_GROUPS,
)
from source.launcher.widgets import (
    AnimatedButton,
    ClickableTextEdit,
    CyberSwitch,
    HeroBanner,
    MeterBar,
)


class LauncherPagesMixin:
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
        layout.addWidget(HeroBanner(self))

        stats = QGridLayout()
        stats.setSpacing(10)
        layout.addLayout(stats)
        self.server_value = self._stat_card(stats, 0, "SERVER NUMBER", "ID")
        self.active_value = self._stat_card(stats, 1, "ACTIVE QUEUE", "TASKS")
        self.waiting_value = self._stat_card(stats, 2, "WAITING QUEUE", "TASKS")
        self.uptime_value = self._stat_card(stats, 3, "UPTIME", "HH:MM:SS")

        middle = QHBoxLayout()
        middle.setSpacing(12)
        layout.addLayout(middle, 1)

        actions, action_layout = self._panel("QUICK ACTIONS")
        actions.setFixedWidth(300)
        self.start_stop_button = self._button("START PROGRAM", "primary")
        self.start_stop_button.clicked.connect(self.toggle_program)
        action_layout.addWidget(self.start_stop_button)

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
        return page

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
        shell_layout.setContentsMargins(0, 0, 0, 0)
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
        tab_frame.setMinimumWidth(270)
        tab_frame.setMaximumWidth(340)
        tab_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        tab_frame.setLayout(tabs)
        content.addWidget(tab_frame)

        form_area = QScrollArea()
        form_area.setWidgetResizable(True)
        form_area.setObjectName("SettingsScroll")
        self.settings_form = QWidget()
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

        action_bar = QHBoxLayout()
        shell_layout.addLayout(action_bar)
        action_bar.addStretch()
        reset_button = self._button("RESET", "secondary")
        reset_button.clicked.connect(self.confirm_reset)
        action_bar.addWidget(reset_button)
        self._render_settings_group("GENERAL")
        return page

    def _render_settings_group(self, group_name):
        self.persist_settings_from_visible_fields(show_log=False, show_error=False)
        while self.settings_form_layout.count():
            item = self.settings_form_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.fields = {}

        heading = QLabel(f"{group_name} SETTINGS")
        heading.setObjectName("SectionHeading")
        self.settings_form_layout.addWidget(heading, 0, 0, 1, 4)

        keys = SETTINGS_GROUPS[group_name]
        for index, key in enumerate(keys, start=1):
            default_value = DEFAULT_SETTINGS[key]
            label = QLabel(key)
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

    def _logs_page(self):
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
            "TEMPLATE",
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
