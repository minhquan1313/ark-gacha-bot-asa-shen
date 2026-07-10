import ctypes
import time
from typing import Callable, Literal, cast

import psutil
import pyautogui

import settings as global_settings
from source.ASA.player import console, player_inventory, player_state
from source.ASA.strucutres import bed, inventory, teleporter
from source.gacha_bot import render
from source.join_sim.source import main as join_main
from source.join_sim.source.auto_join import run_auto_join_server
from source.join_sim.source.menus import success
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
    ):
        self.tasks = list(tasks)
        self.callback = callback
        self.next_index = 0
        self.current = ""

    def start(self, task: str):
        """Advance to an executed task, discarding skipped branch actions."""
        try:
            index = self.tasks.index(task, self.next_index)
        except ValueError:
            return
        self.current = task
        self.next_index = index + 1
        self._publish()

    def insert_after(self, existing_task: str, task: str):
        """Insert a newly confirmed conditional task into the remaining plan."""
        try:
            index = self.tasks.index(existing_task, self.next_index)
        except ValueError:
            return
        self.tasks.insert(index + 1, task)
        self._publish()

    def _publish(self):
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
):
    """Build a compact task label for one transfer dependency action."""
    prefix = f"Acc {account}" if loop_number is None else f"L{loop_number}Acc {account}"
    label = f"{prefix} - {action}"
    return f"{label} - {detail}" if detail else label


def _account_order(account_count: int, start_account: int = 1):
    """Return the runtime account order starting at the requested player.

    Example: _account_order(4, 3) yields accounts 3 and 4.
    """
    return range(max(1, int(start_account)), int(account_count) + 1)


def _pre_plan(
    settings: dict, players: dict, account_count: int, start_account: int = 1
):
    """Build the normal-path dependency action plan for a transfer run."""
    tasks = []
    start_mode = str(settings.get("transfer_start_mode", "default")).strip().lower()
    if start_mode != "destinate":
        for account in _account_order(account_count, start_account):
            if account_count > 1:
                tasks.append(
                    _transfer_task_label(
                        account, "Steam", _steam_account(players, account)
                    )
                )
            tasks.extend(
                [
                    _transfer_task_label(account, "ARK Ready"),
                    _transfer_task_label(
                        account, "Join R", str(settings["resource_server"])
                    ),
                    _transfer_task_label(account, "Wait R Structures"),
                    _transfer_task_label(account, "Check Player"),
                    _transfer_task_label(account, "Withdraw R"),
                    _transfer_task_label(
                        account, "Back Tekpod", _bed_name(players, account)
                    ),
                    _transfer_task_label(account, "Enter Tekpod"),
                ]
            )

    loop_count = int(settings["loop_count"])
    for loop_number in range(1, loop_count + 1):
        loop_start_account = start_account if loop_number == 1 else 1
        for account in _account_order(account_count, loop_start_account):
            if account_count > 1:
                tasks.append(
                    _transfer_task_label(
                        account,
                        "Steam",
                        _steam_account(players, account),
                        loop_number,
                    )
                )
            tasks.extend(
                [
                    _transfer_task_label(account, "ARK Ready", loop_number=loop_number),
                    _transfer_task_label(
                        account,
                        "Join R",
                        str(settings["resource_server"]),
                        loop_number,
                    ),
                    _transfer_task_label(
                        account, "Wait R Structures", loop_number=loop_number
                    ),
                    _transfer_task_label(
                        account, "Leave Tekpod", loop_number=loop_number
                    ),
                    _transfer_task_label(
                        account,
                        "Transfer D",
                        str(settings["destination_server"]),
                        loop_number,
                    ),
                    _transfer_task_label(
                        account, "Wait D Bed", loop_number=loop_number
                    ),
                    _transfer_task_label(
                        account,
                        "Spawn D Bed",
                        _bed_name(players, account),
                        loop_number,
                    ),
                    _transfer_task_label(
                        account,
                        "Wait D Structures",
                        loop_number=loop_number,
                    ),
                    _transfer_task_label(account, "Deposit R", loop_number=loop_number),
                    _transfer_task_label(
                        account,
                        "Transfer R",
                        str(settings["resource_server"]),
                        loop_number,
                    ),
                    _transfer_task_label(
                        account, "Wait R Bed", loop_number=loop_number
                    ),
                    _transfer_task_label(
                        account,
                        "Spawn R Bed",
                        _bed_name(players, account),
                        loop_number,
                    ),
                    _transfer_task_label(
                        account,
                        "Wait R Structures",
                        loop_number=loop_number,
                    ),
                ]
            )
            if loop_number < loop_count:
                tasks.extend(
                    [
                        _transfer_task_label(
                            account, "Withdraw Next", loop_number=loop_number
                        ),
                        _transfer_task_label(
                            account,
                            "Back Tekpod",
                            loop_number=loop_number,
                        ),
                    ]
                )
            tasks.append(
                _transfer_task_label(account, "Enter Tekpod", loop_number=loop_number)
            )
    if account_count > 1:
        final_account = account_count
        final_loop_number = loop_count
        tasks.extend(
            [
                _transfer_task_label(1, "Restore Steam", _steam_account(players, 1)),
                _transfer_task_label(1, "ARK Ready"),
                _transfer_task_label(1, "Join R", str(settings["resource_server"])),
                _transfer_task_label(
                    final_account, "Wait Structures", loop_number=final_loop_number
                ),
                _transfer_task_label(
                    final_account,
                    "Transfer D",
                    str(settings["destination_server"]),
                    final_loop_number,
                ),
                _transfer_task_label(
                    final_account, "Wait D Bed", loop_number=final_loop_number
                ),
                _transfer_task_label(
                    final_account,
                    "Spawn D Bed",
                    _bed_name(players, final_account),
                    final_loop_number,
                ),
                _transfer_task_label(
                    final_account,
                    "Wait D Structures",
                    loop_number=final_loop_number,
                ),
                _transfer_task_label(
                    final_account, "Enter Tekpod", loop_number=final_loop_number
                ),
            ]
        )
    return tasks


