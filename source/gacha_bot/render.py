import time

import pyautogui

import settings
import source.gacha_bot.config
from source.ASA.player import buffs, player_inventory, player_state
from source.ASA.strucutres import bed, teleporter
from source.logs import gachalogs as logs
from source.utility import (
    local_player,
    template,
    utils,
    utils_simple,
    variables,
    windows,
)

global render_flag
render_flag = False  # starts as false as obviously we are not rendering anything


def is_open():
    return template.check_template_no_bounds("bed_radical", 0.6)


def enter_tekpod(allow_eat_implant=True):
    global render_flag
    attempts = 0
    player_state.check_disconnected()
    dl = utils_simple.get_default_clock()
    while not render_flag:
        attempts += 1

        if attempts > source.gacha_bot.config.render_attempts:
            attempts = 0
            player_state.check_state()
            teleporter.teleport_not_default(settings.bed_spawn)
            utils.zero_center()

            if dl():
                logs.logger.warning(
                    f"{attempts} attempts however bot could not get into the render bed we are dieing and respawning to try and fix this"
                )

                if allow_eat_implant:
                    player_inventory.implant_eat()
                    player_state.check_state()  # this should respawn our char in the bed
                else:
                    teleporter.teleport_not_default(settings.bed_spawn)

                attempts = 0
                dl.reset()
                utils.zero_center()

            time.sleep(0.3 * settings.lag_offset)

        player_state.human.reset_crouch()

        utils.zero_center_no_ccc()
        utils.turn_down(15)
        time.sleep(0.3 * settings.lag_offset)

        pyautogui.keyDown(
            chr(utils.keymap_return(local_player.get_input_settings("Use")))
        )

        if not template.template_await_true(
            template.check_template_no_bounds, 1, "bed_radical", 0.6
        ):
            pyautogui.keyUp(
                chr(utils.keymap_return(local_player.get_input_settings("Use")))
            )
            time.sleep(0.5 * settings.lag_offset)
            utils.press_key(local_player.get_input_settings("Run"))

            utils.zero_center()
            utils.turn_down(15)
            time.sleep(0.3 * settings.lag_offset)
            pyautogui.keyDown(
                chr(utils.keymap_return(local_player.get_input_settings("Use")))
            )
            time.sleep(0.5 * settings.lag_offset)

        if template.template_await_true(
            template.check_template_no_bounds, 1, "bed_radical", 0.6
        ):
            time.sleep(0.2 * settings.lag_offset)
            windows.move_mouse(
                variables.get_pixel_loc("radical_laydown_x"),
                variables.get_pixel_loc("radical_laydown_y"),
            )
            time.sleep(0.5 * settings.lag_offset)
            pyautogui.keyUp(
                chr(utils.keymap_return(local_player.get_input_settings("Use")))
            )
            time.sleep(1)
        buff = buffs.check_buffs()
        if buff.check_buffs() == 1:
            logs.logger.debug(
                f"bot is now in the render pod rendering the station after {attempts} attempts"
            )
            render_flag = True
            utils.current_pitch = (
                0  # resetting the pitch for when char leaves the tekpod
            )
        else:
            player_state.check_state()
            logs.logger.error(
                f"we were unable to get into the tekpod on the {attempts} attempt retrying now"
            )

        if attempts >= source.gacha_bot.config.render_attempts:
            logs.logger.error(
                f"we were unable to get into the tekpod after {attempts} attempts pausing execution to avoid unbreakable loops"
            )
            break


def leave_tekpod():
    global render_flag
    player_state.check_disconnected()
    player_state.reset_state()

    time.sleep(0.2 * settings.lag_offset)
    utils.press_key(local_player.get_input_settings("Use"))
    time.sleep(1 * settings.lag_offset)

    buff = buffs.check_buffs()
    if buff.check_buffs() == 1:
        utils.zero_opposite()

        utils.press_key(local_player.get_input_settings("Use"))
        time.sleep(1 * settings.lag_offset)

        dl = utils_simple.get_default_clock()
        while buff.check_buffs() == 1 and not dl():
            player_state.check_disconnected()
            utils.zero_opposite()

            time.sleep(1)
    # Somehow if pressed open tek pod, then we should close it
    bed.close()

    player_state.check_disconnected()
    player_state.reset_state()
    render_flag = False


def fast_travel_to_render():
    if render_flag:
        # we need to leave tekpod and look at it
        leave_tekpod()
        return
    if player_state.human.on_tp:
        # we need to tp to render tp
        teleporter.teleport_not_default(settings.bed_spawn)
