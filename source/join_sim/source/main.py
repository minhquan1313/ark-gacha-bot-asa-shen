import time

import source.join_sim.source.crash.crash as crash
from source.join_sim.source.logs import logger as logs
from source.join_sim.source.menus import (
    failure,
    join_game_menu,
    mod_menu,
    multiplayer_menu,
    start_menu,
    success,
)
from source.join_sim.source.utility import recon_utils
from source.utility import windows

server = 0000


def is_menu():
    return recon_utils.check_template_no_bounds(
        "escape", 0.7
    ) or recon_utils.check_template_no_bounds("escape_obscured", 0.7)


def is_crashed():
    return crash.detect_crash()


def join_round(server: str) -> bool:
    if not is_menu():
        time.sleep(0.5)
        logs.logger.debug("joined server")
        return success.joined_server()  # if we arent in the menu we need to restart

    if not recon_utils.template_await_false(
        recon_utils.check_template, 10.0, "is_logging", 0.7
    ):
        logs.logger.debug("Game logged in")
    else:
        print("failed to log in")
        logs.logger.error("Game failed to log in")
        return False

    start_menu.click_start()
    time.sleep(0.5)
    join_game_menu.click_join_game()
    time.sleep(0.5)
    multiplayer_menu.join_server(server)
    time.sleep(0.5)
    mod_menu.mod_menu_join()
    time.sleep(0.5)
    failure.has_failure()
    time.sleep(0.5)

    return False


def sim_loop():
    if is_menu():
        flag = False
        logs.logger.debug("starting sim")
        while flag != True:
            flag = join_round(server)
            time.sleep(0.2)
        logs.logger.debug("stop sim")


def main_loop(server=server):
    # check if crashed, if crashed reset
    if crash.detect_crash():
        crash.re_open_game()
    # check if in main menu
    if is_menu():
        # start sim close game every 15 20 mins incase server crashed
        flag = False
        time1 = time.time()
        logs.logger.debug("starting sim")
        while flag != True:

            if time.time() - time1 >= 15 * 60 or crash.detect_crash():
                crash.re_open_game()
                time1 = time.time()
                time.sleep(5)

            time.sleep(0.2)
            flag = join_round(server)
            time.sleep(2)

        logs.logger.debug("stop sim")
        return windows.ark_hwnd()


if __name__ == "__main__":
    main_loop()