was_hotfix3_run = False
is_withdrawed_all = False
account_detect_withdrawed_all = None
list_of_withdrawed_dedi = {-1}
list_of_full_dedi = {-1}

station_pushout_yaw_resource = None
station_pushout_yaw_destination = None
transmitter_teleport = ""


def run_transfer_helper(
    config: dict,
    status_callback: Callable[[str], object] | None = None,
    task_callback: Callable[[dict], object] | None = None,
):
    global list_of_withdrawed_dedi
    global list_of_full_dedi

    did_last_transfer_after_withdrawed_all = False
    should_recovery_at_the_end = True
    list_of_withdrawed_dedi = {-1}
    list_of_full_dedi = {-1}

    settings = config["settings"]
    dedis = config["dedis"]
    ui_coords = config["ui_coords"]
    players = config.get("players", {})
    account_count = runtime_account_count(players)
    try:
        start_account = int(config.get("start_account", 1))
    except (TypeError, ValueError):
        start_account = 1
    if account_count > 0:
        start_account = max(1, min(start_account, account_count))
    else:
        start_account = 1
    missing = missing_runtime_inputs(
        settings,
        dedis,
        players,
        steam_accounts=config.get("steam_accounts"),
        start_account=start_account,
    )
    if missing:
        raise TransferConfigError(
            "Missing transfer helper inputs: " + ", ".join(missing)
        )

    current_steam_account = _steam_account(players, start_account)
    task_tracker = TransferTaskTracker(
        _pre_plan(settings, players, account_count, start_account),
        task_callback,
    )

    def emit(message: str):
        if status_callback is not None:
            status_callback(message)

    # DEBUG START
    # update_global_config(settings, "resource", _bed_name(players, 1))
    # teleporter.look_down_teleport_safe()
    # transmitter.is_item_has_timer()
    # time.sleep(9999)

    start_mode = str(settings.get("transfer_start_mode", "default")).strip().lower()
    if start_mode == "destinate":
        emit("Starting destination transfer phase from filled characters.")
    else:
        emit("Starting resource fill phase.")
        for account in _account_order(account_count, start_account):
            # -=-=-=-=-=-=STARTING AT RESOURCE SERVER - DEFAULT MODE-=-=-=-=-=-=
            update_global_config(settings, "resource", _bed_name(players, account))

            if account_count > 1:
                task_tracker.start(
                    _transfer_task_label(
                        account, "Steam", _steam_account(players, account)
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
            task_tracker.start(_transfer_task_label(account, "ARK Ready"))
            if ensure_ark_running(status_callback, settings, ui_coords) is False:
                return False

            # -=-=-=-=-=-=-=-=-=-=-=-=
            emit(
                f"Account {account}: joining resource server {settings['resource_server']}."
            )
            task_tracker.start(
                _transfer_task_label(
                    account, "Join R", str(settings["resource_server"])
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
            if join_main.was_in_mainmenu:
                task_tracker.start(_transfer_task_label(account, "Wait R Structures"))
                wait_structure_load(was_in_bed=True)
            else:
                # -=-=-=-=-=-=-=-=-=-=-=-=
                task_tracker.start(_transfer_task_label(account, "Check Player"))
                player_state.check_state()
                # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(_transfer_task_label(account, "Withdraw R"))
            if withdraw_from_transfer_dedis(dedis, account) is False:
                return False
            # TODO: Have a guard here, to make sure it has timer on resource
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(account, "Back Tekpod", global_settings.bed_spawn)
            )
            go_back_to_bed()
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(_transfer_task_label(account, "Enter Tekpod"))
            render.enter_tekpod(allow_eat_implant=False)

    # Starting loop of go to [des -> deposit -> go back -> withdraw]
    for loop_number in range(1, int(settings["loop_count"]) + 1):
        emit(f"Starting destination loop {loop_number}/{settings['loop_count']}.")
        loop_start_account = start_account if loop_number == 1 else 1
        if is_withdrawed_all:
            if did_last_transfer_after_withdrawed_all:
                # Nothing else to withdraw
                emit("Nothing else to withdraw for now, so stopping loop...")
                break
            elif account_detect_withdrawed_all is not None:
                # This help let all player do last transfer again
                did_last_transfer_after_withdrawed_all = True

        for account in _account_order(account_count, loop_start_account):
            if (
                is_withdrawed_all
                and did_last_transfer_after_withdrawed_all
                and account_detect_withdrawed_all is not None
                and account > account_detect_withdrawed_all
            ):
                continue

            # -=-=-=-=-=-=STARTING AT RESOURCE SERVER - DELIVERY TO DESTINATION SERVER-=-=-=-=-=-=
            update_global_config(settings, "resource", _bed_name(players, account))
            if account_count > 1:
                task_tracker.start(
                    _transfer_task_label(
                        account,
                        "Steam",
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
                _transfer_task_label(account, "ARK Ready", loop_number=loop_number)
            )
            if ensure_ark_running(status_callback, settings, ui_coords) is False:
                return False
            # -=-=-=-=-=-=-=-=-=-=-=-=
            emit(f"Account {account}: joining resource server.")
            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Join R",
                    str(settings["resource_server"]),
                    loop_number,
                )
            )
            if not join_server(settings["resource_server"], status_callback):
                emit(f"Account {account}: resource join failed; stopping.")
                return False
            # -=-=-=-=-=-=-=-=-=-=-=-=
            if start_mode == "default" or join_main.was_in_mainmenu:
                task_tracker.start(
                    _transfer_task_label(
                        account, "Wait R Structures", loop_number=loop_number
                    )
                )
                wait_structure_load(was_in_bed=True)
            else:
                # -=-=-=-=-=-=-=-=-=-=-=-=
                task_tracker.start(
                    _transfer_task_label(
                        account, "Leave Tekpod", loop_number=loop_number
                    )
                )
                player_state.check_state()
                # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Transfer D",
                    str(settings["destination_server"]),
                    loop_number,
                )
            )
            while True:
                transfer_to_server(
                    settings["destination_server"],
                    settings,
                    status_callback,
                    players,
                    account,
                    dedis,
                    "resource",
                )
                if transmitter.was_excess_amount:
                    go_back_to_dedi_and_fix_excess(dedis)
                else:
                    break
            # -=-=-=-=-=-=HERE WE ARE AT THE DESTINATION SERVER-=-=-=-=-=-=
            update_global_config(settings, "destination", _bed_name(players, account))

            task_tracker.start(
                _transfer_task_label(account, "Wait D Bed", loop_number=loop_number)
            )
            wait_for_bed_screen()
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Spawn D Bed",
                    _bed_name(players, account),
                    loop_number,
                )
            )
            spawn_bed(_bed_name(players, account))
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Wait D Structures",
                    loop_number=loop_number,
                )
            )
            wait_structure_load(was_in_bed=True)
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(account, "Deposit R", loop_number=loop_number)
            )
            if deposit_to_transfer_dedis(dedis, account) is False:
                return False

            if hotfix3_recover_after_dedis():
                task_tracker.start(
                    _transfer_task_label(account, "Recovery", loop_number=loop_number)
                )
                if deposit_to_transfer_dedis(dedis, account) is False:
                    return False

            """
            Since we already know when all dedi is already withdrawed
            meaning no dedi left to go back to withdraw, if this is the last account
            then we should stay back here at this destination server.
            
            ONLY APPLY IF THE CURRENT ACCOUNT IS ACCOUNT 1
            """
            if (
                is_withdrawed_all
                and did_last_transfer_after_withdrawed_all
                and account == 1
            ):
                # -=-=-=-=-=-=-=-=-=-=-=-=
                task_tracker.start(
                    _transfer_task_label(
                        account, "Back Tekpod", loop_number=loop_number
                    )
                )
                go_back_to_bed()
                # -=-=-=-=-=-=-=-=-=-=-=-=
                task_tracker.start(
                    _transfer_task_label(
                        account, "Enter Tekpod", loop_number=loop_number
                    )
                )
                render.enter_tekpod(allow_eat_implant=False)

                should_recovery_at_the_end = False
                break

            # -=-=-=-=-=-GO BACK TO RESOURCE SERVER=-=-=-=-=-=-=

            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Transfer R",
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
                dedis,
                "destination",
            )
            # -=-=-=-=-=Here we are back to Resource server-=-=-=-=-=-=-=
            update_global_config(settings, "resource", _bed_name(players, account))
            task_tracker.start(
                _transfer_task_label(account, "Wait R Bed", loop_number=loop_number)
            )
            wait_for_bed_screen()
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Spawn R Bed",
                    _bed_name(players, account),
                    loop_number,
                )
            )
            spawn_bed(_bed_name(players, account))
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(
                    account,
                    "Wait R Structures",
                    loop_number=loop_number,
                )
            )
            wait_structure_load()
            # -=-=-=-=-=-=IF THERE IS STILL MORE LOOP, BECAUSE WE ARE BACK TO RESOURCE SERVER, WE Will withdraw Resource for the next transfer-=-=-=-=-=-=
            if loop_number < int(settings["loop_count"]) and not is_withdrawed_all:
                task_tracker.start(
                    _transfer_task_label(
                        account, "Withdraw Next", loop_number=loop_number
                    )
                )
                if withdraw_from_transfer_dedis(dedis, account) is False:
                    return False
                # TODO: Have a guard here, to make sure it has timer on resource
                # -=-=-=-=-=-=-=-=-=-=-=-=
                task_tracker.start(
                    _transfer_task_label(
                        account, "Back Tekpod", loop_number=loop_number
                    )
                )
                go_back_to_bed()
            else:
                utils.zero_center()  # This will fix player aim wrong direction in the enter_tekpod below
            # -=-=-=-=-=-=-=-=-=-=-=-=
            task_tracker.start(
                _transfer_task_label(account, "Enter Tekpod", loop_number=loop_number)
            )
            render.enter_tekpod(allow_eat_implant=False)

    # Everything is done, now logging back to original account, which is player 1
    if account_count > 1 and should_recovery_at_the_end:
        final_account = account_count
        final_loop_number = int(settings["loop_count"])
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
        task_tracker.start(_transfer_task_label(1, "ARK Ready"))
        if ensure_ark_running(status_callback, settings, ui_coords) is False:
            emit("Player 1 restoration failed: ARK did not become ready.")
            return False
        # -=-=-=-=-=-=-=-=-=-=-=-=
        task_tracker.start(
            _transfer_task_label(1, "Join R", str(settings["resource_server"]))
        )
        if not join_server(settings["resource_server"], status_callback):
            emit("Player 1 restoration failed: resource server join did not complete.")
            return False
        # -=-=-=-=-=-=-=-=-=-=-=-=
        task_tracker.start(
            _transfer_task_label(
                final_account, "Wait Structures", loop_number=final_loop_number
            )
        )
        wait_structure_load(was_in_bed=True)
        # -=-=-=-=-=-=-=-=-=-=-=-=
        task_tracker.start(
            _transfer_task_label(
                final_account,
                "Transfer D",
                str(settings["destination_server"]),
                final_loop_number,
            )
        )
        transfer_to_server(
            settings["destination_server"],
            settings,
            status_callback,
            players,
            final_account,
            dedis,
            "resource",
        )
        # -=-=-=-=-=-=HERE WE ARE AT THE DESTINATION SERVER-=-=-=-=-=-=
        update_global_config(settings, "destination", _bed_name(players, final_account))
        task_tracker.start(
            _transfer_task_label(
                final_account, "Wait D Bed", loop_number=final_loop_number
            )
        )
        wait_for_bed_screen()
        # -=-=-=-=-=-=-=-=-=-=-=-=
        task_tracker.start(
            _transfer_task_label(
                final_account,
                "Spawn D Bed",
                _bed_name(players, final_account),
                final_loop_number,
            )
        )
        spawn_bed(_bed_name(players, final_account))
        # -=-=-=-=-=-=-=-=-=-=-=-=
        task_tracker.start(
            _transfer_task_label(
                final_account,
                "Wait D Structures",
                loop_number=final_loop_number,
            )
        )
        wait_structure_load()
        # -=-=-=-=-=-=-=-=-=-=-=-=
        task_tracker.start(
            _transfer_task_label(
                final_account, "Enter Tekpod", loop_number=final_loop_number
            )
        )
        render.enter_tekpod(allow_eat_implant=False)
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


