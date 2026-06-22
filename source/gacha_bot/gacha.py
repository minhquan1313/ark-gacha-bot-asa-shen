import time

import settings
import source.gacha_bot.config
from source.ASA.player import player_inventory
from source.ASA.strucutres import inventory
from source.logs import gachalogs as logs
from source.utility import template, utils, variables, windows
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


def drop_off(metadata):  # drop off for 150 stacks of seeds
    direction = metadata.side
    turn_constant = 1 if direction == "right" else -1

    utils.turn_right(40 * turn_constant)
    time.sleep(0.2 * settings.lag_offset)
    inventory.open()

    attempt = 0
    while not inventory.is_open():
        attempt += 1
        logs.logger.debug(
            f"the {direction} gacha at {metadata.name} could not be accessed retrying {attempt} / {source.gacha_bot.config.gacha_attempts}"
        )
        utils.zero()
        utils.set_yaw(metadata.yaw)
        utils.turn_right(40 * turn_constant)
        time.sleep(0.2 * settings.lag_offset)
        inventory.open()
        if attempt >= source.gacha_bot.config.gacha_attempts:
            logs.logger.error(
                f"the {direction} gacha at {metadata.name} could not be accesssed after {attempt} attempts"
            )
            break
    temp = False
    if inventory.is_open():
        inventory.transfer_all_from()
        if template.template_await_true(
            template.check_template_no_bounds, 1, "slot_capped", 0.7
        ):
            logs.logger.debug("player is overcapped")
            capture_gacha_overcap_before_drop(f"{metadata.name}_{direction}")
            inventory.drop_all_obj()  # as our player is overcapped the gacha will also be overcapped + we have seeds in our inventory which is more important than pellets
            player_inventory.search_in_inventory("pell")
            if not template.template_await_true(
                template.check_template_no_bounds, 0.5, "snow_owl_pellet", 0.5
            ):
                logs.logger.warning(
                    "GACHA is full of seeds"
                )  # warning the gacha is full of seeds as obviously something is wrong
                player_inventory.close()
                time.sleep(0.1 * settings.lag_offset)
                utils.turn_right(180)
                time.sleep(0.1 * settings.lag_offset)
                player_inventory.open()
                player_inventory.search_in_inventory("seed")
                temp = True
            windows.click(
                variables.get_pixel_loc("inv_slot_start_x") + 50,
                variables.get_pixel_loc("inv_slot_start_y") + 70,
            )
            for _x in range(8):
                windows.move_mouse(
                    variables.get_pixel_loc("inv_slot_start_x") + 50,
                    variables.get_pixel_loc("inv_slot_start_y") + 70,
                )
                utils.press_key("DropItem")
                time.sleep(0.3 * settings.lag_offset)
            time.sleep(0.1 * settings.lag_offset)

    player_inventory.close()
    time.sleep(0.2 * settings.lag_offset)
    if temp:
        utils.turn_left(180)
    utils.turn_right(90 * turn_constant)
    time.sleep(0.3 * settings.lag_offset)
    inventory.open()
    if not template.template_await_true(template.check_template, 2, "crop_plot", 0.7):
        logs.logger.warning(
            f"the {direction} crop plot at {metadata.name}tp failed to open retrying now"
        )
        utils.zero()
        utils.set_yaw(metadata.yaw)
        utils.turn_right(130 * turn_constant)
        time.sleep(0.2 * settings.lag_offset)
        inventory.open()
    if template.check_template("crop_plot", 0.7):
        inventory.transfer_all_from()
        time.sleep(0.2 * settings.lag_offset)
        player_inventory.transfer_all_inventory()  # take out all input all # refreshing owl pelletes
        time.sleep(0.2 * settings.lag_offset)
        inventory.close()
    time.sleep(0.2 * settings.lag_offset)

    utils.turn_left(90 * turn_constant)
    time.sleep(0.2 * settings.lag_offset)
    inventory.open()
    if template.check_template("crop_plot", 0.7):
        logs.logger.debug("failed to turn away from the crop plot retrying now")
        inventory.close()
        time.sleep(0.5 * settings.lag_offset)
        utils.turn_left(90 * turn_constant)
        time.sleep(0.3 * settings.lag_offset)
        inventory.open()
        time.sleep(0.3 * settings.lag_offset)
    if inventory.is_open():
        player_inventory.search_in_inventory("seed")
        time.sleep(0.2 * settings.lag_offset)
        player_inventory.transfer_all_inventory()
        time.sleep(0.2 * settings.lag_offset)
        if settings.seeds_230:
            inventory.search_in_object("pell")
            time.sleep(0.2 * settings.lag_offset)
            inventory.drop_all_obj()
            player_inventory.search_in_inventory("seed")
            time.sleep(0.2 * settings.lag_offset)
            player_inventory.transfer_all_inventory()
            time.sleep(0.2 * settings.lag_offset)
        player_inventory.search_in_inventory("pell")
        time.sleep(0.2 * settings.lag_offset)
        player_inventory.transfer_all_inventory()
        time.sleep(0.2 * settings.lag_offset)
        capture_gacha_seed_deposit(f"{metadata.name}_{direction}")

    inventory.close()
    time.sleep(0.2 * settings.lag_offset)
    utils.turn_left(40 * turn_constant)


def drop_off_nocrop(metadata):  # change reberry time or you will run out of crops
    direction = metadata.side
    turn_constant = 1 if direction == "right" else -1

    utils.turn_right(40 * turn_constant)
    time.sleep(0.2 * settings.lag_offset)

    open_gacha_inv(metadata, direction, turn_constant)

    if inventory.is_open():
        inventory.transfer_all_from()
        capture_gacha_overcap_before_drop(f"{metadata.name}_{direction}")

        inventory.close()
        open_gacha_inv(metadata, direction, turn_constant)

    if inventory.is_open():
        inventory.drop_all_obj()

        inventory.close()
        open_gacha_inv(metadata, direction, turn_constant)

    if inventory.is_open():
        player_inventory.transfer_all_inventory()
        capture_gacha_seed_deposit(f"{metadata.name}_{direction}")

    inventory.close()
    time.sleep(0.2 * settings.lag_offset)
    utils.turn_left(40 * turn_constant)


def open_gacha_inv(metadata, direction, turn_constant):
    inventory.open()

    attempt = 0
    while not inventory.is_open():
        attempt += 1
        logs.logger.debug(
            f"the {direction} gacha at {metadata.name} could not be accessed retrying {attempt} / {source.gacha_bot.config.gacha_attempts}"
        )
        utils.zero()
        utils.set_yaw(metadata.yaw)
        utils.turn_right(40 * turn_constant)
        time.sleep(0.2 * settings.lag_offset)
        inventory.open()
        if attempt >= source.gacha_bot.config.gacha_attempts:
            logs.logger.error(
                f"the {direction} gacha at {metadata.name} could not be accesssed after {attempt} attempts"
            )
            break
