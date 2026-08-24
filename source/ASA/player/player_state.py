import time

import settings
import source.gacha_bot.render
from source.ASA.player import buffs, console, player_inventory, tribelog
from source.ASA.strucutres import bed, teleporter
from source.join_sim.source import main
from source.join_sim.source.menus import success
from source.logs import gachalogs as logs
from source.utility import template, utils, utils_simple
from source.utility.debug_screenshots import (
    CAPTURE_PLAYER_STATE,
    capture_for,
)
from source.utility.structures.transmitter import transmitter

uploaded = False

capture_state = capture_for("player_state", active=CAPTURE_PLAYER_STATE)


class charecter:
    def __init__(self):
        self.crouched = True
        self.weight = 0
        self.health = 0
        self.water = 0
        self.food = 0
        self.bed = False
        self.tp = False
        self.on_bed = False
        self.on_tp = True  # should be starting on a tp anyway

    def crouch(self):
        if not self.crouched:
            utils.press_key("Crouch")
            time.sleep(0.1)  # takes time to crouch and view angles to change
        self.crouched = True

    def reset_crouch(self):
        if self.crouched:
            for _x in range(3):  # just ensuring that we are standing up properly
                utils.press_key("Run")
            time.sleep(0.1)  # takes time to uncrouch ensuring that it has properly
        self.crouched = False

    def is_on_bed(self):
        self.on_bed = True
        self.on_tp = False

    def is_on_tp(self):
        self.on_tp = True
        self.on_bed = False


human = charecter()


def smart_wait_structure_with_teleport(
    *,
    wait_structure: float = 0.0,
    should_close_teleport=False,
    first_wait=5,
    should_check_state=True,
):
    """
    PLAYER MUST NOT IN TEK POD, but don't worry, this one has "check_state" anyway =)))

    Assume player just spawned from transfer server, and already on top of a teleporter

    Return True if structures are loaded -> Good to go, but teleport screen will remain at the end

    Return False if structures are not loaded, likely due to server error like it won't load structure unless player move around a bit
    """

    if wait_structure <= 0:
        wait_structure = settings.wait_structure_load

    delay = wait_structure

    time.sleep(max(0, first_wait))

    if should_check_state:
        check_state()  # Leave tek pod if in tek pod

    teleporter.look_down_teleport()

    dl = utils_simple.get_default_clock(delay)
    while not teleporter.is_open():
        dl2 = utils_simple.get_default_clock(3)
        while not dl2() and not teleporter.is_open():
            utils.press_key("Use")
            if template.template_await_true(teleporter.is_open, 0.3):
                break

        if not teleporter.is_open():
            if dl():
                return False

            logs.logger.warning("teleporter didnt open retrying now")

            utils.press_key("Jump")
            time.sleep(1.3)
            # check state of char which should close out of any windows we are in or rejoin the game
            check_state()

            teleporter.look_down_teleport_safe()
            time.sleep(0.2)
        else:
            # Good to go
            # No need to close teleport, as later it will always open teleport anyway
            if should_close_teleport:
                teleporter.close()

            return True
    return True


def check_disconnected():
    if main.is_menu() or main.is_crashed():
        logs.enable_log()

        logs.logger.critical("We are disconnected from the server", exc_info=True)
        # DEBUG START
        capture_state("disconnected")
        # DEBUG END
        main.main_loop(settings.server_number)
        tribelog.close()
        if not bed.is_open():
            # Checking in case the upcoming screen is a bed spawn from previous server transfer
            logs.logger.warning(
                f"joined back into the server waiting {settings.wait_structure_load} seconds to render everything "
            )
            # DEBUG START
            capture_state("joined")
            # DEBUG END
            if success.was_has_logs:
                # letting everything load back in
                smart_wait_structure_with_teleport()
        return True
    return False


def reset_state(crouch=True):
    logs.logger.debug("resetting char state now")
    console.close()
    player_inventory.close()
    teleporter.close()
    tribelog.close()
    transmitter.close()

    # Ensure not the bed_title from teleport but the actual bed spawn screen
    if template.template_await_false(bed.is_open, 1):
        # guessing the char died will respawn it if the char hasnt died and it just in a tekpod screen it will just exit when it cant find its target bed
        bed.spawn_in(settings.bed_spawn)

    if crouch:
        # makes the char stand up doing this at the end ensures we arent in any inventory
        human.reset_crouch()


def check_state(*, crouch=True, should_replesh=True, should_wait_structure=True):
    # mainliy checked at the start of every task to check for food / water on the char
    if check_disconnected():
        utils.was_initialized = False
        return

    reset_state(crouch)
    buff = buffs.check_buffs()
    type = buff.check_buffs()
    if type == 1 or source.gacha_bot.render.render_flag:
        # type 1 is when char is in the tekpod
        logs.logger.debug(
            f"tekpod buff found on screen leaving tekpod now reason | type : {type} render flag : {source.gacha_bot.render.render_flag}"
        )
        source.gacha_bot.render.leave_tekpod()
    elif (type == 2 or type == 3) and should_replesh:
        logs.logger.warning(
            f"tping back to render bed to replenish food and water | 2= water 3= food | reason:{type}"
        )
        teleporter.teleport_not_default(settings.bed_spawn)
        source.gacha_bot.render.enter_tekpod()
        # assuming 30 seconds should replenish the player back to 100/100
        time.sleep(30)
        source.gacha_bot.render.leave_tekpod()
        time.sleep(1)

    if not utils.was_initialized:
        logs.logger.debug("Doing init location")
        utils.was_initialized = True

        utils.get_yaw_pitch()
        if should_wait_structure:
            smart_wait_structure_with_teleport(should_check_state=False, first_wait=0)
