import time
from typing import Literal, overload

import source.gacha_bot.config
from source.ASA.player import player_inventory, player_state
from source.ASA.strucutres import inventory, teleporter
from source.gacha_bot import pego
from source.gacha_bot.deposit_config import (
    DEDI_CONFIG_PATH,
    collection_destination_error,
)
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
from source.utility.types import (
    CrafterStorageState,
    CraftRoute,
    CrystalDepositRoute,
    DediStorageContainer,
    DediStorageState,
    DepositConfig,
    DepositRouteBase,
    GrindableDepositRoute,
    VaultStorageContainer,
    VaultStorageState,
)

capture_route_ready = capture_for("deposit_route_ready", active=CAPTURE_ROUTE_READY)
capture_grinder_after_withdraw = capture_for(
    "grinder_after_withdraw", active=CAPTURE_GRINDER_WITHDRAW, delay=0
)
capture_vault_after_transfer = capture_for(
    "vault_after_transfer", active=CAPTURE_VAULT_TRANSFER, delay=0
)

g_is_still_have_items = True


def is_grinder():
    return template.check_template("grinder", 0.7)


def is_grinder_grindable():
    return template.check_template("grinder_grind_button", 0.7)


def load_deposit_config() -> DepositConfig:
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


@overload
def _items(container: DediStorageContainer) -> list[DediStorageState]: ...


@overload
def _items(container: VaultStorageState) -> list[str]: ...


@overload
def _items(container: VaultStorageContainer) -> list[VaultStorageState]: ...


def _items(container: DediStorageContainer | VaultStorageContainer | VaultStorageState):
    return container["items"]


def _route_teleport_name(route: DepositRouteBase | CraftRoute):
    teleport_name = route.get("teleport")
    if not teleport_name:
        raise RuntimeError("Deposit route is missing a teleport name.")
    return teleport_name


def _teleport_to_route(route: DepositRouteBase | CraftRoute, *, cached=False):
    teleport_name = _route_teleport_name(route)
    logs.logger.debug(f"Teleporting to deposit route {teleport_name}")

    if cached and teleporter._last_teleporter_name == teleport_name:
        logs.logger.debug(f"Using cached teleport to {teleport_name}")
        return teleport_name

    teleporter.teleport_not_default(teleport_name)

    return teleport_name


def _restore_route_view(reset_crouch: bool = True):
    if reset_crouch:
        player_state.human.reset_crouch()
    utils.zero_center()


def _set_object_crouch(item: DediStorageState):
    crouched = item["crouched"]
    if crouched:
        if not player_state.human.crouched:
            player_state.human.crouch()
            # time.sleep(0.2)
    elif player_state.human.crouched:
        player_state.human.reset_crouch()
        # time.sleep(0.2)


def _turn_to_object(item: DediStorageState):
    location = item["location"]
    yaw = location["yaw"]
    pitch = location["pitch"]
    _set_object_crouch(item)
    utils.turn_to(yaw, pitch)
    time.sleep(0.2)


def _open_inventory_template(
    template_name: str,
    route_metadata: str,
    route_object: DediStorageState,
    object_name: str,
):
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
        _restore_route_view()
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
    player_state.human.reset_crouch()
    player_inventory.open()
    if player_inventory.is_open:
        player_inventory.drop_all_inv()
        time.sleep(0.2)
    player_inventory.close()


def process_fast_dedi(
    route: DepositRouteBase,
    item: DediStorageState,
    index: int,
    _type: str = "crystal",
):
    teleport_name = _route_teleport_name(route)
    label = f"{'Crystal' if _type == 'crystal' else 'Grindable'} dedi {index} on teleport {teleport_name}"
    logs.logger.debug(label)

    dedi.capture_name = label

    dedi.unsafe_fast_deposit_all(item)


