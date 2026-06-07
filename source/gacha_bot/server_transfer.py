import time
from dataclasses import dataclass
from pathlib import Path

from source.launcher.transfer_helper_config import (
    account_slot_for_target,
    active_transfer_dedis,
    missing_runtime_inputs,
    player_bed_name,
    runtime_account_count,
    transfer_dedi_route,
)

RECOVERABLE_RUNTIME_ATTEMPTS = 3


class TransferConfigError(RuntimeError):
    pass


@dataclass
class TransferDependencies:
    switch_account: object
    ensure_ark_running: object
    is_menu: object
    join_server: object
    verify_tribelog: object
    check_state: object
    wait_structure: object
    withdraw_resource: object
    fast_travel_to_bed: object
    enter_tekpod: object
    leave_tekpod: object
    transfer_to_server: object
    wait_for_bed_screen: object
    spawn_bed: object
    stabilize_bed_position: object
    deposit_resource: object
    kill_ark: object


def run_transfer_helper(config, stop_event, status_callback=None, dependencies=None):
    settings = config["settings"]
    dedis = config["dedis"]
    ui_coords = config["ui_coords"]
    players = config.get("players", {})
    missing = missing_runtime_inputs(settings, dedis, ui_coords, players)
    if missing:
        raise TransferConfigError(
            "Missing transfer helper inputs: " + ", ".join(missing)
        )

    deps = dependencies or default_transfer_dependencies(
        config, stop_event, status_callback
    )
    account_count = runtime_account_count(players)
    accounts = range(1, account_count + 1)
    current_account = 1

    def emit(message):
        if status_callback is not None:
            status_callback(message)

    def stopped():
        return stop_event is not None and stop_event.is_set()

    emit("Starting resource fill phase.")
    for account in accounts:
        if stopped():
            return False
        if account_count > 1:
            current_account = deps.switch_account(account, current_account)
        if stopped():
            return False
        if deps.ensure_ark_running() is False or stopped():
            return False
        was_in_menu = deps.is_menu()
        emit(
            f"Account {account}: joining resource server {settings['resource_server']}."
        )
        if not deps.join_server(settings["resource_server"]):
            if stopped():
                return False
            if account_count == 1:
                emit(
                    "Account 1: resource join did not complete; stopping without "
                    "closing ARK."
                )
                return False
            emit(
                f"Account {account}: resource join did not complete; skipping account."
            )
            continue
        if not deps.verify_tribelog():
            if account_count == 1:
                emit(
                    "Account 1: tribe log unavailable on resource server; "
                    "stopping so you can recover the character manually."
                )
                return False
            emit(
                f"Account {account}: tribe log unavailable on resource server; "
                "assuming character is elsewhere and skipping."
            )
            continue
        if stopped():
            return False
        if was_in_menu:
            deps.wait_structure()
            if stopped():
                return False
        deps.check_state(account)
        if stopped():
            return False
        if deps.withdraw_resource(account) is False or stopped():
            return False
        deps.fast_travel_to_bed(_bed_name(players, account))
        if stopped():
            return False
        deps.enter_tekpod()

    for loop_number in range(1, int(settings["loop_count"]) + 1):
        emit(f"Starting transfer loop {loop_number}/{settings['loop_count']}.")
        for account in accounts:
            if stopped():
                return False
            final_account = (
                loop_number == int(settings["loop_count"]) and account == account_count
            )
            if account_count > 1:
                current_account = deps.switch_account(account, current_account)
            if stopped():
                return False
            if deps.ensure_ark_running() is False or stopped():
                return False
            emit(f"Account {account}: joining resource server.")
            if not deps.join_server(settings["resource_server"]):
                emit(f"Account {account}: resource join failed; stopping.")
                return False
            if stopped():
                return False
            deps.wait_structure()
            if stopped():
                return False
            deps.leave_tekpod()
            if stopped():
                return False
            deps.transfer_to_server(settings["destination_server"], account)
            if stopped():
                return False
            deps.wait_for_bed_screen()
            if stopped():
                return False
            deps.spawn_bed(_bed_name(players, account))
            if stopped():
                return False
            deps.wait_structure()
            if stopped():
                return False
            deps.stabilize_bed_position()
            if stopped():
                return False
            if deps.deposit_resource(account) is False or stopped():
                return False
            deps.transfer_to_server(settings["resource_server"], account)
            if stopped():
                return False
            deps.wait_for_bed_screen()
            if stopped():
                return False
            deps.spawn_bed(_bed_name(players, account))
            if stopped():
                return False
            deps.wait_structure()
            if stopped():
                return False
            if deps.withdraw_resource(account) is False or stopped():
                return False
            if not final_account:
                if stopped():
                    return False
                deps.enter_tekpod()

    emit("Server transfer helper finished.")
    return True


