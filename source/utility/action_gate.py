import threading
import time
from contextlib import contextmanager

from source.utility import ark_runtime

ACTION_CHECK_INTERVAL = 0.25
_state = threading.local()
_check_lock = threading.Lock()
_last_check = 0.0


def before_ark_action():
    """Check the ARK state before sending a new game input event."""
    global _last_check

    if getattr(_state, "recovery_depth", 0):
        return

    ark_runtime.wait_until_ready()

    now = time.monotonic()
    with _check_lock:
        if now - _last_check < ACTION_CHECK_INTERVAL:
            return
        _last_check = now

    _state.recovery_depth = getattr(_state, "recovery_depth", 0) + 1
    try:
        from source.ASA.player import player_state

        player_state.check_disconnected()
    finally:
        _state.recovery_depth -= 1


@contextmanager
def recovery_scope():
    """Allow recovery input without recursively invoking the action gate."""
    _state.recovery_depth = getattr(_state, "recovery_depth", 0) + 1
    try:
        yield
    finally:
        _state.recovery_depth -= 1
