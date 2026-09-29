import threading
from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from source.launcher.components.about_page import CombinedAboutPage
from source.launcher.components.logs_page import LogsPage
from source.launcher.components.template_browser import TemplateBrowser
from source.launcher.components.tools_browser import ToolGalleryCard, ToolsBrowser
from source.launcher.config import constants as launcher_constants
from source.launcher.pages.common import (
    APP_VERSION,
    ASSETS,
    ClickableTextEdit,
    QApplication,
    QLabel,
    QSizePolicy,
    Qt,
)
from source.launcher.utils.building_templates import (
    TOOL_CATEGORIES,
)
from source.launcher.utils.update_schedule import UpdateSchedule
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
        """Build the virtualized reader without changing Dashboard filter state."""

        def snapshots(view: str):
            """Expose scheduler data read-only to the Logs page."""
            if view == "RUNNING":
                return self._format_running_snapshot()
            if view == "QUEUE":
                return self._format_queue_snapshot()
            return self.queue_snapshot

        self.logs_page = LogsPage(launcher_constants.GACHA_LOG_FILE, self.clear_logs, self.open_logs, snapshots)
        self.logs_page.store.initial.connect(self._loaded_log_history)
        return self.logs_page

    def _tools_page(self):
        # QTimer.singleShot(300, self.open_server_transfer_helper)
        page, layout = self._page("ToolsPage")
        self.tools_gallery = ToolsBrowser()
        auto_join_card = self._tool_cover_card(
            "Auto Join Server",
            "Enter a server number and retry the existing join flow until the character is detected back in-server.",
            ASSETS["tool.auto_join"],
            self.open_auto_join_server_helper,
        )
        transfer_card = self._tool_cover_card(
            "Server Transfer",
            "Move resources between two servers across multiple Steam accounts(max 4 accounts gives best exp).",
            ASSETS["tool.transfer_server"],
            self.open_server_transfer_helper,
        )
        fertilizer_card = self._tool_cover_card(
            "Crop Plot Fertilizer Refresh",
            "Refresh crop plot fertilizer with one quick helper.",
            ASSETS["tool.auto_fertilizer"],
            self.open_fertilizer_refresh_helper,
        )
        fishing_card = self._tool_cover_card(
            "Auto Fishing",
            "Enjoy AFK fishing",
            ASSETS["tool.auto_fishing"],
            self.open_auto_fishing_helper,
        )
        auto_feed_card = self._tool_cover_card(
            "Auto Baby Feeding",
            "Feed every baby and maintain food and water of character.",
            ASSETS["tool.auto_feed"],
            self.open_auto_feed_helper,
        )
        switch_card = self._tool_cover_card(
            "Switch Steam",
            "Restart Steam with any saved account, or switch accounts before launching ARK.",
            ASSETS["tool.switch_steam"],
            self.open_switch_steam_helper,
        )

        for card in (
            auto_join_card,
            fertilizer_card,
            fishing_card,
            auto_feed_card,
            transfer_card,
            switch_card,
        ):
            self.tools_gallery.add_card(card)
        layout.addWidget(self.tools_gallery)
        return page

    def _tool_cover_card(self, title: str, description: str, image_path: str, handler: Callable):
        """Build a shared gallery card connected to an existing helper."""
        card = ToolGalleryCard(
            title,
            description,
            image_path,
            "Open Tool",
            TOOL_CATEGORIES.get(title, "Unsorted"),
        )
        card.activated.connect(handler)
        return card

    def _btemplates_page(self):
        """Browse read-only building templates and import only from focused previews."""
        page, layout = self._page("BTemplatesPage")
        self.btemplates_gallery = TemplateBrowser(self.toast)
        layout.addWidget(self.btemplates_gallery)
        self.btemplates_gallery.load()
        return page

    def _console_widget(self):
        console = ClickableTextEdit()
        console.setObjectName("Console")
        console.setReadOnly(True)
        console.copied.connect(lambda: self.toast("Logs copied", "success"))
        return console

    def _automatic_update_check(self):
        """Check once per local day, including a missed midnight after sleep."""
        if not getattr(self, "startup_complete", True):
            return
        if not getattr(self, "shutdown_started", False) and getattr(self, "update_auto_check_enabled", True):
            schedule = getattr(self, "update_schedule", None)
            if schedule is None:
                self.update_schedule = schedule = UpdateSchedule()
            if schedule.is_due(datetime.now().astimezone()):
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
        schedule = getattr(self, "update_schedule", None)
        if schedule is None:
            self.update_schedule = schedule = UpdateSchedule()
        try:
            schedule.record_attempt(datetime.now().astimezone())
        except OSError as exc:
            self.append_log(f"[UPDATE] Could not save daily check: {exc}\n")
        if hasattr(self, "about_update_page"):
            self.about_update_page.set_state("checking")
            self._refresh_update_timestamp()
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
        from source.logs.gachalogs import logger

        logger.info("[UPDATE] %s check requested.", "Automatic" if automatic else "Manual")
        try:
            result = check_for_update()
        except Exception as exc:
            logger.exception("[UPDATE] Unexpected check failure.")
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
        page = getattr(self, "about_update_page", None)
        if page is not None:
            page.set_state("error" if result.error else "available" if result.update_available else "current", result.error)
            self.update_current_label.setText(f"Version {result.current.version}")
        action = getattr(self, "update_action_button", None)
        status = getattr(self, "update_status_label", None)
        changelog = getattr(self, "update_changelog_label", None)
        if result.error:
            if status is not None:
                status.show()
                status.setText("UPDATE CHECK FAILED")
            if changelog is not None and page is None:
                self._set_update_notes(f"{result.error}\n\nDetails: check logs file")
            if action is not None:
                action.setText("CHECK FOR UPDATE")
                action.setEnabled(True)
            if automatic:
                self.toast(result.error, "error")
            return

        # latest_label = ("UPDATE AVAILABLE" if result.update_available else "NEWEST VERSION")
        if status is not None:
            # status.setText(f"{latest_label}\nVersion: {result.latest.version}")
            if result.update_available:
                status.show()
                status.setText("UPDATE AVAILABLE" if page is not None else f"UPDATE AVAILABLE\nVersion: {result.latest.version}")
            else:
                status.show()
                status.setText("You're up to date!")
        if changelog is not None:
            manifest = result.latest if result.update_available else result.current
            page.set_manifest(manifest) if page is not None else self._set_update_notes(self._format_manifest_notes(manifest))
        if action is not None:
            action.setText("UPDATE" if result.update_available else "CHECK FOR UPDATE")
            action.setEnabled(True)

        # ruff: disable[SIM102]
        if automatic and result.update_available:
            if self.confirm(
                "Update Available",
                f"Version {result.latest.version} is available. Update now?",
                "UPDATE",
            ):
                self._request_update_restart()

    def _handle_update_action(self):
        """Check for updates or begin the restart flow for an available update."""
        if getattr(self, "update_available", False):
            self._request_update_restart()
        else:
            self._start_update_check()

    def _request_update_restart(self):
        """Ask the Python entry point to restart after launcher cleanup completes."""
        try:
            (REPOSITORY_ROOT / ".update_restart.request").write_text("restart\n", encoding="utf-8")
        except OSError as exc:
            self.dialog("Update Restart Failed", str(exc), "error")
            return
        self._shutdown_resources()
        self.close()

    def _about_page(self):
        """Build the combined page without scheduling a navigation-triggered check."""
        manifest = None
        error = ""
        try:
            manifest = load_manifest()
            version = manifest.version
        except ValueError as exc:
            version = APP_VERSION.lstrip("vV")
            error = f"Unable to load local manifest: {exc}"
        page = CombinedAboutPage(version, self._handle_update_action, self._open_official_website)
        self.about_update_page = page
        self.update_current_label = page.version
        self.update_status_label = page.status
        self.update_action_button = page.action
        self.update_changelog_label = page.notes
        page.set_manifest(manifest)
        if error:
            page.status.setText("Unable to read release information")
            page.set_state("error", error)
        if not hasattr(self, "update_schedule"):
            self.update_schedule = UpdateSchedule()
        self._refresh_update_timestamp()
        return page

    def _refresh_update_timestamp(self):
        """Display the persisted attempt timestamp without claiming a cached success."""
        page = getattr(self, "about_update_page", None)
        if page is not None:
            stamp = getattr(getattr(self, "update_schedule", None), "last_timestamp", None)
            page.last_checked.setText("Last checked: " + (stamp.strftime("%Y-%m-%d %H:%M") if stamp else "Never"))

    def _open_official_website(self):
        """Use the configured official URL or the requested temporary message."""
        url = launcher_constants.OFFICIAL_WEBSITE_URL.strip()
        if url:
            QDesktopServices.openUrl(QUrl(url))
        else:
            self.dialog("Website", "Out of money so no website for now :>", "info")