def _process_vault(
    route: CrystalDepositRoute,
    route_metadata: str,
    vault: VaultStorageState,
    index: int,
):
    global g_is_still_have_items
    if not g_is_still_have_items:
        return

    vault_items = _items(vault)
    if len(vault_items) == 0:
        return

    teleport_name = _route_teleport_name(route)
    label = f"Vault {index} on teleport {teleport_name}"
    logs.logger.debug(label)
    _turn_to_object(vault)

    if not _open_inventory_template("vault", route_metadata, vault, label):
        _restore_route_view(False)
        return

    if player_inventory.is_open() and not player_inventory.is_can_transfer_all():
        g_is_still_have_items = False
        return

    if inventory.is_open():
        time.sleep(0.1)
        for item_name in vault_items:
            player_inventory.search_in_inventory(item_name)
            player_inventory.transfer_all_inventory()
            player_inventory.wait_clear_search()
            time.sleep(0.3)
        capture_vault_after_transfer(label)

    if not player_inventory.is_can_transfer_all():
        g_is_still_have_items = False

    inventory.close()


def _process_grinder(route: GrindableDepositRoute, route_metadata: str):
    teleport_name = _route_teleport_name(route)
    label = f"Grinder on teleport {teleport_name}"
    logs.logger.debug(label)
    grinder = route["grinder"]

    _turn_to_object(grinder)

    if not _open_inventory_template("grinder", route_metadata, grinder, label):
        _restore_route_view(False)
        return

    if is_grinder():
        _grinder_1()
        player_inventory.close()
        time.sleep(0.3)

        with inventory.detect_lag_long_process():
            if not _open_inventory_template("grinder", route_metadata, grinder, label):
                _restore_route_view(False)
                return
            if inventory.was_server_lag_last_open_long:
                _grinder_1()

    if is_grinder():
        inventory.transfer_all_from()
        time.sleep(0.2)
        capture_grinder_after_withdraw(label)
        inventory.close()
        time.sleep(0.2)


def _grinder_1():
    # Check turn on
    if not inventory.is_turned_on():
        inventory.turn_on()
        # NO NEED TO CLOSE INV BECAUSE THE GRINDER WILL UPDATE UI AUTOMATICALLY
        time.sleep(1)

    if not player_inventory.is_can_transfer_all():
        return

    player_inventory.transfer_all_inventory()
    if template.template_await_true(is_grinder_grindable, 1):
        time.sleep(0.1)

        windows.click(
            variables.get_pixel_loc("grinder_grind_all_x"),
            variables.get_pixel_loc("grinder_grind_all_y"),
        )
        time.sleep(0.1)


def _process_crystal_routes(
    route: CrystalDepositRoute,
    open_first_route_crystals: bool = False,
):
    global g_is_still_have_items
    route_metadata = _teleport_to_route(route)

    if not pego.is_crystal_hotbar_visible():
        g_is_still_have_items = False
        return

    if open_first_route_crystals:
        logs.logger.debug("opening crystals")
        open_crystals()

    capture_route_ready(f"Crystal route {_route_teleport_name(route)}")

    utils.zero_center()

    process_dedi_list_route(route, route_metadata, "crystal")

    for index, vault in enumerate(_items(route["vault"]), start=1):
        _process_vault(route, route_metadata, vault, index)


def _first_active_grinder_index(routes: list[GrindableDepositRoute]):
    for index, route in enumerate(routes):
        grinder = route["grinder"]
        if grinder["active"]:
            return index
    return None


def process_dedi_list_route(
    route: DepositRouteBase,
    teleporter: str,
    _type: Literal["crystal", "grinder", "crafter"] = "crystal",
):
    global g_is_still_have_items
    if not g_is_still_have_items:
        return True

    check_on_every_dedi = route["check_on_every_dedi"]
    batch_start_index = 0
    player_inventory.g_last_check_can_transfer = True

    dedi_list = _items(route["dedi"])

    for index, item in enumerate(dedi_list):
        is_last_dedi = index == len(dedi_list) - 1
        should_check = (index + 1) % check_on_every_dedi == 0 or is_last_dedi
        if not should_check:
            process_fast_dedi(route, item, index, _type)
            continue

        with inventory.detect_lag_long_process():
            dedi.open_deposit_all(teleporter, item)

            # if not is_last_dedi:
            #     utils.get_yaw_pitch()

            if not player_inventory.g_last_check_can_transfer:
                g_is_still_have_items = False
                return True

            # Case when user put check on every dedi = 1, so we need to ignore this loop
            if inventory.was_server_lag_last_open_long and batch_start_index <= index:
                logs.logger.warning(
                    f"Server lag detected - retrying dedi from "
                    f"{batch_start_index + 1} to {index + 1}"
                )
                utils.zero_center()
                for retry_index in range(batch_start_index, index + 1):
                    retry_item = dedi_list[retry_index]
                    process_fast_dedi(route, retry_item, retry_index, _type)

            if not is_last_dedi:
                utils.get_yaw_pitch(reset_state=False)

        batch_start_index = index + 1
    return True


