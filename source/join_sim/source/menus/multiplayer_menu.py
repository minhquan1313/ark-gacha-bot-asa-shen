import time

from source.join_sim.source.logs import logger as logs
from source.join_sim.source.utility import recon_utils
from source.utility import utils, windows

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


def is_open():
    return recon_utils.check_template_no_bounds("multiplayer", 0.7)


def clear_search():
    return recon_utils.check_template_no_bounds("search", 0.7)


def wait_clear_search(delay=0.1):
    return recon_utils.template_await_false(
        recon_utils.check_template_no_bounds, delay, "search", 0.7
    )


def is_server_list_loaded():
    return recon_utils.check_template_no_bounds("server_list_loaded", 0.7)


def wait_server_list_loaded(delay=10):
    return recon_utils.template_await_true(
        recon_utils.check_template_no_bounds, delay, "server_list_loaded", 0.7
    )


def mod_menu():
    return recon_utils.check_template_no_bounds("req_mods", 0.7)


def join_button():
    return recon_utils.check_template_no_bounds("join_button", 0.7)


def search_bar_search(server: str):
    if is_open():
        windows.move_mouse(get_pixel_loc("search_x"), get_pixel_loc("search_y"))
        windows.click(get_pixel_loc("search_x"), get_pixel_loc("search_y"))
        windows.click(get_pixel_loc("search_x"), get_pixel_loc("search_y"))
        time.sleep(0.2)
        utils.ctrl_a()
        time.sleep(0.2)
        utils.write(server)


def exit_menu():
    if is_open():
        windows.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))
        recon_utils.window_still_open_no_bounds("multiplayer", 0.7, 1)


def refresh():
    if is_open():
        windows.click(get_pixel_loc("refresh_x"), get_pixel_loc("refresh_y"))


def join_server(server: str):
    if mod_menu():
        logs.logger.debug("mod menu open waiting")
        return False

    if not is_open():
        return False

    logs.logger.debug("joining server")

    timeout = utils.get_default_clock()
    while is_open() and not is_server_list_loaded() and not timeout():
        if not wait_server_list_loaded(1):
            refresh()
    if not is_server_list_loaded():
        return False

    timeout = utils.timed_out_counter(10)
    while is_open() and clear_search() and not timeout():
        search_bar_search(server)
        wait_clear_search(1)
    if clear_search():
        return False

    wait_server_list_loaded(1)

    windows.click(get_pixel_loc("first_server_x"), get_pixel_loc("first_server_y"))
    time.sleep(0.3)
    if is_open() and join_button():
        windows.click(get_pixel_loc("join_x"), get_pixel_loc("join_y"))
    return True
