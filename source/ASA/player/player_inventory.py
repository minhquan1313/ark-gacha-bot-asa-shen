import time
from typing import Literal

from source.ASA import config
from source.ASA.player import player_state
from source.logs import gachalogs as logs
from source.utility import template, utils, utils_simple, variables, windows
from source.utility.types import RoiRegion

resets = 0  # resets happen when char cannot tp therefore it is a major issue
inv_slots = {"x": 222, "y": 280, "distance": 93}
g_last_check_can_transfer: bool = False
g_last_check_can_drop: bool = False

inv_regions: RoiRegion = {
    #
    "start_x": 176,
    "start_y": 236,
    "width": 600,
    "height": 600,
}

buttons = {
    "filter_player_inventory": (240, 860),
    "filter_all": (240, 825),
    "filter_resource": (240, 725),
}


def get_pixel_loc(location):
    return buttons.get(location, (0, 0))


def is_open():
    return template.check_template("inventory", 0.7)


def is_clear_search():
    return template.check_template_no_bounds("search_player_inv", 0.8)


def is_can_drop():
    global g_last_check_can_drop

    g_last_check_can_drop = v = bool(
        template.check_template("inventory_player_drop", 0.8)
    )
    return v


def is_can_transfer_all():
    global g_last_check_can_transfer
    g_last_check_can_transfer = v = bool(
        template.check_template("inventory_player_transfer_all", 0.8)
    )
    return v


def wait_clear_search(timeout=1):
    return template.template_await_true(is_clear_search, timeout)


def open():
    attempts = 0
    while not is_open():
        attempts += 1
        logs.logger.debug(
            f"trying to open player inventory {attempts} / {config.inventory_open_attempts}"
        )
        utils.press_key("ShowMyInventory")
        if template.template_await_true(is_open, 3):
            logs.logger.debug("inventory opened")
            time.sleep(0.2)
            return

        # check state of the char before redoing
        if attempts >= config.inventory_open_attempts:
            logs.logger.error("unable to open up the players inventory")
            break
        time.sleep(0.2)


def close():
    attempts = 0
    while is_open():
        attempts += 1
        logs.logger.debug(
            f"trying to close objects inventory {attempts} / {config.inventory_close_attempts}"
        )

        is_can_transfer_all()

        windows.click(
            variables.get_pixel_loc("close_inv_x"),
            variables.get_pixel_loc("close_inv_y"),
        )
        if not template.template_await_false(is_open, 2):
            return time.sleep(0.3)

        if attempts >= config.inventory_close_attempts:
            logs.logger.error(
                f"unable to close the objects inventory after {attempts} attempts"
            )
            # check state of the char the reason we can do it now is that the latter should spam click close inv
            break


# these functions assume that the inventory is already open
def search_in_inventory(item: str):
    if is_open():
        logs.logger.debug(f"searching in inventory for {item}")
        windows.click(
            variables.get_pixel_loc("search_inventory_x"),
            variables.get_pixel_loc("transfer_all_y"),
        )
        utils.ctrl_a()
        time.sleep(0.2)
        utils.write(item)
        time.sleep(0.3)


def drop_all_inv():
    if is_open():
        logs.logger.debug("dropping all items from our inventory ")
        time.sleep(0.2)
        windows.click(
            variables.get_pixel_loc("drop_all_x"),
            variables.get_pixel_loc("transfer_all_y"),
        )
        time.sleep(0.1)


def transfer_all_inventory():
    if is_open():
        logs.logger.debug("transfering all from our inventory into strucutre")
        windows.click(
            variables.get_pixel_loc("transfer_all_inventory_x"),
            variables.get_pixel_loc("transfer_all_y"),
        )
        time.sleep(0.1)


def change_filter(type: Literal["all", "resource"] = "all"):
    if is_open():
        logs.logger.debug("changing filter from our inventory into structure")

        windows.click(
            *get_pixel_loc("filter_player_inventory"),
        )
        time.sleep(0.1)
        coords = get_pixel_loc(f"filter_{type}")
        windows.click(
            *coords,
        )
        time.sleep(0.1)


def transfer_first_inventory(slot=2):
    """Transfer the first item in player inv, 2nd item mean the first one, because the 1st slot is always player implant"""

    if is_open():
        logs.logger.debug("transfering first item from our inventory into structure")

        if slot == 2:
            for _ in range(2):
                windows.click(
                    variables.get_pixel_loc("inv_slot_player_2nd_x"),
                    variables.get_pixel_loc("inv_slot_player_first_row_y"),
                )
                time.sleep(0.05)
        else:
            _slot = max(1, slot)
            inv_default_grid = 6
            loc_gen = utils_simple.grid_loc_gen(col=inv_default_grid)

            c, r = loc_gen(_slot)
            x = inv_slots["x"] + (inv_slots["distance"] * c)
            y = inv_slots["y"] + (inv_slots["distance"] * r)

            for _ in range(2):
                windows.click(x, y)
                time.sleep(0.05)
        time.sleep(0.5)


def popcorn(
    count=0,
    direction: Literal["to right", "to bottom", "to left", "to top"] = "to right",
    *,
    transfer_instead=False,
):
    """Drop or transfer items from inventory slots in the selected direction."""
    inv_default_grid = 6

    loc_gen = utils_simple.grid_loc_gen(row=inv_default_grid)

    if direction in ("to right", "to left"):
        loc_gen = utils_simple.grid_loc_gen(col=inv_default_grid)

    if is_open() and count >= 1:
        for i in range(count):
            c, r = loc_gen(i)

            if direction == "to left":
                c = inv_default_grid - 1 - c
            elif direction == "to top":
                r = inv_default_grid - 1 - r

            time.sleep(0.05)

            x = inv_slots["x"] + (inv_slots["distance"] * c)
            y = inv_slots["y"] + (inv_slots["distance"] * r)

            if not is_open():
                return

            windows.game_move_mouse(x, y)
            windows.click(x, y)
            time.sleep(0.05)

            utils.press_key("DropItem" if not transfer_instead else "TransferItem")


def implant_eat():
    global resets
    resets += 1
    attempts = 0

    player_state.capture_state("implant eat", 5)
    logs.logger.critical("Eating implant", stack_info=True)
    player_state.reset_state()

    while not template.check_template("death_regions", 0.7):
        attempts += 1
        logs.logger.debug(
            f"trying to eat player implant {attempts} / {config.suicide_attempts}"
        )

        utils.zero_center()
        open()
        close()

        # moving backwards so we dont die on tps and create bags
        for _x in range(30):
            utils.press_key("s")

        open()

        time.sleep(0.5)

        windows.game_move_mouse(
            variables.get_pixel_loc("implant_eat_x"),
            variables.get_pixel_loc("implant_eat_y"),
        )
        windows.click(
            variables.get_pixel_loc("implant_eat_x"),
            variables.get_pixel_loc("implant_eat_y"),
        )

        time.sleep(10)  # accounting for high ping lag
        utils.press_key("Use")

        time.sleep(1)
        windows.game_move_mouse(
            variables.get_pixel_loc("close_inv_x"),
            variables.get_pixel_loc("close_inv_y"),
        )

        if not template.template_await_true(
            template.check_template, 10, "death_regions", 0.7
        ):
            # check state of the char before redoing
            player_state.check_state()

        if attempts >= config.suicide_attempts:
            logs.logger.error("unable to eat player implant")
            break
