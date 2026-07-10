import time

import source.gacha_bot.config
from source.ASA.player import player_inventory
from source.ASA.strucutres import inventory
from source.logs import gachalogs as logs
from source.utility import utils, utils_simple
from source.utility.debug_screenshots import (
    CAPTURE_GACHA_OVERCAP,
    CAPTURE_GACHA_SEED,
    capture_for,
)

capture_gacha_seed_deposit = capture_for(
    "gacha_seed_deposit", active=CAPTURE_GACHA_SEED
)
capture_gacha_overcap_before_drop = capture_for(
    "gacha_overcap_before_drop", active=CAPTURE_GACHA_OVERCAP
)


def open_gacha_inv(teleporter_name: str, direction, turn_constant):
    attempt = 0
    dl = utils_simple.get_default_clock()
    while not inventory.is_open():
        inventory.open()
        attempt += 1
        logs.logger.debug(
            f"the {direction} gacha at {teleporter_name} could not be accessed retrying {attempt} / {source.gacha_bot.config.gacha_attempts}"
        )

        if inventory.is_open():
            return

        utils.zero_center()
        utils.turn_right(40 * turn_constant)
        time.sleep(0.2)

        if dl():
            logs.logger.error(
                f"the {direction} gacha at {teleporter_name} could not be accesssed after {attempt} attempts"
            )
            break


def drop_off_nocrop(
    teleporter_name: str, direction: str
):  # change reberry time or you will run out of crops
    turn_constant = 1 if direction == "right" else -1

    utils.turn_right(40 * turn_constant)
    time.sleep(0.2)

    open_gacha_inv(teleporter_name, direction, turn_constant)
    if inventory.is_open():
        _drop_off_nocrop(teleporter_name, direction)
        inventory.close()

        # Ensure process
        open_gacha_inv(teleporter_name, direction, turn_constant)
        if inventory.was_server_lag_last_open and inventory.is_open():
            # Server lagged, need redoing
            time.sleep(1)
            _drop_off_nocrop(teleporter_name, direction)

        player_inventory.transfer_all_inventory()
        capture_gacha_seed_deposit(f"{teleporter_name}_{direction}")
    inventory.close()


def _drop_off_nocrop(teleporter_name: str, direction):
    inventory.search_in_object("pell")
    inventory.transfer_all_from()
    inventory.wait_clear_search()

    capture_gacha_overcap_before_drop(f"{teleporter_name}_{direction}")
    time.sleep(0.1)
    inventory.drop_all_obj()
