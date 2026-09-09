import time
from contextlib import contextmanager
from typing import Literal

import source.ASA.config
from source.ASA.config import LAGGED_DETECT
from source.ASA.player import player_inventory, player_state
from source.logs import gachalogs as logs
from source.utility import template, utils, utils_simple, variables, windows
from source.utility.types import RoiRegion

inv_slots = {"x": 1245, "y": 280, "distance": 93}

inv_regions: RoiRegion = {
    #
    "start_x": 1202,
    "start_y": 236,
    "width": 600,
    "height": 600,
}


"""
Remember to set this back to false after the long process is done
Otherwise, was_server_lag_last_open will always false if it was once false
"""
_detect_lag_for_long_process = False
was_server_lag_last_open = False
was_server_lag_last_open_long = False
g_last_check_can_drop = False


def is_open():
    return template.check_template("inventory", 0.7)


def is_clear_search():
    return template.check_template_no_bounds("search_object_inv", 0.8)


def is_ready():
    return not template.check_template("waiting_inv", 0.8)


def is_turned_on():
    return not template.check_template("structure_turn_on", 0.8)


def is_can_drop():
    global g_last_check_can_drop

    g_last_check_can_drop = v = bool(template.check_template("inventory_drop", 0.8))
    return v


def turn_on():
    if not is_turned_on():
        coords = template.check_template("structure_turn_on", 0.8)
        if not coords:
            return
        logs.logger.warning("Structure is off, trying to turn it on now...")

        windows.click(*coords)
        time.sleep(0.5)


def wait_clear_search(timeout=1):
    return template.template_await_true(is_clear_search, timeout)


# @contextmanager
# def detect_lag_long_process2(func):
#     global _detect_lag_for_long_process
#     global was_server_lag_last_open_long

#     was_server_lag_last_open_long = False
#     _detect_lag_for_long_process = True

#     is_lagged = utils_simple.get_default_clock(LAGGED_DETECT)
#     func()

#     try:
#         yield is_lagged()
#     finally:
#         _detect_lag_for_long_process = False


@contextmanager
def detect_lag_long_process():
    global _detect_lag_for_long_process
    global was_server_lag_last_open_long

    was_server_lag_last_open_long = False
    _detect_lag_for_long_process = True

    try:
        yield
    finally:
        _detect_lag_for_long_process = False


def open(crouch_if_problem=True):
    global was_server_lag_last_open
    global _detect_lag_for_long_process
    global was_server_lag_last_open_long
    is_lagged = utils_simple.get_default_clock(LAGGED_DETECT)

    attempts = 0
    while not is_open():
        attempts += 1
        logs.logger.debug(
            f"trying to open strucuture inventory {attempts} / {source.ASA.config.inventory_open_attempts}"
        )

        utils.press_key("AccessInventory")
        template.template_await_true(is_open, 3)

        if is_open():
            logs.logger.debug("inventory opened")
            is_still_loading = template.template_await_false(
                template.check_template, 3, "waiting_inv", 0.8
            )
            if is_still_loading:
                dl = utils_simple.get_default_clock()
                while is_open() and not is_ready() and not dl():
                    time.sleep(1)
                    player_state.check_disconnected()
                if is_open() and not is_ready():
                    close()
            time.sleep(0.2)

            was_server_lag_last_open = is_lagged()

            if _detect_lag_for_long_process and not was_server_lag_last_open_long:
                was_server_lag_last_open_long = was_server_lag_last_open

            return  # DONE

        # check state of the char before redoing
        else:
            player_state.check_state(crouch=crouch_if_problem)

        was_server_lag_last_open = True

        if attempts >= source.ASA.config.inventory_open_attempts:
            logs.logger.error("unable to open up the objects inventory")
            break
        time.sleep(0.3)


def close():
    attempts = 0
    while is_open():
        attempts += 1
        logs.logger.debug(
            f"trying to close objects inventory {attempts} / {source.ASA.config.inventory_close_attempts}"
        )
        player_inventory.is_can_transfer_all()
        player_inventory.is_can_drop()

        windows.click(
            variables.get_pixel_loc("close_inv_x"),
            variables.get_pixel_loc("close_inv_y"),
        )
        if not template.template_await_false(is_open, 2):
            return time.sleep(0.3)

        if attempts >= source.ASA.config.inventory_close_attempts:
            logs.logger.error(
                f"unable to close the objects inventory after {attempts} attempts"
            )
            # check state of the char the reason we can do it now is that the latter should spam click close inv
            player_state.check_state()
            break


def search_and_transfer(item: str):
    if is_open():
        search_in_object(item)
        time.sleep(0.1)

        while is_clear_search():
            search_in_object(item)
            time.sleep(0.1)

        transfer_all_from()

        wait_clear_search(3)
        time.sleep(0.1)


# these functions assume that the inventory is already open
def search_in_object(item: str):
    if is_open():
        logs.logger.debug(f"searching in structure/dino for {item}")
        time.sleep(0.2)
        windows.click(
            variables.get_pixel_loc("search_object_x"),
            variables.get_pixel_loc("transfer_all_y"),
        )
        utils.ctrl_a()
        time.sleep(0.2)
        utils.write(item)
        time.sleep(0.2)


def drop_all_obj():
    if is_open():
        logs.logger.debug("dropping all items from object")
        time.sleep(0.2)
        windows.click(
            variables.get_pixel_loc("drop_all_obj_x"),
            variables.get_pixel_loc("transfer_all_y"),
        )
        time.sleep(0.1)


def transfer_all_from():
    if is_open():
        logs.logger.debug("transfering all from object")
        time.sleep(0.2)

        x, y = (
            variables.get_pixel_loc("transfer_all_from_x"),
            variables.get_pixel_loc("transfer_all_y"),
        )

        windows.click(x, y)
        time.sleep(0.1)


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


def craft_item(item: str, count: int = 1, key="a"):
    if is_open():
        # SEARCH-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
        dl: utils_simple.TimedOutCounter = utils_simple.get_default_clock(deadline=3)

        search_in_object(item)
        time.sleep(0.1)
        while is_clear_search() and not dl():
            search_in_object(item)
            time.sleep(0.3)

        if is_clear_search():
            logs.logger.error(f"unable to find {item} in the structure inventory")
            return
        # CRAFT-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
        logs.logger.debug(f"crafting {count} of {item}")

        windows.click(
            inv_slots["x"],
            inv_slots["y"],
        )
        for _ in range(count):
            if player_state.check_disconnected():
                return
            windows.move_mouse(
                inv_slots["x"],
                inv_slots["y"],
            )
            utils.press_key(key)
            if _ + 1 < count:
                time.sleep(0.1)
        windows.move_mouse(
            2,
            2,
        )
        time.sleep(0.1)
