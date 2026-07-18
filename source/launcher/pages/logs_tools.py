from source.launcher.pages.common import (
    APP_NAME,
    APP_TITLE,
    APP_VERSION,
    ASSETS,
    ClickableTextEdit,
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPixmap,
    QSizePolicy,
    Qt,
    ToolCoverCard,
    os,
    utils_simple,
)


class LogsToolsPagesMixin:
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
        clear.clicked.connect(self.clear_logs)
        filter_row.addWidget(clear)

        console, console_layout = self._panel()
        console.setObjectName("ConsolePanel")
        self.full_log = self._console_widget()
        console_layout.addWidget(self.full_log)
        layout.addWidget(console, 1)
        bottom = QHBoxLayout()
        test = self._button("TEST CONSOLE COLOURS  >", "secondary")
        open_logs = self._button("OPEN LOGS", "primary")
        test.clicked.connect(self.check_colours)
        open_logs.clicked.connect(self.open_logs)
        bottom.addWidget(test)
        bottom.addStretch()
        bottom.addWidget(open_logs)
        layout.addLayout(bottom)
        return page

    def _tools_page(self):
        # QTimer.singleShot(300, self.open_server_transfer_helper)
        page, layout = self._page("ToolsPage")
        layout.addWidget(self._page_title("TOOLS"))
        tools_grid = QGridLayout()
        tools_grid.setContentsMargins(0, 0, 0, 0)
        tools_grid.setHorizontalSpacing(12)
        tools_grid.setVerticalSpacing(12)
        # tools_grid.setColumnStretch(0, 1)
        # tools_grid.setColumnStretch(1, 1)

        auto_join_card = self._tool_cover_card(
            "Auto Join Server",
            "Enter a server number and retry the existing join flow until the "
            "character is detected back in-server.",
            ASSETS["welcome"],
            self.open_auto_join_server_helper,
        )
        transfer_card = self._tool_cover_card(
            "Server Transfer Helper",
            "Move resources between two servers across multiple Steam accounts.",
            "assets/templateHammer/GachaBot - Transfer Base.jpg",
            self.open_server_transfer_helper,
        )
        fertilizer_card = self._tool_cover_card(
            "Crop Plot Fertilizer Refresh",
            "Refresh crop plot fertilizer with one quick helper.",
            ASSETS["dashboard"],
            self.open_fertilizer_refresh_helper,
        )
        fishing_card = self._tool_cover_card(
            "Auto Fishing",
            "Enjoy AFK fishing",
            ASSETS["dashboard"],
            self.open_auto_fishing_helper,
        )
        switch_card = self._tool_cover_card(
            "Switch Steam",
            "Restart Steam with any saved account, or switch accounts before "
            "launching ARK.",
            "assets/templateHammer/GachaBot - Render V3.jpg",
            self.open_switch_steam_helper,
        )

        loc_gen = utils_simple.grid_loc_gen(col=2)
        helpers = [
            auto_join_card,
            fertilizer_card,
            fishing_card,
            transfer_card,
            switch_card,
        ]
        for index, helper in enumerate(helpers):
            col, row = loc_gen(index)
            tools_grid.addWidget(helper, row, col)

        layout.addLayout(tools_grid)
        layout.addStretch()
        return page

    def _tool_cover_card(self, title, description, image_path, handler):
        card = ToolCoverCard(image_path)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)
        copy = QLabel(f"{title}\n{description}")
        copy.setObjectName("ToolCoverCopy")
        copy.setWordWrap(True)
        open_tool = self._button("OPEN TOOL", "primary")
        open_tool.clicked.connect(handler)
        card_layout.addWidget(copy, 1, alignment=Qt.AlignmentFlag.AlignBottom)
        card_layout.addWidget(open_tool, alignment=Qt.AlignmentFlag.AlignBottom)
        return card

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
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        current = QLabel("CURRENT VERSION\nv1.0.0")
        current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        latest = QLabel("LATEST VERSION\nv1.1.0\nUpdate available!")
        latest.setObjectName("UpdateLatest")
        latest.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        return page

    def _about_page(self):
        page, layout = self._page("AboutPage")
        layout.addWidget(self._page_title("ABOUT ME"))
        layout.addStretch()
        card, card_layout = self._panel()
        card.setMaximumWidth(420)
        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if os.path.exists(ASSETS["logo"]):
            logo.setPixmap(
                QPixmap(ASSETS["logo"]).scaled(
                    110,
                    110,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        title = QLabel(f"{APP_TITLE}\n{APP_VERSION}")
        title.setObjectName("AboutTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author = QLabel('DEVELOPED BY\nShen\n\n"Code. Automate. Dominate."')
        author.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        thanks.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(logo)
        card_layout.addWidget(title)
        card_layout.addWidget(author)
        card_layout.addLayout(connect)
        card_layout.addWidget(thanks)
        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        return page
