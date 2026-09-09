from typing import cast

from source.launcher.pages.common import (
    APP_NAME,
    APP_TITLE,
    ASSETS,
    COLORS,
    CyberSwitch,
    HeroBanner,
    MeterBar,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPixmap,
    Qt,
    QTimer,
    QVBoxLayout,
    os,
)


class HomePagesMixin:
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
        left.addWidget(start, alignment=Qt.AlignmentFlag.AlignRight)
        left.addStretch()

        art = QLabel()
        art.setObjectName("HeroArt")
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if os.path.exists(ASSETS["welcome"]):
            art.setPixmap(
                QPixmap(ASSETS["welcome"]).scaled(
                    430,
                    430,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
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
        server_card_item = stats.itemAtPosition(0, 0)
        if server_card_item is None:
            raise RuntimeError("Dashboard server card was not created")
        self.dashboard_server_card = server_card_item.widget()
        self.dashboard_server_card.installEventFilter(self)
        self.active_value = self._stat_card(stats, 1, "ACTIVE QUEUE", "TASKS")
        self.waiting_value = self._stat_card(stats, 2, "WAITING QUEUE", "TASKS")
        self.uptime_value = self._stat_card(stats, 3, "UPTIME", "HH:MM:SS")

        middle = QHBoxLayout()
        middle.setSpacing(dashboard_gutter)
        layout.addLayout(middle, 1)

        actions, action_layout = self._panel("QUICK ACTIONS")
        self.dashboard_actions_card = actions
        self.start_stop_button = self._button("START GBOT", "primary")
        self.start_stop_button.setToolTip("Hotkey: Shift + Alt + N")
        self.start_stop_button.clicked.connect(self.toggle_program)
        action_layout.addWidget(self.start_stop_button)

        # start_game_row = QHBoxLayout()
        start_game_row = QVBoxLayout()
        start_game_row.setSpacing(8)
        self.start_game_button = self._button("ARK ASCENDED", "secondary")
        self.start_game_button.setToolTip(
            "Left-click: apply all automation settings and start ARK. "
            "Right-click: apply only 1920x1080 and fullscreen settings."
        )
        self.start_game_button.clicked.connect(
            getattr(self, "start_game", lambda: None)
        )
        self.start_game_button.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.start_game_button.customContextMenuRequested.connect(
            lambda _pos: getattr(
                self, "start_game_with_display_settings", lambda: None
            )()
        )
        start_game_row.addWidget(self.start_game_button, 1)
        getattr(self, "_update_start_game_button_visibility", lambda: None)()

        self.restore_game_settings_button = self._icon_button(
            "icon.restore_settings",
            "Restore the original display mode and ARK config. "
            "Right-click to clear saved restore data.",
            "danger",
        )
        self.restore_game_settings_button.clicked.connect(
            getattr(self, "restore_game_settings", lambda: None)
        )
        self.restore_game_settings_button.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.restore_game_settings_button.customContextMenuRequested.connect(
            lambda _pos: getattr(self, "clear_game_restore_settings", lambda: None)()
        )
        start_game_row.addWidget(self.restore_game_settings_button)
        action_layout.addLayout(start_game_row)
        getattr(self, "_update_game_restore_button_visibility", lambda: None)()

        auto_start_box = QFrame()
        auto_start_box.setObjectName("InlineSwitchBox")
        auto_layout = QVBoxLayout(auto_start_box)
        auto_layout.setContentsMargins(10, 8, 10, 8)
        auto_layout.setSpacing(4)
        self.auto_start_switch = CyberSwitch("AUTO START")
        self.auto_start_switch.toggled.connect(
            getattr(self, "toggle_auto_start_program", lambda _checked: None)
        )
        self.auto_start_hint = QLabel("Start program when launcher opens")
        self.auto_start_hint.setObjectName("MutedCopy")
        auto_layout.addWidget(self.auto_start_switch)
        auto_layout.addWidget(self.auto_start_hint)
        action_layout.addWidget(auto_start_box)
        action_layout.addStretch()
        middle.addWidget(actions)

        console, console_layout = self._panel("LIVE CONSOLE (LATEST)")
        console.setObjectName("ConsolePanel")
        console_layout.setContentsMargins(16, 12, 16, 16)
        self.dashboard_log = self._console_widget()
        console_overlay = QFrame()
        console_overlay.setObjectName("ConsoleOverlay")
        overlay_layout = QGridLayout(console_overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(0)
        overlay_layout.addWidget(self.dashboard_log, 0, 0)
        open_logs = self._button("OPEN FULL LOGS", "secondary")
        open_logs.clicked.connect(lambda: self.show_page("logs"))
        overlay_layout.addWidget(
            open_logs,
            0,
            0,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
        )
        console_layout.addWidget(console_overlay, 1)
        middle.addWidget(console, 1)

        footer = QGridLayout()
        footer.setSpacing(8)
        layout.addLayout(footer)
        self.memory_value, self.memory_meter = cast(
            tuple[QLabel, MeterBar],
            self._footer_stat(footer, 0, "MEMORY USAGE", True, COLORS["green"]),
        )
        self.cpu_value, self.cpu_meter = cast(
            tuple[QLabel, MeterBar],
            self._footer_stat(footer, 1, "CPU USAGE", True, COLORS["cyan"]),
        )
        self.runner_value = cast(QLabel, self._footer_stat(footer, 2, "RUNNER"))
        self.activity_value = cast(
            QLabel, self._footer_stat(footer, 3, "LAST ACTIVITY")
        )
        self.clock_value = cast(QLabel, self._footer_stat(footer, 4, "SYSTEM TIME"))
        getattr(self, "_update_start_stop_button", lambda: None)()
        getattr(self, "_update_auto_start_switch", lambda: None)()
        QTimer.singleShot(0, self._sync_dashboard_actions_width)
        return page

    def _sync_dashboard_actions_width(self):
        if (
            hasattr(self, "dashboard_actions_card")
            and self.dashboard_server_card is not None
        ):
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
        panel_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(value, alignment=Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(sub, alignment=Qt.AlignmentFlag.AlignCenter)
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
            else "BadgeWarn"
            if state == "INCOMPLETE"
            else "BadgePending"
        )
        layout.addWidget(label)
        layout.addWidget(title, 1)
        layout.addWidget(badge)
        return item
