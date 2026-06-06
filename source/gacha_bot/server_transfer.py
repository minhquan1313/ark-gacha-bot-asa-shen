import time
from dataclasses import dataclass
from pathlib import Path

from source.launcher.transfer_helper_config import (
    account_slot_for_target,
    active_transfer_dedis,
    missing_runtime_inputs,
    player_bed_name,
    runtime_account_count,
)

RECOVERABLE_RUNTIME_ATTEMPTS = 3


class TransferConfigError(RuntimeError):
    pass


@dataclass
class TransferDependencies:
    switch_account: object
    ensure_ark_running: object
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
        deps.ensure_ark_running()
        emit(
            f"Account {account}: joining resource server {settings['resource_server']}."
        )
        if not deps.join_server(settings["resource_server"]):
            if account_count == 1:
                emit(
                    "Account 1: resource join did not complete; stopping without "
                    "closing ARK."
                )
                return False
            emit(
                f"Account {account}: resource join did not complete; skipping account."
            )
            deps.kill_ark()
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
            deps.kill_ark()
            continue
        deps.check_state(account)
        deps.withdraw_resource()
        deps.fast_travel_to_bed(_bed_name(players, account))
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
            deps.ensure_ark_running()
            emit(f"Account {account}: joining resource server.")
            if not deps.join_server(settings["resource_server"]):
                emit(f"Account {account}: resource join failed; stopping.")
                return False
            deps.wait_structure()
            deps.leave_tekpod()
            deps.transfer_to_server(settings["destination_server"], account)
            deps.wait_for_bed_screen()
            deps.spawn_bed(_bed_name(players, account))
            deps.wait_structure()
            deps.stabilize_bed_position()
            deps.deposit_resource()
            deps.transfer_to_server(settings["resource_server"], account)
            deps.wait_for_bed_screen()
            deps.spawn_bed(_bed_name(players, account))
            deps.wait_structure()
            deps.withdraw_resource()
            if not final_account:
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
        ensure_ark_running=lambda: ensure_ark_running(stop_event, status_callback),
        join_server=lambda server: join_server(server, stop_event, status_callback),
        verify_tribelog=verify_tribelog,
        check_state=lambda account=None: check_transfer_player_state(
            settings, players, account, settings["resource_server"]
        ),
        wait_structure=lambda: stop_wait(
            stop_event, int(settings["structure_load_delay"])
        ),
        withdraw_resource=lambda: withdraw_from_transfer_dedis(
            dedis, settings, stop_event
        ),
        fast_travel_to_bed=fast_travel_to_bed,
        enter_tekpod=enter_tekpod,
        leave_tekpod=leave_tekpod,
        transfer_to_server=lambda server, account=None: transfer_to_server(
            server, settings, ui_coords, stop_event, status_callback, players, account
        ),
        wait_for_bed_screen=lambda: wait_for_bed_screen(stop_event),
        spawn_bed=spawn_bed,
        stabilize_bed_position=stabilize_bed_position,
        deposit_resource=lambda: deposit_to_transfer_dedis(dedis),
        kill_ark=kill_ark,
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

    kill_ark()
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


def ensure_ark_running(stop_event, status_callback=None):
    from source.launcher.ark_game_setup import (
        ARK_PROCESS_NAME,
        launch_ark_through_steam,
    )
    from source.launcher.system import validate_ark_window

    emit = status_callback or (lambda _message: None)
    if not _process_running(ARK_PROCESS_NAME):
        emit("Launching ARK through Steam.")
        launch_ark_through_steam()
    deadline = time.monotonic() + 60
    last_error = None
    while time.monotonic() < deadline:
        if stop_event is not None and stop_event.is_set():
            return False
        if _process_running(ARK_PROCESS_NAME):
            try:
                validate_ark_window()
                return True
            except RuntimeError as exc:
                last_error = exc
        time.sleep(1)
    if last_error is not None:
        raise RuntimeError(f"ARK did not reach a usable window state: {last_error}")
    raise RuntimeError("ARK did not start.")


