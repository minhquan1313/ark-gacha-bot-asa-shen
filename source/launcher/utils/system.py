import ctypes
import time
from ctypes import wintypes
from typing import cast

from source.launcher.config.constants import (
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


def find_window_handle(window_title: str, contains: bool = False):
    """Return the first visible window matching a title.

    Example: find_window_handle("ArkAscended", contains=True)
    """
    user32 = ctypes.windll.user32
    if not contains:
        return cast(int, user32.FindWindowW(None, window_title))

    hwnd: int = user32.FindWindowW(None, window_title)
    if hwnd:
        return hwnd
    if not all(
        hasattr(user32, name)
        for name in (
            "EnumWindows",
            "GetWindowTextLengthW",
            "GetWindowTextW",
            "IsWindowVisible",
        )
    ):
        return 0

    needle = window_title.casefold()
    matched_hwnd = 0

    enum_windows_proc = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
    )

    def callback(hwnd, _lparam):
        nonlocal matched_hwnd
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        if needle in buffer.value.casefold():
            matched_hwnd = hwnd
            return False
        return True

    user32.EnumWindows(enum_windows_proc(callback), 0)
    return matched_hwnd


def _should_match_window_title_contains(window_title: str):
    return window_title == GAME_WINDOW_TITLE


def find_window_size(window_title):
    hwnd = find_window_handle(
        window_title, contains=_should_match_window_title_contains(window_title)
    )
    if not hwnd:
        return None

    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None

    return rect.right - rect.left, rect.bottom - rect.top


def focus_window_if_needed(
    window_title: str, center_cursor_when_switching: bool = False
):
    """Activate a window with bounded retries and verify foreground ownership."""
    user32 = ctypes.windll.user32
    hwnd = find_window_handle(
        window_title, contains=_should_match_window_title_contains(window_title)
    )
    if not hwnd:
        return False
    foreground_hwnd = user32.GetForegroundWindow()
    if foreground_hwnd == hwnd:
        return True

    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
    if center_cursor_when_switching:
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise RuntimeError(f"Unable to read {window_title} window position.")
        if not user32.SetCursorPos(
            (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2
        ):
            raise RuntimeError("Unable to center the mouse cursor.")

    kernel32 = ctypes.windll.kernel32
    current_thread_id = kernel32.GetCurrentThreadId()
    attachment_error = 0
    # Try normal activation first. Later attempts use a fresh foreground thread,
    # since launchers and transient windows can disappear during a focus switch.
    for attempt in range(3):
        attached = False
        foreground_thread_id = 0
        try:
            if attempt:
                hwnd = find_window_handle(
                    window_title,
                    contains=_should_match_window_title_contains(window_title),
                )
                if not hwnd:
                    return False
                foreground_hwnd = user32.GetForegroundWindow()
                if foreground_hwnd == hwnd:
                    return True
                foreground_thread_id = user32.GetWindowThreadProcessId(
                    foreground_hwnd, None
                )
                if foreground_thread_id and foreground_thread_id != current_thread_id:
                    attached = bool(
                        user32.AttachThreadInput(
                            current_thread_id, foreground_thread_id, True
                        )
                    )
                    if not attached:
                        attachment_error = kernel32.GetLastError()
                if user32.IsIconic(hwnd):
                    user32.ShowWindow(hwnd, 9)

            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            # The observed foreground window is authoritative, even when an API
            # reports failure or activation completes asynchronously.
            deadline = time.monotonic() + 0.25
            while user32.GetForegroundWindow() != hwnd:
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.01)
            else:
                return True
        finally:
            if attached:
                user32.AttachThreadInput(current_thread_id, foreground_thread_id, False)
        if attempt < 2:
            time.sleep(0.1)

    foreground_hwnd = user32.GetForegroundWindow()
    foreground_pid = wintypes.DWORD()
    foreground_thread_id = user32.GetWindowThreadProcessId(
        foreground_hwnd, ctypes.byref(foreground_pid)
    )
    foreground_title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(foreground_hwnd, foreground_title, len(foreground_title))
    raise RuntimeError(
        f"Unable to focus {window_title} window after 3 attempts; "
        f"target HWND={hwnd}, foreground HWND={foreground_hwnd}, "
        f"title={foreground_title.value!r}, PID={foreground_pid.value}, "
        f"thread={foreground_thread_id}, current thread={current_thread_id}, "
        f"last AttachThreadInput error={attachment_error}."
    )


def validate_ark_window():
    game_size = find_window_size(GAME_WINDOW_TITLE)
    if game_size is None:
        raise RuntimeError(f"{GAME_WINDOW_TITLE} window was not found.")
    if game_size not in SUPPORTED_GAME_RESOLUTIONS:
        supported_sizes = ", ".join(
            f"{width}x{height}" for width, height in SUPPORTED_GAME_RESOLUTIONS
        )
        raise RuntimeError(
            f"Detected {GAME_WINDOW_TITLE} size: {game_size[0]}x{game_size[1]}. "
            f"{GAME_WINDOW_TITLE} must run at one of: {supported_sizes}."
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