def is_menu():
    return bool(join_main.is_menu())


def join_server(server, status_callback=None):
    join_main.was_in_mainmenu = False
    player_state.reset_state()
    return run_auto_join_server(server, status_callback)


def update_global_config(
    settings: dict,
    current_server: Literal["destination", "resource"] = "resource",
    bed="",
):
    global station_pushout_yaw_resource
    global station_pushout_yaw_destination

    utils.was_initialized = False
    global_settings.bed_spawn = bed
    global_settings.ping = int(settings["ping"])
    global_settings.server_number = str(settings[f"{current_server}_server"])
    global_settings.station_yaw = float(settings[f"{current_server}_station_yaw"])
    # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    global_settings.wait_structure_load = float(settings["structure_load_delay"])

    if current_server == "resource":
        if global_settings.station_pushout_yaw is not None:
            station_pushout_yaw_destination = global_settings.station_pushout_yaw

        global_settings.station_pushout_yaw = (
            station_pushout_yaw_resource
            if station_pushout_yaw_resource is not None
            else None
        )
    else:
        if global_settings.station_pushout_yaw is not None:
            station_pushout_yaw_resource = global_settings.station_pushout_yaw

        global_settings.station_pushout_yaw = (
            station_pushout_yaw_destination
            if station_pushout_yaw_destination is not None
            else None
        )


