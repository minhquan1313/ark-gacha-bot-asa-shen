import time

REOPEN_INTERVAL_SECONDS = 15 * 60


def normalize_server_number(server):
    server = str(server).strip()
    if not server or server == "0" or not server.isdigit():
        raise ValueError("Server number must be a non-zero number.")
    return server


def _stopped(stop_event):
    return stop_event is not None and stop_event.is_set()


def _wait(stop_event, seconds):
    if stop_event is not None:
        return stop_event.wait(seconds)
    time.sleep(seconds)
    return False


def _is_menu_cancellable():
    from source.join_sim.source import main as join_main

    return join_main.is_menu()


def _click_start_cancellable(stop_event):
    from source.join_sim.source.menus import start_menu
    from source.join_sim.source.utility import recon_utils, windows
    from source.join_sim.source.logs import logger as logs

    if _stopped(stop_event) or not start_menu.is_open():
        return
    if start_menu.is_disconnected():
        if _stopped(stop_event):
            return
        windows.click(
            start_menu.get_pixel_loc("accept_x"),
            start_menu.get_pixel_loc("accept_y"),
        )
        recon_utils.window_still_open_no_bounds("accept", 0.7, 1)
    if _stopped(stop_event):
        return
    if start_menu.is_network_failure():
        if _stopped(stop_event):
            return
        windows.click(
            start_menu.get_pixel_loc("accept_x"),
            start_menu.get_pixel_loc("accept_y"),
        )
        recon_utils.window_still_open_no_bounds("network_failure", 0.7, 1)
    if _stopped(stop_event):
        return
    logs.logger.debug("clicking start")
    windows.click(
        start_menu.get_pixel_loc("accept_x"),
        start_menu.get_pixel_loc("accept_y"),
    )
    if _stopped(stop_event):
        return
    windows.click(
        start_menu.get_pixel_loc("start_x"),
        start_menu.get_pixel_loc("start_y"),
    )
    recon_utils.window_still_open_no_bounds("join_last_session", 0.7, 1)


def _click_join_game_cancellable(stop_event):
    from source.join_sim.source.menus import join_game_menu
    from source.join_sim.source.utility import recon_utils, windows
    from source.join_sim.source.logs import logger as logs

    if _stopped(stop_event) or not join_game_menu.is_open():
        return
    logs.logger.debug("click join game")
    location = recon_utils.template_find("join_game")
    if _stopped(stop_event):
        return
    windows.click(location[0], location[1])
    recon_utils.window_still_open_no_bounds("join_game", 0.7, 1)


def _search_bar_search_cancellable(server, stop_event):
    from source.join_sim.source.menus import multiplayer_menu
    from source.join_sim.source.utility import utils, windows

    if _stopped(stop_event) or not multiplayer_menu.is_open():
        return
    windows.move_mouse(
        multiplayer_menu.get_pixel_loc("search_x"),
        multiplayer_menu.get_pixel_loc("search_y"),
    )
    if _stopped(stop_event):
        return
    windows.click(
        multiplayer_menu.get_pixel_loc("search_x"),
        multiplayer_menu.get_pixel_loc("search_y"),
    )
    if _stopped(stop_event):
        return
    windows.click(
        multiplayer_menu.get_pixel_loc("search_x"),
        multiplayer_menu.get_pixel_loc("search_y"),
    )
    if _wait(stop_event, 0.2):
        return
    utils.ctrl_a()
    if _wait(stop_event, 0.2):
        return
    if _stopped(stop_event):
        return
    utils.write(server)


def _join_server_cancellable(server, stop_event):
    from source.join_sim.source.menus import multiplayer_menu
    from source.join_sim.source.utility import windows
    from source.join_sim.source.logs import logger as logs

    if _stopped(stop_event):
        return
    if multiplayer_menu.mod_menu():
        logs.logger.debug("mod menu open waiting")
        return
    if not multiplayer_menu.is_open():
        return
    logs.logger.debug("joining server")
    _search_bar_search_cancellable(server, stop_event)
    if _wait(stop_event, 1):
        return
    windows.click(
        multiplayer_menu.get_pixel_loc("first_server_x"),
        multiplayer_menu.get_pixel_loc("first_server_y"),
    )
    if _wait(stop_event, 0.5):
        return
    if (
        not _stopped(stop_event)
        and multiplayer_menu.is_open()
        and multiplayer_menu.join_button()
    ):
        windows.click(
            multiplayer_menu.get_pixel_loc("join_x"),
            multiplayer_menu.get_pixel_loc("join_y"),
        )


def _mod_menu_join_cancellable(stop_event):
    from source.join_sim.source.menus import mod_menu
    from source.join_sim.source.utility import recon_utils, windows
    from source.join_sim.source.logs import logger as logs

    if _stopped(stop_event) or not mod_menu.is_open():
        return
    logs.logger.debug("mod menu click")
    windows.click(
        mod_menu.get_pixel_loc("mod_join_x"),
        mod_menu.get_pixel_loc("mod_join_y"),
    )
    recon_utils.window_still_open_no_bounds("req_mods", 0.7, 1)


