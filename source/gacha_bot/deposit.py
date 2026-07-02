import time
from typing import Literal

import settings
import source.gacha_bot.config
from source.ASA.player import player_inventory, player_state
from source.ASA.stations import custom_stations
from source.ASA.stations.custom_stations import station_metadata
from source.ASA.strucutres import inventory, teleporter
from source.gacha_bot import pego
from source.gacha_bot.deposit_config import DEDI_CONFIG_PATH
from source.gacha_bot.deposit_config import load_deposit_config as load_route_config
from source.logs import gachalogs as logs
from source.utility import template, utils, utils_simple, variables, windows
from source.utility.debug_screenshots import (
    CAPTURE_GRINDER_WITHDRAW,
    CAPTURE_ROUTE_READY,
    CAPTURE_VAULT_TRANSFER,
    capture_for,
)
from source.utility.structures.dedi import dedi
from source.utility.types import DediStorageState

capture_route_ready = capture_for("deposit_route_ready", active=CAPTURE_ROUTE_READY)
capture_grinder_after_withdraw = capture_for(
    "grinder_after_withdraw", active=CAPTURE_GRINDER_WITHDRAW, delay=0
)
capture_vault_after_transfer = capture_for(
    "vault_after_transfer", active=CAPTURE_VAULT_TRANSFER, delay=0
)

can_deposit_vault = True


def is_grinder():
    return template.check_template("grinder", 0.7)


def is_grinder_grindable():
    return template.check_template("grinder_grind_button", 0.7)


def load_deposit_config():
    try:
        return load_route_config(
            DEDI_CONFIG_PATH,
            create_missing=True,
            raise_on_missing=True,
        )
    except FileNotFoundError as exc:
        message = str(exc)
        logs.logger.error(message)
        raise RuntimeError(message) from exc
    except ValueError as exc:
        message = f"{DEDI_CONFIG_PATH} is invalid: {exc}"
        logs.logger.error(message)
        raise RuntimeError(message) from exc


def _items(container):
    if not isinstance(container, dict):
        return []
    items = container.get("items", [])
    if isinstance(items, list):
        return items
    return []


