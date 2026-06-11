import time

import pyautogui

from source.join_sim.source.logs import logger as logs
from source.join_sim.source.utility import recon_utils
from source.utility import windows

buttons = {
    "search_x": 1672,
    "search_y": 195,
    "first_server_x": 1672,
    "first_server_y": 328,
    "join_x": 1672,
    "join_y": 945,
    "refresh_x": 930,
    "refresh_y": 937,
    "back_x": 172,
    "back_y": 885,
    "cancel_x": 1069,
    "cancel_y": 727,
    "red_okay_x": 952,
    "red_okay_y": 660,
    "mod_join_x": 525,
    "mod_join_y": 937,
}


def get_pixel_loc(location):
    return buttons.get(location)


def is_server_full():
    return recon_utils.check_template_no_bounds("server_full", 0.7)


def is_red_fail():
    return recon_utils.check_template_no_bounds("red_fail", 0.7)


def no_sessions():
    return recon_utils.check_template_no_bounds("no_session", 0.7)


def has_failure():
    if is_server_full():
        logs.logger.debug("server full")
        windows.click(get_pixel_loc("cancel_x"), get_pixel_loc("cancel_y"))
        recon_utils.window_still_open_no_bounds("server_full", 0.7, 2)
        time.sleep(1)
        windows.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))

    if is_red_fail():
        logs.logger.debug("red fail")
        time.sleep(1)
        pyautogui.click(get_pixel_loc("red_okay_x"), get_pixel_loc("red_okay_y"))
        recon_utils.window_still_open_no_bounds("red_fail", 0.7, 2)
        time.sleep(1)
        pyautogui.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))

    if no_sessions():
        logs.logger.debug("no sessions found")
        time.sleep(1)
        pyautogui.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))
        time.sleep(1)
