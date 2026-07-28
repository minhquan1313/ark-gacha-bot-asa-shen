import threading

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
    QVBoxLayout,
    QWidget,
    ToolCoverCard,
    os,
    utils_simple,
)
from source.launcher.utils.update_service import (
    REPOSITORY_ROOT,
    UpdateCheckResult,
    UpdateManifest,
    check_for_update,
    load_manifest,
)


class LogsToolsPagesMixin:
    @staticmethod
    def _format_manifest_notes(manifest):
        """Format release metadata for the update-page notes panel."""
        notes = [manifest.title, f"Released: {manifest.released_at}"]
        notes.extend(f"- {item}" for item in manifest.changelog)
        return "\n".join(item for item in notes if item)

    def _set_update_notes(self, text):
        """Render each release-note line as its own expanding label."""
        notes_panel = self.update_changelog_label
        notes_layout = notes_panel.layout()
        while notes_layout.count():
            item = notes_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for line in text.splitlines() or [""]:
            label = QLabel(line)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
            notes_layout.addWidget(label)

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
        auto_feed_card = self._tool_cover_card(
            "Auto Baby Feeding",
            "Feed every configured Baby and maintain food and water between cycles.",
            ASSETS["welcome"],
            self.open_auto_feed_helper,
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
            auto_feed_card,
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
        card.setMinimumWidth(0)
        card.setMaximumWidth(400)
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        icon = QLabel("[GUpdate]")
        icon.setObjectName("UpdateIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        local_manifest = None
        local_manifest_error = ""
        try:
            current_manifest = load_manifest()
            current_version = current_manifest.version
            local_manifest = current_manifest
        except ValueError as exc:
            current_version = APP_VERSION.lstrip("vV")
            local_manifest_error = f"Unable to load local manifest: {exc}"
        current = QLabel(f"Version: {current_version}")
        self.update_current_label = current
        current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        latest = QLabel("Checking status not started")
        latest.setObjectName("UpdateLatest")
        latest.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_status_label = latest
        changelog, changelog_layout = self._panel("RELEASE NOTES")
        changelog_text = QWidget()
        changelog_text.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        notes_layout = QVBoxLayout(changelog_text)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.setSpacing(2)
        self.update_changelog_label = changelog_text
        self._set_update_notes(
            local_manifest_error or self._format_manifest_notes(local_manifest)
        )
        changelog.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        changelog_layout.addWidget(changelog_text)
        row = QHBoxLayout()
        action = self._button("CHECK UPDATE", "primary")
        action.clicked.connect(self._handle_update_action)
        self.update_action_button = action
        row.addWidget(action)
        card_layout.addWidget(icon)
        card_layout.addWidget(current)
        card_layout.addWidget(latest)
        card_layout.addWidget(changelog)
        card_layout.addLayout(row)
        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        return page

    def _automatic_update_check(self):
        """Start the periodic update check while automatic checks are enabled."""
        if not getattr(self, "shutdown_started", False) and getattr(
            self, "update_auto_check_enabled", True
        ):
            self._start_update_check(automatic=True)

    def _start_update_check(self, automatic=False):
        """Run the shared updater check without blocking the launcher UI."""
        if getattr(self, "shutdown_started", False):
            return
        if getattr(self, "update_check_in_progress", False):
            action = getattr(self, "update_action_button", None)
            if action is not None:
                action.setEnabled(False)
                action.setText("CHECKING...")
            status = getattr(self, "update_status_label", None)
            if status is not None:
                status.show()
                status.setText("CHECKING FOR UPDATE...")
            return
        self.update_check_in_progress = True
        self.update_check_automatic = automatic
        action = getattr(self, "update_action_button", None)
        if action is not None:
            action.setEnabled(False)
            action.setText("CHECKING...")
        status = getattr(self, "update_status_label", None)
        if status is not None:
            status.show()
            status.setText("CHECKING FOR UPDATE...")
        threading.Thread(
            target=self._run_update_check,
            args=(automatic,),
            daemon=True,
        ).start()

    def _run_update_check(self, automatic):
        """Execute the update service on a worker thread."""
        try:
            result = check_for_update()
        except Exception as exc:
            try:
                current = load_manifest()
            except Exception:
                current = UpdateManifest("0.0.0", "", "", ())
            result = UpdateCheckResult(current, current, False, str(exc))
        self.update_check_finished.emit(result, automatic)

    def _on_update_check_finished(self, result: UpdateCheckResult, automatic):
        """Render check results and optionally ask about an automatic update."""
        if getattr(self, "shutdown_started", False):
            self.update_check_in_progress = False
            return
        self.update_check_in_progress = False
        self.update_check_automatic = False
        self.update_available = result.update_available
        action = getattr(self, "update_action_button", None)
        status = getattr(self, "update_status_label", None)
        changelog = getattr(self, "update_changelog_label", None)
        if result.error:
            if status is not None:
                status.show()
                status.setText("UPDATE CHECK FAILED")
            if changelog is not None:
                self._set_update_notes(result.error)
            if action is not None:
                action.setText("CHECK UPDATE")
                action.setEnabled(True)
            if automatic:
                self.toast(result.error, "error")
            return

        # latest_label = ("UPDATE AVAILABLE" if result.update_available else "NEWEST VERSION")
        if status is not None:
            # status.setText(f"{latest_label}\nVersion: {result.latest.version}")
            if result.update_available:
                status.show()
                status.setText(f"UPDATE AVAILABLE\nVersion: {result.latest.version}")
            else:
                status.hide()
        if changelog is not None:
            manifest = result.latest if result.update_available else result.current
            self._set_update_notes(self._format_manifest_notes(manifest))
        if action is not None:
            action.setText("UPDATE" if result.update_available else "CHECK UPDATE")
            action.setEnabled(True)

        if automatic and result.update_available:
            if self.confirm(
                "Update Available",
                f"Version {result.latest.version} is available. Update now?",
                "UPDATE",
            ):
                self._request_update_restart()
            else:
                self.update_auto_check_enabled = False
                self.auto_update_timer.stop()

    def _handle_update_action(self):
        """Check for updates or begin the restart flow for an available update."""
        if getattr(self, "update_available", False):
            self._request_update_restart()
        else:
            self._start_update_check()

    def _request_update_restart(self):
        """Ask run.bat to restart after its current launcher cleanup completes."""
        try:
            (REPOSITORY_ROOT / ".update_restart.request").write_text(
                "restart\n", encoding="utf-8"
            )
        except OSError as exc:
            self.dialog("Update Restart Failed", str(exc), "error")
            return
        self._shutdown_resources()
        self.close()

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
