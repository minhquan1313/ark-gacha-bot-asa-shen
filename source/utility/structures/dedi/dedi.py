import time

import settings
from source.ASA.player import player_inventory, player_state
from source.ASA.stations.custom_stations import station_metadata
from source.ASA.strucutres import inventory, teleporter
from source.logs import gachalogs as logs
from source.utility import template, utils, windows
from source.utility.debug_screenshots import (
    CAPTURE_DEDI_DEPOSIT_CRYSTAL,
    CAPTURE_DEDI_DEPOSIT_GRIND,
    capture_for,
)
from source.utility.types import DediStorageState

buttons = {
    "dedi_withdraw_x": 967,
    "dedi_withdraw_y": 838,
    "dedi_deposit_x": 967,
    "dedi_deposit_y": 879,
}

capture_name: str | None = None
capture_dedi_deposit_crystal = capture_for(
    "dedi_deposit_crystal", active=CAPTURE_DEDI_DEPOSIT_CRYSTAL, delay=0.1
)
capture_dedi_deposit_grind = capture_for(
    "dedi_deposit_grind", active=CAPTURE_DEDI_DEPOSIT_GRIND, delay=0.1
)


def get_pixel_loc(location):
    return buttons.get(location)


def is_open():
    return template.check_template("dedi", 0.7)


def is_has_resource():
    return template.check_template("dedi_deposit_ready", 0.7)


def deposit_first_item():
    if not is_open():
        return

    player_inventory.transfer_first_inventory()


def set_crouch(item: DediStorageState):
    crouched = item.get("crouched", False) if isinstance(item, dict) else False
    if crouched:
        player_state.human.crouch()
    else:
        player_state.human.reset_crouch()


def turn_to_dedi(item: DediStorageState):
    location = item.get("location", {}) if isinstance(item, dict) else {}
    yaw = float(location["yaw"])
    pitch = float(location["pitch"])
    set_crouch(item)
    utils.turn_to(yaw, pitch)


def recover_if_problem(metadata: station_metadata, item: DediStorageState):
    player_state.check_state()
    teleporter.teleport_not_default(metadata)
    utils.zero_center()
    turn_to_dedi(item)


def _capture_deposit() -> None:
    """Capture the current crystal or grindable deposit before inventory closes."""

    if not capture_name:
        return

    normalized_name = capture_name.casefold()
    if normalized_name.startswith("crystal"):
        capture_dedi_deposit_crystal(capture_name)
    elif normalized_name.startswith("grind"):
        capture_dedi_deposit_grind(capture_name)


def ensure_has_resource():
    if not is_open():
        return

    dl = utils.get_default_clock()
    attempt = 0
    while is_open() and not is_has_resource() and not dl():
        attempt += 1
        logs.logger.warning(f"Dedi is empty, trying to put 1 item inside[{attempt}]")
        deposit_first_item()

        if template.template_await_true(is_has_resource, 2):
            return
        else:
            logs.logger.error("Dedi still empty, retying")

    if dl():
        logs.logger.critical("Failed to put 1st item to dedi inventory")


def open(metadata: station_metadata, item: DediStorageState):
    """Should be ready also, as it use inventory.open"""

    dl = utils.get_default_clock()
    attempt = 0
    while not dl():
        attempt += 1
        logs.logger.debug(f"Trying to open dedi inventory[{attempt}]")
        inventory.open()

        if is_open():
            return
        else:
            logs.logger.error("Failed to open dedi inventory")
            recover_if_problem(metadata, item)
        time.sleep(0.3 * settings.lag_offset)

    if dl():
        logs.logger.critical("Failed to open dedi inventory")


def open_deposit_all(metadata: station_metadata, item: DediStorageState) -> bool:
    global capture_name
    dl = utils.get_default_clock(multiplier=3)
    attempt = 0
    # Open inventory
    while not dl():
        attempt += 1
        logs.logger.debug(f"Trying to deposit all[{attempt}]")

        turn_to_dedi(item)

        open(metadata, item)
        if not is_open():
            recover_if_problem(metadata, item)
            continue

        # Ready
        ensure_has_resource()
        if not is_has_resource():
            recover_if_problem(metadata, item)
            continue

        windows.click(
            get_pixel_loc("dedi_deposit_x"),
            get_pixel_loc("dedi_deposit_y"),
        )
        _capture_deposit()
        inventory.close()
        if capture_name:
            logs.logger.debug(f"{capture_name} deposit handshake completed")

        capture_name = None
        return True

    capture_name = None
    return False


def open_withdraw_all(metadata: station_metadata, item: DediStorageState):
    dl = utils.get_default_clock(multiplier=3)
    attempt = 0
    # Open inventory
    while not dl():
        attempt += 1
        logs.logger.debug(f"Trying to withdraw all[{attempt}]")

        turn_to_dedi(item)

        open(metadata, item)

        if not is_open():
            recover_if_problem(metadata, item)
            continue

        windows.click(
            get_pixel_loc("dedi_withdraw_x"),
            get_pixel_loc("dedi_withdraw_y"),
        )
        inventory.close()

        return True

    return False
