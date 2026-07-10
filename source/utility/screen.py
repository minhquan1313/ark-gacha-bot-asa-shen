import mss
import numpy as np

from source.launcher.config.constants import (
    SUPPORTED_GAME_RESOLUTIONS,
)

capture_width, capture_height = SUPPORTED_GAME_RESOLUTIONS[0]
mon = {"top": 0, "left": 0, "width": capture_width, "height": capture_height}


def get_screen_roi(start_x, start_y, width, height):
    region = {"top": start_y, "left": start_x, "width": width, "height": height}
    with mss.mss() as sct:
        screenshot = sct.grab(region)
        return np.array(screenshot)


if __name__ == "__main__":
    pass
