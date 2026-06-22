import ctypes
from ctypes import wintypes

import mss
import numpy as np

from source.launcher.config.constants import GAME_WINDOW_TITLE


def find_window_by_title(title):
    return ctypes.windll.user32.FindWindowW(None, title)


def find_screen_size():
    hwnd = find_window_by_title(GAME_WINDOW_TITLE)
    rect = wintypes.RECT()
    if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        height = rect.bottom - rect.top
        width = rect.right - rect.left
        print(f"application size is {width}x{height}")
        return width, height


screen_width, screen_height = find_screen_size()

if (screen_width, screen_height) == (1920, 1080):
    mon = {"top": 0, "left": 0, "width": 1920, "height": 1080}
else:
    print(
        f"{screen_width}x{screen_height} is not a valid screen res it needs to be 1920x1080"
    )
    input("")  # prevents the closing of the window instantly
    exit()


def get_screen_roi(start_x, start_y, width, height):

    region = {"top": start_y, "left": start_x, "width": width, "height": height}
    with mss.mss() as sct:
        screenshot = sct.grab(region)
        return np.array(screenshot)


if __name__ == "__main__":
    pass
