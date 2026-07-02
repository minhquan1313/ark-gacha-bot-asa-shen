import ctypes
import time
from typing import Callable

import psutil
import pyautogui

import settings as global_settings
from source.ASA.player import player_state, tribelog
from source.ASA.stations import custom_stations
from source.ASA.strucutres import bed, teleporter
from source.data import shared
from source.gacha_bot import render
from source.join_sim.source import main as join_main
from source.join_sim.source.auto_join import run_auto_join_server
from source.launcher import ark_game_setup
from source.launcher.ark_game_setup import (
    ARK_PROCESS_NAME,
    launch_ark_through_steam,
)
from source.launcher.config.transfer_helper_config import (
    active_transfer_dedis,
    missing_runtime_inputs,
    player_bed_name,
    player_steam_account,
    runtime_account_count,
    transfer_dedi_route,
)
from source.launcher.utils import steam_accounts
from source.launcher.utils.deposit_helper_capture import focus_game_window
from source.launcher.utils.steam_switch import switch_steam_account
from source.launcher.utils.system import focus_window_if_needed, validate_ark_window
from source.logs import gachalogs as logs
from source.utility import template, utils, utils_simple
from source.utility.structures.dedi import dedi
from source.utility.structures.transmitter import transmitter
from source.utility.types import DediStorageState

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


class TransferTaskTracker:
    """Publish the current transfer action and its next three planned actions."""

    def __init__(
        self,
        tasks: list[str],
        callback: Callable[[dict], object] | None,
    ) -> None:
        self.tasks = list(tasks)
        self.callback = callback
        self.next_index = 0
        self.current = ""

    def start(self, task: str) -> None:
        """Advance to an executed task, discarding skipped branch actions."""
        try:
            index = self.tasks.index(task, self.next_index)
        except ValueError:
            return
        self.current = task
        self.next_index = index + 1
        self._publish()

    def insert_after(self, existing_task: str, task: str) -> None:
        """Insert a newly confirmed conditional task into the remaining plan."""
        try:
            index = self.tasks.index(existing_task, self.next_index)
        except ValueError:
            return
        self.tasks.insert(index + 1, task)
        self._publish()

    def _publish(self) -> None:
        """Emit the task state using the main runner snapshot shape."""
        if self.callback is None:
            return
        upcoming = self.tasks[self.next_index : self.next_index + 3]
        self.callback(
            {
                "running": [{"name": self.current}] if self.current else [],
                "active": [{"name": name, "state": "READY"} for name in upcoming],
                "waiting": [],
            }
        )


def _transfer_task_label(
    account: int,
    action: str,
    detail: str = "",
    loop_number: int | None = None,
) -> str:
    """Build a compact task label for one transfer dependency action."""
    prefix = (
        f"Acc {account}" if loop_number is None else f"Acc {account} L{loop_number}"
    )
    label = f"{prefix} - {action}"
    return f"{label} - {detail}" if detail else label


