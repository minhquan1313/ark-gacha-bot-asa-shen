import ctypes
import time
from ctypes import wintypes

try:
    import pyautogui
except ImportError:
    pyautogui = None

from PySide6.QtWidgets import QApplication

from source.launcher.constants import GAME_WINDOW_TITLE


def focus_game_window(window_title=GAME_WINDOW_TITLE):
    hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
    if not hwnd:
        raise RuntimeError(f"{window_title} window was not found.")
    ctypes.windll.user32.ShowWindow(hwnd, 9)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)


def capture_ccc_yaw_pitch():
    if pyautogui is None:
        raise RuntimeError("pyautogui is required to capture yaw/pitch.")

    focus_game_window()
    console_key = _console_key()
    clipboard = QApplication.clipboard()
    clipboard.setText("ccc")

    pyautogui.press(_pyautogui_key(console_key))
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.05)
    pyautogui.press("enter")
    time.sleep(0.25)

    data = clipboard.text().strip()
    values = data.split()
    if len(values) < 5:
        raise RuntimeError(f"Unable to parse ccc clipboard data: {data}")

    try:
        return float(values[3]), float(values[4])
    except ValueError as exc:
        raise RuntimeError(f"Invalid yaw/pitch in ccc clipboard data: {data}") from exc


def register_shift_n_hotkey(hwnd, hotkey_id):
    return bool(ctypes.windll.user32.RegisterHotKey(hwnd, hotkey_id, 0x0004, 0x4E))


def unregister_hotkey(hwnd, hotkey_id):
    ctypes.windll.user32.UnregisterHotKey(hwnd, hotkey_id)


def _console_key():
    try:
        from source.utility import local_player

        key = local_player.get_input_settings("ConsoleKeys")
        if key:
            return key.lower()
    except BaseException:
        pass
    return "tilde"


def _pyautogui_key(key):
    mapping = {
        "tilde": "`",
        "consolekeys": "`",
        "leftshift": "shift",
        "leftcontrol": "ctrl",
        "leftctrl": "ctrl",
        "return": "enter",
        "spacebar": "space",
    }
    return mapping.get(str(key).lower(), str(key).lower())
