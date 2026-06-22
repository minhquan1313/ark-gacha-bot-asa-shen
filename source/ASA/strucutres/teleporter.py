import time

import settings
import source.ASA.config
import source.ASA.stations.custom_stations
from source.ASA.player import player_state, tribelog
from source.ASA.strucutres import bed
from source.logs import gachalogs as logs
from source.utility import template, utils, variables, windows


def is_open():
    return template.check_template("teleporter_title", 0.7)


def open():
    """
    player should already be looking down at the teleporter this just opens and WILL try and correct if there are issues
    """
    attempts = 0
    dl = utils.get_default_clock()
    while not is_open() and not dl():
        attempts += 1
        logs.logger.debug(
            f"trying to open teleporter {attempts} / {source.ASA.config.teleporter_open_attempts}"
        )
        utils.press_key("Use")

        if not template.template_await_true(
            template.check_template, 3, "teleporter_title", 0.7
        ):
            logs.logger.warning("teleporter didnt open retrying now")
            player_state.check_state()
            # check state of char which should close out of any windows we are in or rejoin the game
            utils.pitch_zero()  # reseting the chars pitch/yaw
            utils.turn_down(80)
            time.sleep(0.2 * settings.lag_offset)
        else:
            logs.logger.debug("teleporter opened")

        if attempts - 1 == source.ASA.config.teleporter_open_attempts:
            logs.logger.error(
                f"unable to open up the teleporter after {source.ASA.config.teleporter_open_attempts} attempts"
            )
            bed.spawn_in(settings.bed_spawn)
            time.sleep(20)
            utils.pitch_zero()  # reseting the chars pitch/yaw
            utils.turn_down(80)
            time.sleep(5)
            break

        if attempts >= source.ASA.config.teleporter_open_attempts:
            logs.logger.error(
                f"unable to open up the teleporter after {source.ASA.config.teleporter_open_attempts} attempts, eating implant and trying to reset"
            )
            bed.spawn_in(settings.bed_spawn)
            time.sleep(20)
            utils.pitch_zero()  # reseting the chars pitch/yaw
            utils.turn_down(80)
            time.sleep(5)

            attempts = 0
            dl = utils.get_default_clock()


def close():
    attempts = 0
    while is_open():
        attempts += 1
        logs.logger.debug(
            f"trying to close the teleporter {attempts} / {source.ASA.config.teleporter_close_attempts}"
        )
        windows.click(
            variables.get_pixel_loc("back_button_tp_x"),
            variables.get_pixel_loc("back_button_tp_y"),
        )
        time.sleep(0.2 * settings.lag_offset)

        if attempts >= source.ASA.config.teleporter_close_attempts:
            logs.logger.error(
                f"unable to close the teleporter after {source.ASA.config.teleporter_close_attempts} attempts"
            )
            break


def teleport_not_default(
    arg: source.ASA.stations.custom_stations.station_metadata | str,
    fallback_bed_name=None,
):
    fallback_bed_name = fallback_bed_name or settings.bed_spawn
    if not player_state.human.on_tp:
        time.sleep(0.2 * settings.lag_offset)
        utils.turn_down(80)
        time.sleep(0.3 * settings.lag_offset)
        bed.fast_travel(fallback_bed_name)
        time.sleep(0.2 * settings.lag_offset)

    if isinstance(arg, source.ASA.stations.custom_stations.station_metadata):
        stationdata = arg
    else:
        stationdata = source.ASA.stations.custom_stations.get_station_metadata(arg)

    teleporter_name = stationdata.name
    time.sleep(0.3 * settings.lag_offset)
    utils.turn_down(80)
    time.sleep(0.3 * settings.lag_offset)

    open()
    if is_open():
        player_state.human.is_on_tp()

        # ENSURE TP IS OPEN AND SERVER LOADED PROCESS
        deadline = utils.get_default_clock()
        time.sleep(
            0.3 * settings.lag_offset
        )  # preventing the orange text from the starting teleport screen messing things up
        while True:
            windows.click(
                variables.get_pixel_loc("first_bed_slot_x"),
                variables.get_pixel_loc("first_bed_slot_y"),
            )
            if not template.template_await_true(template.check_teleporter_orange, 3):
                logs.logger.warning(
                    "orange pixel for teleporter ready not found - list not loaded"
                )
                player_state.check_disconnected()
            else:
                break
            time.sleep(
                0.3 * settings.lag_offset
            )  # preventing the orange text from the starting teleport screen messing things up

            if deadline():
                player_state.reset_state()
                time.sleep(0.3 * settings.lag_offset)

                bed.spawn_in(fallback_bed_name)

                utils.turn_down(80)
                time.sleep(0.3 * settings.lag_offset)

                open()

                deadline = utils.get_default_clock()
        # ENSURE DONE

        counter = 0
        while template.check_template_no_bounds("search", 0.7):
            counter += 1
            windows.click(
                variables.get_pixel_loc("search_bar_bed_alive_x"),
                variables.get_pixel_loc("search_bar_bed_y"),
            )  # im lazy this is the same position as the teleporter search bar
            utils.ctrl_a()
            utils.write(teleporter_name)
            time.sleep(0.5 * settings.lag_offset)
            if counter >= 3:
                logs.logger.error("search still detected likely did type anything")
                break
        windows.click(
            variables.get_pixel_loc("first_bed_slot_x"),
            variables.get_pixel_loc("first_bed_slot_y"),
        )
        time.sleep(
            0.3 * settings.lag_offset
        )  # preventing the orange text from the starting teleport screen messing things up
        if not template.template_await_true(template.check_teleporter_orange, 3):
            logs.logger.warning(
                "orange pixel for teleporter ready not found likely already on the tp we are just exiting the tp treating it as the tp we should be on"
            )
            close()  # closing out as either the TP couldnt be found however we still want to change to the station yaw so we still continue
        else:
            time.sleep(0.2 * settings.lag_offset)
            windows.click(
                variables.get_pixel_loc("first_bed_slot_x"),
                variables.get_pixel_loc("first_bed_slot_y"),
            )
            time.sleep(0.2 * settings.lag_offset)
            windows.click(
                variables.get_pixel_loc("spawn_button_x"),
                variables.get_pixel_loc("spawn_button_y"),
            )

            if template.template_await_true(template.white_flash, 1):
                logs.logger.debug("white flash detected waiting for up too 5 seconds")
                template.template_await_false(template.white_flash, 5)

            # Extra step to ensure we are teleported(not sitting at the old teleport due to server lag/save)
            time.sleep(0.3 * settings.lag_offset)
            open()
            close()
            tribelog.open()
            tribelog.close()

        time.sleep(0.5 * settings.lag_offset)
        if (
            settings.singleplayer
        ):  # single player for some reason changes view angles when you tp
            utils.current_pitch = 0
            utils.turn_down(80)
            time.sleep(0.2)