def default_transfer_dependencies(config, stop_event, status_callback=None):
    settings = config["settings"]
    dedis = config["dedis"]
    ui_coords = config["ui_coords"]
    players = config.get("players", {})

    return TransferDependencies(
        switch_account=lambda target, current: switch_steam_account(
            target,
            current,
            runtime_account_count(players),
            ui_coords,
            stop_event,
            status_callback,
        ),
        ensure_ark_running=lambda: ensure_ark_running(
            stop_event, status_callback, settings, ui_coords
        ),
        is_menu=is_menu,
        join_server=lambda server: join_server(server, stop_event, status_callback),
        verify_tribelog=verify_tribelog,
        check_state=lambda account=None: check_transfer_player_state(
            settings, players, account, settings["resource_server"]
        ),
        wait_structure=lambda: stop_wait(
            stop_event, int(settings["structure_load_delay"])
        ),
        withdraw_resource=lambda account=None: withdraw_from_transfer_dedis(
            dedis, settings, stop_event, ui_coords, players, account
        ),
        fast_travel_to_bed=lambda name: fast_travel_to_bed(name, stop_event),
        enter_tekpod=enter_tekpod,
        leave_tekpod=leave_tekpod,
        transfer_to_server=lambda server, account=None: transfer_to_server(
            server, settings, ui_coords, stop_event, status_callback, players, account
        ),
        wait_for_bed_screen=lambda: wait_for_bed_screen(stop_event),
        spawn_bed=lambda name: spawn_bed(name, stop_event),
        stabilize_bed_position=stabilize_bed_position,
        deposit_resource=lambda account=None: deposit_to_transfer_dedis(
            dedis, ui_coords, settings, stop_event, players, account
        ),
        kill_ark=lambda: kill_ark(stop_event, ui_coords, status_callback),
    )


def switch_steam_account(
    target_account,
    current_account,
    account_count,
    ui_coords,
    stop_event,
    status_callback=None,
):
    if int(target_account) == int(current_account):
        return int(current_account)
    slot = account_slot_for_target(
        ui_coords, account_count, current_account, target_account
    )
    steam = ui_coords["steam"]
    emit = status_callback or (lambda _message: None)
    import pyautogui

    if not kill_ark(stop_event, ui_coords, emit):
        return int(current_account)
    if stop_wait(stop_event, 5):
        return int(current_account)
    from source.utility import template

    change_ready_template = _register_template_region(
        steam["change_account_ready_template"], steam["change_account_ready_region"]
    )
    switch_account_template = _register_template_region(
        steam["switch_account_template"], steam["switch_account_region"]
    )
    for attempt in range(1, RECOVERABLE_RUNTIME_ATTEMPTS + 1):
        if stop_event is not None and stop_event.is_set():
            return int(current_account)
        if not _ensure_steam_window_ready(
            steam, stop_event, emit, launch_if_missing=True
        ):
            return int(current_account)
        for key in ("menu", "change_account"):
            if stop_wait(stop_event, 0.2):
                return int(current_account)
            coord = steam[key]
            pyautogui.click(int(coord["x"]), int(coord["y"]))
        emit(
            "Waiting for Steam change-account continue button "
            f"({attempt}/{RECOVERABLE_RUNTIME_ATTEMPTS})."
        )
        ready = _wait_for_template_visible(
            template.check_template_no_bounds,
            float(steam.get("change_account_ready_timeout", 60)),
            stop_event,
            change_ready_template,
            0.75,
        )
        if stop_event is not None and stop_event.is_set():
            return int(current_account)
        if not ready:
            emit("Steam change-account continue button was not ready; retrying.")
            continue
        if stop_wait(stop_event, 0.2):
            return int(current_account)
        coord = steam["continue"]
        time.sleep(0.3 * settings_lag_offset())
        pyautogui.click(int(coord["x"]), int(coord["y"]))
        emit(
            f"Waiting for Steam account picker for account {target_account} "
            f"({attempt}/{RECOVERABLE_RUNTIME_ATTEMPTS})."
        )
        picker_ready = _wait_for_template_visible(
            template.check_template_no_bounds,
            float(steam.get("switch_account_timeout", 60)),
            stop_event,
            switch_account_template,
            0.75,
        )
        if stop_event is not None and stop_event.is_set():
            return int(current_account)
        if picker_ready:
            break
        emit("Steam account picker was not detected; retrying.")
    else:
        raise RuntimeError(
            "Steam account switch UI was not ready after "
            f"{RECOVERABLE_RUNTIME_ATTEMPTS} attempts."
        )
    pyautogui.click(int(slot["x"]), int(slot["y"]))
    if not _ensure_steam_window_ready(steam, stop_event, emit, launch_if_missing=False):
        return int(current_account)
    return int(target_account)


