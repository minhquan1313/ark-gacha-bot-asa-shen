import time

from source.ASA.config import LAGGED_DETECT
from source.ASA.player import player_inventory, player_state
from source.ASA.strucutres import inventory, teleporter
from source.logs import gachalogs as logs
from source.utility import template, utils, utils_simple, windows
from source.utility.debug_screenshots import (
    CAPTURE_DEDI_DEPOSIT_CRYSTAL,
    CAPTURE_DEDI_DEPOSIT_GRIND,
    capture_for,
)
from source.utility.types import DediStorageState

buttons = {
    "dedi_withdraw": (1438, 200),
    "dedi_deposit": (967, 879),
    "dedi_clear_resource": (967, 834),
}

capture_name: str | None = None
capture_dedi_deposit_crystal = capture_for(
    "dedi_deposit_crystal", active=CAPTURE_DEDI_DEPOSIT_CRYSTAL, delay=0.1
)
capture_dedi_deposit_grind = capture_for(
    "dedi_deposit_grind", active=CAPTURE_DEDI_DEPOSIT_GRIND, delay=0.1
)

was_clear_dedi = False
was_last_dedi_empty = False


def get_pixel_loc(location):
    return buttons.get(location, (0, 0))


def is_open():
    return template.check_template("dedi", 0.7)


def is_empty():
    global was_last_dedi_empty
    was_last_dedi_empty = bool(template.check_template("dedi_deposit_clear", 0.7))
    return was_last_dedi_empty


def is_can_deposit():
    global was_last_dedi_empty
    has_deposit_button = bool(template.check_template("dedi_deposit_ready", 0.7))
    was_last_dedi_empty = not has_deposit_button
    return has_deposit_button


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
    time.sleep(0.2)


def recover_if_problem(teleporter_name: str, item: DediStorageState):
    player_state.check_state()
    teleporter.teleport_not_default(teleporter_name)

    utils.get_yaw_pitch()
    turn_to_dedi(item)


def _capture_deposit():
    """Capture the current crystal or grindable deposit before inventory closes."""

    if not capture_name:
        return

    normalized_name = capture_name.casefold()
    if normalized_name.startswith("crystal"):
        capture_dedi_deposit_crystal(capture_name)
    else:
        # elif normalized_name.startswith("grind"):
        capture_dedi_deposit_grind(capture_name)


def ensure_has_resource():
    if not is_open():
        return

    attempt = 0
    while is_open() and player_inventory.is_can_transfer_all() and not is_can_deposit():
        attempt += 1

        if attempt > 3:
            logs.logger.critical("Failed to put 1st item to dedi inventory")
            return

        logs.logger.warning(f"Dedi is empty, trying to put 1 item inside[{attempt}]")

        # Making sure it's resource filter first
        player_inventory.change_filter("resource")
        time.sleep(0.2)

        player_inventory.transfer_first_inventory(0)
        time.sleep(0.2)

        # After deposit, change filter back to all(Reset)
        player_inventory.change_filter("all")

        if template.template_await_true(is_can_deposit, 3):
            return
        else:
            logs.logger.error("Dedi still empty, retying")


def open(teleporter_name: str, item: DediStorageState):
    attempt = 0
    dl = utils_simple.get_default_clock()
    while not is_open():
        attempt += 1
        logs.logger.debug(f"Trying to open dedi inventory[{attempt}]")
        inventory.open(crouch_if_problem=False)

        if is_open():
            return
        else:
            logs.logger.error("Failed to open dedi inventory")
            recover_if_problem(teleporter_name, item)

        time.sleep(0.3)

        if dl():
            logs.logger.critical("Failed to open dedi inventory")
            return


def unsafe_fast_deposit_all(item: DediStorageState):
    global capture_name
    turn_to_dedi(item)

    utils.press_key("Use")
    _capture_deposit()
    utils_simple.sleep()

    if capture_name:
        logs.logger.debug(f"{capture_name} deposit handshake completed")
    capture_name = None


