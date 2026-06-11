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
    while not is_open():
        attempts += 1
        logs.logger.debug(
            f"trying to open teleporter {attempts} / {source.ASA.config.teleporter_open_attempts}"
        )
        utils.press_key("Use")

        if not template.template_await_true(
            template.check_template, 60 * settings.lag_offset, "teleporter_title", 0.7
        ):
            logs.logger.warning("teleporter didnt open retrying now")
            player_state.check_state()
            # check state of char which should close out of any windows we are in or rejoin the game
            utils.pitch_zero()  # reseting the chars pitch/yaw
            utils.turn_down(80)
            time.sleep(0.2 * settings.lag_offset)
        else:
            logs.logger.debug(f"teleporter opened")

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
                f"unable to open up the teleporter after {source.ASA.config.teleporter_open_attempts} attempts"
            )
            break


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


def teleport_not_default(arg):
    if player_state.human.on_tp == False:
        time.sleep(0.2 * settings.lag_offset)
        utils.turn_down(80)
        time.sleep(0.3 * settings.lag_offset)
        bed.fast_travel(settings.bed_spawn)  # spawns on render bed which is on the tp
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
    time.sleep(
        0.2 * settings.lag_offset
    )  # waiting for teleport_icon to populate on the screen before we check
    if is_open():
        player_state.human.is_on_tp()
        if template.teleport_icon(0.55):
            start = time.time()
            logs.logger.debug(
                f"teleport icons are not on the teleport screen waiting for up to 10 seconds for them to appear"
            )
            template.template_await_true(template.teleport_icon, 10, 0.55)
            logs.logger.debug(
                f"time taken for teleporter icon to appear : {time.time() - start}"
            )
        counter = 0
        while template.check_template_no_bounds("search", 0.7):
            counter += 1
            windows.click(
                variables.get_pixel_loc("search_bar_bed_alive_x"),
                variables.get_pixel_loc("search_bar_bed_y"),
            )  # im lazy this is the same position as the teleporter search bar
            utils.ctrl_a()
            utils.write(teleporter_name)
            time.sleep(0.2 * settings.lag_offset)
            if counter >= 3:
                logs.logger.error(f"search still detected likely did type anything")
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
                f"orange pixel for teleporter ready not found likely already on the tp we are just exiting the tp treating it as the tp we should be on"
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

            if template.template_await_true(template.white_flash, 2):
                logs.logger.debug(f"white flash detected waiting for up too 5 seconds")
                template.template_await_false(template.white_flash, 5)
            tribelog.open()
            tribelog.close()
        time.sleep(0.5 * settings.lag_offset)
        if (
            settings.singleplayer
        ):  # single player for some reason changes view angles when you tp
            utils.current_pitch = 0
            utils.turn_down(80)
            time.sleep(0.2)
        utils.turn_up(80)
        time.sleep(0.2)
        utils.set_yaw(stationdata.yaw)


def transfer_open(stop_event=None):
    attempts = 0
    while not is_open():
        if _transfer_stopped(stop_event):
            return False
        attempts += 1
        logs.logger.debug(
            f"trying to open teleporter {attempts} / {source.ASA.config.teleporter_open_attempts}"
        )
        utils.press_key("Use")

        if not template.template_await_true(
            template.check_template, 2, "teleporter_title", 0.7
        ):
            logs.logger.warning("teleporter didnt open retrying now")
            player_state.check_state()
            utils.pitch_zero()
            utils.turn_down(80)
            if _transfer_wait(stop_event, 0.2 * settings.lag_offset):
                return False
        else:
            logs.logger.debug(f"teleporter opened")

        if attempts - 1 == source.ASA.config.teleporter_open_attempts:
            logs.logger.error(
                f"unable to open up the teleporter after {source.ASA.config.teleporter_open_attempts} attempts"
            )
            bed.transfer_spawn_in(settings.bed_spawn, stop_event)
            if _transfer_wait(stop_event, 20):
                return False
            utils.pitch_zero()
            utils.turn_down(80)
            if _transfer_wait(stop_event, 5):
                return False
            break

        if attempts >= source.ASA.config.teleporter_open_attempts:
            logs.logger.error(
                f"unable to open up the teleporter after {source.ASA.config.teleporter_open_attempts} attempts"
            )
            break
    return True


