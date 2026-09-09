import time

from source.join_sim.source.logs import logger as logs
from source.join_sim.source.menus import multiplayer_menu
from source.join_sim.source.utility import recon_utils
from source.utility import ark_input

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
    return recon_utils.check_template_no_bounds(
        "server_full", 0.7
    ) or recon_utils.check_template_no_bounds("server_full_2", 0.7)


def is_red_fail():
    return recon_utils.check_template_no_bounds("red_fail", 0.7)


def no_sessions():
    # If server is island, it might always give true
    # so use this with caution
    return recon_utils.check_template_no_bounds("no_session", 0.7)


def click_go_back():
    ark_input.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))
    time.sleep(0.5)


def has_failure(should_go_back=True):
    any_failed = False
    if is_server_full():
        logs.logger.debug("Server full")

        ark_input.click(get_pixel_loc("cancel_x"), get_pixel_loc("cancel_y"))
        recon_utils.window_still_open_no_bounds("server_full", 0.7, 2)
        time.sleep(0.3)

        if should_go_back:
            click_go_back()
        any_failed = True

    if is_red_fail():
        logs.logger.debug("Red fail")

        ark_input.click(get_pixel_loc("red_okay_x"), get_pixel_loc("red_okay_y"))
        recon_utils.window_still_open_no_bounds("red_fail", 0.7, 2)
        time.sleep(0.3)

        if should_go_back:
            click_go_back()
        any_failed = True

    # if no_sessions():
    #     logs.logger.debug("no sessions found")

    #     time.sleep(1)
    #     click_go_back()
    #     any_failed = True
    #     should_go_back = False

    if should_go_back and multiplayer_menu.is_open():
        time.sleep(1)
        click_go_back()

    return any_failed
