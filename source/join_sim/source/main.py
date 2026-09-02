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
from source.utility import ark_input, utils_simple, windows

was_in_mainmenu = False


def is_menu():
    return is_menu_clear() or is_menu_obscured()


def is_menu_clear() -> bool:
    return recon_utils.check_template_no_bounds("escape", 0.7)


def is_menu_obscured():
    return recon_utils.check_template_no_bounds("escape_obscured", 0.7)


def is_logging_in():
    return recon_utils.check_template("is_logging", 0.7)


def is_crashed():
    return crash.detect_crash()


def is_pause_menu():
    return recon_utils.check_template("pause_menu", 0.7)


should_click = True


def join_round(server: str):
    global should_click
    if should_click:
        # This click will skip game intro
        ark_input.click(2, 2)
    # Assume
    was_logging_in = is_logging_in()

    if not is_menu():
        time.sleep(0.5)
        logs.logger.debug("joined server")
        return success.joined_server()  # if we arent in the menu we need to restart

    global was_in_mainmenu
    was_in_mainmenu = True

    if not recon_utils.template_await_false(is_logging_in, 10.0):
        if was_logging_in:
            logs.logger.debug("Game logged in")
    else:
        print("failed to log in")
        logs.logger.error("Game failed to log in")
        return False

    if start_menu.click_start():
        time.sleep(0.5)

    if join_game_menu.click_join_game():
        time.sleep(0.5)

    if multiplayer_menu.join_server(server):
        should_click = False
        time.sleep(0.5)

        if mod_menu.is_loading():
            recon_utils.template_await_false(mod_menu.is_loading, 3)
            recon_utils.template_await_true(mod_menu.is_open, 3)
            time.sleep(0.3)
        else:
            time.sleep(0.5)

    if mod_menu.mod_menu_join():
        time.sleep(0.5)

    if failure.has_failure():
        ark_input.click(2, 2)
        time.sleep(0.5)

    return False


def main_loop(server="0000"):
    # check if crashed, if crashed reset
    if crash.detect_crash():
        crash.re_open_game()
    # check if in main menu
    if is_menu():
        # start sim close game every 15 20 mins incase server crashed
        is_success = False
        dl = utils_simple.get_default_clock(60 * 15)
        logs.logger.debug("starting sim")
        while not is_success:
            if dl() or crash.detect_crash():
                crash.re_open_game()
                time.sleep(0.2)
                dl.reset()

            is_success = join_round(server)
            time.sleep(0.2)

        logs.logger.debug("stop sim")
        return windows.ark_hwnd()


if __name__ == "__main__":
    main_loop()
