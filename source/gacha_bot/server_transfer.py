import time
from dataclasses import dataclass

from source.launcher.transfer_helper_config import (
    account_slot_for_target,
    active_transfer_dedis,
    bed_name,
    missing_runtime_inputs,
)


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
    missing = missing_runtime_inputs(settings, dedis, ui_coords)
    if missing:
        raise TransferConfigError(
            "Missing transfer helper inputs: " + ", ".join(missing)
        )

    deps = dependencies or default_transfer_dependencies(
        config, stop_event, status_callback
    )
    accounts = range(1, int(settings["account_count"]) + 1)
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
        current_account = deps.switch_account(account, current_account)
        deps.ensure_ark_running()
        emit(
            f"Account {account}: joining resource server {settings['resource_server']}."
        )
        if not deps.join_server(settings["resource_server"]):
            emit(
                f"Account {account}: resource join did not complete; skipping account."
            )
            deps.kill_ark()
            continue
        if not deps.verify_tribelog():
            emit(
                f"Account {account}: tribe log unavailable on resource server; "
                "assuming character is elsewhere and skipping."
            )
            deps.kill_ark()
            continue
        deps.check_state()
        deps.withdraw_resource()
        deps.fast_travel_to_bed(_bed_name(settings, account))
        deps.enter_tekpod()

    for loop_number in range(1, int(settings["loop_count"]) + 1):
        emit(f"Starting transfer loop {loop_number}/{settings['loop_count']}.")
        for account in accounts:
            if stopped():
                return False
            final_account = loop_number == int(
                settings["loop_count"]
            ) and account == int(settings["account_count"])
            current_account = deps.switch_account(account, current_account)
            deps.ensure_ark_running()
            emit(f"Account {account}: joining resource server.")
            if not deps.join_server(settings["resource_server"]):
                emit(f"Account {account}: resource join failed; stopping.")
                return False
            deps.wait_structure()
            deps.leave_tekpod()
            deps.transfer_to_server(settings["destination_server"])
            deps.wait_for_bed_screen()
            deps.spawn_bed(_bed_name(settings, account))
            deps.wait_structure()
            deps.stabilize_bed_position()
            deps.deposit_resource()
            deps.transfer_to_server(settings["resource_server"])
            deps.wait_for_bed_screen()
            deps.spawn_bed(_bed_name(settings, account))
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

    return TransferDependencies(
        switch_account=lambda target, current: switch_steam_account(
            target,
            current,
            int(settings["account_count"]),
            ui_coords,
            stop_event,
            status_callback,
        ),
        ensure_ark_running=lambda: ensure_ark_running(stop_event, status_callback),
        join_server=lambda server: join_server(server, stop_event, status_callback),
        verify_tribelog=verify_tribelog,
        check_state=check_player_state,
        wait_structure=lambda: stop_wait(
            stop_event, int(settings["structure_load_delay"])
        ),
        withdraw_resource=lambda: withdraw_from_transfer_dedis(
            dedis, settings, stop_event
        ),
        fast_travel_to_bed=fast_travel_to_bed,
        enter_tekpod=enter_tekpod,
        leave_tekpod=leave_tekpod,
        transfer_to_server=lambda server: transfer_to_server(
            server, settings, ui_coords, stop_event, status_callback
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
    from source.launcher.system import focus_window_if_needed

    kill_ark()
    focus_window_if_needed(
        steam.get("window_title", "Steam"), center_cursor_when_switching=True
    )
    for key in ("menu", "change_account", "continue"):
        if stop_wait(stop_event, 0.2):
            return int(current_account)
        coord = steam[key]
        pyautogui.click(int(coord["x"]), int(coord["y"]))
    emit(f"Waiting for Steam account picker to restart for account {target_account}.")
    if stop_wait(stop_event, int(steam.get("restart_delay", 8))):
        return int(current_account)
    pyautogui.click(int(slot["x"]), int(slot["y"]))
    return int(target_account)


def ensure_ark_running(stop_event, status_callback=None):
    from source.launcher.ark_game_setup import (
        ARK_PROCESS_NAME,
        launch_ark_through_steam,
    )

    if _process_running(ARK_PROCESS_NAME):
        return
    emit = status_callback or (lambda _message: None)
    emit("Launching ARK through Steam.")
    launch_ark_through_steam()
    stop_wait(stop_event, 15)


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
    from source.ASA.player import player_state

    player_state.check_state()


def withdraw_from_transfer_dedis(dedis, settings, stop_event):
    import settings as global_settings
    from source.ASA.player import player_state
    from source.ASA.stations import custom_stations
    from source.ASA.strucutres import inventory, teleporter
    from source.utility import template, utils, variables, windows

    global_settings.lag_offset = float(settings["lag_offset"])
    global_settings.station_yaw = float(settings["resource_station_yaw"])
    route_metadata = custom_stations.get_station_metadata(dedis["teleport"])
    teleporter.teleport_not_default(route_metadata)
    utils.set_yaw(float(settings["resource_station_yaw"]))
    player_state.human.reset_crouch()
    for index, item in enumerate(active_transfer_dedis(dedis), 1):
        if stop_event is not None and stop_event.is_set():
            return False
        _turn_to_dedi_item(item)
        deadline = time.monotonic() + int(global_settings.dedi_handshake_timeout)
        while time.monotonic() < deadline:
            utils.press_key("AccessInventory")
            if template.template_await_true(
                template.check_template, 2, "inventory", 0.7
            ):
                while (
                    template.check_template("waiting_inv", 0.8)
                    and time.monotonic() < deadline
                ):
                    if stop_event is not None and stop_event.is_set():
                        return False
                    time.sleep(0.05)
                windows.click(
                    variables.get_pixel_loc("dedi_withdraw_x"),
                    variables.get_pixel_loc("dedi_withdraw_y"),
                )
                inventory.transfer_all_from()
                inventory.close()
                break
            time.sleep(0.5 * global_settings.lag_offset)
        else:
            inventory.close()
            raise RuntimeError(f"Transfer dedi {index} withdraw timed out.")
    player_state.human.reset_crouch()
    return True


def deposit_to_transfer_dedis(dedis):
    from source.ASA.stations import custom_stations
    from source.gacha_bot import deposit

    route_metadata = custom_stations.get_station_metadata(dedis["teleport"])
    for index, item in enumerate(active_transfer_dedis(dedis), 1):
        if not deposit._deposit_to_dedi(route_metadata, item, f"Transfer dedi {index}"):
            return False
    return True


def transfer_to_server(server, settings, ui_coords, stop_event, status_callback=None):
    import pyautogui
    from source.ASA.strucutres import inventory, teleporter
    from source.utility import utils

    emit = status_callback or (lambda _message: None)
    transfer = ui_coords["transfer"]
    teleporter.teleport_not_default(settings["transmitter_teleport"])
    utils.set_yaw(float(settings["destination_station_yaw"]))
    inventory.open()
    _click_coord(transfer["transfer_button"])
    while not (stop_event is not None and stop_event.is_set()):
        _click_coord(transfer["server_search"])
        pyautogui.hotkey("ctrl", "a")
        pyautogui.write(str(server))
        _click_coord(transfer["first_server"])
        _click_coord(transfer["join_button"])
        stop_wait(stop_event, 1)
        if not _template_visible(
            transfer["not_ready_template"], transfer["not_ready_region"]
        ):
            emit(f"Transfer to server {server} requested.")
            return True
        _click_coord(transfer["not_ready_ok"])
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


def _bed_name(settings, account):
    return bed_name(settings["bed_prefix"], account, settings["bed_prefix_pad_start"])


def _turn_to_dedi_item(item):
    from source.ASA.player import player_state
    from source.utility import utils

    location = item.get("location", {})
    if item.get("crouched", False):
        player_state.human.crouch()
    else:
        player_state.human.reset_crouch()
    utils.turn_to(float(location.get("yaw", 0.0)), float(location.get("pitch", 0.0)))


def _click_coord(coord):
    import pyautogui

    pyautogui.click(int(coord["x"]), int(coord["y"]))


def _template_visible(template_path, region, threshold=0.75):
    import cv2
    import numpy as np
    from source.utility import screen

    image = cv2.imread(str(template_path))
    if image is None:
        return False
    roi = screen.get_screen_roi(
        int(region["start_x"]),
        int(region["start_y"]),
        int(region["width"]),
        int(region["height"]),
    )
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    res = cv2.matchTemplate(gray_roi, gray_image, cv2.TM_CCOEFF_NORMED)
    _min_val, max_val, _min_loc, _max_loc = cv2.minMaxLoc(res)
    return bool(max_val >= threshold)


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
