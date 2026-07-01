import ctypes
import time

from source.launcher.config.constants import GAME_WINDOW_TITLE
from source.launcher.utils import system

MOD_ALT = 0x0001
MOD_SHIFT = 0x0004
KEY_N = 0x4E


def focus_game_window(
    window_title=GAME_WINDOW_TITLE, center_cursor_when_switching=False
):
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Window focusing is only available on Windows.")
    if window_title == GAME_WINDOW_TITLE:
        system.validate_ark_window()
    if not system.focus_window_if_needed(window_title, center_cursor_when_switching):
        raise RuntimeError(f"{window_title} window was not found.")
    time.sleep(0.15)


def capture_ccc_yaw_pitch():
    focus_game_window()
    try:
        from source.ASA.player import console
    except Exception as exc:
        raise RuntimeError(
            f"Unable to load existing console capture flow: {exc}"
        ) from exc

    data = console.console_ccc(reset_state_before_capture=False)
    if data is None:
        raise RuntimeError("CCC did not return clipboard data.")

    return parse_ccc_yaw_pitch(data)


def view_yaw_pitch(yaw, pitch):
    focus_game_window()
    from source.utility import utils

    utils.get_yaw_pitch()
    utils.turn_to(float(yaw), float(pitch))


def view_yaw(yaw):
    view_yaw_pitch(yaw, 0.0)


def view_route_entry(yaw, pitch, crouched):
    focus_game_window()
    from source.ASA.player import player_state
    from source.utility import utils

    utils.get_yaw_pitch()
    player_state.human.reset_crouch()
    utils.turn_to(float(yaw), float(pitch))
    if crouched:
        player_state.human.crouch()


def preload_capture_view_dependencies():
    try:
        system.validate_ark_window()
    except RuntimeError:
        return None

    from source.ASA.player import console, player_state
    from source.utility import utils

    return console, player_state, utils


def parse_ccc_yaw_pitch(data):
    values = data if isinstance(data, (list, tuple)) else str(data).strip().split()
    if len(values) < 5:
        raise RuntimeError(f"Unable to parse ccc clipboard data: {' '.join(values)}")

    try:
        return float(values[3]), float(values[4])
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid yaw/pitch in ccc clipboard data: {' '.join(values)}"
        ) from exc


def register_alt_n_hotkey(hwnd, hotkey_id):
    return bool(ctypes.windll.user32.RegisterHotKey(hwnd, hotkey_id, MOD_ALT, KEY_N))


def register_shift_alt_n_hotkey(hwnd, hotkey_id):
    return bool(
        ctypes.windll.user32.RegisterHotKey(hwnd, hotkey_id, MOD_ALT | MOD_SHIFT, KEY_N)
    )


def unregister_hotkey(hwnd, hotkey_id):
    ctypes.windll.user32.UnregisterHotKey(hwnd, hotkey_id)
