import time

import settings
import source.gacha_bot.config
from source.ASA.player import player_inventory
from source.ASA.strucutres import inventory
from source.logs import gachalogs as logs
from source.utility import utils
from source.utility.debug_screenshots import CAPTURE_PEGO_CRYSTAL, capture_for

capture_pego_crystal_withdraw = capture_for(
    "pego_crystal_withdraw", active=CAPTURE_PEGO_CRYSTAL
)


def pego_pickup(metadata):
    attempt = 0
    utils.turn_up(15)
    time.sleep(0.2 * settings.lag_offset)
    inventory.open()
    while not inventory.is_open():
        attempt += 1
        logs.logger.debug(
            f"the pego at {metadata.name} could not be accessed retrying {attempt} / {source.gacha_bot.config.pego_attempts}"
        )
        utils.zero()
        utils.set_yaw(metadata.yaw)
        utils.turn_up(15)
        time.sleep(0.2 * settings.lag_offset)
        inventory.open()
        if attempt >= source.gacha_bot.config.pego_attempts:
            logs.logger.error(
                f"the pego at {metadata.name} could not be accesssed after {attempt} attempts"
            )
            break

    if inventory.is_open():  # prevents pego being FLUNG
        player_inventory.drop_all_inv()
        time.sleep(0.2 * settings.lag_offset)
        inventory.transfer_all_from()
        time.sleep(0.2 * settings.lag_offset)
        capture_pego_crystal_withdraw(metadata.name)
        inventory.close()

    time.sleep(0.1 * settings.lag_offset)
    utils.turn_down(utils.current_pitch)
    time.sleep(0.1 * settings.lag_offset)
