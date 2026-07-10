import time

import source.ASA.config
from source.ASA.player import player_state
from source.logs import gachalogs as logs
from source.utility import template, utils, variables, windows


def is_open():
    return template.check_template_no_bounds("tribelog_check", 0.8)


def open(overwrite_amount=0):
    attempts = 0
    logs.logger.debug("trying to open up the tribelog screen")
    while not is_open():
        attempts += 1
        utils.press_key("ShowTribeManager")
        time.sleep(0.1)
        if (
            attempts >= source.ASA.config.tribelog_open_attempts
            if overwrite_amount == 0
            else overwrite_amount + 1
        ):
            logs.logger.warning(f"tribelogs didnt open in {attempts} attempts")
            break


def close():
    attempts = 0
    while is_open():
        attempts += 1
        logs.logger.debug(
            f"trying to close out of the tribelog screen {attempts} / {source.ASA.config.tribelog_close_attempts} "
        )
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