def wait_structure_load(was_in_bed=False):
    if was_in_bed:
        time.sleep(min(5, global_settings.wait_structure_load))

    if not player_state.smart_wait_structure_with_teleport(first_wait=0):
        hotfix3_structure_wont_load()


def withdraw_from_transfer_dedis(
    dedis: dict,
    account: int | None = None,
):
    global list_of_withdrawed_dedi
    global is_withdrawed_all
    global account_detect_withdrawed_all

    if is_withdrawed_all:
        return True

    resource_route = transfer_dedi_route(dedis, "resource")
    route_teleport_name = resource_route["teleport"]

    teleporter.teleport_not_default(route_teleport_name)
    utils.zero_center()

    items: list[DediStorageState] = active_transfer_dedis(dedis, "resource")
    almost_full = False
    for index, item in enumerate(items, 1):
        if index in list_of_withdrawed_dedi:
            continue

        dedi.was_clear_dedi = dedi.was_last_dedi_empty = False
        player_inventory.g_last_check_can_transfer = False

        label = f"Transfer dedi {index}"
        if not dedi.open_withdraw_all(
            route_teleport_name, item, should_clear_on_empty=True
        ):
            logs.logger.error(f"{label} transfer withdraw failed")
            return False
        logs.logger.debug(f"{label} transfer withdraw completed")

        if almost_full:
            # This above the g_last_check_can_transfer, just to make sure
            # about the case of dedi has less than 300 stack, like 200 stacks
            # which is not the maximum player can carry each time
            return True
        if player_inventory.g_last_check_can_transfer:
            almost_full = True

        list_of_withdrawed_dedi.add(index - 1)

        # Last dedi is here, if it's last dedi and previous dedi already marked as withdrawed / empty
        is_last_dedi = index == len(items)  # index started at 1(not 0)
        if not is_last_dedi:
            continue

        is_last_2_dedi_checked = (index - 1) in list_of_withdrawed_dedi

        if (
            is_last_dedi
            and is_last_2_dedi_checked
            and (dedi.was_clear_dedi or dedi.was_last_dedi_empty)
        ):
            # Last dedi didn't have any resource after take all, and cleared
            list_of_withdrawed_dedi.add(index)
            is_withdrawed_all = True
            account_detect_withdrawed_all = account
        # player_state.reset_state()  # Close inv

    return True


