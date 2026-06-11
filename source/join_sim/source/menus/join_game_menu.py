from source.join_sim.source.logs import logger as logs
from source.join_sim.source.utility import recon_utils
from source.utility import windows

buttons = {"join_game_x": 689, "join_game_y": 532, "back_x": 960, "back_y": 960}


def get_pixel_loc(location):
    return buttons.get(location)


def is_open():
    return recon_utils.check_template_no_bounds("join_game", 0.7)


def click_join_game():
    if is_open():
        logs.logger.debug("click join game")
        location = recon_utils.template_find("join_game")
        windows.click(location[0], location[1])
        recon_utils.window_still_open_no_bounds("join_game", 0.7, 1)


def exit_menu():
    if is_open():
        windows.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))
        recon_utils.window_still_open_no_bounds("join_game", 0.7, 1)
