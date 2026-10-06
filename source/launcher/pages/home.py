from PySide6.QtWidgets import QScrollArea, QSizePolicy

from source.launcher.components.dashboard import (
    DashboardButton,
    DashboardConsole,
    DashboardHero,
    DashboardSwitch,
    IconBadge,
    NeonPanel,
    StatCard,
    StatusCard,
    text_label,
)
from source.launcher.dashboard_theme import dashboard_style
from source.launcher.pages.common import (
    APP_NAME,
    APP_TITLE,
    ASSETS,
    CyberSwitch,
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
        copy = QLabel(f"AUTOMATE. MANAGE. DOMINATE.\n\n{APP_NAME} is your compact companion for managing automation tasks, queues, and local offline runs with style.")
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
        """Build the reference composition around the existing runtime connections."""
        page, layout = self._page("DashboardPage")
        self.dashboard_content = page
        self.dashboard_layout = layout
        scroll = QScrollArea()
        scroll.setObjectName("DashboardScroll")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        scroll.setStyleSheet("QScrollArea#DashboardScroll { background: #02080E; border: none; }")
        self.dashboard_hero = DashboardHero()
        layout.addWidget(self.dashboard_hero)

        self.dashboard_stats = QGridLayout()
        self.dashboard_stat_cards = [
            StatCard("SERVER NUMBER", "ID", "server"),
            StatCard("ACTIVE QUEUE", "TASKS", "queue"),
            StatCard("WAITING QUEUE", "TASKS", "clock"),
            StatCard("UPTIME", "HH : MM : SS", "clock"),
        ]
        for column, card in enumerate(self.dashboard_stat_cards):
            self.dashboard_stats.addWidget(card, 0, column)
            self.dashboard_stats.setColumnStretch(column, 1)
        self.dashboard_server_card = self.dashboard_stat_cards[0]
        self.server_value, self.active_value, self.waiting_value, self.uptime_value = (card.value for card in self.dashboard_stat_cards)
        layout.addLayout(self.dashboard_stats)

        self.dashboard_middle = QGridLayout()
        layout.addLayout(self.dashboard_middle, 1)
        actions = NeonPanel()
        self.dashboard_actions_card = actions
        action_layout = QVBoxLayout(actions)
        self.dashboard_action_layout = action_layout
        head = QHBoxLayout()
        head.addWidget(IconBadge("bolt", False))
        headings = QVBoxLayout()
        headings.setSpacing(2)
        headings.addWidget(text_label("QUICK ACTIONS", "section"))
        headings.addWidget(text_label("GET THINGS DONE", "muted"))
        head.addLayout(headings, 1)
        action_layout.addLayout(head)
        self.start_stop_button = DashboardButton("START GBOT", "primary", "play")
        self.start_stop_button.setToolTip("Hotkey: Shift + Alt + N")
        self.start_stop_button.clicked.connect(self.toggle_program)
        action_layout.addWidget(self.start_stop_button)

        self.restore_game_settings_button = DashboardButton("RESTORE SETTINGS", "secondary", "update")
        self.restore_game_settings_button.setToolTip("Restore the saved monitor layout, original display mode, and ARK config. Right-click to clear saved restore data.")
        self.restore_game_settings_button.clicked.connect(self.restore_game_settings)
        self.restore_game_settings_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.restore_game_settings_button.customContextMenuRequested.connect(lambda _pos: self.clear_game_restore_settings())
        action_layout.addWidget(self.restore_game_settings_button)
        self._update_game_restore_button_visibility()

        self.start_game_button = DashboardButton("ARK ASCENDED", "secondary", "play")
        self.start_game_button.setToolTip("Left-click: keep only the primary monitor, apply all automation settings, and start ARK. Right-click: apply only 1920x1080 and fullscreen settings.")
        self.start_game_button.clicked.connect(self.start_game)
        self.start_game_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.start_game_button.customContextMenuRequested.connect(lambda _pos: self.start_game_with_display_settings())
        action_layout.addWidget(self.start_game_button)
        self._update_start_game_button_visibility()

        action_layout.addStretch(1)
        self.dashboard_quote = text_label('"CONSISTENT AUTOMATION\n   CREATES FREEDOM."', "subtitle")
        action_layout.addWidget(self.dashboard_quote)
        self.dashboard_middle.addWidget(actions, 0, 0)

        console = NeonPanel()
        self.dashboard_console_panel = console
        console_layout = QVBoxLayout(console)
        console_layout.setContentsMargins(10, 10, 10, 10)
        console_layout.setSpacing(8)
        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(IconBadge("terminal", False))
        header.addWidget(text_label("LIVE CONSOLE (LATEST)", "section"), 1)
        header.addWidget(text_label("AUTO SCROLL", "footer"))
        self.dashboard_auto_scroll = DashboardSwitch("")
        self.dashboard_auto_scroll.setAccessibleName("Auto scroll dashboard console")
        self.dashboard_auto_scroll.setFixedWidth(58)
        self.dashboard_auto_scroll.setChecked(True)
        header.addWidget(self.dashboard_auto_scroll)
        self.dashboard_clear_button = DashboardButton("CLEAR", icon="trash", compact=True)
        self.dashboard_clear_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.dashboard_clear_button.clicked.connect(self.clear_logs)
        header.addWidget(self.dashboard_clear_button)
        console_layout.addLayout(header)
        divider = QFrame()
        divider.setObjectName("ConsoleDivider")
        divider.setFixedHeight(1)
        console_layout.addWidget(divider)
        self.dashboard_log = DashboardConsole()
        self.dashboard_log.copied.connect(lambda: self.toast("Logs copied", "success"))
        self.dashboard_auto_scroll.toggled.connect(self.dashboard_log.set_auto_scroll)
        console_layout.addWidget(self.dashboard_log, 1)
        self.dashboard_open_logs = DashboardButton("OPEN FULL LOGS", compact=True)
        self.dashboard_open_logs.clicked.connect(lambda: self.show_page("logs"))
        console_layout.addWidget(self.dashboard_open_logs, alignment=Qt.AlignmentFlag.AlignRight)
        self.dashboard_middle.addWidget(console, 0, 1)

        self.dashboard_footer = QGridLayout()
        self.dashboard_status_cards = [
            StatusCard("MEMORY USAGE", "chip", True, True),
            StatusCard("CPU USAGE", "chip", True),
            StatusCard("RUNNER", "play"),
            StatusCard("LAST ACTIVITY", "activity"),
            StatusCard("SYSTEM TIME", "clock"),
        ]
        for column, card in enumerate(self.dashboard_status_cards):
            self.dashboard_footer.addWidget(card, 0, column)
        memory, cpu, runner, activity, clock = self.dashboard_status_cards
        self.memory_value, self.memory_meter = memory.value, memory.meter
        self.memory_percent_value = memory.percent
        self.cpu_value, self.cpu_meter = cpu.value, cpu.meter
        self.runner_value, self.activity_value, self.clock_value = (
            runner.value,
            activity.value,
            clock.value,
        )
        layout.addLayout(self.dashboard_footer)
        self.dashboard_signature = text_label("SHEN GBOT  |  AUTOMATION FOR A BETTER TOMORROW", "footer")
        self.dashboard_signature.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.dashboard_signature)
        self._dashboard_layout_key = None
        self._update_start_stop_button()
        self._update_auto_start_switch()
        QTimer.singleShot(0, self._sync_dashboard_actions_width)
        return scroll

    def _sync_dashboard_actions_width(self):
        """Apply responsive reference proportions without fixed widget coordinates."""
        if not hasattr(self, "dashboard_content"):
            return
        scale = max(0.78125, min(1.0, self.width() / 1536, self.height() / 1024))
        compact = self.width() < 1100
        key = (round(scale, 3), compact)
        if key == self._dashboard_layout_key:
            return
        self._dashboard_layout_key = key
        self.dashboard_content.setStyleSheet(dashboard_style(scale))
        gutter = round(16 * scale)
        self.dashboard_layout.setContentsMargins(gutter, round(10 * scale), gutter, round(30 * scale))
        self.dashboard_layout.setSpacing(gutter)
        self.dashboard_hero.set_scale(scale)
        self.dashboard_action_layout.setContentsMargins(gutter, gutter, gutter, gutter)
        self.dashboard_action_layout.setSpacing(gutter)
        for button in self.dashboard_content.findChildren(DashboardButton):
            button.set_scale(scale)
        self.dashboard_quote.setVisible(not compact)
        for grid in (
            self.dashboard_stats,
            self.dashboard_middle,
            self.dashboard_footer,
        ):
            grid.setSpacing(gutter)
        for index, card in enumerate(self.dashboard_stat_cards):
            self.dashboard_stats.removeWidget(card)
            self.dashboard_stats.addWidget(card, index // 2 if compact else 0, index % 2 if compact else index)
            card.set_scale(scale)
        for column in range(4):
            self.dashboard_stats.setColumnStretch(column, 1 if column < (2 if compact else 4) else 0)
        self.dashboard_middle.removeWidget(self.dashboard_console_panel)
        self.dashboard_middle.addWidget(self.dashboard_console_panel, 1 if compact else 0, 0 if compact else 1)
        self.dashboard_middle.setColumnStretch(0, 1 if compact else 26)
        self.dashboard_middle.setColumnStretch(1, 0 if compact else 74)
        self.dashboard_console_panel.setMinimumHeight(240 if compact else 200)
        for index, card in enumerate(self.dashboard_status_cards):
            self.dashboard_footer.removeWidget(card)
            self.dashboard_footer.addWidget(card, index // 2 if compact else 0, index % 2 if compact else index)
            card.set_scale(scale)
        for column, stretch in enumerate((33, 27, 11, 13, 13)):
            self.dashboard_footer.setColumnStretch(column, (1 if column < 2 else 0) if compact else stretch)
        # Settle nested grid geometry before returning from a maximize/restore turn.
        self.dashboard_layout.activate()

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
        body = QLabel("Set your gacha station names below. These names will be used for text automation and queue processing.")
        body.setObjectName("MutedCopy")
        body.setWordWrap(True)
        go = self._button("GO TO SETTINGS  >", "primary")
        go.clicked.connect(lambda: self.show_page("settings"))
        tip, tip_layout = self._panel("TIP")
        tip_text = QLabel("Make sure the names match exactly with your in-game stations to avoid errors.")
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
        badge.setObjectName("BadgeDone" if state == "DONE" else "BadgeWarn" if state == "INCOMPLETE" else "BadgePending")
        layout.addWidget(label)
        layout.addWidget(title, 1)
        layout.addWidget(badge)
        return item