def _has_failure_cancellable(stop_event):
    import pyautogui

    from source.join_sim.source.menus import failure
    from source.join_sim.source.utility import recon_utils, windows
    from source.join_sim.source.logs import logger as logs

    if _stopped(stop_event):
        return
    if failure.is_server_full():
        logs.logger.debug("server full")
        windows.click(
            failure.get_pixel_loc("cancel_x"),
            failure.get_pixel_loc("cancel_y"),
        )
        recon_utils.window_still_open_no_bounds("server_full", 0.7, 2)
        if _wait(stop_event, 1):
            return
        windows.click(
            failure.get_pixel_loc("back_x"),
            failure.get_pixel_loc("back_y"),
        )

    if _stopped(stop_event):
        return
    if failure.is_red_fail():
        logs.logger.debug("red fail")
        if _wait(stop_event, 1):
            return
        pyautogui.click(
            failure.get_pixel_loc("red_okay_x"),
            failure.get_pixel_loc("red_okay_y"),
        )
        recon_utils.window_still_open_no_bounds("red_fail", 0.7, 2)
        if _wait(stop_event, 1):
            return
        pyautogui.click(
            failure.get_pixel_loc("back_x"),
            failure.get_pixel_loc("back_y"),
        )

    if _stopped(stop_event):
        return
    if failure.no_sessions():
        logs.logger.debug("no sessions found")
        if _wait(stop_event, 1):
            return
        pyautogui.click(
            failure.get_pixel_loc("back_x"),
            failure.get_pixel_loc("back_y"),
        )
        _wait(stop_event, 1)


def _joined_server_cancellable(stop_event):
    from source.join_sim.source.menus import success
    from source.join_sim.source.utility import utils

    if _stopped(stop_event):
        return False
    if success.bed_spawn() or success.download():
        return True
    if _stopped(stop_event):
        return False
    utils.press_key("ShowTribeManager")
    if _wait(stop_event, 0.5):
        return False
    if success.logs():
        return True
    return False


def join_round_cancellable(server, stop_event):
    from source.join_sim.source.logs import logger as logs

    if _stopped(stop_event):
        return False
    if not _is_menu_cancellable():
        if _wait(stop_event, 0.5):
            return False
        logs.logger.debug("joined server")
        return _joined_server_cancellable(stop_event)

    if _wait(stop_event, 0.5):
        return False
    _click_start_cancellable(stop_event)
    if _wait(stop_event, 0.5):
        return False
    _click_join_game_cancellable(stop_event)
    if _wait(stop_event, 0.5):
        return False
    _join_server_cancellable(server, stop_event)
    if _wait(stop_event, 0.5):
        return False
    _mod_menu_join_cancellable(stop_event)
    if _wait(stop_event, 0.5):
        return False
    _has_failure_cancellable(stop_event)
    _wait(stop_event, 0.5)
    return False


def run_auto_join_server(
    server,
    stop_event,
    status_callback=None,
    join_round=None,
    is_menu=None,
    detect_crash=None,
    re_open_game=None,
    sleep=time.sleep,
    now=time.monotonic,
    retry_delay=2,
    reopen_interval=REOPEN_INTERVAL_SECONDS,
    reopen_pause=5,
):
    server = normalize_server_number(server)
    use_cancellable_join_round = join_round is None

    if join_round is None:
        join_round = join_round_cancellable
    if is_menu is None:
        from source.join_sim.source import main as join_main

        is_menu = join_main.is_menu
    if detect_crash is None or re_open_game is None:
        from source.join_sim.source.crash import crash

        detect_crash = detect_crash or crash.detect_crash
        re_open_game = re_open_game or crash.re_open_game

    def emit(message):
        if status_callback is not None:
            status_callback(message)

    def stop_wait(seconds):
        deadline = now() + seconds
        while not stop_event.is_set() and now() < deadline:
            sleep(min(0.2, max(0, deadline - now())))

    last_reopen = now()
    emit(f"Starting auto join for server {server}...")

    while not stop_event.is_set():
        if detect_crash():
            emit("Crash detected. Reopening game...")
            re_open_game()
            last_reopen = now()
            stop_wait(reopen_pause)
            continue

        if is_menu() and now() - last_reopen >= reopen_interval:
            emit("Still in menu. Reopening game before retrying...")
            re_open_game()
            last_reopen = now()
            stop_wait(reopen_pause)
            continue

        emit(f"Trying to join server {server}...")
        if use_cancellable_join_round:
            joined = join_round(server, stop_event)
        else:
            joined = join_round(server)
        if joined:
            emit(f"Joined server {server}.")
            return True

        stop_wait(retry_delay)

    emit("Auto join stopped.")
    return False
