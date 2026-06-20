import time
from dataclasses import dataclass
from pathlib import Path

from source.launcher.transfer_helper_config import (
    active_transfer_dedis,
    missing_runtime_inputs,
    player_bed_name,
    player_steam_account,
    runtime_account_count,
    transfer_dedi_route,
)

RECOVERABLE_RUNTIME_ATTEMPTS = 3
STEAM_DIALOG_BUTTONS = {
    "launch_option_select": {"x": 800, "y": 450},
    "launch_option_checkbox": {"x": 756, "y": 628},
    "launch_option_play": {"x": 1000, "y": 525},
    #
    "cloud_sync_conflict_play": {"x": 1066, "y": 644},
}


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


def run_transfer_helper(config, status_callback=None, dependencies=None):
    settings = config["settings"]
    dedis = config["dedis"]
    ui_coords = config["ui_coords"]
    players = config.get("players", {})
    missing = missing_runtime_inputs(
        settings,
        dedis,
        ui_coords,
        players,
        steam_accounts=config.get("steam_accounts"),
    )
    if missing:
        raise TransferConfigError(
            "Missing transfer helper inputs: " + ", ".join(missing)
        )

    deps = dependencies or default_transfer_dependencies(config, status_callback)
    account_count = runtime_account_count(players)
    accounts = range(1, account_count + 1)
    current_steam_account = _steam_account(players, 1)

    def emit(message):
        if status_callback is not None:
            status_callback(message)

    def stopped():
        return False

    emit("Starting resource fill phase.")
    for account in accounts:
        if stopped():
            return False
        if account_count > 1:
            current_steam_account = deps.switch_account(account, current_steam_account)
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
        emit(f"Starting destination loop {loop_number}/{settings['loop_count']}.")
        for account in accounts:
            if stopped():
                return False
            if account_count > 1:
                current_steam_account = deps.switch_account(
                    account, current_steam_account
                )
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
            if loop_number < int(settings["loop_count"]):
                if deps.withdraw_resource(account) is False or stopped():
                    return False
                deps.enter_tekpod()

    emit("Server transfer helper finished.")
    return True


def default_transfer_dependencies(config, status_callback=None):
    settings = config["settings"]
    dedis = config["dedis"]
    ui_coords = config["ui_coords"]
    players = config.get("players", {})

    return TransferDependencies(
        switch_account=lambda target, current: switch_steam_account(
            target,
            current,
            players,
            ui_coords,
            status_callback,
        ),
        ensure_ark_running=lambda: ensure_ark_running(
            status_callback, settings, ui_coords
        ),
        is_menu=is_menu,
        join_server=lambda server: join_server(server, status_callback),
        verify_tribelog=verify_tribelog,
        check_state=lambda account=None: check_transfer_player_state(
            settings, players, account, settings["resource_server"]
        ),
        wait_structure=lambda: time.sleep(int(settings["structure_load_delay"])),
        withdraw_resource=lambda account=None: withdraw_from_transfer_dedis(
            dedis, settings, ui_coords, players, account
        ),
        fast_travel_to_bed=fast_travel_to_bed,
        enter_tekpod=enter_tekpod,
        leave_tekpod=leave_tekpod,
        transfer_to_server=lambda server, account=None: transfer_to_server(
            server, settings, ui_coords, status_callback, players, account
        ),
        wait_for_bed_screen=wait_for_bed_screen,
        spawn_bed=spawn_bed,
        stabilize_bed_position=stabilize_bed_position,
        deposit_resource=lambda account=None: deposit_to_transfer_dedis(
            dedis, ui_coords, settings, players, account
        ),
        kill_ark=lambda: kill_ark(ui_coords, status_callback),
    )


