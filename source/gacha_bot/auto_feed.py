import time

import settings
from source.ASA.player import buffs, player_inventory, player_state, tribelog
from source.ASA.strucutres import inventory
from source.gacha_bot import render
from source.logs import gachalogs as logs
from source.utility import template, utils, utils_simple, windows


def turn_to_baby(baby: dict):
    location = baby["location"]

    utils.get_yaw_pitch()
    utils.turn_to(float(location["yaw"]), float(location["pitch"]))
    if baby.get("crouched"):
        player_state.human.crouch()
    else:
        player_state.human.reset_crouch()


def _feed_baby(baby: dict) -> None:
    """Turn to one Baby and transfer the configured food keyword."""

    turn_to_baby(baby)

    dl = utils_simple.get_default_clock()

    while not inventory.is_open():
        if dl():
            logs.logger.error("Failed to open baby inv")
            return

        inventory.open()

        if not inventory.is_open():
            player_state.check_state()
            turn_to_baby(baby)

    windows.click(603, 197)  # Auto stack
    time.sleep(0.1)

    player_inventory.search_in_inventory(str(baby["food"]))

    if inventory.is_can_drop():
        inventory.transfer_all_from()

        dl.reset()
        while template.template_await_false(inventory.is_can_drop, 2) and not dl():
            player_state.check_disconnected()
        time.sleep(0.2)

    player_inventory.transfer_all_inventory()

    # dl.reset()
    # while not template.template_await_true(inventory.is_can_drop, 2) and not dl():
    #     player_state.check_disconnected()
    # time.sleep(0.1)

    player_inventory.close()


def _feed_pass(babies: list[dict]) -> None:
    """Leave Tek pod if needed and feed every configured Baby once."""
    player_state.check_state(
        crouch=False, should_replesh=False, should_wait_structure=False
    )
    for index, baby in enumerate(babies, 1):
        logs.logger.info("Feeding Baby %s", index)
        _feed_baby(baby)
    time.sleep(0.2)


def _wait_in_tekpod(feed_cycle: int) -> None:
    """Keep the character in Tek pod for one configured feeding cycle."""
    render.enter_tekpod()
    dl = utils_simple.get_default_clock(feed_cycle)
    logs.logger.info(f"In tek pod, wait {dl.to_string(normalized=True)}")
    logs.disable_log()
    while not dl():
        player_state.check_disconnected()
        tribelog.open()

        if dl.remain() > 10:
            time.sleep(10)
            tribelog.close()
        else:
            time.sleep(dl.remain())
    logs.enable_log()


def _press_slot(slot: int) -> None:
    """Press the configured UseItem action unless the slot is disabled."""
    if slot in range(10):
        utils.press_key(f"UseItem{slot}")


def _wait_without_tekpod(feed_cycle: int, food_slot: int, water_slot: int) -> None:
    """Maintain food and water until the non-Tek-pod cycle deadline."""
    utils.press_key("Prone")
    dl = utils_simple.get_default_clock(feed_cycle)
    logs.logger.info(f"Lied on the ground, wait {dl.to_string(normalized=True)}")
    while not dl():
        player_state.check_disconnected()
        state = buffs.check_buffs().check_buffs()
        if state == 2:
            _press_slot(water_slot)
        elif state == 3:
            _press_slot(food_slot)

        if dl.remain() > 10:
            time.sleep(10)
        else:
            time.sleep(dl.remain())


def update_global_config(config: dict):
    if config["tek_pod"] and config["station_yaw"]:
        settings.station_yaw = float(config["station_yaw"])
    utils.was_initialized = True


def run_auto_feed(config: dict) -> bool:
    """Run Auto Baby Feeding until the helper process is stopped."""
    babies = config["babies"]

    update_global_config(config)

    while True:
        _feed_pass(babies)
        if config["tek_pod"]:
            _wait_in_tekpod(config["feed_cycle"])
        else:
            _wait_without_tekpod(
                config["feed_cycle"], config["food_slot"], config["water_slot"]
            )
        if not config["tek_pod"]:
            utils.turn_to(float(settings.station_yaw), 0.0)
