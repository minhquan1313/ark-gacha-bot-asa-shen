from source.join_sim.source.logs import logger as logs
from source.join_sim.source.utility import recon_utils
from source.utility import windows
from source.utility.types import RoiRegion, RoiRegionReconKey

buttons = {"join_game_x": 689, "join_game_y": 532, "back_x": 960, "back_y": 960}

join_game_buttons: list[RoiRegionReconKey] = [
    #
    "join_game",
    "join_game_3_gen1",
    "join_game_4_gen1",
    "join_game_5_gen1",
]
join_game_location: RoiRegion = {
    "start_x": 50,
    "start_y": 300,
    "width": 1777,
    "height": 527,
}

last_join_game_button: RoiRegionReconKey | None = None
registered = False


def register_template_roi():
    global registered
    if registered:
        return

    registered = True

    recon_utils.register_roi(
        {button: join_game_location.copy() for button in join_game_buttons}
    )


def get_pixel_loc(location):
    return buttons.get(location)


def is_open():
    global last_join_game_button
    global join_game_buttons
    global join_game_location

    register_template_roi()

    for button in join_game_buttons:
        if recon_utils.check_template_no_bounds(button, 0.7):
            last_join_game_button = button
            return True

    last_join_game_button = None
    return False


def join_game_coords():
    global last_join_game_button
    if is_open() and last_join_game_button is not None:
        return recon_utils.template_find(last_join_game_button)

    return (0, 0)


def click_join_game():
    if is_open():
        logs.logger.debug("click join game")
        location = join_game_coords()
        windows.click(location[0], location[1])
        recon_utils.window_still_open_no_bounds("join_game", 0.7, 1)
        return True
    return False


def exit_menu():
    if is_open():
        windows.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))
        recon_utils.window_still_open_no_bounds("join_game", 0.7, 1)