def _transfer_task_plan(settings: dict, players: dict, account_count: int) -> list[str]:
    """Build the normal-path dependency action plan for a transfer run."""
    tasks = []
    start_mode = str(settings.get("transfer_start_mode", "default")).strip().lower()
    if start_mode != "destinate":
        for account in range(1, account_count + 1):
            if account_count > 1:
                tasks.append(
                    _transfer_task_label(
                        account, "Switch Steam", _steam_account(players, account)
                    )
                )
            tasks.extend(
                [
                    _transfer_task_label(account, "Ensure ARK Ready"),
                    _transfer_task_label(account, "Check Menu State"),
                    _transfer_task_label(
                        account, "Join Resource", str(settings["resource_server"])
                    ),
                    _transfer_task_label(account, "Verify Tribe Log"),
                    _transfer_task_label(account, "Check Player State"),
                    _transfer_task_label(account, "Withdraw Resources"),
                    _transfer_task_label(
                        account, "Going back to Tekpod", _bed_name(players, account)
                    ),
                    _transfer_task_label(account, "Enter Tekpod"),
                ]
            )

    loop_count = int(settings["loop_count"])
    for loop_number in range(1, loop_count + 1):
        for account in range(1, account_count + 1):
            if account_count > 1:
                tasks.append(
                    _transfer_task_label(
                        account,
                        "Switch Steam",
                        _steam_account(players, account),
                        loop_number,
                    )
                )
            tasks.extend(
                [
                    _transfer_task_label(
                        account, "Ensure ARK Ready", loop_number=loop_number
                    ),
                    _transfer_task_label(
                        account,
                        "Join Resource",
                        str(settings["resource_server"]),
                        loop_number,
                    ),
                    _transfer_task_label(
                        account, "Wait Resource Structures", loop_number=loop_number
                    ),
                    _transfer_task_label(
                        account, "Leave Tekpod", loop_number=loop_number
                    ),
                    _transfer_task_label(
                        account,
                        "Transfer Destination",
                        str(settings["destination_server"]),
                        loop_number,
                    ),
                    _transfer_task_label(
                        account, "Wait Destination Bed", loop_number=loop_number
                    ),
                    _transfer_task_label(
                        account,
                        "Spawn Destination Bed",
                        _bed_name(players, account),
                        loop_number,
                    ),
                    _transfer_task_label(
                        account,
                        "Wait Destination Structures",
                        loop_number=loop_number,
                    ),
                    _transfer_task_label(
                        account, "Deposit Resources", loop_number=loop_number
                    ),
                    _transfer_task_label(
                        account,
                        "Transfer Resource",
                        str(settings["resource_server"]),
                        loop_number,
                    ),
                    _transfer_task_label(
                        account, "Wait Resource Bed", loop_number=loop_number
                    ),
                    _transfer_task_label(
                        account,
                        "Spawn Resource Bed",
                        _bed_name(players, account),
                        loop_number,
                    ),
                    _transfer_task_label(
                        account,
                        "Wait Resource Structures",
                        loop_number=loop_number,
                    ),
                ]
            )
            if loop_number < loop_count:
                tasks.extend(
                    [
                        _transfer_task_label(
                            account, "Withdraw Resources", loop_number=loop_number
                        ),
                        _transfer_task_label(
                            account,
                            "Going back to Tekpod",
                            loop_number=loop_number,
                        ),
                    ]
                )
            tasks.append(
                _transfer_task_label(account, "Enter Tekpod", loop_number=loop_number)
            )
    if account_count > 1:
        tasks.extend(
            [
                _transfer_task_label(1, "Restore Steam", _steam_account(players, 1)),
                _transfer_task_label(1, "Restore ARK"),
                _transfer_task_label(
                    1, "Restore Resource", str(settings["resource_server"])
                ),
            ]
        )
    return tasks


