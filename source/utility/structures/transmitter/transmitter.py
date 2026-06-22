import time

import settings
from source.ASA import config
from source.ASA.player import player_state
from source.ASA.stations.custom_stations import station_metadata
from source.ASA.strucutres import inventory, teleporter
from source.logs import gachalogs as logs
from source.utility import template, utils, windows
from source.utility.structures.transmitter import transmitter_transfer_menu

buttons = {
    "transfer_to_another_server_button_x": 960,
    "transfer_to_another_server_button_y": 790,
    "back_x": 1800,
    "back_y": 66,
}


def get_pixel_loc(location):
    return buttons.get(location)


def is_open():
    return template.check_template("transmitter_inv", 0.7)


def is_open_ready():
    return is_open() and template.check_template("trans_inv_ready", 0.7)


def is_turned_on():
    if not is_open():
        return False

    coords = template.check_template("structure_turn_on", 0.7)
    return not coords


def ensure_active(metadata: station_metadata):
    """This function to make sure the transmitter is ON, so if it's not, turn it on and reopen inv"""
    if is_turned_on():
        return True

    coords = template.check_template("structure_turn_on", 0.7)
    if not coords:
        return False
    logs.logger.warning("Transmitter is off, trying to turn it on now...")

    windows.click(*coords)
    time.sleep(0.5 * settings.lag_offset)

    inventory.close()
    time.sleep(0.5 * settings.lag_offset)

    open_raw(metadata)

    return True


def close():
    if is_open():
        windows.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))
        template.template_await_false(is_open, 2)
    transmitter_transfer_menu.close()


def open_transfer_server_list():
    if not is_open():
        return

    dl = utils.get_default_clock()
    while not dl() and not transmitter_transfer_menu.is_open():
        windows.click(
            get_pixel_loc("transfer_to_another_server_button_x"),
            get_pixel_loc("transfer_to_another_server_button_y"),
        )
        time.sleep(0.3 * settings.lag_offset)

    if not transmitter_transfer_menu.is_open():
        logs.logger.error("Can't open transmitter server menu")


def recover_if_problem(metadata: station_metadata):
    player_state.check_state()
    teleporter.teleport_not_default(metadata)
    utils.zero_center()


def open_raw(metadata: station_metadata):
    # Open inventory
    dl = utils.get_default_clock()
    while not dl():
        inventory.open()

        if is_open():
            break
        else:
            recover_if_problem(metadata)


def open(metadata: station_metadata):
    # Open inventory
    open_raw(metadata)

    ensure_active(metadata)

    if not is_open():
        logs.logger.error(
            f"Can't open transmitter inventory after {config.timeout_deadline}"
        )
        return

    # Wait for loading
    dl = utils.get_default_clock()
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


def open_and_transfer(metadata: station_metadata, server_number=0):
    """
    When this is done, it should be ready at the bed spawning screen
    """

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
            open(metadata)

            if not is_open():
                player_state.check_state()
                time.sleep(0.5 * settings.lag_offset)

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
        open_transfer_server_list()

        # PERFORM TRANSFER, SUCCESS ONLY WHEN IT SHOW BEDS
        success = transmitter_transfer_menu.do_join_server(str(server_number))
        if success:
            logs.logger.debug("Successfully joined destination server!")

            return True

        else:
            # elif not player_state.uploaded:
            transmitter_transfer_menu.has_failure()
            if not player_state.uploaded:
                player_state.check_state()
                utils.zero_center()

        time.sleep(1 * settings.lag_offset)