def transfer_teleport_not_default(arg, fallback_bed_name=None, stop_event=None):
    fallback_bed_name = fallback_bed_name or settings.bed_spawn
    if _transfer_stopped(stop_event):
        return False
    if player_state.human.on_tp == False:
        if _transfer_wait(stop_event, 0.2 * settings.lag_offset):
            return False
        utils.turn_down(80)
        if _transfer_wait(stop_event, 0.3 * settings.lag_offset):
            return False
        if bed.transfer_fast_travel(fallback_bed_name, stop_event) is False:
            return False
        if _transfer_wait(stop_event, 0.2 * settings.lag_offset):
            return False

    if isinstance(arg, source.ASA.stations.custom_stations.station_metadata):
        stationdata = arg
    else:
        stationdata = source.ASA.stations.custom_stations.get_station_metadata(arg)

    teleporter_name = stationdata.name
    if _transfer_wait(stop_event, 0.3 * settings.lag_offset):
        return False
    utils.turn_down(80)
    if _transfer_wait(stop_event, 0.3 * settings.lag_offset):
        return False
    if transfer_open(stop_event) is False:
        return False
    if _transfer_wait(stop_event, 0.2 * settings.lag_offset):
        return False
    if is_open():
        player_state.human.is_on_tp()
        if template.teleport_icon(0.55):
            start = time.time()
            logs.logger.debug(
                f"teleport icons are not on the teleport screen waiting for up to 10 seconds for them to appear"
            )
            template.template_await_true(template.teleport_icon, 10, 0.55)
            logs.logger.debug(
                f"time taken for teleporter icon to appear : {time.time() - start}"
            )
        counter = 0
        while template.check_template_no_bounds("search", 0.7):
            counter += 1
            windows.click(
                variables.get_pixel_loc("search_bar_bed_alive_x"),
                variables.get_pixel_loc("search_bar_bed_y"),
            )
            utils.ctrl_a()
            utils.write(teleporter_name)
            if _transfer_wait(stop_event, 0.2 * settings.lag_offset):
                return False
            if counter >= 3:
                logs.logger.error(f"search still detected likely did type anything")
                break
        windows.click(
            variables.get_pixel_loc("first_bed_slot_x"),
            variables.get_pixel_loc("first_bed_slot_y"),
        )
        if _transfer_wait(stop_event, 0.3 * settings.lag_offset):
            return False
        if not template.template_await_true(template.check_teleporter_orange, 3):
            logs.logger.warning(
                f"orange pixel for teleporter ready not found likely already on the tp we are just exiting the tp treating it as the tp we should be on"
            )
            close()

        else:
            if _transfer_wait(stop_event, 0.2 * settings.lag_offset):
                return False
            windows.click(
                variables.get_pixel_loc("first_bed_slot_x"),
                variables.get_pixel_loc("first_bed_slot_y"),
            )
            if _transfer_wait(stop_event, 0.2 * settings.lag_offset):
                return False
            windows.click(
                variables.get_pixel_loc("spawn_button_x"),
                variables.get_pixel_loc("spawn_button_y"),
            )

            if template.template_await_true(template.white_flash, 2):
                logs.logger.debug(f"white flash detected waiting for up too 5 seconds")
                template.template_await_false(template.white_flash, 5)
            tribelog.open()
            tribelog.close()
        if _transfer_wait(stop_event, 0.5 * settings.lag_offset):
            return False
        if settings.singleplayer:
            utils.current_pitch = 0
            utils.turn_down(80)
            if _transfer_wait(stop_event, 0.2):
                return False
        utils.turn_up(80)
        if _transfer_wait(stop_event, 0.2):
            return False
        utils.set_yaw(stationdata.yaw)
    return True


def _transfer_stopped(stop_event):
    return stop_event is not None and stop_event.is_set()


def _transfer_wait(stop_event, seconds):
    if stop_event is not None:
        return stop_event.wait(seconds)
    time.sleep(seconds)
    return False
