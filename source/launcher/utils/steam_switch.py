import ctypes
import time
from pathlib import Path
from typing import Callable

from source.launcher import ark_game_setup
from source.launcher.config.transfer_helper_config import player_steam_account
from source.launcher.utils import steam_accounts
from source.utility import utils

STEAM_SIGN_IN_WINDOW_TITLE = "Sign in to Steam"
STEAM_WINDOW_POLL_SECONDS = 0.1


def switch_steam_account(
    target_account: int,
    current_steam_account: str,
    players: dict[str, object],
    ui_coords: dict[str, object],
    status_callback: Callable[[str], object] | None = None,
    *,
    force_restart: bool = False,
    loginusers: Path | None = None,
    steam_restart_interval: int = 30,
) -> str:
    """Select an account and retry until Steam is visible and maximized."""

    target_steam_account = player_steam_account(players, target_account)
    if not target_steam_account:
        raise RuntimeError(f"Player {target_account} has no Steam account assigned.")
    if target_steam_account == current_steam_account and not force_restart:
        return current_steam_account

    readiness_seconds = int(steam_restart_interval)
    if readiness_seconds < 1:
        raise ValueError("steam_restart_interval must be at least 1.")
    emit = status_callback or (lambda _message: None)

    if target_steam_account == current_steam_account:
        emit(f"Restarting Steam with account {target_steam_account}.")
    else:
        emit(f"Switching Steam account to {target_steam_account}.")
    emit("Closing ARK before restarting Steam.")

    utils.close_ark_with_console_exit()

    ark_game_setup.kill_running_ark()

    if loginusers is None:
        steam_accounts.select_auto_login_account(target_steam_account)
    else:
        steam_accounts.select_auto_login_account(target_steam_account, loginusers)
    steam_accounts.close_steam()

    steam_config = ui_coords.get("steam", {})
    restart_delay = 8
    if isinstance(steam_config, dict):
        restart_delay = steam_config.get("restart_delay", 8)
    time.sleep(float(restart_delay))

    window_title = "Steam"
    if isinstance(steam_config, dict):
        window_title = str(steam_config.get("window_title") or window_title)
    attempt = 1
    while True:
        emit(f"Launching Steam (attempt {attempt}).")
        try:
            steam_accounts.launch_steam()
            if _wait_for_steam_window(window_title, readiness_seconds):
                emit(f"Steam is visible and maximized for {target_steam_account}.")
                return target_steam_account
        except Exception as exc:
            emit(f"Steam launch attempt {attempt} failed: {exc}")

        emit(
            "Steam was not visible and maximized within "
            f"{readiness_seconds} seconds; restarting (attempt {attempt + 1})."
        )
        ark_game_setup.kill_running_ark()
        steam_accounts.close_steam()
        time.sleep(float(restart_delay))
        attempt += 1


def _wait_for_steam_window(window_title: str, timeout_seconds: int) -> bool:
    """Wait for sign-in to finish before accepting the main Steam window."""
    deadline = time.monotonic() + timeout_seconds
    sign_in_was_visible = False
    while time.monotonic() < deadline:
        if _is_window_visible(STEAM_SIGN_IN_WINDOW_TITLE):
            sign_in_was_visible = True
        elif sign_in_was_visible and _show_and_confirm_maximized(window_title):
            return True
        time.sleep(STEAM_WINDOW_POLL_SECONDS)
    return False


def _is_window_visible(window_title: str) -> bool:
    """Return whether an exact-title Windows window exists and is visible."""
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Steam window checks are only available on Windows.")
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, window_title)
    return bool(hwnd and user32.IsWindowVisible(hwnd))


def _show_and_confirm_maximized(window_title: str) -> bool:
    """Show and maximize Steam, then verify both required window states."""
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Steam window checks are only available on Windows.")
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, window_title)
    if not hwnd:
        return False
    if not user32.IsWindowVisible(hwnd):
        return False
    if not user32.IsZoomed(hwnd):
        user32.ShowWindow(hwnd, 3)
    user32.BringWindowToTop(hwnd)
    return bool(user32.IsWindowVisible(hwnd) and user32.IsZoomed(hwnd))
