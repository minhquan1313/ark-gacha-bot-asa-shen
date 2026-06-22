import time
from collections.abc import Callable

from source.join_sim.source import main as join_main
from source.join_sim.source.crash import crash
from source.join_sim.source.server_number import normalize_server_number

RETRY_DELAY_SECONDS = 2
REOPEN_INTERVAL_SECONDS = 15 * 60
REOPEN_PAUSE_SECONDS = 5


def run_auto_join_server(
    server: object,
    status_callback: Callable[[str], object] | None = None,
) -> bool:
    server = normalize_server_number(server)

    def emit(message: str) -> None:
        if status_callback is not None:
            status_callback(message)

    last_reopen = time.monotonic()
    emit(f"Starting auto join for server {server}...")

    while True:
        if crash.detect_crash():
            emit("Crash detected. Reopening game...")
            crash.re_open_game()
            last_reopen = time.monotonic()
            time.sleep(REOPEN_PAUSE_SECONDS)
            continue

        if (
            join_main.is_menu()
            and time.monotonic() - last_reopen >= REOPEN_INTERVAL_SECONDS
        ):
            emit("Still in menu. Reopening game before retrying...")
            crash.re_open_game()
            last_reopen = time.monotonic()
            time.sleep(REOPEN_PAUSE_SECONDS)
            continue

        emit(f"Trying to join server {server}...")
        if join_main.join_round(server):
            emit(f"Joined server {server}.")
            return True

        time.sleep(RETRY_DELAY_SECONDS)