def deposit_to_transfer_dedis(
    dedis: dict,
    account: int | None = None,
):
    global list_of_full_dedi

    destination_route = transfer_dedi_route(dedis, "destination")
    route_teleport_name = destination_route["teleport"]

    teleporter.teleport_not_default(route_teleport_name)
    utils.zero_center()

    items: list[DediStorageState] = active_transfer_dedis(dedis, "destination")
    for index, item in enumerate(items, 1):
        if index in list_of_full_dedi:
            continue

        player_inventory.g_last_check_can_transfer = True

        label = f"Transfer dedi {index}"
        if not dedi.open_deposit_all(route_teleport_name, item):
            logs.logger.error(f"{label} transfer deposit failed")
            return False
        logs.logger.debug(f"{label} transfer deposit completed")

        if not player_inventory.g_last_check_can_transfer:
            return True

        list_of_full_dedi.add(index - 1)

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


def _focus_visible_steam_window(steam: dict | None, status_callback=None):
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


def rotate_safe_view_pickup_bag():
    utils.zero_opposite()
    utils.turn_down(40)  # Turn down 40 to take all popcorn
    time.sleep(0.2)


def rotate_safe_view_drop_bag():
    utils.zero_center_no_ccc()
    utils.turn_down(180)
    time.sleep(0.2)


