import time

from source.ASA import config
from source.ASA.player import player_inventory, player_state
from source.ASA.strucutres import inventory, teleporter
from source.logs import gachalogs as logs
from source.utility import template, utils, utils_simple, windows
from source.utility.structures.transmitter import transmitter_transfer_menu

buttons = {
    "back_x": 1800,
    "back_y": 66,
}
was_excess_amount = False


def get_pixel_loc(location):
    return buttons.get(location)


def is_open():
    return template.check_template("transmitter_inv", 0.7)


def is_open_ready():
    return is_open() and template.check_template("trans_inv_ready", 0.7)


def ensure_active():
    """This function to make sure the transmitter is ON, so if it's not, turn it on and reopen inv"""
    if not inventory.is_open():
        return False

    if inventory.is_turned_on():
        logs.logger.debug("Transmitter is already ON, no need to turn it on again")
        return True

    inventory.turn_on()

    inventory.close()
    time.sleep(1)

    open_raw()

    return True


def close():
    transmitter_transfer_menu.close()

    attempts = 0
    while is_open():
        attempts += 1
        logs.logger.debug(
            f"Trying to close Transmitter inventory {attempts} / {config.inventory_close_attempts}"
        )
        windows.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))

        if not template.template_await_false(is_open, 2):
            return time.sleep(0.3)

        if attempts >= config.inventory_close_attempts:
            logs.logger.error(f"Unable to close Transmitter after {attempts} attempts")
            # check state of the char the reason we can do it now is that the latter should spam click close inv
            player_state.check_state()
            break


def recover_if_problem():
    player_state.check_state()
    teleporter.teleport_not_default(teleporter._last_teleporter_name)
    utils.zero_center()


def open_raw():
    # Open inventory
    dl = utils_simple.get_default_clock()
    while not dl():
        inventory.open()

        if inventory.is_open():
            return
        else:
            recover_if_problem()


def open():
    """
    Open and ensure it's turned on
    """
    # Open inventory
    open_raw()

    ensure_active()

    if not is_open():
        logs.logger.error(
            f"Can't open transmitter inventory after {config.timeout_deadline}"
        )
        return

    # Wait for loading
    dl = utils_simple.get_default_clock()
    while is_open() and not dl():
        if template.template_await_true(is_open_ready, 1):
            logs.logger.debug("Transmitter is ready for actions")
            return
        else:
            player_state.check_disconnected()

    if not is_open_ready():
        logs.logger.error(
            f"Transmitter inventory failed to load after {config.timeout_deadline}"
        )


def is_item_has_timer():
    # First stage should be already opened and powered
    if not is_open_ready() or not inventory.is_open():
        return False

    item_with_timer = template.capture_for_compare("capture_item_player_second_slot")
    inventory.close()

    player_inventory.open()

    # If item before(when in transmitter) might has timer OR NOT, and the item in player inventory will never have timer
    # If this function return true, mean it's changed -> still have timer
    is_still_timer = template.capture_compare_changed(
        "capture_item_player_second_slot", item_with_timer
    )

    logs.logger.debug(f"{'Still have timer' if is_still_timer else 'Not have timer'}")

    inventory.close()

    return is_still_timer


def open_and_has_timer():
    """
    Return True if player still has timer
    """
    player_state.uploaded = False
    attempt_inv = 0
    # OPEN TRANS INV
    while not is_open():
        attempt_inv += 1

        open()

        if not is_open():
            time.sleep(0.5)
            player_state.check_state()

        if attempt_inv >= config.inventory_open_attempts:
            logs.logger.critical(
                f"Can't open transmitter inventory after {attempt_inv} attempts"
            )
            break
    if not is_open():
        return False

    still = is_item_has_timer()
    return still


def open_and_transfer(server_number="0000"):
    """
    When this is done, it should be ready at the bed spawning screen
    """

    global was_excess_amount
    was_excess_amount = False
    player_state.uploaded = False

    attempt = 0
    while True:
        attempt += 1
        attempt_inv = 0
        # OPEN TRANS INV
        while not is_open() and not player_state.uploaded:
            attempt_inv += 1

            if transmitter_transfer_menu.is_open():
                break
            logs.logger.debug(
                f"Open transmitter inventory {attempt_inv}/{config.inventory_open_attempts}"
            )
            open()

            if not is_open():
                time.sleep(0.5)
                player_state.check_state()

            if attempt_inv >= config.inventory_open_attempts:
                logs.logger.critical(
                    f"Can't open transmitter inventory after {attempt_inv} attempts"
                )
                break

        if (
            not transmitter_transfer_menu.is_open()
            and not player_state.uploaded
            and not is_open()
        ):
            return False

        # OPEN TRANS SERVER LIST
        transmitter_transfer_menu.open()

        # PERFORM TRANSFER, SUCCESS ONLY WHEN IT SHOW BEDS
        success = transmitter_transfer_menu.do_join_server(str(server_number))
        if success:
            logs.logger.debug("Successfully joined destination server!")
            return True
        else:
            transmitter_transfer_menu.has_failure()
            if not player_state.uploaded:
                player_state.check_state()
                utils.zero_center()
            if was_excess_amount:
                return False

        time.sleep(1)