def join_server(server, stop_event, status_callback=None):
    from source.join_sim.source.auto_join import run_auto_join_server

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
    from source.ASA.strucutres import teleporter
    from source.gacha_bot import render
    from source.utility import template

    check_transfer_disconnected(settings, server)
    reset_transfer_state(settings, players, account)
    if template.check_buffs("tek_pod_buff", 0.7) or render.render_flag:
        render.leave_tekpod()
    elif template.check_buffs("dehydration", 0.7) or template.check_buffs(
        "starving", 0.7
    ):
        target = _bed_name(players or {}, account) if account is not None else ""
        if not target:
            target = str(settings.get("transmitter_teleport", "")).strip()
        if target:
            teleporter.teleport_not_default(target)
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


def withdraw_from_transfer_dedis(dedis, settings, stop_event):
    import settings as global_settings
    from source.ASA.stations import custom_stations
    from source.ASA.strucutres import teleporter
    from source.gacha_bot import deposit
    from source.utility import utils

    global_settings.lag_offset = float(settings["lag_offset"])
    global_settings.station_yaw = float(settings["resource_station_yaw"])
    route_metadata = custom_stations.get_station_metadata(dedis["teleport"])
    teleporter.teleport_not_default(route_metadata)
    deposit._restore_route_view(route_metadata)
    for index, item in enumerate(active_transfer_dedis(dedis), 1):
        if stop_event is not None and stop_event.is_set():
            return False
        label = f"Transfer dedi {index}"
        if not deposit._withdraw_from_dedi(route_metadata, item, label, stop_event):
            return False
    utils.set_yaw(float(settings["resource_station_yaw"]))
    return True


def deposit_to_transfer_dedis(dedis):
    from source.ASA.stations import custom_stations
    from source.gacha_bot import deposit

    route_metadata = custom_stations.get_station_metadata(dedis["teleport"])
    for index, item in enumerate(active_transfer_dedis(dedis), 1):
        if not deposit._deposit_to_dedi(route_metadata, item, f"Transfer dedi {index}"):
            return False
    return True


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
    for attempt in range(1, RECOVERABLE_RUNTIME_ATTEMPTS + 1):
        if stop_event is not None and stop_event.is_set():
            return False
        teleporter.teleport_not_default(settings["transmitter_teleport"])
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


def spawn_bed(name):
    from source.ASA.strucutres import bed

    bed.spawn_in(name)


def fast_travel_to_bed(name):
    from source.ASA.strucutres import bed

    bed.fast_travel(name)


def stabilize_bed_position():
    leave_tekpod()


def enter_tekpod():
    from source.gacha_bot import render

    render.enter_tekpod()


def leave_tekpod():
    from source.gacha_bot import render

    render.leave_tekpod()


def kill_ark():
    from source.launcher.ark_game_setup import kill_running_ark

    kill_running_ark()


def stop_wait(stop_event, seconds):
    if stop_event is not None:
        return stop_event.wait(seconds)
    time.sleep(seconds)
    return False


def _bed_name(players, account):
    return player_bed_name(players, account)


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
    deadline = time.monotonic() + timeout
    launched = False
    last_error = None
    while time.monotonic() < deadline:
        if stop_event is not None and stop_event.is_set():
            return False
        try:
            if _focus_steam_window_maximized(title):
                return True
        except RuntimeError as exc:
            last_error = exc
        if launch_if_missing and not launched:
            steam_exe = _running_steam_exe_path()
            emit("Opening Steam window.")
            subprocess.Popen([str(steam_exe)])
            launched = True
        time.sleep(0.5)
    if last_error is not None:
        raise RuntimeError(f"Steam window was not ready: {last_error}")
    raise RuntimeError(f"{title} window was not found.")


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
