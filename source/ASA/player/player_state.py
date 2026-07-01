import time

import settings
import source.gacha_bot.render
from source.ASA.player import buffs, console, player_inventory, tribelog
from source.ASA.strucutres import bed, teleporter
from source.join_sim.source import main
from source.logs import gachalogs as logs
from source.utility import template, utils
from source.utility.debug_screenshots import (
    CAPTURE_PLAYER_STATE,
    capture_for,
)
from source.utility.structures.transmitter import transmitter

global crouched
global uploaded
global human
crouched = False
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


def check_disconnected():
    if main.is_menu() or main.is_crashed():
        logs.logger.critical("we are disconnected from the server")
        # DEBUG START
        capture_state("disconnected")
        # DEBUG END
        main.main_loop(str(settings.server_number))
        tribelog.close()
        logs.logger.warning(
            "joined back into the server waiting 30 seconds to render everything "
        )
        # DEBUG START
        capture_state("joined")
        # DEBUG END
        time.sleep(30)  # letting everything load back in
        utils.zero_center()
        return True
    return False


def reset_state():
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

    # makes the char stand up doing this at the end ensures we arent in any inventory
    human.reset_crouch()


def check_state():  # mainliy checked at the start of every task to check for food / water on the char
    check_disconnected()
    reset_state()
    buff = buffs.check_buffs()
    type = buff.check_buffs()
    if (
        type == 1 or source.gacha_bot.render.render_flag
    ):  # type 1 is when char is in the tekpod
        logs.logger.debug(
            f"tekpod buff found on screen leaving tekpod now reason | type : {type} render flag : {source.gacha_bot.render.render_flag}"
        )
        source.gacha_bot.render.leave_tekpod()
    elif type == 2 or type == 3:
        logs.logger.warning(
            f"tping back to render bed to replenish food and water | 2= water 3= food | reason:{type}"
        )
        teleporter.teleport_not_default(settings.bed_spawn)
        source.gacha_bot.render.enter_tekpod()
        time.sleep(
            30
        )  # assuming 30 seconds should replenish the player back to 100/100
        source.gacha_bot.render.leave_tekpod()
        time.sleep(1)