def open_deposit_all(
    teleporter_name: str, item: DediStorageState, *, ensure_resource=True
):
    global capture_name
    dl = utils_simple.get_default_clock(multiplier=3)
    attempt = 0
    # Open inventory
    while True:
        if dl():
            capture_name = None
            logs.logger.critical("Failed to deposit all items to dedi inventory")
            return False

        attempt += 1
        logs.logger.debug(f"Trying to deposit all[{attempt}]")

        turn_to_dedi(item)

        open(teleporter_name, item)
        if not is_open():
            recover_if_problem(teleporter_name, item)
            continue

        # Ready
        if ensure_resource:
            ensure_has_resource()

            if not is_can_deposit():
                if player_inventory.is_can_transfer_all():
                    recover_if_problem(teleporter_name, item)
                    continue
                else:
                    # NOTHING ON PLAYER INVENTORY, SO NOTHING TO DEPOSIT, RETURN TRUE
                    inventory.close()
                    return True
        elif (
            not player_inventory.is_can_transfer_all()
            and not is_can_deposit()
            or is_empty()
        ):
            inventory.close()
            return True

        windows.click(*get_pixel_loc("dedi_deposit"))
        _capture_deposit()
        inventory.close()
        if capture_name:
            logs.logger.debug(f"{capture_name} deposit handshake completed")

        capture_name = None
        return True


def open_deposit_stack(
    count: int, teleporter_name: str, item: DediStorageState, *, ensure_resource=True
):
    global capture_name

    if count < 1:
        return True

    dl = utils_simple.get_default_clock(multiplier=3)
    attempt = 0
    # Open inventory
    while True:
        if dl():
            capture_name = None
            logs.logger.critical("Failed to deposit all items to dedi inventory")
            return False

        attempt += 1
        logs.logger.debug(f"Trying to deposit all[{attempt}]")

        turn_to_dedi(item)

        open(teleporter_name, item)
        if not is_open():
            recover_if_problem(teleporter_name, item)
            continue

        # Ready
        if ensure_resource:
            ensure_has_resource()

            if not is_can_deposit():
                if player_inventory.is_can_transfer_all():
                    recover_if_problem(teleporter_name, item)
                    continue
                else:
                    # NOTHING ON PLAYER INVENTORY, SO NOTHING TO DEPOSIT, RETURN TRUE
                    inventory.close()
                    return True
        elif (
            not player_inventory.is_can_transfer_all()
            and not is_can_deposit()
            or is_empty()
        ):
            inventory.close()
            return True

        player_inventory.popcorn(count, transfer_instead=True)

        _capture_deposit()
        inventory.close()
        if capture_name:
            logs.logger.debug(f"{capture_name} deposit handshake completed")

        capture_name = None
        return True


def clear_resource():
    global was_clear_dedi

    if not is_open():
        return

    windows.click(*get_pixel_loc("dedi_clear_resource"))
    was_clear_dedi = True
    player_inventory.is_can_transfer_all()
    inventory.close()


def open_withdraw_all(
    teleporter_name: str,
    item: DediStorageState,
    *,
    should_clear_on_empty=False,
    ensure_safe_transfer_timer=True,
):
    global was_clear_dedi
    was_clear_dedi = False
    dl = utils_simple.get_default_clock(multiplier=3)
    attempt = 0

    turn_to_dedi(item)
    # Open inventory
    while not dl():
        attempt += 1
        logs.logger.debug(f"Trying to withdraw all[{attempt}]")

        with inventory.detect_lag_long_process():
            open(teleporter_name, item)

            if not is_open():
                recover_if_problem(teleporter_name, item)
                continue

            if not is_can_deposit():
                player_inventory.is_can_transfer_all()
                inventory.close()
                return True

            if should_clear_on_empty and is_empty():
                clear_resource()
                return True

            # If the server save right at this moment, then boom, we need to redo it
            # Otherwise, the resource won't have timer and will be lost on transfer
            windows.click(*get_pixel_loc("dedi_withdraw"))

            is_lagged = ensure_safe_transfer_timer and (
                inventory.was_server_lag_last_open_long
                or (
                    not is_empty()
                    and not template.template_await_true(
                        player_inventory.is_can_transfer_all, LAGGED_DETECT
                    )
                )
            )
            if is_lagged:
                logs.logger.critical(
                    "Server save detected, redo to make sure no resource loss if transfer server!!!"
                )

                inventory.close()
                recover_if_problem(teleporter_name, item)
                open(teleporter_name, item)

                windows.click(*get_pixel_loc("dedi_deposit"))
                time.sleep(0.2)
                inventory.close()
                recover_if_problem(teleporter_name, item)

                dl.reset()
                continue

        if should_clear_on_empty and template.template_await_true(is_empty, 0.3):
            clear_resource()
            return True

        # Addition check for higher level module uses
        player_inventory.is_can_transfer_all()
        inventory.close()

        return True

    return False