def hotfix3_recover_after_dedis():
    if not was_hotfix3_run:
        return False

    player_state.check_state()
    teleporter.teleport_not_default(global_settings.bed_spawn)

    rotate_safe_view_pickup_bag()
    utils.press_key("AccessInventory")
    time.sleep(0.5)

    player_inventory.open()
    can_drop = player_inventory.is_can_drop()
    player_inventory.close()
    if can_drop:
        return True

    # Here if previous can't detect any item in player inv(can drop item failed to detect)
    # Then it could be a server lag, so need to perform this ensure
    player_state.smart_wait_structure_with_teleport(
        should_close_teleport=True,
        wait_structure=utils_simple.get_default_timeout_value(),
    )

    player_inventory.open()
    can_drop = player_inventory.is_can_drop()
    player_inventory.close()

    return can_drop


def hotfix3_structure_wont_load():

    player_state.check_disconnected()
    player_state.reset_state()

    rotate_safe_view_drop_bag()
    player_inventory.open()
    did_drop_bag = False
    while player_inventory.is_can_drop():
        player_inventory.drop_all_inv()
        did_drop_bag = True
        if template.template_await_true(player_inventory.is_can_drop, 0.5):
            break
    player_inventory.close()

    step = 3
    for _ in range(step):
        utils.press_key("Jump")
        time.sleep(1.3)

    render.enter_tekpod(allow_eat_implant=False)
    render.leave_tekpod()

    if not did_drop_bag:
        return

    rotate_safe_view_drop_bag()
    while not inventory.is_open():
        inventory.open()
        if not inventory.is_open():
            player_state.check_state()
            utils.zero_opposite()
            utils.turn_down(80)
            time.sleep(0.2)

    inventory.transfer_all_from()
    while inventory.is_open():
        inventory.popcorn(6, direction="to right")

    rotate_safe_view_pickup_bag()
    time.sleep(0.3)
    utils.press_key("AccessInventory")  # Take all

    global was_hotfix3_run
    was_hotfix3_run = True