def run_transfer_helper(
    config: dict,
    status_callback: Callable[[str], object] | None = None,
    task_callback: Callable[[dict], object] | None = None,
) -> bool:

    settings = config["settings"]
    dedis = config["dedis"]
    ui_coords = config["ui_coords"]
    players = config.get("players", {})
    missing = missing_runtime_inputs(
        settings,
        dedis,
        players,
        steam_accounts=config.get("steam_accounts"),
    )
    if missing:
        raise TransferConfigError(
            "Missing transfer helper inputs: " + ", ".join(missing)
        )

    account_count = runtime_account_count(players)
    accounts = range(1, account_count + 1)
    current_steam_account = _steam_account(players, 1)
    task_tracker = TransferTaskTracker(
        _transfer_task_plan(settings, players, account_count), task_callback
    )

    def emit(message: str) -> None:
        if status_callback is not None:
            status_callback(message)

    start_mode = str(settings.get("transfer_start_mode", "default")).strip().lower()
    if start_mode == "destinate":
        emit("Starting destination transfer phase from filled characters.")
    else:
        emit("Starting resource fill phase.")
        for account in accounts:
            global_settings.station_yaw = float(settings["resource_station_yaw"])
            if account_count > 1:
                task_tracker.start(
                    _transfer_task_label(
                        account, "Switch Steam", _steam_account(players, account)
                    )
                )
                current_steam_account = switch_steam_account(
                    account,
                    current_steam_account,
                    players,
                    ui_coords,
                    status_callback,
                    steam_restart_interval=settings.get("steam_restart_interval", 30),
                )
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(_transfer_task_label(account, "Ensure ARK Ready"))
            if ensure_ark_running(status_callback, settings, ui_coords) is False:
                return False

            # -=-=-=-=-=-=-=-=-=-=-=-=
            emit(
                f"Account {account}: joining resource server {settings['resource_server']}."
            )
            task_tracker.start(
                _transfer_task_label(
                    account, "Join Resource", str(settings["resource_server"])
                )
            )
            if not join_server(settings["resource_server"], status_callback):
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
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(_transfer_task_label(account, "Check Menu State"))
            if shared.was_in_mainmenu:
                task_tracker.insert_after(
                    _transfer_task_label(account, "Verify Tribe Log"),
                    _transfer_task_label(account, "Wait Resource Structures"),
                )
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(_transfer_task_label(account, "Verify Tribe Log"))
            if not verify_tribelog():
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
            # -=-=-=-=-=-=-=-=-=-=-=-=
            if shared.was_in_mainmenu:
                task_tracker.start(
                    _transfer_task_label(account, "Wait Resource Structures")
                )
                time.sleep(int(settings["structure_load_delay"]))
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(_transfer_task_label(account, "Check Player State"))
            check_transfer_player_state(
                settings, players, account, settings["resource_server"]
            )
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(_transfer_task_label(account, "Withdraw Resources"))
            if withdraw_from_transfer_dedis(dedis, settings, players, account) is False:
                return False
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(
                    account, "Going back to Tekpod", _bed_name(players, account)
                )
            )
            go_back_to_bed(_bed_name(players, account))
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(_transfer_task_label(account, "Enter Tekpod"))
            enter_tekpod()

    # Starting loop of go to [des -> deposit -> go back -> withdraw]
    for loop_number in range(1, int(settings["loop_count"]) + 1):
        emit(f"Starting destination loop {loop_number}/{settings['loop_count']}.")
        for account in accounts:
            global_settings.station_yaw = float(settings["resource_station_yaw"])

            if account_count > 1:
                task_tracker.start(
                    _transfer_task_label(
                        account,
                        "Switch Steam",
                        _steam_account(players, account),
                        loop_number,
                    )
                )
                current_steam_account = switch_steam_account(
                    account,
                    current_steam_account,
                    players,
                    ui_coords,
                    status_callback,
                    steam_restart_interval=settings.get("steam_restart_interval", 30),
                )
            task_tracker.start(
                _transfer_task_label(
                    account, "Ensure ARK Ready", loop_number=loop_number
                )
            )
            if ensure_ark_running(status_callback, settings, ui_coords) is False:
                return False
            # -=-=-=-=-=-=-=-=-=-=-=-=
            emit(f"Account {account}: joining resource server.")
            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Join Resource",
                    str(settings["resource_server"]),
                    loop_number,
                )
            )
            if not join_server(settings["resource_server"], status_callback):
                emit(f"Account {account}: resource join failed; stopping.")
                return False
            # -=-=-=-=-=-=-=-=-=-=-=-=
            if start_mode == "default" or shared.was_in_mainmenu:
                task_tracker.start(
                    _transfer_task_label(
                        account, "Wait Resource Structures", loop_number=loop_number
                    )
                )
                time.sleep(int(settings["structure_load_delay"]))
            else:
                pass
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(account, "Leave Tekpod", loop_number=loop_number)
            )
            leave_tekpod()
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Transfer Destination",
                    str(settings["destination_server"]),
                    loop_number,
                )
            )
            transfer_to_server(
                settings["destination_server"],
                settings,
                status_callback,
                players,
                account,
            )
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(
                    account, "Wait Destination Bed", loop_number=loop_number
                )
            )
            wait_for_bed_screen()
            # -=-=-=-=-=-=HERE WE ARE AT THE DESTINATION SERVER-=-=-=-=-=-=
            global_settings.station_yaw = float(settings["destination_station_yaw"])
            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Spawn Destination Bed",
                    _bed_name(players, account),
                    loop_number,
                )
            )
            spawn_bed(_bed_name(players, account))
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Wait Destination Structures",
                    loop_number=loop_number,
                )
            )
            time.sleep(int(settings["structure_load_delay"]))
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(
                    account, "Deposit Resources", loop_number=loop_number
                )
            )
            if deposit_to_transfer_dedis(dedis, settings, players, account) is False:
                return False

            # -=-=-=-=-=-GO BACK TO RESOURCE SERVER=-=-=-=-=-=-=

            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Transfer Resource",
                    str(settings["resource_server"]),
                    loop_number,
                )
            )
            transfer_to_server(
                settings["resource_server"],
                settings,
                status_callback,
                players,
                account,
            )
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(
                    account, "Wait Resource Bed", loop_number=loop_number
                )
            )
            wait_for_bed_screen()
            # -=-=-=-=-=Here we are back to Resource server-=-=-=-=-=-=-=
            global_settings.station_yaw = float(settings["resource_station_yaw"])

            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Spawn Resource Bed",
                    _bed_name(players, account),
                    loop_number,
                )
            )
            spawn_bed(_bed_name(players, account))
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Wait Resource Structures",
                    loop_number=loop_number,
                )
            )
            time.sleep(int(settings["structure_load_delay"]))
            # -=-=-=-=-=-=IF THERE IS STILL MORE LOOP-=-=-=-=-=-=
            if loop_number < int(settings["loop_count"]):
                task_tracker.start(
                    _transfer_task_label(
                        account, "Withdraw Resources", loop_number=loop_number
                    )
                )
                if (
                    withdraw_from_transfer_dedis(dedis, settings, players, account)
                    is False
                ):
                    return False
                # -=-=-=-=-=-=-=-=-=-=-=-=
                task_tracker.start(
                    _transfer_task_label(
                        account, "Going back to Tekpod", loop_number=loop_number
                    )
                )
                go_back_to_bed(_bed_name(players, account))
            else:
                utils.zero_center()  # This will fix player aim wrong direction in the enter_tekpod below
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(account, "Enter Tekpod", loop_number=loop_number)
            )
            enter_tekpod()
    # Everything is done, now logging back to original account, which is player 1
    if account_count > 1:
        task_tracker.start(
            _transfer_task_label(1, "Restore Steam", _steam_account(players, 1))
        )
        current_steam_account = switch_steam_account(
            1,
            current_steam_account,
            players,
            ui_coords,
            status_callback,
            steam_restart_interval=settings.get("steam_restart_interval", 30),
        )
        # -=-=-=-=-=-=-=-=-=-=-=-=
        task_tracker.start(_transfer_task_label(1, "Restore ARK"))
        if ensure_ark_running(status_callback, settings, ui_coords) is False:
            emit("Player 1 restoration failed: ARK did not become ready.")
            return False
        # -=-=-=-=-=-=-=-=-=-=-=-=
        task_tracker.start(
            _transfer_task_label(
                1, "Restore Resource", str(settings["resource_server"])
            )
        )
        if not join_server(settings["resource_server"], status_callback):
            emit("Player 1 restoration failed: resource server join did not complete.")
            return False

    emit("Server transfer helper finished.")
    return True


