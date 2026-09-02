import ctypes
import threading
import time

from source.launcher.config.constants import GAME_WINDOW_TITLE
from source.launcher.utils import system
from source.utility.runner_state import emit_runner_state

POLL_INTERVAL = 1.0
PAUSE_CHECK_INTERVAL = 0.25

_state_lock = threading.Lock()
_paused = False
_pause_reason = ""
_last_pause_check = 0.0


def is_ark_foreground():
    """Return whether the ARK window currently owns foreground focus."""
    hwnd = system.find_window_handle(GAME_WINDOW_TITLE, contains=True)
    return bool(hwnd) and ctypes.windll.user32.GetForegroundWindow() == hwnd


def _set_paused(reason: str):
    global _paused, _pause_reason
    with _state_lock:
        if _paused:
            _pause_reason = reason
            return
        _paused = True
        _pause_reason = reason
    emit_runner_state("PAUSED")


def _set_running():
    global _paused, _pause_reason
    with _state_lock:
        if not _paused:
            return
        _paused = False
        _pause_reason = ""
    emit_runner_state("RUNNING")


def _pause_menu_is_visible():
    """Check the ARK pause menu only after ARK has foreground focus."""
    from source.join_sim.source import main

    return main.is_pause_menu()


def wait_until_ready():
    """Wait until ARK is focused and its pause menu is closed.

    The foreground check is deliberately performed before any screenshot-based
    check, so another window cannot be mistaken for an ARK menu.
    """
    global _last_pause_check

    while True:
        if not is_ark_foreground():
            _set_paused("FOCUS")
            time.sleep(POLL_INTERVAL)
            continue

        now = time.monotonic()
        if now - _last_pause_check >= PAUSE_CHECK_INTERVAL:
            _last_pause_check = now
            if _pause_menu_is_visible():
                _set_paused("MENU")
                time.sleep(POLL_INTERVAL)
                continue

        _set_running()
        return
