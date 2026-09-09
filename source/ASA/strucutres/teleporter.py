import time
from contextlib import contextmanager
from contextvars import ContextVar

import settings
import source.ASA.config
from source.ASA.player import console, player_state
from source.ASA.strucutres import bed
from source.logs import gachalogs as logs
from source.utility import template, utils, utils_simple, variables, windows

_last_teleporter_name: str = ""
_suicide_recovery_allowed = ContextVar(
    "teleporter_suicide_recovery_allowed", default=True
)


@contextmanager
def prevent_suicide_recovery():
    """Protect nested teleport calls for this context and restore policy on exit."""
    token = _suicide_recovery_allowed.set(False)
    try:
        yield
    finally:
        _suicide_recovery_allowed.reset(token)


def _stop_for_manual_recovery(reason: str):
    """Return to the main menu and stop without destructive teleport recovery."""
    message = (
        f"Teleport stopped: {reason}. Manual recovery required; "
        "suicide recovery is disabled."
    )
    logs.logger.error(message)
    try:
        console.console_exit_mainmenu()
    except Exception as exc:
        raise RuntimeError(message) from exc
    raise RuntimeError(message)


def is_open():
    return template.check_template("teleporter_title", 0.7)


def is_open_name_prompt():
    return template.check_template("teleporter_write_your_text", 0.7)  # Update this


def open():
    """Open the teleporter, stopping before unsafe recovery when suicide is forbidden."""
    allow_suicide = _suicide_recovery_allowed.get()
    attempts = 0
    dl = utils_simple.get_default_clock()

    while not is_open() and not dl():
        attempts += 1
        logs.logger.debug(
            f"trying to open teleporter {attempts} / {source.ASA.config.teleporter_open_attempts}"
        )

        dl2 = utils_simple.get_default_clock(3)
        while not dl2() and not is_open():
            utils.press_key("Use")
            if template.template_await_true(is_open, 0.3):
                break

        if not is_open():
            logs.logger.warning("teleporter didnt open retrying now")
            # check state of char which should close out of any windows we are in or rejoin the game
            player_state.check_state()

            look_down_teleport_safe()
            time.sleep(0.2)
        else:
            logs.logger.debug("teleporter opened")
            return True

        if dl():
            logs.logger.error(
                f"unable to open up the teleporter after {source.ASA.config.teleporter_open_attempts} attempts, eating implant and trying to reset"
            )
            if not allow_suicide:
                _stop_for_manual_recovery("teleporter did not open")

            bed.spawn_in(settings.bed_spawn)
            time.sleep(20)
            utils.zero_center()  # reseting the chars pitch/yaw
            look_down_teleport_raw()
            time.sleep(0.2)
            dl.reset()

    return False


def close():
    attempts = 0

    if is_open_name_prompt():
        windows.click(
            variables.get_pixel_loc("cancel_name_tp_x"),
            variables.get_pixel_loc("cancel_name_tp_y"),
        )
        time.sleep(0.1)

    while is_open():
        attempts += 1
        logs.logger.debug(
            f"trying to close the teleporter {attempts} / {source.ASA.config.teleporter_close_attempts}"
        )
        windows.click(
            variables.get_pixel_loc("back_button_tp_x"),
            variables.get_pixel_loc("back_button_tp_y"),
        )

        if not template.template_await_false(is_open, 2):
            return time.sleep(0.3)

        if attempts >= source.ASA.config.teleporter_close_attempts:
            logs.logger.error(
                f"unable to close the teleporter after {source.ASA.config.teleporter_close_attempts} attempts"
            )
            break


def look_down_teleport_safe():
    utils.set_pitch(-80)
    time.sleep(0.2)


def look_down_teleport_raw():
    utils.turn_down(180)


def look_down_teleport():
    look_down_teleport_raw()
    time.sleep(0.2)


def teleport_not_default(teleporter_name: str, fallback_bed_name=None):
    """Teleport to a named destination, optionally forbidding inventory-loss recovery."""
    global _last_teleporter_name
    _last_teleporter_name = teleporter_name
    allow_suicide = _suicide_recovery_allowed.get()

    fallback_bed_name = fallback_bed_name or settings.bed_spawn
    if not player_state.human.on_tp:
        # I'm not sure when this if will be called, but I'll keep it here because the original code already include it
        if not allow_suicide:
            _stop_for_manual_recovery(
                "reaching the teleporter requires bed fast travel"
            )
        look_down_teleport()
        bed.fast_travel(fallback_bed_name)
        time.sleep(0.2)

    if not is_open():
        look_down_teleport()
        open()

    if is_open():
        player_state.human.is_on_tp()

        dl = utils_simple.get_default_clock()
        while True:
            if dl():
                if not allow_suicide:
                    _stop_for_manual_recovery(
                        "teleporter destination list did not load"
                    )
                player_state.reset_state()
                time.sleep(0.3)

                bed.spawn_in(fallback_bed_name)

                look_down_teleport()

                open()
                if not is_open():
                    return

                dl.reset()

            # ENSURE TP IS OPEN AND SERVER LOADED PROCESS
            dl2 = utils_simple.get_default_clock(3)
            detected = False
            while not dl2():
                windows.click(
                    variables.get_pixel_loc("first_bed_slot_x"),
                    variables.get_pixel_loc("first_bed_slot_y"),
                )
                if template.template_await_true(template.check_teleporter_orange, 0.3):
                    # Server list loaded
                    detected = True
                    break
                else:
                    logs.logger.warning(
                        "orange pixel for teleporter ready not found - list not loaded"
                    )
                    if allow_suicide:
                        player_state.check_disconnected()

            if detected:
                break

            time.sleep(
                0.3
            )  # preventing the orange text from the starting teleport screen messing things up

        counter = 0
        while template.check_template_no_bounds("search", 0.7):
            counter += 1

            windows.click(
                variables.get_pixel_loc("search_bar_bed_alive_x"),
                variables.get_pixel_loc("search_bar_bed_y"),
            )  # im lazy this is the same position as the teleporter search bar

            utils.ctrl_a()
            utils.write(teleporter_name)
            time.sleep(0.5)
            if counter >= 3:
                logs.logger.error("search still detected likely did type anything")
                break

        dl = utils_simple.get_default_clock(3)
        while not template.check_teleporter_orange():
            windows.click(
                variables.get_pixel_loc("first_bed_slot_x"),
                variables.get_pixel_loc("first_bed_slot_y"),
            )
            if (
                template.template_await_true(template.check_teleporter_orange, 0.5)
                or dl()
            ):
                break

        if not template.check_teleporter_orange():
            logs.logger.warning(
                "orange pixel for teleporter ready not found likely already on the tp we are just exiting the tp treating it as the tp we should be on"
            )
            close()  # closing out as either the TP couldnt be found however we still want to change to the station yaw so we still continue
        else:
            windows.click(
                variables.get_pixel_loc("first_bed_slot_x"),
                variables.get_pixel_loc("first_bed_slot_y"),
            )
            time.sleep(0.2)
            windows.click(
                variables.get_pixel_loc("spawn_button_x"),
                variables.get_pixel_loc("spawn_button_y"),
            )

            if template.template_await_true(template.white_flash, 1):
                logs.logger.debug("white flash detected waiting for up too 5 seconds")
                template.template_await_false(template.white_flash, 5)

            # Extra step to ensure we are teleported(not sitting at the old teleport due to server lag/save)
            open()
            close()
            time.sleep(0.5)
            # DONE
        if (
            settings.singleplayer
        ):  # single player for some reason changes view angles when you tp
            utils.current_pitch = 0
            look_down_teleport()