def switch_steam_account(
    target_account,
    current_steam_account,
    players,
    ui_coords,
    status_callback=None,
):
    target_steam_account = _steam_account(players, target_account)
    if not target_steam_account:
        raise RuntimeError(f"Player {target_account} has no Steam account assigned.")
    if target_steam_account == current_steam_account:
        return current_steam_account
    emit = status_callback or (lambda _message: None)
    from source.launcher import steam_accounts

    emit(f"Switching Steam account to {target_steam_account}.")
    kill_ark(ui_coords, emit)
    steam_accounts.select_auto_login_account(target_steam_account)
    steam_accounts.close_steam()
    time.sleep(float(ui_coords.get("steam", {}).get("restart_delay", 8)))
    # steam_accounts.launch_ark_with_steam()
    return target_steam_account


def ensure_ark_running(status_callback=None, settings=None, ui_coords=None):
    from source.launcher.ark_game_setup import (
        ARK_PROCESS_NAME,
        launch_ark_through_steam,
    )
    from source.launcher.system import validate_ark_window
    from source.utility import utils

    emit = status_callback or (lambda _message: None)
    timeout = _settings_int(settings, "ark_window_ready_timeout", 120)
    attempts = _settings_int(settings, "ark_launch_attempts", 3)
    last_error = None
    launched = False

    if ui_coords is None:
        return False
    steam = ui_coords["steam"]

    for attempt in range(1, attempts + 1):
        if not _process_running(ARK_PROCESS_NAME):
            emit("Launching ARK through Steam.")
            launch_ark_through_steam()
            launched = True
        deadline = utils.timed_out_counter(timeout)
        while not deadline():
            if _process_running(ARK_PROCESS_NAME):
                try:
                    window_size = validate_ark_window()
                    if launched:
                        return _prepare_ark_window_for_join(
                            status_callback, window_size
                        )
                    return True
                except RuntimeError as exc:
                    last_error = exc
            steam_has_failure(steam, emit)
            time.sleep(1)
        if attempt >= attempts:
            break
        emit(
            "ARK did not reach a usable window state; relaunching "
            f"({attempt}/{attempts})."
        )
        if not kill_ark(status_callback=status_callback):
            return False
        time.sleep(2)
        launched = False
    if last_error is not None:
        raise RuntimeError(
            "ARK did not reach a usable window state after "
            f"{attempts} attempt(s): {last_error}"
        )
    raise RuntimeError(f"ARK did not start after {attempts} attempt(s).")


def _prepare_ark_window_for_join(status_callback=None, window_size=None):
    emit = status_callback or (lambda _message: None)
    emit("ARK detected. Focusing game before joining server.")
    time.sleep(2)
    _focus_ark_window_for_join(window_size)
    return True


