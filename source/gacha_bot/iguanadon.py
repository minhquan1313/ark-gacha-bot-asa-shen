import time

import settings
import source.gacha_bot.config
from source.ASA.player import player_inventory, player_state
from source.ASA.strucutres import inventory, teleporter
from source.gacha_bot import stations
from source.logs import gachalogs as logs
from source.utility import template, utils, utils_simple
from source.utility.debug_screenshots import CAPTURE_IGUANADON_SEED, capture_for

IGUANODON_REMOTE_LAG_THRESHOLD_SECONDS = 3.0

capture_iguanadon_seed_withdraw = capture_for(
    "iguanadon_seed_withdraw", active=CAPTURE_IGUANADON_SEED
)
should_drop_useless = False


def is_tek_trough():
    return template.check_template("tek_trough", 0.7)


def _recover_berry_station():
    teleporter.teleport_not_default(teleporter._last_teleporter_name)

    if settings.external_berry:
        logs.logger.debug("sleeping for 20 seconds as external")
        time.sleep(
            settings.wait_structure_load
        )  # letting station spawn in if you have to tp away
    utils.zero_center()


def berry_collection(turn_down=0):
    global should_drop_useless
    attempt = 0
    dl = utils_simple.get_default_clock()

    while True:
        utils.turn_down(turn_down)
        time.sleep(0.5)

        inventory.open()

        if inventory.is_open() and is_tek_trough():
            if should_drop_useless:
                player_inventory.drop_all_inv()
                time.sleep(0.2)
                inventory.close()
                inventory.open()
                if not inventory.is_open():
                    _recover_berry_station()
                    continue

            inventory.transfer_all_from()
            inventory.close()
            return

        logs.logger.error(
            f"tek trough was not opened; retrying {attempt} / "
            f"{source.gacha_bot.config.tek_trough_attempts}"
        )
        # if failed to open inventory
        if dl():
            logs.logger.critical(
                "tek trough failed to open; suiciding and restarting berry station"
            )

            dl.reset()

            player_inventory.implant_eat()
            player_state.check_state()

        _recover_berry_station()


def berry_station():
    global should_drop_useless

    berry_collection(0)

    berry_collection(50)

    should_drop_useless = False


def _seed_reset():
    inventory.transfer_all_from()  # doing this should prevent the seed not appearing first try
    player_inventory.search_in_inventory(settings.berry_type)
    player_inventory.transfer_all_inventory()


def seed(type):
    if inventory.is_open():
        _seed_reset()
        inventory.close()

        # ENSURE PROCESS
        with inventory.detect_lag_long_process():
            iguanadon_open()
            if inventory.was_server_lag_last_open_long and inventory.is_open():
                time.sleep(1)
                _seed_reset()

        if (
            type == 2
            and stations.did_collect_tek_troughs
            and player_inventory.is_can_drop()
        ):
            time.sleep(0.2)
            player_inventory.drop_all_inv()  # doing this second time round to drop everything else that is not needed by the bot

            # ENSURE PROCESS
            inventory.close()
            iguanadon_open()

        time.sleep(0.1)
    inventory.close()

    utils.press_key("Use")
    time.sleep(2)

    iguanadon_open()
    if inventory.is_open():
        inventory.search_in_object("seed")

        if settings.iguanadon_seed_throw_amount > 0:
            inventory.popcorn(settings.iguanadon_seed_throw_amount)
            inventory.close()

            # ENSURE
            with inventory.detect_lag_long_process():
                iguanadon_open()
                if inventory.is_open() and inventory.was_server_lag_last_open_long:
                    inventory.search_in_object("seed")
                    inventory.popcorn(settings.iguanadon_seed_throw_amount)

        # FINAL
        inventory.transfer_all_from()
        time.sleep(0.3)

        capture_iguanadon_seed_withdraw(f"seed_{type}")
        inventory.close()

    time.sleep(0.2)


def iguanadon_open():
    attempt = 0
    time.sleep(0.2)
    inventory.open()
    while not inventory.is_open():
        attempt += 1
        logs.logger.debug(
            f"the iguanadon could not be accessed retrying {attempt} / {source.gacha_bot.config.iguanadon_attempts}"
        )
        utils.zero_center()
        time.sleep(0.2)
        inventory.open()
        if attempt >= source.gacha_bot.config.iguanadon_attempts:
            logs.logger.error(
                f"the iguanadon could not be accesssed after {attempt} attempts"
            )
            break


def iguanadon():
    iguanadon_open()
    seed(2)
