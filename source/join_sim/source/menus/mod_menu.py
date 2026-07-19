import pyautogui

from source.join_sim.source.logs import logger as logs
from source.join_sim.source.utility import recon_utils

buttons = {"mod_join_x": 525, "mod_join_y": 937}


def get_pixel_loc(location):
    return buttons.get(location)


def is_loading():
    return recon_utils.check_template_no_bounds("req_mods_loading", 0.7)


def is_open():
    return recon_utils.check_template_no_bounds("req_mods", 0.7)


def mod_menu_join():
    if is_open():
        logs.logger.debug("mod menu click")
        pyautogui.click(get_pixel_loc("mod_join_x"), get_pixel_loc("mod_join_y"))
        recon_utils.window_still_open_no_bounds("req_mods", 0.7, 1)
        return True
    return False
