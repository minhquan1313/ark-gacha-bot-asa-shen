import time

from source.ASA.player import player_state
from source.join_sim.source import main as join_main
from source.join_sim.source.crash import crash
from source.join_sim.source.logs import logger as join_logs
from source.join_sim.source.menus import multiplayer_menu
from source.join_sim.source.server_number import normalize_server_number
from source.launcher.utils import deposit_helper_capture
from source.logs import gachalogs as logs
from source.utility import utils_simple

REOPEN_INTERVAL_SECONDS = 15 * 60  # 15 mins
JOIN_GAME_MENU_FAIL_THRESHOLD = 30  # amount the screen still in server list menu or can understand it like max number of times menu failed to show up(from back button),


def run_auto_join_server(server: object, afk_join: bool = False):
    logged = False
    server = normalize_server_number(server)

    dl = utils_simple.get_default_clock(REOPEN_INTERVAL_SECONDS)
    cl = utils_simple.get_default_clock()
    join_game_menu_fail_count = 0
    logs.logger.info(f"Starting auto join for server {server}...")

    while True:
        if multiplayer_menu.is_open():  # the server list menu
            join_game_menu_fail_count += 1
            if join_game_menu_fail_count >= JOIN_GAME_MENU_FAIL_THRESHOLD:
                logs.logger.warning("Looks like joining stuck, reopening game...")
                crash.re_open_game()
                join_game_menu_fail_count = 0
                time.sleep(10)
        else:
            join_game_menu_fail_count = 0

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
            logs.logger.info(f"Took {cl.eslapsed_str(normalized=True)} to join.")
            if not afk_join:
                logs.logger.info(f"Joined server {server}.")
                return True
            else:
                if not logged:
                    logs.logger.info("AFK Enabled!")

                    join_logs.disable_log()
                    logs.disable_log()

                    logged = True
                time.sleep(20)
                player_state.reset_state()
                dl.reset()
        elif logged:
            join_logs.disable_log()
            logs.disable_log()
            logged = False
