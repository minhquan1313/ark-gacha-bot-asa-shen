import ctypes
import time

from source.launcher.constants import GAME_WINDOW_TITLE


def focus_game_window(window_title=GAME_WINDOW_TITLE):
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Window focusing is only available on Windows.")
    hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
    if not hwnd:
        raise RuntimeError(f"{window_title} window was not found.")
    ctypes.windll.user32.ShowWindow(hwnd, 9)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)


def capture_ccc_yaw_pitch():
    focus_game_window()
    try:
        from source.ASA.player import console
    except Exception as exc:
        raise RuntimeError(
            f"Unable to load existing console capture flow: {exc}"
        ) from exc

    data = console.console_ccc()
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
    utils.press_key("Run")
    player_state.human.crouched = False
    utils.turn_to(float(yaw), float(pitch))
    if crouched:
        player_state.human.crouch()


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
    return bool(ctypes.windll.user32.RegisterHotKey(hwnd, hotkey_id, 0x0001, 0x4E))


def unregister_hotkey(hwnd, hotkey_id):
    ctypes.windll.user32.UnregisterHotKey(hwnd, hotkey_id)
