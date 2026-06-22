import time

import settings
from source.ASA import config
from source.ASA.player import player_state
from source.logs import gachalogs as logs
from source.utility import template, utils, variables, windows

resets = 0  # resets happen when char cannot tp therefore it is a major issue


def is_open():
    return template.check_template("inventory", 0.7)


def is_clear_search():
    return template.check_template_no_bounds("search_player_inv", 0.8)


def wait_clear_search(timeout=2):
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
            return

        # check state of the char before redoing
        if attempts >= config.inventory_open_attempts:
            logs.logger.error("unable to open up the players inventory")
            break
    time.sleep(0.3 * settings.lag_offset)


def close():
    attempts = 0
    while is_open():
        attempts += 1
        logs.logger.debug(
            f"trying to close objects inventory {attempts} / {config.inventory_close_attempts}"
        )
        windows.click(
            variables.get_pixel_loc("close_inv_x"),
            variables.get_pixel_loc("close_inv_y"),
        )
        template.template_await_false(template.check_template, 2, "inventory", 0.7)

        if attempts >= config.inventory_close_attempts:
            logs.logger.error(
                f"unable to close the objects inventory after {attempts} attempts"
            )
            # check state of the char the reason we can do it now is that the latter should spam click close inv
            break
    time.sleep(0.3 * settings.lag_offset)


# these functions assume that the inventory is already open
def search_in_inventory(item: str):
    if is_open():
        logs.logger.debug(f"searching in inventory for {item}")
        windows.click(
            variables.get_pixel_loc("search_inventory_x"),
            variables.get_pixel_loc("transfer_all_y"),
        )
        utils.ctrl_a()
        time.sleep(0.2 * settings.lag_offset)
        utils.write(item)
        time.sleep(0.3 * settings.lag_offset)


def drop_all_inv():
    if is_open():
        logs.logger.debug("dropping all items from our inventory ")
        time.sleep(0.2 * settings.lag_offset)
        windows.click(
            variables.get_pixel_loc("drop_all_x"),
            variables.get_pixel_loc("transfer_all_y"),
        )
        time.sleep(0.1 * settings.lag_offset)


def transfer_all_inventory():
    if is_open():
        logs.logger.debug("transfering all from our inventory into strucutre")
        windows.click(
            variables.get_pixel_loc("transfer_all_inventory_x"),
            variables.get_pixel_loc("transfer_all_y"),
        )
        time.sleep(0.1 * settings.lag_offset)


def transfer_first_inventory():
    """Transfer the first item in player inv, 2nd item mean the first one, because the 1st slot is always player implant"""

    if is_open():
        logs.logger.debug("transfering first item from our inventory into structure")
        windows.click(
            variables.get_pixel_loc("inv_slot_player_2nd_x"),
            variables.get_pixel_loc("inv_slot_player_first_row_y"),
        )
        time.sleep(0.05)
        windows.click(
            variables.get_pixel_loc("inv_slot_player_2nd_x"),
            variables.get_pixel_loc("inv_slot_player_first_row_y"),
        )
        time.sleep(0.5 * settings.lag_offset)


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
        utils.press_key("ShowMyInventory")
        open()
        close()

        # moving backwards so we dont die on tps and create bags
        for _x in range(30):
            utils.press_key("s")
        open()
        windows.move_mouse(
            variables.get_pixel_loc("implant_eat_x"),
            variables.get_pixel_loc("implant_eat_y"),
        )
        windows.click(
            variables.get_pixel_loc("implant_eat_x"),
            variables.get_pixel_loc("implant_eat_y"),
        )

        time.sleep(10)  # accounting for high ping lag
        utils.press_key("Use")

        if not template.template_await_true(
            template.check_template, 10, "death_regions", 0.7
        ):
            # check state of the char before redoing
            player_state.check_state()

        if attempts >= config.suicide_attempts:
            logs.logger.error("unable to eat player implant")
            break
