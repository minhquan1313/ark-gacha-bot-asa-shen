from source.join_sim.source import main as join_main
from source.join_sim.source.crash import crash
from source.join_sim.source.server_number import normalize_server_number
from source.launcher.utils import deposit_helper_capture
from source.logs import gachalogs as logs
from source.utility import utils_simple

REOPEN_INTERVAL_SECONDS = 15 * 60  # 15 mins


def run_auto_join_server(server: object):
    server = normalize_server_number(server)

    dl = utils_simple.get_default_clock(REOPEN_INTERVAL_SECONDS)
    logs.logger.info(f"Starting auto join for server {server}...")

    while True:
        if crash.detect_crash():
            logs.logger.warning("Crash detected. Reopening game...")
            crash.re_open_game()
            dl.reset()
            continue

        deposit_helper_capture.focus_game_window()

        if join_main.is_menu() and dl():
            logs.logger.info("Still in menu. Reopening game before retrying...")
            crash.re_open_game()
            dl.reset()
            continue

        logs.logger.info(f"Trying to join server {server}...")
        if join_main.join_round(server):
            logs.logger.info(f"Joined server {server}.")
            return True