def _process_grindable_routes(routes: list[GrindableDepositRoute]):
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


def resolve_collection_destination(dedi_teleport: str):
    """Resolve one unambiguous, usable teleport before collecting materials."""
    config = load_deposit_config()
    error = collection_destination_error(config, dedi_teleport)
    if error:
        logs.logger.warning(f"Collection destination {dedi_teleport!r}: {error}")
        return None
    for routes in (
        config["depositCrystalData"],
        config["depositGrindableData"],
        config["depositGeneralData"],
    ):
        for route in routes:
            if route["teleport"] == dedi_teleport:
                return route
    return None


def deposit_collection(route: DepositRouteBase):
    """Deposit collected materials only into this station's dedicated storage."""
    global g_is_still_have_items
    g_is_still_have_items = True
    _teleport_to_route(route)
    utils.get_yaw_pitch()
    return _deposit_collect_items(route, route["dedi"]["items"], "source-item")


def _deposit_collect_items(
    route: DepositRouteBase, items: list[DediStorageState], label: str
):
    """Deposit the player's current inventory through one collect-route dedi list."""
    if not items:
        logs.logger.warning(
            f"No {label} dedis configured on collect route {_route_teleport_name(route)}."
        )
        return False
    teleporter = _route_teleport_name(route)
    collect_route: DepositRouteBase = {
        "teleport": route["teleport"],
        "check_on_every_dedi": route["check_on_every_dedi"],
        "dedi": {"items": items},
    }
    return process_dedi_list_route(collect_route, teleporter, "crafter")


def open_crafter(crafter: CrafterStorageState):
    dl = utils_simple.get_default_clock()
    while not inventory.is_open():
        if dl():
            logs.logger.error("Crafter inventory could not be opened.")
            return False

        inventory.open()
        if not inventory.is_open():
            logs.logger.error("Crafter inventory could not be opened, retrying...")
            player_state.check_state()
            utils.get_yaw_pitch()
            _turn_to_object(crafter)

    return True


def craft(route: CraftRoute):
    """Visit one teleport and deposit each crafter's output into shared dedis."""
    global g_is_still_have_items
    g_is_still_have_items = True
    crafters = [crafter for crafter in route["crafters"] if crafter["item"].strip()]
    dedis = route["dedi"]["items"]
    if not route["teleport"].strip() or not dedis or not crafters:
        return False
    _teleport_to_route(route, cached=True)

    for i, crafter in enumerate(crafters):
        player_state.check_disconnected()
        utils.get_yaw_pitch()
        _turn_to_object(crafter)
        if not open_crafter(crafter):
            return False
        if not inventory.is_turned_on():
            inventory.turn_on()
            time.sleep(1)
        inventory.craft_item(crafter["item"], 12)
        inventory.transfer_all_from()
        inventory.wait_clear_search()
        inventory.close()

        # Ensure the crafter interaction has completed before depositing output.
        if not open_crafter(crafter):
            return False
        inventory.close()
        g_is_still_have_items = player_inventory.g_last_check_can_drop

        if not g_is_still_have_items:
            logs.logger.warning(
                f"Stop craft from crafter {i + 1}[{crafter['item']}] as detected no resource to craft"
            )
            return True

        if not _deposit_collect_items(route, dedis, "crafted-item"):
            return False
    return True


def deposit_all():
    global g_is_still_have_items
    g_is_still_have_items = True

    deposit_config = load_deposit_config()
    crystal_routes = deposit_config["depositCrystalData"]
    grindable_routes = deposit_config["depositGrindableData"]
    for index, route in enumerate(crystal_routes):
        if g_is_still_have_items:
            _process_crystal_routes(
                route,
                open_first_route_crystals=index == 0,
            )
        else:
            break

    return (
        _process_grindable_routes(grindable_routes) if g_is_still_have_items else True
    )