def ensure_ark_running(stop_event, status_callback=None, settings=None, ui_coords=None):
    import pyautogui

    from source.launcher.ark_game_setup import (
        ARK_PROCESS_NAME,
        launch_ark_through_steam,
    )
    from source.launcher.system import validate_ark_window
    from source.utility import template

    emit = status_callback or (lambda _message: None)
    timeout = _settings_int(settings, "ark_window_ready_timeout", 180)
    attempts = _settings_int(settings, "ark_launch_attempts", 3)
    last_error = None
    launched = False

    if ui_coords is None:
        return False
    steam = ui_coords["steam"]

    steam_unable_to_sync_template = _register_template_region(
        steam["steam_unable_to_sync_template"],
        steam["steam_unable_to_sync_region"],
    )

    for attempt in range(1, attempts + 1):
        if stop_event is not None and stop_event.is_set():
            return False
        if not _process_running(ARK_PROCESS_NAME):
            emit("Launching ARK through Steam.")
            launch_ark_through_steam()
            launched = True
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if stop_event is not None and stop_event.is_set():
                return False
            if _process_running(ARK_PROCESS_NAME):
                try:
                    window_size = validate_ark_window()
                    if launched:
                        return _prepare_ark_window_for_join(
                            stop_event, status_callback, window_size
                        )
                    return True
                except RuntimeError as exc:
                    last_error = exc
            # Sometime started same ARK through Steam when switch account will cause sync issues
            wont_sync = template.check_template_no_bounds(
                steam_unable_to_sync_template, 0.8
            )
            if wont_sync:
                if stop_wait(stop_event, 0.2):
                    return False
                coord = steam["steam_unable_to_sync_continue"]
                pyautogui.click(int(coord["x"]), int(coord["y"]))
            time.sleep(1)
        if stop_event is not None and stop_event.is_set():
            return False
        if attempt >= attempts:
            break
        emit(
            "ARK did not reach a usable window state; relaunching "
            f"({attempt}/{attempts})."
        )
        if not kill_ark(stop_event, status_callback=status_callback):
            return False
        if stop_wait(stop_event, 2):
            return False
        launched = False
    if last_error is not None:
        raise RuntimeError(
            "ARK did not reach a usable window state after "
            f"{attempts} attempt(s): {last_error}"
        )
    raise RuntimeError(f"ARK did not start after {attempts} attempt(s).")


def _prepare_ark_window_for_join(stop_event, status_callback=None, window_size=None):
    emit = status_callback or (lambda _message: None)
    emit("ARK detected. Focusing game before joining server.")
    if stop_wait(stop_event, 2):
        return False
    _focus_ark_window_for_join(window_size)
    return True


