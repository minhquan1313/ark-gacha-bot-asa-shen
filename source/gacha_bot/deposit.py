import time
import settings
import json
from source.utility import utils ,template , windows ,variables ,screen ,local_player
from source.logs import gachalogs as logs
from source.ASA.strucutres import teleporter , inventory
from source.ASA.stations import custom_stations
from source.ASA.player import player_inventory , player_state
import source.gacha_bot.config
from source.gacha_bot.deposit_config import DEDI_CONFIG_PATH
from source.gacha_bot.deposit_config import load_deposit_config as load_route_config


def load_deposit_config():
    try:
        return load_route_config(
            DEDI_CONFIG_PATH,
            crystal_teleport=settings.drop_off,
            grindable_teleport=settings.grindables,
            create_missing=True,
            raise_on_missing=True,
        )
    except FileNotFoundError as exc:
        message = str(exc)
        logs.logger.error(message)
        raise RuntimeError(message)
    except ValueError as exc:
        message = f"{DEDI_CONFIG_PATH} is invalid: {exc}"
        logs.logger.error(message)
        raise RuntimeError(message)


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


def _route_teleport_name(route):
    teleport_name = route.get("teleport") if isinstance(route, dict) else None
    if not teleport_name:
        raise RuntimeError("Deposit route is missing a teleport name.")
    return teleport_name


def _teleport_to_route(route):
    teleport_name = _route_teleport_name(route)
    metadata = custom_stations.get_station_metadata(teleport_name)
    logs.logger.debug(f"teleporting to deposit route {teleport_name}")
    teleporter.teleport_not_default(metadata)
    return metadata


def _restore_route_view(metadata):
    player_state.human.reset_crouch()
    utils.set_pitch(0)
    utils.set_yaw(metadata.yaw)


def _turn_to_object(route_metadata, item):
    location = item.get("location", {}) if isinstance(item, dict) else {}
    yaw = _float_setting(location, "yaw", 0.0)
    pitch = _float_setting(location, "pitch", 0.0)
    utils.set_pitch(0)
    utils.set_yaw(route_metadata.yaw)
    crouched = item.get("crouched", False) if isinstance(item, dict) else False
    if crouched:
        player_state.human.crouch()
    else:
        player_state.human.reset_crouch()
    utils.turn_to(yaw, pitch)


def _open_inventory_template(
    template_name, route, route_metadata, route_object, object_name
):
    teleport_name = _route_teleport_name(route)
    inventory.open()
    attempt = 0
    while not template.template_await_true(
        template.check_template, 1, template_name, 0.7
    ):
        attempt += 1
        logs.logger.error(
            f"{object_name} on teleport {teleport_name} was not opened; retrying"
        )
        inventory.close()
        _restore_route_view(route_metadata)
        _turn_to_object(route_metadata, route_object)
        inventory.open()
        if attempt >= source.gacha_bot.config.grinder_attempts:
            logs.logger.error(
                f"{object_name} on teleport {teleport_name} failed to open"
            )
            return False
    return True


def open_crystals():
    count = 0
    while template.check_template("crystal_in_hotbar",0.7) and count < 450: # count is alittle higher incase while pressing the button it doesnt triger
        for x in range(10):
            utils.press_key(f"UseItem{x+1}")
            count += 1


def drop_useless():
    player_inventory.open()
    if template.check_template("inventory",0.7):
        player_inventory.drop_all_inv()
        time.sleep(0.2*settings.lag_offset)
    player_inventory.close()


def _process_crystal_dedi(route, route_metadata, item, index):
    teleport_name = _route_teleport_name(route)
    label = f"Crystal dedi {index} on teleport {teleport_name}"
    logs.logger.debug(label)
    _turn_to_object(route_metadata, item)
    time.sleep(0.3 * settings.lag_offset)
    utils.press_key("Use")
    time.sleep(0.3 * settings.lag_offset)
    _restore_route_view(route_metadata)