def go_back_to_dedi_and_fix_excess(dedis: dict):
    resource_route = transfer_dedi_route(dedis, "resource")
    route_teleport_name = resource_route["teleport"]

    teleporter.teleport_not_default(route_teleport_name)
    utils.zero_center()

    items: list[DediStorageState] = active_transfer_dedis(dedis, "resource")
    for index, item in enumerate(items, 1):
        label = f"Transfer dedi {index}"
        if not dedi.open_deposit_stack(
            3, route_teleport_name, item, ensure_resource=False
        ):
            logs.logger.error(f"{label} transfer withdraw failed")
            return False
        logs.logger.debug(f"{label} transfer withdraw completed")

    return True


def transfer_to_server(
    server,
    settings,
    status_callback=None,
    players=None,
    account=None,
    dedis=None,
    transmitter_side="resource",
):
    if isinstance(status_callback, dict) and callable(players):
        status_callback, players, account, dedis = players, account, dedis, None
    emit = (
        cast(Callable[[str], object], status_callback)
        if callable(status_callback)
        else (lambda _message: None)
    )

    transmitter_teleport = _transfer_transmitter_teleport(
        settings, dedis, transmitter_side
    )

    for attempt in range(1, RECOVERABLE_RUNTIME_ATTEMPTS + 1):
        teleporter.teleport_not_default(transmitter_teleport)
        utils.zero_center()

        emit(
            f"Transferring to server {server} "
            f"({attempt}/{RECOVERABLE_RUNTIME_ATTEMPTS})."
        )

        if transmitter.open_and_transfer(server):
            emit(f"Transfer to server {server} requested.")
            return True

        if transmitter.was_excess_amount:
            return False

        if attempt < RECOVERABLE_RUNTIME_ATTEMPTS:
            emit("Transmitter transfer did not complete; recovering player state.")
            player_state.check_state()
            utils.zero_center()
            time.sleep(0.5)

    raise RuntimeError(f"Transfer to server {server} did not complete.")


def _transfer_transmitter_teleport(
    settings: dict, dedis: dict | None = None, side: str = "resource"
):
    route = transfer_dedi_route(dedis or {}, side)
    transmitter_teleport = str(route.get("transmitter_teleport", "")).strip()
    if transmitter_teleport:
        return transmitter_teleport
    return str(settings.get("transmitter_teleport", "")).strip()


def wait_for_bed_screen():
    dl = utils_simple.get_default_clock(60)
    while True:
        if bed.is_open_respawn():
            return True

        if success.download():
            raise RuntimeError(
                "Can't select character to spawn, please fix it yourself"
            )

        if player_state.check_disconnected():
            dl.reset()

        if dl():
            # Somehow after uploaded/transfer server, the des server never loaded
            dl.reset()
            console.console_exit_mainmenu()
            template.template_await_true(join_main.is_menu, 10)
            time.sleep(0.5)

            player_state.check_state()
        time.sleep(0.5)


def spawn_bed(name):
    bed.spawn_in(name)
    return True


def go_back_to_bed():
    if not render.render_flag:
        logs.logger.debug(
            f"render flag{render.render_flag} we are trying to get into the pod now"
        )
        player_state.reset_state()
        teleporter.teleport_not_default(global_settings.bed_spawn)
    else:
        player_state.check_disconnected()
    return True


def _bed_name(players, account):
    return player_bed_name(players, account)


def _steam_account(players, account):
    return player_steam_account(players, account)


def _focus_steam_window_maximized(window_title: str):
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
