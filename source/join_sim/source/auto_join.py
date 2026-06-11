import time

REOPEN_INTERVAL_SECONDS = 15 * 60


def normalize_server_number(server):
    server = str(server).strip()
    if not server or server == "0" or not server.isdigit():
        raise ValueError("Server number must be a non-zero number.")
    return server


def run_auto_join_server(
    server,
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

    if join_round is None or is_menu is None:
        from source.join_sim.source import main as join_main

        join_round = join_round or join_main.join_round
        is_menu = is_menu or join_main.is_menu

    if detect_crash is None or re_open_game is None:
        from source.join_sim.source.crash import crash

        detect_crash = detect_crash or crash.detect_crash
        re_open_game = re_open_game or crash.re_open_game

    def emit(message):
        if status_callback is not None:
            status_callback(message)

    last_reopen = now()
    emit(f"Starting auto join for server {server}...")

    while True:
        if detect_crash():
            emit("Crash detected. Reopening game...")
            re_open_game()
            last_reopen = now()
            sleep(reopen_pause)
            continue

        if is_menu() and now() - last_reopen >= reopen_interval:
            emit("Still in menu. Reopening game before retrying...")
            re_open_game()
            last_reopen = now()
            sleep(reopen_pause)
            continue

        emit(f"Trying to join server {server}...")
        if join_round(server):
            emit(f"Joined server {server}.")
            return True

        sleep(retry_delay)