def ensure_ark_running(status_callback=None, settings=None, ui_coords=None):
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
        dl = utils_simple.get_default_clock(timeout)
        while not dl():
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
        _restart_steam_before_ark_retry(
            steam,
            _settings_int(settings, "steam_restart_interval", 30),
            emit,
        )
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
    focus_game_window(center_cursor_when_switching=True)
    time.sleep(1)
    return True


def _focus_ark_window_for_join(window_size=None):
    focus_game_window(center_cursor_when_switching=True)
    # Click in middle of screen to skip the intro and quickly go to the main menu, which can help with faster joins
    width, height = window_size or (1920, 1080)
    pyautogui.click(int(width) // 2, int(height) // 2)


def is_menu():
    return bool(join_main.is_menu())


def join_server(server, status_callback=None):
    _focus_ark_window_for_join(validate_ark_window())

    shared.was_in_mainmenu = False

    return run_auto_join_server(server, status_callback)


def verify_tribelog():
    tribelog.open()
    opened = tribelog.is_open()
    tribelog.close()
    return bool(opened)


def check_transfer_player_state(settings, players=None, account=None, server=None):
    bed = _bed_name(players or {}, account) if account is not None else ""
    if not bed:
        bed = str(settings.get("transmitter_teleport", "")).strip()

    global_settings.server_number = server
    global_settings.bed_spawn = bed

    player_state.check_state()


def withdraw_from_transfer_dedis(
    dedis: dict,
    settings: dict,
    players: dict | None = None,
    account: int | None = None,
) -> bool:
    global_settings.lag_offset = float(settings["lag_offset"])
    global_settings.station_yaw = float(settings["resource_station_yaw"])

    resource_route = transfer_dedi_route(dedis, "resource")
    route_metadata = custom_stations.get_station_metadata(resource_route["teleport"])
    fallback_bed_name = _fallback_bed_name(players, account)
    if fallback_bed_name:
        global_settings.bed_spawn = fallback_bed_name

    teleporter.teleport_not_default(route_metadata, fallback_bed_name=fallback_bed_name)
    utils.zero_center()

    items: list[DediStorageState] = active_transfer_dedis(dedis, "resource")
    for index, item in enumerate(items, 1):
        label = f"Transfer dedi {index}"
        if not dedi.open_withdraw_all(route_metadata, item):
            logs.logger.error(f"{label} transfer withdraw failed")
            return False
        logs.logger.debug(f"{label} transfer withdraw completed")

    return True


def deposit_to_transfer_dedis(
    dedis: dict,
    settings: dict,
    players: dict | None = None,
    account: int | None = None,
) -> bool:
    global_settings.lag_offset = float(settings["lag_offset"])
    global_settings.station_yaw = float(settings["destination_station_yaw"])

    destination_route = transfer_dedi_route(dedis, "destination")
    route_metadata = custom_stations.get_station_metadata(destination_route["teleport"])
    fallback_bed_name = _fallback_bed_name(players, account)
    if fallback_bed_name:
        global_settings.bed_spawn = fallback_bed_name

    teleporter.teleport_not_default(route_metadata, fallback_bed_name=fallback_bed_name)
    utils.zero_center()

    items: list[DediStorageState] = active_transfer_dedis(dedis, "destination")
    for index, item in enumerate(items, 1):
        label = f"Transfer dedi {index}"
        if not dedi.open_deposit_all(route_metadata, item):
            logs.logger.error(f"{label} transfer deposit failed")
            return False
        logs.logger.debug(f"{label} transfer deposit completed")

    return True


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
    try:
        return bool(template.check_template_no_bounds("steam_launch_option", 0.8))
    except Exception:
        return False


def steam_cloud_sync_conflict_is_open():
    try:
        return bool(template.check_template_no_bounds("steam_cloud_sync_conflic", 0.8))
    except Exception:
        return False


def steam_has_failure(steam, status_callback=None):
    """Handle known Steam launch dialogs before ARK becomes usable."""
    emit = status_callback or (lambda _message: None)
    if not _focus_visible_steam_window(steam, emit):
        return False

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


def _restart_steam_before_ark_retry(
    steam: dict | None, timeout: int, emit: Callable[[str], object]
):
    """Hard-reset ARK and Steam before the next ARK launch attempt."""
    ark_game_setup.kill_running_ark()
    steam_accounts.close_steam()

    restart_delay = 8
    if isinstance(steam, dict):
        restart_delay = steam.get("restart_delay", restart_delay)
    time.sleep(float(restart_delay))

    emit("Restarting Steam before relaunching ARK.")
    steam_accounts.launch_steam()

    dl = utils_simple.get_default_clock(timeout)
    while not dl():
        if _focus_visible_steam_window(steam, emit):
            emit("Steam is visible and maximized before ARK retry.")
            return True
        time.sleep(1)

    emit("Steam was not visible and maximized before ARK retry; relaunching ARK.")
    return False


def _focus_visible_steam_window(steam: dict | None, status_callback=None) -> bool:
    """Focus and maximize Steam only when its window exists and is visible."""
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


def transfer_to_server(
    server,
    settings,
    status_callback=None,
    players=None,
    account=None,
):
    emit = status_callback or (lambda _message: None)

    fallback_bed_name = _fallback_bed_name(players, account)
    metadata = custom_stations.get_station_metadata(settings["transmitter_teleport"])

    for attempt in range(1, RECOVERABLE_RUNTIME_ATTEMPTS + 1):
        teleporter.teleport_not_default(
            metadata,
            fallback_bed_name=fallback_bed_name,
        )
        utils.zero_center()

        emit(
            f"Transferring to server {server} "
            f"({attempt}/{RECOVERABLE_RUNTIME_ATTEMPTS})."
        )

        if transmitter.open_and_transfer(metadata, server):
            emit(f"Transfer to server {server} requested.")
            return True

        if attempt < RECOVERABLE_RUNTIME_ATTEMPTS:
            emit("Transmitter transfer did not complete; recovering player state.")
            check_transfer_player_state(settings, players, account, server)

            utils.zero_center()
            time.sleep(0.5)

    raise RuntimeError(f"Transfer to server {server} did not complete.")


def wait_for_bed_screen():
    while True:
        if bed.is_open():
            return True
        time.sleep(0.5)


def spawn_bed(name):
    bed.spawn_in(name)
    return True


def go_back_to_bed(name):
    global_settings.bed_spawn = name

    if not render.render_flag:
        logs.logger.debug(
            f"render flag{render.render_flag} we are trying to get into the pod now"
        )
        player_state.reset_state()
        teleporter.teleport_not_default(name)
    else:
        player_state.check_disconnected()
    return True


def enter_tekpod():
    render.enter_tekpod(allow_eat_implant=False)


def leave_tekpod():
    render.leave_tekpod()


def _bed_name(players, account):
    return player_bed_name(players, account)


def _steam_account(players, account):
    return player_steam_account(players, account)


def _fallback_bed_name(players, account):
    if account is None:
        return None
    return _bed_name(players or {}, account)


def _focus_steam_window_maximized(window_title: str) -> bool:
    if not focus_window_if_needed(window_title, center_cursor_when_switching=True):
        return False
    hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
    if not hwnd:
        return False
    if not ctypes.windll.user32.IsZoomed(hwnd):
        ctypes.windll.user32.ShowWindow(hwnd, 3)
    ctypes.windll.user32.BringWindowToTop(hwnd)
    return True


def _process_running(process_name):
    for proc in psutil.process_iter(attrs=["name"]):
        try:
            if str(proc.info.get("name", "")).lower() == process_name.lower():
                return True
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return False
