import time
from abc import ABC, abstractmethod

import settings
import source.gacha_bot.render
from source.ASA.player import console, player_inventory, player_state, tribelog
from source.ASA.strucutres import teleporter
from source.gacha_bot import deposit, gacha, iguanadon, pego, render
from source.gacha_bot.craft_config import valid_craft_route
from source.logs import gachalogs as logs
from source.utility import utils
from source.utility.types import CraftRoute

global berry_station
global last_berry
last_berry = 0
berry_station = True
did_collect_tek_troughs = False


class base_task(ABC):
    def __init__(self):
        self.has_run_before = False
        self.name = ""

    @abstractmethod
    def execute(self):
        pass

    @abstractmethod
    def get_priority_level(self):
        return int(0)

    @abstractmethod
    def get_requeue_delay(self):
        return int(0)

    def mark_as_run(self):
        self.has_run_before = True


def _iguanodon_seed():
    """Refill berries when due and prepare seeds using the shared station state."""

    global berry_station
    global last_berry
    global did_collect_tek_troughs

    temp = False
    time_between = time.time() - last_berry

    # if time is greater than 4 hours since the last time you went to berry station
    if berry_station or time_between > settings.time_to_reberry:
        # or if berry station is true( when you go to tekpod and drop all ) and the time between has been longer than 36 second since youve last been
        teleporter.teleport_not_default(settings.berry_station)
        if settings.external_berry:
            logs.logger.debug("sleeping for 20 seconds as external")
            time.sleep(
                settings.wait_structure_load
            )  # letting station spawn in if you have to tp away
        utils.zero_center()

        iguanadon.berry_station()
        last_berry = time.time()
        berry_station = False
        did_collect_tek_troughs = True
        temp = True
    else:
        did_collect_tek_troughs = False

    teleporter.teleport_not_default(settings.iguanadon)  # iguanadon is a centeral tp

    utils.zero_center()
    if settings.external_berry and temp:  # quick fix for level 1 bug
        logs.logger.debug(
            "reconnecting because of level 1 bug - you chose external berry will sleep for 60 seconds as a way to ensure that we are fully loaded in"
        )
        console.console_write("reconnect")
        # takes a while for the reonnect to actually go into action
        time.sleep(settings.wait_reconnect)
    iguanadon.iguanadon()


class gacha_station(base_task):
    def __init__(self, name, teleporter_name, direction):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name  # also the same as bed name for y
        self.direction = direction

    def execute(self):
        player_state.check_state()

        _iguanodon_seed()
        teleporter.teleport_not_default(self.teleporter_name)

        utils.zero_center()
        gacha.drop_off_nocrop(self.teleporter_name, self.direction)

    def get_priority_level(self):
        return 3

    def get_requeue_delay(self):
        return settings.gacha_feed_delay


class gacha_collect_station(base_task):
    def __init__(
        self,
        name: str,
        teleporter_name: str,
        direction: str,
        item: str,
        dedi_teleport: str = "",
    ):
        """Configure one collection task and its shared deposit destination."""
        super().__init__()
        self.name = f"C.{name}"
        self.teleporter_name = teleporter_name
        self.direction = direction
        self.item = item
        self.dedi_teleport = dedi_teleport

    def execute(self):
        """Feed, collect, and deposit at the selected station without crafting."""
        route = deposit.resolve_collection_destination(self.dedi_teleport)
        if not self.item.strip() or route is None:
            logs.logger.warning(
                f"Skipping {self.name}: configure an item and a valid Dedi destination."
            )
            return
        player_state.check_state()
        _iguanodon_seed()
        teleporter.teleport_not_default(self.teleporter_name)
        utils.zero_center()
        gacha.drop_off_nocrop(self.teleporter_name, self.direction, self.item)
        deposit.deposit_collection(route)

    def get_priority_level(self):
        return 4

    def get_requeue_delay(self):
        return settings.gacha_collect_feed_delay


class craft_station(base_task):
    def __init__(self, route: CraftRoute, index: int):
        """Schedule one configured crafter independently of gacha collection."""
        super().__init__()
        self.route = route
        self.name = f"Craft.{index + 1}.{route['teleport']}"

    def execute(self):
        """Craft and deposit this station's output."""
        if not valid_craft_route(self.route):
            logs.logger.warning(f"Skipping {self.name}: incomplete craft station.")
            return
        player_state.check_state()
        deposit.craft(self.route)

    def get_priority_level(self):
        """Run crafting after collection tasks that are ready."""
        return 5

    def get_requeue_delay(self):
        """Use the shared interval configured on the Craft page."""
        return settings.craft_delay


class pego_station(base_task):
    def __init__(self, name, teleporter_name, delay):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name
        self.delay = delay
        # self.is_first_run = True

    def execute(self):
        # DEBUG START
        # print("Start debugging")
        # recon_utils.IS_DEBUG = True
        # recon_utils.DEBUG_ITEM = "pause_menu"
        # recon_utils.DEBUG_BEEP = True
        # while True:
        #     main.is_pause_menu()
        #     time.sleep(0.3)

        # utils.zero_center()
        # transmitter.open_and_transfer(5842)
        # print("Done debugging - Waiting 9999")
        # raise RuntimeError("DONE DEBUG")
        # time.sleep(9999)

        player_state.check_state()

        teleporter.teleport_not_default(self.teleporter_name)
        utils.zero_center()

        pego.pego_pickup(self.teleporter_name)

        deposit.deposit_all()

    def get_priority_level(self):
        return 2  # highest prio level as we cant have these get capped

    def get_requeue_delay(self):
        # delay cannot be constant as stations can cover different amounts of space each |||| 2 stacks of berries to 1 crystal 4 gachas to 1 pego
        return self.delay


class render_station(base_task):
    def __init__(self):
        super().__init__()
        self.name = settings.bed_spawn

    def execute(self):
        global berry_station
        # setting to true as we will be away for mostlikly for a few hours
        berry_station = True

        if not source.gacha_bot.render.render_flag:
            logs.logger.debug(
                f"render flag{render.render_flag} we are trying to get into the pod now"
            )
            player_state.reset_state()
            teleporter.teleport_not_default(settings.bed_spawn)
            render.enter_tekpod()
            player_inventory.open()
            player_inventory.drop_all_inv()
            player_inventory.close()
            tribelog.open()
        else:
            player_state.check_disconnected()
            tribelog.close()
            time.sleep(1)
            tribelog.open()

    def get_priority_level(self):
        return 8

    def get_requeue_delay(self):
        return 30  # after triggered we will wait for 30 seconds reduces the amount of cpu usage
