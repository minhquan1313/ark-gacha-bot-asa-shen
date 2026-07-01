import time
from contextlib import contextmanager
from typing import Literal

import settings
import source.ASA.config
from source.ASA.player import player_state
from source.logs import gachalogs as logs
from source.utility import template, utils, utils_simple, variables, windows

inv_slots = {"x": 1245, "y": 280, "distance": 93}

"""
Remember to set this back to false after the long process is done
Otherwise, was_server_lag_last_open will always false if it was once false
"""
_detect_lag_for_long_process = False
was_server_lag_last_open = False


def is_open():
    return template.check_template("inventory", 0.7)


def is_clear_search():
    return template.check_template_no_bounds("search_object_inv", 0.8)


def is_ready():
    return not template.check_template("waiting_inv", 0.8)


def is_turned_on():
    return not template.check_template("structure_turn_on", 0.8)


def turn_on():
    if not is_turned_on():
        coords = template.check_template("structure_turn_on", 0.8)
        if not coords:
            return
        logs.logger.warning("Transmitter is off, trying to turn it on now...")

        windows.click(*coords)
        time.sleep(0.5 * settings.lag_offset)


def wait_clear_search(timeout=1):
    return template.template_await_true(is_clear_search, timeout)


@contextmanager
def detect_lag_long_process():
    global _detect_lag_for_long_process

    _detect_lag_for_long_process = True
    try:
        yield
    finally:
        _detect_lag_for_long_process = False


def open():
    global was_server_lag_last_open
    global _detect_lag_for_long_process
    is_lagged = utils_simple.get_default_clock(3)

    attempts = 0
    while not is_open():
        attempts += 1
        logs.logger.debug(
            f"trying to open strucuture inventory {attempts} / {source.ASA.config.inventory_open_attempts}"
        )
        utils.press_key("AccessInventory")
        if template.template_await_true(is_open, 3):
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
            time.sleep(0.2 * settings.lag_offset)

            if not _detect_lag_for_long_process or not was_server_lag_last_open:
                was_server_lag_last_open = is_lagged()

            return  # DONE

        # check state of the char before redoing
        else:
            player_state.check_state()

        was_server_lag_last_open = True

        if attempts >= source.ASA.config.inventory_open_attempts:
            logs.logger.error("unable to open up the objects inventory")
            break
        time.sleep(0.3 * settings.lag_offset)


def close():
    attempts = 0
    while is_open():
        attempts += 1
        logs.logger.debug(
            f"trying to close objects inventory {attempts} / {source.ASA.config.inventory_close_attempts}"
        )
        windows.click(
            variables.get_pixel_loc("close_inv_x"),
            variables.get_pixel_loc("close_inv_y"),
        )
        if not template.template_await_false(is_open, 2):
            return time.sleep(0.3 * settings.lag_offset)

        if attempts >= source.ASA.config.inventory_close_attempts:
            logs.logger.error(
                f"unable to close the objects inventory after {attempts} attempts"
            )
            # check state of the char the reason we can do it now is that the latter should spam click close inv
            player_state.check_state()
            break


# these functions assume that the inventory is already open
def search_in_object(item: str):
    if is_open():
        logs.logger.debug(f"searching in structure/dino for {item}")
        time.sleep(0.2 * settings.lag_offset)
        windows.click(
            variables.get_pixel_loc("search_object_x"),
            variables.get_pixel_loc("transfer_all_y"),
        )
        utils.ctrl_a()
        time.sleep(0.2 * settings.lag_offset)
        utils.write(item)
        time.sleep(0.2 * settings.lag_offset)


def drop_all_obj():
    if is_open():
        logs.logger.debug("dropping all items from object")
        time.sleep(0.2 * settings.lag_offset)
        windows.click(
            variables.get_pixel_loc("drop_all_obj_x"),
            variables.get_pixel_loc("transfer_all_y"),
        )
        time.sleep(0.1 * settings.lag_offset)


def transfer_all_from():
    if is_open():
        logs.logger.debug("transfering all from object")
        time.sleep(0.2 * settings.lag_offset)
        windows.click(
            variables.get_pixel_loc("transfer_all_from_x"),
            variables.get_pixel_loc("transfer_all_y"),
        )
        time.sleep(0.1 * settings.lag_offset)


def popcorn(
    count=0, direction: Literal["left", "down"] = "left", *, transfer_instead=False
):
    loc_gen = (
        utils_simple.grid_loc_gen(row=6)
        if direction == "down"
        else utils_simple.grid_loc_gen(col=6)
    )

    if is_open() and count >= 1:
        for i in range(count):
            c, r = loc_gen(i)

            time.sleep(0.05 * settings.lag_offset)

            x = inv_slots["x"] + (inv_slots["distance"] * c)
            # Y pos = startY + distanceBetweenSlots * i
            y = inv_slots["y"] + (inv_slots["distance"] * r)
            windows.move_mouse(x, y)

            windows.click(x, y)
            time.sleep(0.05 * settings.lag_offset)

            utils.press_key("DropItem" if not transfer_instead else "TransferItem")
        time.sleep(0.1 * settings.lag_offset)
