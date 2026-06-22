import time
from abc import ABC, abstractmethod

import settings
import source.gacha_bot.config
import source.gacha_bot.render
from source.ASA.player import console, player_inventory, player_state, tribelog
from source.ASA.stations import custom_stations
from source.ASA.strucutres import teleporter
from source.gacha_bot import deposit, gacha, iguanadon, pego, render
from source.logs import gachalogs as logs
from source.utility import template, utils

global berry_station
global last_berry
last_berry = 0
berry_station = True


class base_task(ABC):
    def __init__(self):
        self.has_run_before = False
        self.name = ""

    @abstractmethod
    def execute(self):
        pass

    @abstractmethod
    def get_priority_level(self) -> int:
        pass

    @abstractmethod
    def get_requeue_delay(self) -> int:
        pass

    def mark_as_run(self):
        self.has_run_before = True


class gacha_station(base_task):
    def __init__(self, name, teleporter_name, direction):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name  # also the same as bed name for y
        self.direction = direction

    def execute(self):
        player_state.check_state()
        global berry_station
        global last_berry

        temp = False
        time_between = time.time() - last_berry

        gacha_metadata = custom_stations.get_station_metadata(self.teleporter_name)
        gacha_metadata.side = self.direction

        berry_metadata = custom_stations.get_station_metadata(settings.berry_station)
        iguanadon_metadata = custom_stations.get_station_metadata(settings.iguanadon)
        if (
            berry_station
            or time_between > source.gacha_bot.config.time_to_reberry * 60 * 60
        ):  # if time is greater than 4 hours since the last time you went to berry station
            teleporter.teleport_not_default(
                berry_metadata
            )  # or if berry station is true( when you go to tekpod and drop all ) and the time between has been longer than 30 mins since youve last been
            if settings.external_berry:
                logs.logger.debug("sleeping for 20 seconds as external")
                time.sleep(20)  # letting station spawn in if you have to tp away
            utils.zero_center()

            iguanadon.berry_station(berry_metadata)
            last_berry = time.time()
            berry_station = False
            temp = True

        teleporter.teleport_not_default(
            iguanadon_metadata
        )  # iguanadon is a centeral tp
        utils.zero_center()

        if settings.external_berry and temp:  # quick fix for level 1 bug
            logs.logger.debug(
                "reconnecting because of level 1 bug - you chose external berry will sleep for 60 seconds as a way to ensure that we are fully loaded in"
            )
            console.console_write("reconnect")
            time.sleep(60)  # takes a while for the reonnect to actually go into action

        iguanadon.iguanadon(iguanadon_metadata)
        teleporter.teleport_not_default(gacha_metadata)
        utils.zero_center()

        if settings.side_crop_plot:
            gacha.drop_off(gacha_metadata)
        else:
            gacha.drop_off_nocrop(gacha_metadata)

    def get_priority_level(self):
        return 3

    def get_requeue_delay(self):
        if settings.seeds_230:
            delay = (
                settings.gacha_230_feed_delay
            )  # should take about this amount of time to do 230 slots of seeds
        else:
            # delay can be constant as it will be the same for all gachas 142 stacks took 110 mins
            delay = settings.gacha_feed_delay
        return delay


class pego_station(base_task):
    def __init__(self, name, teleporter_name, delay):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name
        self.delay = delay

    def execute(self):
        player_state.check_state()

        # print("Start debugging")
        # while True:
        #     template.check_template_no_bounds("search_player_inv", 0.7)
        #     time.sleep(0.3)

        # transmitter.open_and_transfer(5842)
        # print("Done debugging - Waiting 9999")
        # time.sleep(9999)

        pego_metadata = custom_stations.get_station_metadata(self.teleporter_name)
        teleporter.teleport_not_default(pego_metadata)
        utils.zero_center()

        pego.pego_pickup(pego_metadata)
        if template.check_template("crystal_in_hotbar", 0.7):
            deposit.deposit_all(None)
        else:
            logs.logger.info(
                "Bot has no crystals in hotbar we are skipping the deposit step"
            )

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
        berry_station = (
            True  # setting to true as we will be away for mostlikly for a few hours
        )
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

    def get_priority_level(self):
        return 8

    def get_requeue_delay(self):
        return 30  # after triggered we will wait for 30 seconds reduces the amount of cpu usage


class pause(base_task):
    def __init__(self, time):
        super().__init__()
        self.name = "pause"
        self.time = time

    def execute(self):
        player_state.check_state()
        teleporter.teleport_not_default(settings.bed_spawn)
        render.enter_tekpod()
        time.sleep(self.time)
        render.leave_tekpod()

    def get_priority_level(self):
        return 1

    def get_requeue_delay(self):
        return 0


class crafting(base_task):
    def __init__(self): ...
    def execute(self): ...
    def get_priority_level(self):
        return 7

    def get_requeue_delay(self):
        return 90


class transfer(base_task):
    def __init__(self): ...
    def execute(self): ...
    def get_priority_level(self):
        return

    def get_requeue_delay(self):
        return 0
