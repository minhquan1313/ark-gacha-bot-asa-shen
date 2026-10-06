import time

import source.gacha_bot.config
from source.ASA.player import player_inventory
from source.ASA.strucutres import inventory
from source.logs import gachalogs as logs
from source.utility import template, utils, utils_simple
from source.utility.debug_screenshots import CAPTURE_PEGO_CRYSTAL, capture_for

capture_pego_crystal_withdraw = capture_for("pego_crystal_withdraw", active=CAPTURE_PEGO_CRYSTAL)


def is_crystal_hotbar_visible():
    return template.check_template("crystal_in_hotbar", 0.7)


def auto_assign_crystal():
    player_inventory.open()
    if not player_inventory.is_open():
        return
    player_inventory.search_and_assign_to_hotbar("gacha crystal", list(range(10)))
    player_inventory.close()


def look():
    utils.turn_up(15)
    time.sleep(0.2)


first_time = True


def pego_pickup(teleporter_name: str):
    global first_time

    look()
    open(teleporter_name)
    if inventory.is_open():  # prevents pego being FLUNG
        # if player_inventory.is_can_drop():
        #     player_inventory.drop_all_inv()
        #     time.sleep(0.2)

        #     # ENSURE
        #     inventory.close()
        #     open(teleporter_name)
        #     if not inventory.is_open():
        #         player_state.check_state()
        #         utils.zero_center()
        #         look()
        #         open(teleporter_name)
        #         if not inventory.is_open():
        #             return
        inventory.transfer_all_from()
        time.sleep(0.2)
        capture_pego_crystal_withdraw(teleporter_name)
        inventory.close()

        # ENSURE ALL CRYSTAL IS TRANSFERRED
        # So it won't break the next checking crystals in player hotbar process
        if not is_crystal_hotbar_visible():
            open(teleporter_name)
            inventory.close()

            if not is_crystal_hotbar_visible() and player_inventory.g_last_check_can_drop and first_time:
                auto_assign_crystal()

                if not is_crystal_hotbar_visible():
                    import winsound

                    for _ in range(3):
                        winsound.Beep(800, 200)
                        time.sleep(0.1)
                    raise RuntimeError("Please manually assign crystals to hotbar first")
        first_time = False


def open(teleporter_name: str):
    inventory.open()

    attempt = 0
    dl = utils_simple.get_default_clock()
    while not inventory.is_open():
        attempt += 1
        logs.logger.debug(f"the pego at {teleporter_name} could not be accessed retrying {attempt} / {source.gacha_bot.config.pego_attempts}")
        utils.zero_center()
        utils.turn_up(15)
        time.sleep(0.2)
        inventory.open()
        if dl():
            logs.logger.error(f"the pego at {teleporter_name} could not be accesssed after {attempt} attempts")
            break