def _focus_ark_window_for_join(window_size=None):
    import pyautogui

    from source.launcher.deposit_helper_capture import focus_game_window

    focus_game_window(center_cursor_when_switching=True)
    _refresh_join_sim_ark_handle()
    # Click in middle of screen to skip the intro and quickly go to the main menu, which can help with faster joins
    width, height = window_size or (1920, 1080)
    pyautogui.click(int(width) // 2, int(height) // 2)


def _refresh_join_sim_ark_handle():
    from source.launcher.constants import GAME_WINDOW_TITLE

    hwnd = _ark_window_handle(GAME_WINDOW_TITLE)
    if not hwnd:
        raise RuntimeError(f"{GAME_WINDOW_TITLE} window was not found.")
    return hwnd


def _ark_window_handle(window_title):
    import ctypes

    return ctypes.windll.user32.FindWindowW(None, window_title)


def is_menu():
    from source.join_sim.source import main

    return bool(main.is_menu())


def join_server(server, status_callback=None):
    from source.join_sim.source.auto_join import run_auto_join_server
    from source.launcher.system import validate_ark_window

    _focus_ark_window_for_join(validate_ark_window())

    return run_auto_join_server(server, status_callback)


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
            teleporter.teleport_not_default(target, fallback_bed_name=target)
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
    main.main_loop(target_server)
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
    dedis, settings, ui_coords=None, players=None, account=None
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
    teleporter.teleport_not_default(route_metadata, fallback_bed_name=fallback_bed_name)
    deposit._restore_route_view(route_metadata)
    for index, item in enumerate(active_transfer_dedis(dedis, "resource"), 1):
        label = f"Transfer dedi {index}"
        if not _transfer_withdraw_from_dedi(
            route_metadata,
            item,
            label,
            settings,
            ui_coords,
            fallback_bed_name,
        ):
            return False
    utils.set_yaw(float(settings["resource_station_yaw"]))
    return True


def deposit_to_transfer_dedis(
    dedis, ui_coords=None, settings=None, players=None, account=None
):
    from source.ASA.stations import custom_stations

    destination_route = transfer_dedi_route(dedis, "destination")
    route_metadata = custom_stations.get_station_metadata(destination_route["teleport"])
    fallback_bed_name = _fallback_bed_name(players, account)
    for index, item in enumerate(active_transfer_dedis(dedis, "destination"), 1):
        if not _transfer_deposit_to_dedi(
            route_metadata,
            item,
            f"Transfer dedi {index}",
            settings or {},
            ui_coords or {},
            fallback_bed_name,
        ):
            return False
    return True


def _transfer_withdraw_from_dedi(
    route_metadata,
    item,
    label,
    settings,
    ui_coords=None,
    fallback_bed_name=None,
):
    from source.ASA.strucutres import inventory
    from source.logs import gachalogs as logs

    timeout = _transfer_dedi_open_timeout(ui_coords)
    for attempt in range(1, RECOVERABLE_RUNTIME_ATTEMPTS + 1):
        if _open_transfer_dedi_inventory(route_metadata, item, label, timeout):
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
            _recover_transfer_dedi_position(route_metadata, item, fallback_bed_name)
    return False


def _transfer_deposit_to_dedi(
    route_metadata,
    item,
    label,
    settings,
    ui_coords,
    fallback_bed_name=None,
):
    from source.ASA.strucutres import inventory
    from source.logs import gachalogs as logs
    from source.utility import template, utils, variables, windows

    transfer = ui_coords.get("transfer", {})
    ready_template = _template_item(transfer["dedi_deposit_ready_template"])
    timeout = _transfer_dedi_open_timeout(ui_coords)
    attempts = int(transfer.get("dedi_init_attempts", RECOVERABLE_RUNTIME_ATTEMPTS))
    attempts = max(1, attempts)
    for attempt in range(1, attempts + 1):
        if not _open_transfer_dedi_inventory(route_metadata, item, label, timeout):
            inventory.close()
            logs.logger.error(
                f"{label} transfer deposit open timed out after {timeout} seconds "
                f"on attempt {attempt} / {attempts}"
            )
            if attempt < attempts:
                _recover_transfer_dedi_position(route_metadata, item, fallback_bed_name)
            continue
        if _wait_for_template_visible(
            template.check_template,
            0,
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
        init_coord = transfer["dedi_init_click"]
        windows.click(int(init_coord["x"]), int(init_coord["y"]))
        utils.press_key("T")
        inventory.close()
        if attempt < attempts:
            _recover_transfer_dedi_position(route_metadata, item, fallback_bed_name)
    return False


def _recover_transfer_dedi_position(route_metadata, item, fallback_bed_name=None):
    from source.ASA.strucutres import teleporter
    from source.gacha_bot import deposit

    teleporter.teleport_not_default(route_metadata, fallback_bed_name=fallback_bed_name)
    deposit._restore_route_view(route_metadata)
    deposit._turn_to_object(route_metadata, item)


def _open_transfer_dedi_inventory(route_metadata, item, label, timeout):
    from source.ASA.strucutres import inventory
    from source.gacha_bot import deposit
    from source.utility import template, utils

    deposit._turn_to_object(route_metadata, item)
    time.sleep(0.3 * float(settings_lag_offset()))

    deadline = utils.timed_out_counter(float(timeout))
    while not deadline():
        inventory.open()
        if inventory.is_open():
            return True

        inventory.close()
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


def steam_launch_option_is_open():
    from source.utility import template

    try:
        return bool(template.check_template_no_bounds("steam_launch_option", 0.8))
    except Exception:
        return False


def steam_cloud_sync_conflict_is_open():
    from source.utility import template

    try:
        return bool(template.check_template_no_bounds("steam_cloud_sync_conflic", 0.8))
    except Exception:
        return False


def steam_has_failure(steam, status_callback=None):
    """Handle known Steam launch dialogs before ARK becomes usable."""
    emit = status_callback or (lambda _message: None)
    if not _focus_visible_steam_window(steam, emit):
        return False

    import pyautogui

    if steam_launch_option_is_open():
        emit("Detected Steam launch option dialog.")
        _click_steam_button(pyautogui, "launch_option_select")
        time.sleep(0.2)
        _click_steam_button(pyautogui, "launch_option_checkbox")
        time.sleep(0.2)
        _click_steam_button(pyautogui, "launch_option_play")
        time.sleep(0.2)
        return True

    if steam_cloud_sync_conflict_is_open():
        emit("Detected Steam cloud sync conflict dialog.")
        _click_steam_button(pyautogui, "cloud_sync_conflict_play")
        time.sleep(0.2)
        return True

    return False


def _focus_visible_steam_window(steam: dict | None, status_callback=None) -> bool:
    """Focus and maximize Steam only when its window exists and is visible."""
    import ctypes

    emit = status_callback or (lambda _message: None)
    title = "Steam"
    if isinstance(steam, dict):
        title = steam.get("window_title") or title

    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return False
    if not user32.IsWindowVisible(hwnd):
        return False

    try:
        return bool(_focus_steam_window_maximized(title))
    except RuntimeError as exc:
        emit(f"Steam window focus failed: {exc}")
        return False


def _click_steam_button(pyautogui, button_name):
    coord = STEAM_DIALOG_BUTTONS[button_name]
    pyautogui.click(int(coord["x"]), int(coord["y"]))


def _coord_complete(value):
    if not isinstance(value, dict):
        return False
    return value.get("x") is not None and value.get("y") is not None


def transfer_to_server(
    server,
    settings,
    ui_coords,
    status_callback=None,
    players=None,
    account=None,
):
    from source.ASA.strucutres import teleporter
    from source.utility import utils
    from source.utility.structures.transmitter import transmitter

    emit = status_callback or (lambda _message: None)
    yaw_key = (
        "resource_station_yaw"
        if str(server) == str(settings["destination_server"])
        else "destination_station_yaw"
    )
    fallback_bed_name = _fallback_bed_name(players, account)
    for attempt in range(1, RECOVERABLE_RUNTIME_ATTEMPTS + 1):
        teleporter.teleport_not_default(
            settings["transmitter_teleport"],
            fallback_bed_name=fallback_bed_name,
        )
        utils.set_yaw(float(settings[yaw_key]))
        emit(
            f"Transferring to server {server} "
            f"({attempt}/{RECOVERABLE_RUNTIME_ATTEMPTS})."
        )
        if transmitter.open_and_transfer(server):
            emit(f"Transfer to server {server} requested.")
            return True
        if attempt < RECOVERABLE_RUNTIME_ATTEMPTS:
            emit("Transmitter transfer did not complete; recovering player state.")
            check_transfer_player_state(settings, players, account, server)
            time.sleep(0.5)
    raise RuntimeError(f"Transfer to server {server} did not complete.")


def wait_for_bed_screen():
    from source.ASA.strucutres import bed

    while True:
        if bed.is_open():
            return True
        time.sleep(0.5)


def spawn_bed(name):
    from source.ASA.strucutres import bed

    bed.spawn_in(name)
    return True


def fast_travel_to_bed(name):
    from source.ASA.strucutres import bed

    bed.fast_travel(name)
    return True


def stabilize_bed_position():
    leave_tekpod()


def enter_tekpod():
    from source.gacha_bot import render

    render.enter_tekpod()


def leave_tekpod():
    from source.gacha_bot import render

    render.leave_tekpod()


def kill_ark(ui_coords=None, status_callback=None):
    close_ark_with_console_exit(status_callback)
    return True


def close_ark_with_console_exit(status_callback=None):
    from source.launcher.deposit_helper_capture import focus_game_window
    from source.utility import utils

    emit = status_callback or (lambda _message: None)
    attempt = 0
    while True:
        attempt += 1
        if not _ark_window_exists():
            return True
        try:
            focus_game_window(center_cursor_when_switching=True)
            _send_ark_exit_command(emit, attempt)
        except Exception as exc:
            emit(f"ARK exit command failed: {exc}; retrying.")
        deadline = utils.timed_out_counter(10)
        while not deadline():
            if not _ark_window_exists():
                return True
            time.sleep(0.5)
        emit("ARK window is still visible after exit command; retrying.")


def _send_ark_exit_command(status_callback=None, attempt=1):
    from source.ASA.player import console, player_state

    emit = status_callback or (lambda _message: None)
    emit(f"Closing ARK with console exit (attempt {attempt}).")
    player_state.reset_state()
    console.console_write("exit")


def _ark_window_exists():
    from source.launcher.constants import GAME_WINDOW_TITLE

    return bool(_ark_window_handle(GAME_WINDOW_TITLE))


def _reset_open_main_menu_console():
    from source.utility import utils

    utils.press_key("ConsoleKeys")
    time.sleep(0.1)
    utils.press_key("Enter")
    return True


def _wait_for_ark_loading_screen(timeout=30):
    from source.utility import utils

    deadline = utils.timed_out_counter(float(timeout))
    while not deadline():
        if _safe_check_join_template_no_bounds("loading_screen", 0.7):
            return True
        time.sleep(0.5)
    return bool(_safe_check_join_template_no_bounds("loading_screen", 0.7))


def _wait_for_ark_main_menu(timeout=30):
    from source.utility import utils

    deadline = utils.timed_out_counter(float(timeout))
    while not deadline():
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


def _bed_name(players, account):
    return player_bed_name(players, account)


def _steam_account(players, account):
    return player_steam_account(players, account)


def _fallback_bed_name(players, account):
    if account is None:
        return None
    return _bed_name(players or {}, account)


def _click_coord(coord):
    import pyautogui

    pyautogui.click(int(coord["x"]), int(coord["y"]))


def _wait_for_template_visible(check_func, timeout, *args):
    from source.utility import utils

    deadline = utils.timed_out_counter(float(timeout))
    while not deadline():
        if check_func(*args):
            return True
        time.sleep(0.05)
    return bool(check_func(*args))


def _template_item(template_path):
    return Path(str(template_path)).stem


def _ensure_steam_window_ready(steam, status_callback=None, launch_if_missing=True):
    import subprocess

    from source.utility import utils

    emit = status_callback or (lambda _message: None)
    title = steam.get("window_title", "Steam")
    timeout = float(steam.get("window_ready_timeout", 5))
    last_error = None
    steam_exe = _running_steam_exe_path()
    if launch_if_missing:
        emit("Opening Steam window.")
        subprocess.Popen([str(steam_exe)])
    for attempt in range(1, RECOVERABLE_RUNTIME_ATTEMPTS + 1):
        deadline = utils.timed_out_counter(timeout)
        while not deadline():
            try:
                if _focus_steam_window_maximized(title):
                    return True
            except RuntimeError as exc:
                last_error = exc
            time.sleep(0.5)
        emit(
            "Steam window was not ready; restarting Steam "
            f"({attempt}/{RECOVERABLE_RUNTIME_ATTEMPTS})."
        )
        subprocess.run(["taskkill", "/f", "/im", "steam.exe"], check=False)
        time.sleep(1)
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
