import ctypes
from ctypes import wintypes

import mss
import numpy as np

from source.launcher.config.constants import (
    GAME_WINDOW_TITLE,
    SUPPORTED_GAME_RESOLUTIONS,
)

capture_width, capture_height = SUPPORTED_GAME_RESOLUTIONS[0]
mon = {"top": 0, "left": 0, "width": capture_width, "height": capture_height}


def find_window_by_title(title):
    return ctypes.windll.user32.FindWindowW(None, title)


def find_screen_size() -> tuple[int, int] | None:
    """Return the ARK window size when Windows exposes a valid rectangle."""
    hwnd = find_window_by_title(GAME_WINDOW_TITLE)
    if not hwnd:
        return None

    rect = wintypes.RECT()
    if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        height = rect.bottom - rect.top
        width = rect.right - rect.left
        print(f"application size is {width}x{height}")
        return width, height
    return None


def get_screen_roi(start_x, start_y, width, height):

    region = {"top": start_y, "left": start_x, "width": width, "height": height}
    with mss.mss() as sct:
        screenshot = sct.grab(region)
        return np.array(screenshot)


if __name__ == "__main__":
    pass
