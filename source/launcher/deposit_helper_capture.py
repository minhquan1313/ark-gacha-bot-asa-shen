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


def register_shift_n_hotkey(hwnd, hotkey_id):
    return bool(ctypes.windll.user32.RegisterHotKey(hwnd, hotkey_id, 0x0004, 0x4E))


def unregister_hotkey(hwnd, hotkey_id):
    ctypes.windll.user32.UnregisterHotKey(hwnd, hotkey_id)
