import ctypes
from ctypes import wintypes

from source.launcher.constants import (
    GAME_WINDOW_TITLE,
    SUPPORTED_GAME_RESOLUTIONS,
)


class MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def find_window_size(window_title):
    hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
    if not hwnd:
        return None

    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None

    return rect.right - rect.left, rect.bottom - rect.top


def focus_window_if_needed(window_title, center_cursor_when_switching=False):
    hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
    if not hwnd:
        return False
    if ctypes.windll.user32.GetForegroundWindow() == hwnd:
        return True

    ctypes.windll.user32.ShowWindow(hwnd, 9)
    if center_cursor_when_switching:
        rect = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise RuntimeError(f"Unable to read {window_title} window position.")
        center_x = (rect.left + rect.right) // 2
        center_y = (rect.top + rect.bottom) // 2
        if not ctypes.windll.user32.SetCursorPos(center_x, center_y):
            raise RuntimeError("Unable to center the mouse cursor.")
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    return True


def validate_ark_window():
    game_size = find_window_size(GAME_WINDOW_TITLE)
    if game_size is None:
        raise RuntimeError(f"{GAME_WINDOW_TITLE} window was not found.")
    if game_size not in SUPPORTED_GAME_RESOLUTIONS:
        raise RuntimeError(
            f"Detected {GAME_WINDOW_TITLE} size: {game_size[0]}x{game_size[1]}. "
            f"{GAME_WINDOW_TITLE} must run at 1920x1080."
        )
    return game_size


def get_memory_usage_gb():
    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None

    used = status.ullTotalPhys - status.ullAvailPhys
    return used / (1024**3), status.ullTotalPhys / (1024**3)


def _filetime_to_int(filetime):
    return (filetime.dwHighDateTime << 32) + filetime.dwLowDateTime


def get_cpu_times():
    idle = wintypes.FILETIME()
    kernel = wintypes.FILETIME()
    user = wintypes.FILETIME()

    if not ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
    ):
        return None

    return _filetime_to_int(idle), _filetime_to_int(kernel), _filetime_to_int(user)


def calculate_cpu_percent(previous_times, current_times):
    if not previous_times or not current_times:
        return None

    previous_idle, previous_kernel, previous_user = previous_times
    current_idle, current_kernel, current_user = current_times

    idle_delta = current_idle - previous_idle
    kernel_delta = current_kernel - previous_kernel
    user_delta = current_user - previous_user
    total_delta = kernel_delta + user_delta

    if total_delta <= 0:
        return None

    return max(0.0, min(100.0, 100.0 * (total_delta - idle_delta) / total_delta))