def _focus_ark_window_for_join(window_size=None):
    import pyautogui

    from source.launcher.deposit_helper_capture import focus_game_window

    focus_game_window(center_cursor_when_switching=True)
    _refresh_join_sim_ark_handle()
    width, height = window_size or (1920, 1080)
    pyautogui.click(int(width) // 2, int(height) // 2)


def _refresh_join_sim_ark_handle():
    from source.join_sim.source.utility import windows
    from source.launcher.constants import GAME_WINDOW_TITLE

    hwnd = _ark_window_handle(GAME_WINDOW_TITLE)
    if not hwnd:
        raise RuntimeError(f"{GAME_WINDOW_TITLE} window was not found.")
    windows.hwnd = hwnd
    return hwnd


def _ark_window_handle(window_title):
    import ctypes

    return ctypes.windll.user32.FindWindowW(None, window_title)


def is_menu():
    from source.join_sim.source import main

    return bool(main.is_menu())


def join_server(server, stop_event, status_callback=None):
    from source.join_sim.source.auto_join import run_auto_join_server
    from source.launcher.system import validate_ark_window

    if stop_event is not None and stop_event.is_set():
        return False
    _focus_ark_window_for_join(validate_ark_window())
    if stop_event is not None and stop_event.is_set():
        return False

    return run_auto_join_server(server, stop_event, status_callback)


def verify_tribelog():
    from source.ASA.player import tribelog

    tribelog.open()
    opened = tribelog.is_open()
    tribelog.close()
    return bool(opened)


def check_player_state():
    check_transfer_player_state({})


def check_transfer_player_state(settings, players=None, account=None, server=None):
    from source.ASA.player import buffs
    from source.ASA.strucutres import teleporter
    from source.gacha_bot import render

    check_transfer_disconnected(settings, server)
    reset_transfer_state(settings, players, account)
    buff_state = buffs.check_buffs().check_buffs()
    if buff_state == 1 or render.render_flag:
        render.leave_tekpod()
    elif buff_state == 2 or buff_state == 3:
        target = _bed_name(players or {}, account) if account is not None else ""
        if not target:
            target = str(settings.get("transmitter_teleport", "")).strip()
        if target:
            teleporter.transfer_teleport_not_default(target, fallback_bed_name=target)
            render.enter_tekpod()
            time.sleep(30)
            render.leave_tekpod()
            time.sleep(1)


def check_transfer_disconnected(settings, server):
    from source.ASA.player import tribelog
    from source.join_sim.source import main
    from source.logs import gachalogs as logs
    from source.utility import utils, windows

    if not (main.is_menu() or main.is_crashed()):
        return
    target_server = str(server or settings.get("resource_server", ""))
    logs.logger.critical("transfer helper disconnected from the server")
    windows.hwnd = main.main_loop(target_server)
    tribelog.close()
    logs.logger.critical(
        "transfer helper rejoined the server; waiting 30 seconds for structures"
    )
    time.sleep(30)
    yaw_key = (
        "destination_station_yaw"
        if str(target_server) == str(settings.get("destination_server"))
        else "resource_station_yaw"
    )
    utils.set_yaw(float(settings.get(yaw_key, 0.0)))


def reset_transfer_state(settings, players=None, account=None):
    from source.ASA.player import player_inventory, tribelog
    from source.ASA.strucutres import bed, teleporter
    from source.utility import utils

    player_inventory.close()
    teleporter.close()
    tribelog.close()
    if bed.is_open() and account is not None:
        bed.spawn_in(_bed_name(players or {}, account))
    utils.press_key("Run")


def withdraw_from_transfer_dedis(
    dedis, settings, stop_event, ui_coords=None, players=None, account=None
):
    import settings as global_settings
    from source.ASA.stations import custom_stations
    from source.ASA.strucutres import teleporter
    from source.gacha_bot import deposit
    from source.utility import utils

    global_settings.lag_offset = float(settings["lag_offset"])
    global_settings.station_yaw = float(settings["resource_station_yaw"])
    resource_route = transfer_dedi_route(dedis, "resource")
    route_metadata = custom_stations.get_station_metadata(resource_route["teleport"])
    fallback_bed_name = _fallback_bed_name(players, account)
    teleporter.transfer_teleport_not_default(
        route_metadata, fallback_bed_name=fallback_bed_name, stop_event=stop_event
    )
    deposit._restore_route_view(route_metadata)
    for index, item in enumerate(active_transfer_dedis(dedis, "resource"), 1):
        if stop_event is not None and stop_event.is_set():
            return False
        label = f"Transfer dedi {index}"
        if not _transfer_withdraw_from_dedi(
            route_metadata,
            item,
            label,
            settings,
            stop_event,
            ui_coords,
            fallback_bed_name,
        ):
            return False
    utils.set_yaw(float(settings["resource_station_yaw"]))
    return True


def deposit_to_transfer_dedis(
    dedis, ui_coords=None, settings=None, stop_event=None, players=None, account=None
):
    from source.ASA.stations import custom_stations

    destination_route = transfer_dedi_route(dedis, "destination")
    route_metadata = custom_stations.get_station_metadata(destination_route["teleport"])
    fallback_bed_name = _fallback_bed_name(players, account)
    for index, item in enumerate(active_transfer_dedis(dedis, "destination"), 1):
        if stop_event is not None and stop_event.is_set():
            return False
        if not _transfer_deposit_to_dedi(
            route_metadata,
            item,
            f"Transfer dedi {index}",
            settings or {},
            ui_coords or {},
            stop_event,
            fallback_bed_name,
        ):
            return False
    return True


def _transfer_withdraw_from_dedi(
    route_metadata,
    item,
    label,
    settings,
    stop_event=None,
    ui_coords=None,
    fallback_bed_name=None,
):
    from source.ASA.strucutres import inventory
    from source.gacha_bot import deposit
    from source.logs import gachalogs as logs

    timeout = _transfer_dedi_open_timeout(ui_coords)
    for attempt in range(1, RECOVERABLE_RUNTIME_ATTEMPTS + 1):
        if stop_event is not None and stop_event.is_set():
            inventory.close()
            return False
        if _open_transfer_dedi_inventory(
            route_metadata, item, label, timeout, stop_event
        ):
            inventory.transfer_all_from()
            inventory.close()
            logs.logger.debug(f"{label} transfer withdraw completed")
            return True
        inventory.close()
        logs.logger.error(
            f"{label} transfer withdraw timed out after {timeout} seconds "
            f"on attempt {attempt} / {RECOVERABLE_RUNTIME_ATTEMPTS}"
        )
        if attempt < RECOVERABLE_RUNTIME_ATTEMPTS:
            _recover_transfer_dedi_position(
                route_metadata, item, fallback_bed_name, stop_event
            )
    return False


def _transfer_deposit_to_dedi(
    route_metadata,
    item,
    label,
    settings,
    ui_coords,
    stop_event=None,
    fallback_bed_name=None,
):
    from source.ASA.strucutres import inventory
    from source.logs import gachalogs as logs
    from source.utility import template, utils, variables, windows

    transfer = ui_coords.get("transfer", {})
    ready_template = _register_template_region(
        transfer["dedi_deposit_ready_template"],
        transfer["dedi_deposit_ready_region"],
    )
    timeout = _transfer_dedi_open_timeout(ui_coords)
    attempts = int(transfer.get("dedi_init_attempts", RECOVERABLE_RUNTIME_ATTEMPTS))
    attempts = max(1, attempts)
    for attempt in range(1, attempts + 1):
        if stop_event is not None and stop_event.is_set():
            inventory.close()
            return False
        if not _open_transfer_dedi_inventory(
            route_metadata, item, label, timeout, stop_event
        ):
            inventory.close()
            logs.logger.error(
                f"{label} transfer deposit open timed out after {timeout} seconds "
                f"on attempt {attempt} / {attempts}"
            )
            if attempt < attempts:
                _recover_transfer_dedi_position(
                    route_metadata, item, fallback_bed_name, stop_event
                )
            continue
        if _wait_for_template_visible(
            template.check_template,
            0,
            None,
            ready_template,
            0.75,
        ):
            windows.click(
                variables.get_pixel_loc("dedi_deposit_x"),
                variables.get_pixel_loc("dedi_deposit_y"),
            )
            inventory.close()
            logs.logger.debug(f"{label} transfer deposit completed")
            return True
        logs.logger.warning(f"{label} destination dedi not initialized; initializing")
        if stop_event is not None and stop_event.is_set():
            inventory.close()
            return False
        init_coord = transfer["dedi_init_click"]
        windows.click(int(init_coord["x"]), int(init_coord["y"]))
        utils.press_key("T")
        inventory.close()
        if attempt < attempts:
            _recover_transfer_dedi_position(
                route_metadata, item, fallback_bed_name, stop_event
            )
    return False


def _recover_transfer_dedi_position(
    route_metadata, item, fallback_bed_name=None, stop_event=None
):
    from source.ASA.strucutres import teleporter
    from source.gacha_bot import deposit

    teleporter.transfer_teleport_not_default(
        route_metadata, fallback_bed_name=fallback_bed_name, stop_event=stop_event
    )
    deposit._restore_route_view(route_metadata)
    deposit._turn_to_object(route_metadata, item)


def _open_transfer_dedi_inventory(
    route_metadata, item, label, timeout, stop_event=None
):
    from source.ASA.strucutres import inventory
    from source.gacha_bot import deposit
    from source.utility import template, utils

    deposit._turn_to_object(route_metadata, item)
    time.sleep(0.3 * float(settings_lag_offset()))
    deadline = time.monotonic() + float(timeout)
    while time.monotonic() < deadline:
        if stop_event is not None and stop_event.is_set():
            inventory.close()
            return False
        utils.press_key("AccessInventory")
        if template.template_await_true(template.check_template, 2, "inventory", 0.7):
            waiting_for_remote = template.template_await_true(
                template.check_template, 2, "waiting_inv", 0.8
            )
            while (
                waiting_for_remote
                and time.monotonic() < deadline
                and template.check_template("inventory", 0.7)
            ):
                if stop_event is not None and stop_event.is_set():
                    inventory.close()
                    return False
                time.sleep(0.05)
                waiting_for_remote = template.check_template("waiting_inv", 0.8)
            if template.check_template("inventory", 0.7) and not waiting_for_remote:
                return True
        time.sleep(0.5 * float(settings_lag_offset()))
    return False


def _transfer_dedi_open_timeout(ui_coords):
    try:
        return float(ui_coords.get("transfer", {}).get("dedi_open_timeout", 60))
    except (AttributeError, TypeError, ValueError):
        return 60.0


def settings_lag_offset():
    try:
        import settings

        return float(getattr(settings, "lag_offset", 1))
    except Exception:
        return 1.0


def _settings_int(settings, key, default):
    try:
        value = settings.get(key, default)
    except AttributeError:
        value = default
    try:
        value = int(value)
    except (TypeError, ValueError):
        return int(default)
    return max(1, value)


def transfer_to_server(
    server,
    settings,
    ui_coords,
    stop_event,
    status_callback=None,
    players=None,
    account=None,
):
    import pyautogui

    from source.ASA.strucutres import inventory, teleporter
    from source.utility import template, utils

    emit = status_callback or (lambda _message: None)
    transfer = ui_coords["transfer"]
    yaw_key = (
        "resource_station_yaw"
        if str(server) == str(settings["destination_server"])
        else "destination_station_yaw"
    )
    transmitter_template = _register_template_region(
        transfer["transmitter_title_template"], transfer["transmitter_title_region"]
    )
    transmitter_open = False
    fallback_bed_name = _fallback_bed_name(players, account)
    for attempt in range(1, RECOVERABLE_RUNTIME_ATTEMPTS + 1):
        if stop_event is not None and stop_event.is_set():
            return False
        teleporter.transfer_teleport_not_default(
            settings["transmitter_teleport"],
            fallback_bed_name=fallback_bed_name,
            stop_event=stop_event,
        )
        utils.set_yaw(float(settings[yaw_key]))
        inventory.open()
        emit(
            "Checking transmitter inventory "
            f"({attempt}/{RECOVERABLE_RUNTIME_ATTEMPTS})."
        )
        transmitter_open = _wait_for_template_visible(
            template.check_template,
            2,
            stop_event,
            transmitter_template,
            0.7,
        )
        if transmitter_open:
            break
        if attempt < RECOVERABLE_RUNTIME_ATTEMPTS:
            emit("Transmitter inventory was not detected; recovering player state.")
            check_transfer_player_state(settings, players, account, server)
            stop_wait(stop_event, 0.5)
    if not transmitter_open:
        if stop_event is not None and stop_event.is_set():
            return False
        raise RuntimeError("Transmitter inventory was not detected.")
    _click_coord(transfer["transfer_button"])
    not_ready_template = _register_template_region(
        transfer["not_ready_template"], transfer["not_ready_region"]
    )
    while not (stop_event is not None and stop_event.is_set()):
        _click_coord(transfer["server_search"])
        pyautogui.hotkey("ctrl", "a")
        pyautogui.write(str(server))
        _click_coord(transfer["first_server"])
        _click_coord(transfer["join_button"])
        stop_wait(stop_event, 1)
        if not _wait_for_template_visible(
            template.check_template_no_bounds,
            0,
            stop_event,
            not_ready_template,
            0.75,
        ):
            emit(f"Transfer to server {server} requested.")
            return True
        _click_coord(transfer["transfer_not_ready_cancel"])
        emit(f"Server {server} transfer timer not ready; retrying.")
        stop_wait(stop_event, int(settings["transfer_retry_delay"]))
    return False


def wait_for_bed_screen(stop_event):
    from source.ASA.strucutres import bed

    while not (stop_event is not None and stop_event.is_set()):
        if bed.is_open():
            return True
        time.sleep(0.5)
    return False


def spawn_bed(name, stop_event=None):
    from source.ASA.strucutres import bed

    return bed.transfer_spawn_in(name, stop_event)


def fast_travel_to_bed(name, stop_event=None):
    from source.ASA.strucutres import bed

    return bed.transfer_fast_travel(name, stop_event)


def stabilize_bed_position():
    leave_tekpod()


def enter_tekpod():
    from source.gacha_bot import render

    render.enter_tekpod()


def leave_tekpod():
    from source.gacha_bot import render

    render.leave_tekpod()


def kill_ark(stop_event=None, ui_coords=None, status_callback=None):
    from source.launcher.ark_game_setup import kill_running_ark

    if not _logout_before_kill_ark(stop_event, ui_coords, status_callback):
        return False
    kill_running_ark()
    return True


def _logout_before_kill_ark(stop_event=None, ui_coords=None, status_callback=None):
    from source.launcher.deposit_helper_capture import focus_game_window

    emit = status_callback or (lambda _message: None)
    try:
        focus_game_window(center_cursor_when_switching=True)
    except RuntimeError:
        return False
    if stop_event is not None and stop_event.is_set():
        return False
    try:
        _refresh_join_sim_ark_handle()
    except RuntimeError:
        return False
    emit("Returning ARK to main menu before closing.")
    return _open_main_menu_until_safe_to_kill(stop_event, emit)


def _open_main_menu_until_safe_to_kill(stop_event, status_callback=None):
    emit = status_callback or (lambda _message: None)
    attempt = 0
    while not (stop_event is not None and stop_event.is_set()):
        attempt += 1
        if not _send_open_main_menu(stop_event, emit, attempt):
            continue
        if _wait_for_ark_main_menu(stop_event, timeout=30):
            return True
        else:
            emit("ARK main menu did not appear after loading; resetting console.")
        if not _reset_open_main_menu_console(stop_event):
            return False
    return False


def _send_open_main_menu(stop_event, status_callback=None, attempt=1):
    from source.ASA.player import console, player_state

    emit = status_callback or (lambda _message: None)
    if stop_event is not None and stop_event.is_set():
        return False
    try:
        emit(f"Opening ARK main menu (attempt {attempt}).")
        player_state.reset_state()
        console.console_write("open MainMenu")
        return True
    except Exception as exc:
        emit(f"open MainMenu failed: {exc}; resetting console.")
        _reset_open_main_menu_console(stop_event)
        return False


def _reset_open_main_menu_console(stop_event):
    from source.utility import utils

    utils.press_key("ConsoleKeys")
    if stop_wait(stop_event, 0.1):
        return False
    utils.press_key("Enter")
    return not (stop_event is not None and stop_event.is_set())


def _wait_for_ark_loading_screen(stop_event, timeout=30):
    deadline = time.monotonic() + float(timeout)
    while time.monotonic() < deadline:
        if stop_event is not None and stop_event.is_set():
            return False
        if _safe_check_join_template_no_bounds("loading_screen", 0.7):
            return True
        time.sleep(0.5)
    return bool(_safe_check_join_template_no_bounds("loading_screen", 0.7))


def _wait_for_ark_main_menu(stop_event, timeout=30):
    deadline = time.monotonic() + float(timeout)
    while time.monotonic() < deadline:
        if stop_event is not None and stop_event.is_set():
            return False
        if _safe_is_ark_main_menu():
            return True
        time.sleep(0.5)
    return bool(_safe_is_ark_main_menu())


def _safe_check_join_template_no_bounds(item, threshold):
    from source.join_sim.source.utility import recon_utils

    try:
        return bool(recon_utils.check_template_no_bounds(item, threshold))
    except Exception:
        return False


def _safe_is_ark_main_menu():
    from source.join_sim.source import main as join_main

    try:
        return bool(join_main.is_menu())
    except Exception:
        return False


def stop_wait(stop_event, seconds):
    if stop_event is not None:
        return stop_event.wait(seconds)
    time.sleep(seconds)
    return False


def _bed_name(players, account):
    return player_bed_name(players, account)


def _fallback_bed_name(players, account):
    if account is None:
        return None
    return _bed_name(players or {}, account)


def _click_coord(coord):
    import pyautogui

    pyautogui.click(int(coord["x"]), int(coord["y"]))


def _wait_for_template_visible(check_func, timeout, stop_event, *args):
    deadline = time.monotonic() + float(timeout)
    while time.monotonic() < deadline:
        if stop_event is not None and stop_event.is_set():
            return False
        if check_func(*args):
            return True
        time.sleep(0.05)
    return bool(check_func(*args))


def _register_template_region(template_path, region):
    from source.utility import template

    item = Path(str(template_path)).stem
    template.roi_regions[item] = {
        "start_x": int(region["start_x"]),
        "start_y": int(region["start_y"]),
        "width": int(region["width"]),
        "height": int(region["height"]),
    }
    return item


def _ensure_steam_window_ready(
    steam, stop_event, status_callback=None, launch_if_missing=True
):
    import subprocess

    emit = status_callback or (lambda _message: None)
    title = steam.get("window_title", "Steam")
    timeout = float(steam.get("window_ready_timeout", 5))
    last_error = None
    steam_exe = _running_steam_exe_path()
    if launch_if_missing:
        emit("Opening Steam window.")
        subprocess.Popen([str(steam_exe)])
    for attempt in range(1, RECOVERABLE_RUNTIME_ATTEMPTS + 1):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if stop_event is not None and stop_event.is_set():
                return False
            try:
                if _focus_steam_window_maximized(title):
                    return True
            except RuntimeError as exc:
                last_error = exc
            time.sleep(0.5)
        if stop_event is not None and stop_event.is_set():
            return False
        emit(
            "Steam window was not ready; restarting Steam "
            f"({attempt}/{RECOVERABLE_RUNTIME_ATTEMPTS})."
        )
        subprocess.run(["taskkill", "/f", "/im", "steam.exe"], check=False)
        if stop_wait(stop_event, 1):
            return False
        subprocess.Popen([str(steam_exe)])
    if last_error is not None:
        raise RuntimeError(f"Steam window was not ready after retries: {last_error}")
    raise RuntimeError(f"{title} window was not found after retries.")


def _focus_steam_window_maximized(window_title):
    import ctypes

    from source.launcher.system import focus_window_if_needed

    if not focus_window_if_needed(window_title, center_cursor_when_switching=True):
        return False
    hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
    if not hwnd:
        return False
    ctypes.windll.user32.ShowWindow(hwnd, 3)
    ctypes.windll.user32.BringWindowToTop(hwnd)
    return True


def _running_steam_exe_path():
    from source.launcher.ark_game_setup import find_running_steam_dir

    steam_exe = find_running_steam_dir() / "steam.exe"
    if not steam_exe.exists():
        raise RuntimeError(f"steam.exe was not found: {steam_exe}")
    return steam_exe


def _process_running(process_name):
    try:
        import psutil
    except ImportError:
        return False
    for proc in psutil.process_iter(attrs=["name"]):
        try:
            if str(proc.info.get("name", "")).lower() == process_name.lower():
                return True
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return False
