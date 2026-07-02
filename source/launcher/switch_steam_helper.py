from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from source.launcher.components.custom_pyside_component import NoWheelComboBox
from source.launcher.components.helper_window import WorkerHelperWindow
from source.launcher.components.widgets import (
    AnimatedButton,
    LoadingSpinner,
    WrappedStatusLabel,
)
from source.launcher.config.constants import HELPER_HEIGHT, HELPER_WIDTH
from source.launcher.utils import steam_accounts


class SwitchSteamHelper(WorkerHelperWindow):
    """Provide account selection and one-shot Steam restart actions."""

    status_changed = Signal(str)
    worker_ready = Signal()
    worker_finished = Signal(str)

    def __init__(self, owner: object) -> None:
        super().__init__(
            owner,
            "SWITCH STEAM",
            HELPER_WIDTH,
            HELPER_HEIGHT,
            route_kind="switch_steam",
            route_index=None,
            hotkey_hint="ALT + N focuses this helper",
            unavailable_hotkey_hint="ALT + N focus hotkey unavailable",
        )
        self.running_hotkey_hint = self.hotkey_hint
        self.loginusers_file: Path | None = None
        self.accounts: list[dict[str, object]] = []
        self.current_account = ""
        self.pending_action = ""
        self.pending_account = ""
        self.switching = False
        self.launcher_start_game_enabled = self._launcher_start_game_is_enabled()
        self._build_ui()
        start_game_signal = getattr(owner, "start_game_enabled_changed", None)
        if start_game_signal is not None:
            start_game_signal.connect(self._sync_start_game_enabled)
        self._register_hotkey()
        self.status_changed.connect(self.status.setText)
        self.worker_ready.connect(self._on_worker_ready)
        self.worker_finished.connect(self._on_worker_finished)
        self._load_initial_accounts()

    def _build_ui(self) -> None:
        """Build the compact account selector and two action controls."""
        self.description = QLabel(
            "Select a Steam account to restart Steam, or switch accounts before "
            "starting ARK. ARK is closed before every Steam restart."
        )
        self.description.setObjectName("MutedCopy")
        self.description.setWordWrap(True)
        self.content_layout.addWidget(self.description)

        self.account_combo = NoWheelComboBox()
        self.account_combo.setObjectName("HelperCombo")
        self.account_combo.currentIndexChanged.connect(self._selection_changed)
        self.content_layout.addWidget(self.account_combo)

        # actions = QHBoxLayout()
        actions = QVBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        self.switch_button = AnimatedButton("SWITCH", "primary")
        self.switch_button.clicked.connect(self.switch_account)
        self.start_game_button = AnimatedButton("START GAME", "secondary")
        self.start_game_button.clicked.connect(self.start_game)
        actions.addWidget(self.switch_button)
        actions.addWidget(self.start_game_button)
        self.content_layout.addLayout(actions)

        self.status_spinner = LoadingSpinner()
        self.status = WrappedStatusLabel("Loading Steam accounts...")
        self.status.setObjectName("HelperStatus")
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(8)
        status_row.addWidget(self.status_spinner)
        status_row.addWidget(self.status, 1)
        self.content_layout.addLayout(status_row)

    def _load_initial_accounts(self) -> None:
        """Resolve the VDF once and select the account marked MostRecent."""
        try:
            self.loginusers_file = steam_accounts.loginusers_path().resolve()
            accounts = steam_accounts.load_steam_accounts(self.loginusers_file)
            current = steam_accounts.most_recent_account_name(accounts)
            self._set_accounts(accounts, current, current)
        except Exception as exc:
            self._show_load_error(exc)

    def _set_accounts(
        self,
        accounts: list[dict[str, object]],
        current: str,
        selected: str,
    ) -> None:
        """Populate account labels while retaining raw account names as item data."""
        self.accounts = accounts
        self.current_account = current
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        selected_index = -1
        for account in accounts:
            name = str(account.get("account_name", "")).strip()
            if not name:
                continue
            label = f"{name} (CURRENT)" if name == current else name
            self.account_combo.addItem(label, name)
            if name == selected:
                selected_index = self.account_combo.count() - 1
        if selected_index < 0 and self.account_combo.count():
            selected_index = 0
        self.account_combo.setCurrentIndex(selected_index)
        self.account_combo.blockSignals(False)
        self._selection_changed()

    def _selected_account(self) -> str:
        """Return the raw account name represented by the combo selection."""
        value = self.account_combo.currentData()
        return str(value).strip() if value is not None else ""

    def _launcher_start_game_is_enabled(self) -> bool:
        """Read the launcher's current START GAME state when available."""
        button = getattr(self.owner, "start_game_button", None)
        return button is None or button.isEnabled()

    def _sync_start_game_enabled(self, enabled: bool) -> None:
        """Mirror launcher availability without overriding worker state."""
        self.launcher_start_game_enabled = bool(enabled)
        valid = bool(self._selected_account())
        self.start_game_button.setEnabled(
            valid and not self.switching and self.launcher_start_game_enabled
        )

    def _selection_changed(self, _index: int = -1) -> None:
        """Update status copy without disabling valid same-account actions."""
        if self.switching:
            return
        selected = self._selected_account()
        valid = bool(selected)
        self.switch_button.setEnabled(valid)
        self.start_game_button.setEnabled(valid and self.launcher_start_game_enabled)
        if not selected:
            self.status.setText("No Steam accounts are available.")
        elif selected == self.current_account:
            self.status.setText(
                f"Current Steam account: {selected}. SWITCH will restart Steam."
            )
        else:
            current = self.current_account or "unknown"
            self.status.setText(f"Ready to switch Steam from {current} to {selected}.")

    def _refresh_before_action(self) -> tuple[str, str] | None:
        """Re-read the stored VDF and validate the selected account before acting."""
        selected = self._selected_account()
        if self.loginusers_file is None or not selected:
            self.status.setText("Steam account information is unavailable.")
            return None
        try:
            accounts = steam_accounts.load_steam_accounts(self.loginusers_file)
            names = {str(account.get("account_name", "")) for account in accounts}
            if selected not in names:
                raise RuntimeError(
                    f"Steam account is no longer present in loginusers.vdf: {selected}"
                )
            current = steam_accounts.most_recent_account_name(accounts)
            self._set_accounts(accounts, current, selected)
            return selected, current
        except Exception as exc:
            self.status.setText(f"Cannot read Steam accounts: {exc}")
            return None

    def switch_account(self) -> None:
        """Force a Steam restart for the selected account."""
        state = self._refresh_before_action()
        if state is not None:
            self._start_switch(state[0], "switch")

    def start_game(self) -> None:
        """Start ARK directly or switch accounts first when required."""
        state = self._refresh_before_action()
        if state is None:
            return
        selected, current = state
        if selected == current:
            self.owner.start_game()
            return
        self._start_switch(selected, "start_game")

    def _start_switch(self, account: str, action: str) -> None:
        """Start the one-shot account switch worker and lock helper controls."""
        if self.switching or self.loginusers_file is None:
            return
        self.switching = True
        self.pending_action = action
        self.pending_account = account
        self.status_spinner.start()
        self.account_combo.setEnabled(False)
        self.switch_button.setEnabled(False)
        self.start_game_button.setEnabled(False)
        self.status.setText(f"Loading Steam switch modules for {account}...")
        try:
            self._start_worker(
                "switch_steam",
                "--account",
                account,
                "--loginusers",
                str(self.loginusers_file),
            )
        except Exception as exc:
            self._restore_after_worker()
            self.status.setText(f"Cannot switch Steam account: {exc}")

    def _active_button(self) -> AnimatedButton:
        """Return the action button that initiated the current worker."""
        if self.pending_action == "start_game":
            return self.start_game_button
        return self.switch_button

    def handle_hotkey(self) -> None:
        """Keep the global helper hotkey focus-only for destructive actions."""
        self.refocus_helper()

    def _on_worker_ready(self) -> None:
        """Report that imports and runtime validation completed."""
        if self.switching:
            self.status_spinner.stop()
            self.status.setText(f"Restarting Steam as {self.pending_account}...")

    def _on_worker_finished(self, message: str) -> None:
        """Restore controls and optionally continue into the launcher game flow."""
        account = self.pending_account
        start_game_after = self.pending_action == "start_game"
        succeeded = message == f"Steam restarted for {account}."
        if self._finish_worker():
            return
        self._restore_after_worker()
        if not succeeded:
            self.status.setText(message)
            return

        self.current_account = account
        self._set_accounts(self.accounts, account, account)
        self.status.setText(f"Steam restarted for {account}.")
        if start_game_after:
            self.start_game_button.setEnabled(False)
            QTimer.singleShot(0, self.owner.start_game)

    def _restore_after_worker(self) -> None:
        """Stop loading animation and restore idle interaction state."""
        self.status_spinner.stop()
        self.switching = False
        self.pending_action = ""
        self.pending_account = ""
        self.account_combo.setEnabled(True)
        valid = bool(self._selected_account())
        self.switch_button.setEnabled(valid)
        self.start_game_button.setEnabled(valid and self.launcher_start_game_enabled)

    def _show_load_error(self, exc: Exception) -> None:
        """Expose account discovery failures through status text only."""
        self.account_combo.setEnabled(False)
        self.switch_button.setEnabled(False)
        self.start_game_button.setEnabled(False)
        self.status.setText(f"Cannot load Steam accounts: {exc}")