def _process_vault(route, route_metadata, vault, index):
    vault_items = _items(vault)
    if len(vault_items) == 0:
        return

    teleport_name = _route_teleport_name(route)
    label = f"Vault {index} on teleport {teleport_name}"
    logs.logger.debug(label)
    _turn_to_object(route_metadata, vault)
    time.sleep(0.2 * settings.lag_offset)

    if not _open_inventory_template("vault", route, route_metadata, vault, label):
        _restore_route_view(route_metadata)
        return

    if template.template_await_true(template.check_template, 1, "inventory", 0.7):
        time.sleep(0.1 * settings.lag_offset)
        for item_name in vault_items:
            player_inventory.search_in_inventory(item_name)
            player_inventory.transfer_all_inventory()
            time.sleep(0.3 * settings.lag_offset)
    inventory.close()
    template.template_await_false(template.check_template, 1, "inventory", 0.7)
    time.sleep(0.2 * settings.lag_offset)
    _restore_route_view(route_metadata)


def _process_grinder(route, route_metadata):
    teleport_name = _route_teleport_name(route)
    label = f"Grinder on teleport {teleport_name}"
    logs.logger.debug(label)
    grinder = route.get("grinder", {})
    _turn_to_object(route_metadata, grinder)
    time.sleep(0.5 * settings.lag_offset)

    if not _open_inventory_template("grinder", route, route_metadata, grinder, label):
        _restore_route_view(route_metadata)
        return

    if template.check_template("grinder", 0.7):
        player_inventory.transfer_all_inventory()
        time.sleep(0.3 * settings.lag_offset)
        windows.click(
            variables.get_pixel_loc("dedi_withdraw_x"),
            variables.get_pixel_loc("dedi_withdraw_y"),
        )
        time.sleep(0.3 * settings.lag_offset)
        inventory.close()

    template.template_await_false(template.check_template, 1, "inventory", 0.7)
    time.sleep(0.2 * settings.lag_offset)

    if not _open_inventory_template("grinder", route, route_metadata, grinder, label):
        _restore_route_view(route_metadata)
        return

    if template.check_template("grinder", 0.7):
        inventory.transfer_all_from()
        time.sleep(0.2 * settings.lag_offset)
        inventory.close()

    template.template_await_false(template.check_template, 1, "inventory", 0.7)
    time.sleep(0.2 * settings.lag_offset)
    _restore_route_view(route_metadata)


def _process_grindable_dedi(route, route_metadata, item, index):
    teleport_name = _route_teleport_name(route)
    label = f"Grindable dedi {index} on teleport {teleport_name}"
    logs.logger.debug(label)
    _turn_to_object(route_metadata, item)
    time.sleep(0.3 * settings.lag_offset)
    utils.press_key("Use")
    time.sleep(0.3 * settings.lag_offset)
    _restore_route_view(route_metadata)


def _process_crystal_route(route, open_first_route_crystals=False):
    route_metadata = _teleport_to_route(route)
    if open_first_route_crystals:
        logs.logger.debug("opening crystals")
        open_crystals()

    for index, item in enumerate(_items(route.get("dedi", {})), start=1):
        _process_crystal_dedi(route, route_metadata, item, index)

    for index, vault in enumerate(_items(route.get("vault", {})), start=1):
        _process_vault(route, route_metadata, vault, index)

    _restore_route_view(route_metadata)


def _first_active_grinder_index(routes):
    for index, route in enumerate(routes):
        grinder = route.get("grinder", {}) if isinstance(route, dict) else {}
        if grinder.get("active", False):
            return index
    return None


def _process_grindable_route(route, route_metadata):
    for index, item in enumerate(_items(route.get("dedi", {})), start=1):
        _process_grindable_dedi(route, route_metadata, item, index)
    _restore_route_view(route_metadata)


def _process_grindable_routes(routes):
    active_index = _first_active_grinder_index(routes)
    if active_index is None:
        logs.logger.error(
            "No active grinder found in depositGrindableData; dropping useless inventory "
            "at the first grindable teleport and skipping grindable routes."
        )
        route_metadata = _teleport_to_route(routes[0])
        drop_useless()
        _restore_route_view(route_metadata)
        return

    active_route = routes[active_index]
    route_metadata = _teleport_to_route(active_route)
    _process_grinder(active_route, route_metadata)
    _process_grindable_route(active_route, route_metadata)

    for index, route in enumerate(routes):
        if index == active_index:
            continue
        route_metadata = _teleport_to_route(route)
        _process_grindable_route(route, route_metadata)


def deposit_all(metadata):
    deposit_config = load_deposit_config()
    crystal_routes = deposit_config["depositCrystalData"]
    grindable_routes = deposit_config["depositGrindableData"]

    for index, route in enumerate(crystal_routes):
        _process_crystal_route(route, open_first_route_crystals=index == 0)

    _process_grindable_routes(grindable_routes)
