import contextlib
import ctypes
import threading
import time

from source.launcher.config.constants import GAME_WINDOW_TITLE
from source.launcher.utils import system
from source.utility import utils_simple
from source.utility.runner_state import emit_runner_state

POLL_INTERVAL = 1.0
PAUSE_CHECK_INTERVAL = 0.25

STARTED = time.monotonic()
_state_lock = threading.Lock()
_paused = False
_pause_reason = ""
_pause_started = 0.0
_last_pause_check = 0.0
_should_pause = True


@contextlib.contextmanager
def temporary_disable():
    """Skip runtime pause checks within the block, restoring the previous setting."""
    global _should_pause
    previous = _should_pause
    _should_pause = False
    try:
        yield
    finally:
        _should_pause = previous


def is_ark_foreground():
    """Return whether the ARK window currently owns foreground focus."""
    hwnd = system.find_window_handle(GAME_WINDOW_TITLE, contains=True)
    return bool(hwnd) and ctypes.windll.user32.GetForegroundWindow() == hwnd


def is_ark_window_open():
    """Return whether ARK still has a window that can be paused."""
    return bool(system.find_window_handle(GAME_WINDOW_TITLE, contains=True))


def _set_paused(reason: str):
    global _paused, _pause_reason, _pause_started
    with _state_lock:
        if _paused:
            _pause_reason = reason
            return
        _pause_started = time.monotonic()
        _paused = True
        _pause_reason = reason
    emit_runner_state("PAUSED")


def _set_running():
    global _paused, _pause_reason, _pause_started
    with _state_lock:
        if not _paused:
            return
        utils_simple.adjust_clocks_after_pause(_pause_started, time.monotonic())
        _paused = False
        _pause_reason = ""
        _pause_started = 0.0
    emit_runner_state("RUNNING")


def _pause_menu_is_visible():
    """Check the ARK pause menu only after ARK has foreground focus."""
    from source.join_sim.source import main

    return main.is_pause_menu()


def wait_until_ready():
    """Wait while an existing ARK window is unfocused or paused.

    The foreground check is deliberately performed before any screenshot-based
    check, so another window cannot be mistaken for an ARK menu. If ARK has
    closed, explicit disconnect recovery is responsible for restoring it.
    """
    global _last_pause_check

    if time.monotonic() - STARTED < 1:
        return

    while _should_pause:
        if not is_ark_window_open():
            _set_running()
            return

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
