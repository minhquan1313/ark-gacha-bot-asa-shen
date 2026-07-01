import time

import settings
import source.gacha_bot.config
from source.ASA.player import player_inventory
from source.ASA.strucutres import inventory
from source.logs import gachalogs as logs
from source.utility import template, utils, utils_simple
from source.utility.debug_screenshots import CAPTURE_PEGO_CRYSTAL, capture_for

capture_pego_crystal_withdraw = capture_for(
    "pego_crystal_withdraw", active=CAPTURE_PEGO_CRYSTAL
)


def is_crystal_hotbar_visible():
    return template.check_template("crystal_in_hotbar", 0.7)


def pego_pickup(metadata):
    utils.turn_up(15)
    time.sleep(0.2 * settings.lag_offset)

    open(metadata)
    if inventory.is_open():  # prevents pego being FLUNG
        if player_inventory.is_can_drop():
            player_inventory.drop_all_inv()
            time.sleep(0.2 * settings.lag_offset)

            # ENSURE
            inventory.close()
            open(metadata)
            if not inventory.is_open():
                return

        inventory.transfer_all_from()
        time.sleep(0.2 * settings.lag_offset)
        capture_pego_crystal_withdraw(metadata.name)
        inventory.close()

        # ENSURE ALL CRYSTAL IS TRANSFERRED
        # So it won't break the next checking crystals in player hotbar process
        if not template.template_await_true(is_crystal_hotbar_visible, 1):
            open(metadata)
            inventory.close()


def open(metadata):
    inventory.open()

    attempt = 0
    dl = utils_simple.get_default_clock()
    while not inventory.is_open():
        attempt += 1
        logs.logger.debug(
            f"the pego at {metadata.name} could not be accessed retrying {attempt} / {source.gacha_bot.config.pego_attempts}"
        )
        utils.zero_center(metadata.yaw)
        utils.turn_up(15)
        time.sleep(0.2 * settings.lag_offset)
        inventory.open()
        if dl():
            logs.logger.error(
                f"the pego at {metadata.name} could not be accesssed after {attempt} attempts"
            )
            break