def _float_setting(container, key, default=0.0):
    try:
        return float(container.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _route_teleport_name(route: dict) -> str:
    teleport_name = route.get("teleport") if isinstance(route, dict) else None
    if not teleport_name:
        raise RuntimeError("Deposit route is missing a teleport name.")
    return teleport_name


def _teleport_to_route(route: dict) -> station_metadata:
    teleport_name = _route_teleport_name(route)
    metadata = custom_stations.get_station_metadata(teleport_name)
    logs.logger.debug(f"Teleporting to deposit route {teleport_name}")

    teleporter.teleport_not_default(metadata)

    return metadata


def _route_matches_metadata(route: dict, metadata: station_metadata | None) -> bool:
    return metadata is not None and getattr(
        metadata, "name", None
    ) == _route_teleport_name(route)


def _restore_route_view(metadata: station_metadata, reset_crouch: bool = True) -> None:
    if reset_crouch:
        player_state.human.reset_crouch()
    utils.zero_center(metadata.yaw)


def _set_object_crouch(item: DediStorageState) -> None:
    crouched = item.get("crouched", False) if isinstance(item, dict) else False
    if crouched:
        if not player_state.human.crouched:
            player_state.human.crouch()
            # time.sleep(0.2 * settings.lag_offset)
    elif player_state.human.crouched:
        player_state.human.reset_crouch()
        # time.sleep(0.2 * settings.lag_offset)


def _turn_to_object(item: DediStorageState) -> None:
    location = item.get("location", {}) if isinstance(item, dict) else {}
    yaw = _float_setting(location, "yaw", 0.0)
    pitch = _float_setting(location, "pitch", 0.0)
    _set_object_crouch(item)
    utils.turn_to(yaw, pitch)
    time.sleep(0.2 * settings.lag_offset)


def _open_inventory_template(template_name, route_metadata, route_object, object_name):
    inventory.open()
    attempt = 0
    dl = utils_simple.get_default_clock()
    while not template.template_await_true(
        template.check_template, 1, template_name, 0.7
    ):
        attempt += 1
        logs.logger.error(
            f"{object_name} was not opened; retrying {attempt}/{source.gacha_bot.config.grinder_attempts}"
        )
        inventory.close()
        _restore_route_view(route_metadata)
        _turn_to_object(route_object)
        inventory.open()
        if dl():
            logs.logger.error(f"{object_name} failed to open")
            return False
    return True


def open_crystals():
    count = 0
    while pego.is_crystal_hotbar_visible():
        for x in range(10):
            utils.press_key(f"UseItem{x + 1}")
            count += 1


def drop_useless():
    player_inventory.open()
    if player_inventory.is_open:
        player_inventory.drop_all_inv()
        time.sleep(0.2 * settings.lag_offset)
    player_inventory.close()


def process_fast_dedi(
    route: dict,
    item: DediStorageState,
    index: int,
    _type: Literal["crystal", "grinder"] = "crystal",
) -> bool:
    teleport_name = _route_teleport_name(route)
    label = f"{'Crystal' if _type == 'crystal' else 'Grindable'} dedi {index} on teleport {teleport_name}"
    logs.logger.debug(label)

    dedi.capture_name = label

    dedi.unsafe_fast_deposit_all(item)
    return True


def _process_vault(route, route_metadata, vault, index):
    global can_deposit_vault
    if not can_deposit_vault:
        return

    vault_items = _items(vault)
    if len(vault_items) == 0:
        return

    teleport_name = _route_teleport_name(route)
    label = f"Vault {index} on teleport {teleport_name}"
    logs.logger.debug(label)
    _turn_to_object(vault)

    if not _open_inventory_template("vault", route_metadata, vault, label):
        _restore_route_view(route_metadata, reset_crouch=False)
        return

    if player_inventory.is_open() and not player_inventory.is_can_transfer_all():
        can_deposit_vault = False
        return

    if inventory.is_open():
        time.sleep(0.1 * settings.lag_offset)
        for item_name in vault_items:
            player_inventory.search_in_inventory(item_name)
            player_inventory.transfer_all_inventory()
            player_inventory.wait_clear_search()
            time.sleep(0.3 * settings.lag_offset)
        capture_vault_after_transfer(label)

    if not player_inventory.is_can_transfer_all():
        can_deposit_vault = False

    inventory.close()


def _process_grinder(route, route_metadata):
    teleport_name = _route_teleport_name(route)
    label = f"Grinder on teleport {teleport_name}"
    logs.logger.debug(label)
    grinder = route.get("grinder", {})

    _turn_to_object(grinder)

    if not _open_inventory_template("grinder", route_metadata, grinder, label):
        _restore_route_view(route_metadata, reset_crouch=False)
        return

    if is_grinder():
        _grinder_1()
        player_inventory.close()
        time.sleep(0.3 * settings.lag_offset)

        with inventory.detect_lag_long_process():
            if not _open_inventory_template("grinder", route_metadata, grinder, label):
                _restore_route_view(route_metadata, reset_crouch=False)
                return
            if inventory.was_server_lag_last_open:
                _grinder_1()

    if is_grinder():
        inventory.transfer_all_from()
        time.sleep(0.2 * settings.lag_offset)
        capture_grinder_after_withdraw(label)
        inventory.close()
        time.sleep(0.2 * settings.lag_offset)


def _grinder_1():
    # Check turn on
    if not inventory.is_turned_on():
        inventory.turn_on()
        # NO NEED TO CLOSE INV BECAUSE THE GRINDER WILL UPDATE UI AUTOMATICALLY
        time.sleep(1 * settings.lag_offset)

    if not player_inventory.is_can_transfer_all():
        return

    player_inventory.transfer_all_inventory()
    template.template_await_true(is_grinder_grindable, 0.5)
    time.sleep(0.1 * settings.lag_offset)

    windows.click(
        variables.get_pixel_loc("grinder_grind_all_x"),
        variables.get_pixel_loc("grinder_grind_all_y"),
    )


def _process_crystal_routes(
    route: dict,
    open_first_route_crystals: bool = False,
    current_metadata: station_metadata | None = None,
    skip_if_current: bool = False,
) -> bool:
    if skip_if_current and _route_matches_metadata(route, current_metadata):
        route_metadata = current_metadata
        logs.logger.debug(
            f"Already on deposit route {_route_teleport_name(route)}; skipping teleport"
        )
    else:
        route_metadata = _teleport_to_route(route)

    if open_first_route_crystals:
        logs.logger.debug("opening crystals")
        open_crystals()

    capture_route_ready(f"Crystal route {_route_teleport_name(route)}")

    utils.zero_center()

    process_dedi_list_route(route, route_metadata, "crystal")

    # SLOW BUT SAFE DEPOSIT
    # for index, item in enumerate(_items(route.get("dedi", {})), start=1):
    #     if not _process_crystal_dedi(route, route_metadata, item, index):
    #         return False

    for index, vault in enumerate(_items(route.get("vault", {})), start=1):
        _process_vault(route, route_metadata, vault, index)

    return True


def _first_active_grinder_index(routes):
    for index, route in enumerate(routes):
        grinder = route.get("grinder", {}) if isinstance(route, dict) else {}
        if grinder.get("active", False):
            return index
    return None


def process_dedi_list_route(
    route: dict,
    route_metadata: station_metadata,
    _type: Literal["crystal", "grinder"] = "crystal",
):
    check_on_every_dedi = route["check_on_every_dedi"]
    batch_start_index = 0

    dedi_list = _items(route.get("dedi", {}))

    for index, item in enumerate(dedi_list):
        is_last_dedi = index == len(dedi_list) - 1
        should_check = (index + 1) % check_on_every_dedi == 0 or is_last_dedi
        if not should_check:
            process_fast_dedi(route, item, index, _type)
            continue

        with inventory.detect_lag_long_process():
            dedi.open_deposit_all(route_metadata, item)

            if inventory.was_server_lag_last_open:
                logs.logger.warning(
                    f"Server lag detected - retrying dedi from "
                    f"{batch_start_index + 1} to {index + 1}"
                )

                for retry_index in range(batch_start_index, index + 1):
                    retry_item = dedi_list[retry_index]
                    process_fast_dedi(route, retry_item, retry_index, _type)

        batch_start_index = index + 1
    return True


def _process_grindable_routes(routes: list[dict]) -> bool:
    if len(routes) == 0:
        logs.logger.warning(
            "No grindable routes configured in depositGrindableData; skipping grindable deposits."
        )
        return True

    active_index = _first_active_grinder_index(routes)
    if active_index is None:
        logs.logger.error(
            "No active grinder found in depositGrindableData; dropping useless inventory "
            "at the first grindable teleport and skipping grindable routes."
        )
        route_metadata = _teleport_to_route(routes[0])
        drop_useless()
        return True

    active_route = routes[active_index]
    route_metadata = _teleport_to_route(active_route)

    utils.zero_center()
    _process_grinder(active_route, route_metadata)

    # Process the current station where has same grinder
    utils.zero_center()
    if not process_dedi_list_route(active_route, route_metadata, "grinder"):
        return False

    # Process the rest stations except the one that has grinder
    for index, route in enumerate(routes):
        if index == active_index:
            continue
        route_metadata = _teleport_to_route(route)

        utils.zero_center()
        if not process_dedi_list_route(route, route_metadata, "grinder"):
            return False

    drop_useless()

    return True


def deposit_all(metadata: station_metadata | None) -> bool:
    global can_deposit_vault
    can_deposit_vault = True

    deposit_config = load_deposit_config()
    crystal_routes = deposit_config["depositCrystalData"]
    grindable_routes = deposit_config["depositGrindableData"]
    for index, route in enumerate(crystal_routes):
        if not _process_crystal_routes(
            route,
            open_first_route_crystals=index == 0,
            current_metadata=metadata if index == 0 else None,
            skip_if_current=index == 0,
        ):
            return False

    return _process_grindable_routes(grindable_routes) if can_deposit_vault else True
