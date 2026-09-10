import time

import settings
from source.ASA import config
from source.ASA.player import console, player_inventory, player_state
from source.ASA.strucutres import bed, teleporter
from source.gacha_bot import render
from source.join_sim.source import main
from source.join_sim.source.menus import success
from source.logs import gachalogs as logs
from source.utility import ark_input, template, utils, utils_simple, windows
from source.utility.structures.transmitter import transmitter

buttons = {
    "transfer_to_another_server_button": (960, 790),
    "server_search": (1500, 180),
    "first_server": (400, 320),
    "join_button": (1640, 890),
    "back_menu": (230, 895),
    "refresh": (994, 896),
    "transfer_not_ready_cancel": (1070, 730),
    "failure_connection_accept": (849, 731),
    "failure_attempting_accept": (815, 732),
}


def get_pixel_loc(location):
    return buttons.get(location, (0, 0))


def is_open():
    return template.check_template_no_bounds("transmitter_server_menu", 0.7)


def open():
    if not transmitter.is_open():
        return

    windows.click(
        *get_pixel_loc("transfer_to_another_server_button"),
    )

    if not template.template_await_true(is_open, 3):
        logs.logger.error("Can't open transmitter server menu")
        return

    time.sleep(0.5)


def close():
    attempts = 0
    while is_open():
        attempts += 1
        logs.logger.debug(
            f"Trying to close Transmitter menu inventory {attempts} / {config.inventory_close_attempts}"
        )
        windows.click(*get_pixel_loc("back_menu"))
        time.sleep(0.2)

        has_failure()

        if not template.template_await_false(is_open, 2):
            return time.sleep(0.3)

        if attempts >= config.inventory_close_attempts:
            logs.logger.error(
                f"Unable to close Transmitter menu after {attempts} attempts"
            )
            # check state of the char the reason we can do it now is that the latter should spam click close inv
            player_state.check_disconnected()
            break


def is_clear_search():
    return template.check_template_no_bounds("transmitter_server_search", 0.7)


def wait_clear_search(delay=0.1):
    return template.template_await_false(
        template.check_template_no_bounds, delay, "transmitter_server_search", 0.7
    )


def is_server_list_loaded():
    return template.check_template_no_bounds("server_list_trans_loaded", 0.7)


def is_server_join_success():
    return template.check_template("server_trans_uploaded", 0.9)


def is_join_button_visible():
    return template.check_template_no_bounds("transfer_join_button", 0.7)


def wait_server_list_loaded(delay=10):
    return template.template_await_true(
        template.check_template_no_bounds, delay, "server_list_trans_loaded", 0.7
    )


def refresh():
    if is_open():
        windows.click(*get_pixel_loc("refresh"))


def join_server():
    if is_open():
        windows.click(*get_pixel_loc("join_button"))


def cancel_transfer():
    if is_open():
        windows.click(
            *get_pixel_loc("transfer_not_ready_cancel"),
        )


def search_bar_search(server: str):
    if not is_open():
        return False

    windows.game_move_mouse(*get_pixel_loc("server_search"))

    windows.click(*get_pixel_loc("server_search"))
    windows.click(*get_pixel_loc("server_search"))
    time.sleep(0.2)

    utils.ctrl_a()

    time.sleep(0.2)
    utils.write(server)
    return True


def failure_is_connection_failed():
    return template.check_template_no_bounds("transmitter_server_fail_connection", 0.7)


def failure_excess_amount():
    transmitter.was_excess_amount = template.check_template(
        "transmitter_server_excess", 0.8
    )
    # transmitter.was_excess_amount = False
    return transmitter.was_excess_amount


def failure_is_not_ready():
    """This happened right after click transfer IF Player still has timer, not ready to upload yet, so expect to press cancel to prevent item loss"""
    return template.check_template_no_bounds("transfer_not_ready_popup", 0.7)


def failure_is_attempting():
    return template.check_template_no_bounds("transmitter_server_fail_attempting", 0.7)


def has_failure():
    if failure_is_connection_failed():
        if not player_state.uploaded:
            logs.logger.warning(
                "Server connection timeout but player still not uploaded"
            )
            windows.click(
                *get_pixel_loc("failure_connection_accept"),
            )
            time.sleep(1)
        else:
            logs.logger.warning("Server connection timeout but player UPLOADED")
            # After accepting, game may open main menu auto, so just wait so just in case
            windows.click(
                *get_pixel_loc("failure_connection_accept"),
            )

            time.sleep(
                10
            )  # Wait 10s, maybe after 10s, the screen will turn to other server

            if is_open() or transmitter.is_open():
                console.console_write("open MainMenu")
                time.sleep(1)

    if failure_is_attempting():
        logs.logger.warning("Pressing back when player is uploading")
        windows.click(
            *get_pixel_loc("failure_attempting_accept"),
        )
        time.sleep(1)

    if failure_is_not_ready():
        logs.logger.warning("Timer not ready")
        cancel_transfer()
        time.sleep(1)


def transfer_timer_handle(should_go_tekpod=True):
    should_go_tek_pod = utils_simple.get_default_clock(30)
    sleep_tek_pod_for = 10
    while failure_is_not_ready():
        # Timer not ready
        time.sleep(1)
        cancel_transfer()
        time.sleep(0.2)

        if should_go_tekpod and should_go_tek_pod():
            cl = utils_simple.get_default_clock()

            cancel_transfer()
            time.sleep(0.2)
            close()
            current_tele = teleporter._last_teleporter_name
            teleporter.teleport_not_default(settings.bed_spawn)
            render.enter_tekpod(allow_eat_implant=False)
            player_inventory.open()

            time.sleep(max(5, sleep_tek_pod_for - cl.eslapsed()))

            player_state.check_state()
            teleporter.teleport_not_default(current_tele)

            return False

        windows.click(*get_pixel_loc("first_server"))
        time.sleep(0.2)
        windows.click(*get_pixel_loc("join_button"))
        time.sleep(0.2)

        if player_state.check_disconnected():
            return False

    return True


def sign_of_uploaded():
    return bed.is_open_respawn() or main.is_menu()


def do_join_server(server: str, *, should_go_tekpod=True):
    if not is_open():
        time.sleep(0.5)
        logs.logger.debug(
            "Don't detect transmitter server menu, maybe already joined server, checking..."
        )
        return success.joined_server()

    dl = utils_simple.get_default_clock()
    while is_open() and not is_server_list_loaded() and not dl():
        if not wait_server_list_loaded(1):
            refresh()
            player_state.check_disconnected()
    if not is_server_list_loaded():
        return False

    dl = utils_simple.get_default_clock(10)
    while is_open() and is_clear_search() and not dl():
        search_bar_search(server)
        wait_clear_search(1)
        player_state.check_disconnected()
    if is_clear_search():
        return False

    wait_server_list_loaded(1)

    windows.click(*get_pixel_loc("first_server"))

    if not template.template_await_true(template.check_transfer_server_orange, 1):
        logs.logger.warning(
            "orange pixel for transmitter server not found likely server is shutdown"
        )
        return False

    logs.logger.debug("Orange detected, ready for transfer")
    time.sleep(0.1)

    can_join = False
    if template.template_await_true(is_join_button_visible, 1):
        can_join = True
    if not can_join:
        return False

    time.sleep(0.1)
    windows.click(*get_pixel_loc("join_button"))
    time.sleep(0.2)

    if not transfer_timer_handle(should_go_tekpod):
        return False

    dl = utils_simple.get_default_clock(60)
    while is_open():
        if dl():
            close()
            break

        player_state.uploaded = False

        dl2 = utils_simple.get_default_clock(5)
        clicked = 1  # Don't change, as previous we already clicked it once, so it should start as 1
        max_click = 2
        # Click join button again
        while not dl2():
            if template.template_await_true(is_server_join_success, 0.8):
                player_state.uploaded = True
                break

            if failure_excess_amount():
                close()
                return False

            if clicked < max_click:
                clicked += 1
                windows.click(
                    *get_pixel_loc("first_server"),
                )
                time.sleep(0.1)

                windows.click(
                    *get_pixel_loc("join_button"),
                )

        if player_state.uploaded:
            logs.logger.warning("Detected Survival UPLOADED")

            time.sleep(2)

            if is_open():
                search_bar_search("Joining...")
                ark_input.click(2, 2)

            if template.template_await_true(sign_of_uploaded, 30):  # noqa: SIM103
                # Return False intentionally to trigger one additional verification cycle.
                return False if bed.is_open_respawn() else True  # noqa: SIM211
            else:
                # Return True to exit when the upload succeeded but the destination server never loaded.
                console.console_exit_mainmenu()
                template.template_await_true(sign_of_uploaded, 10)
                time.sleep(0.5)
                return True
        elif sign_of_uploaded():
            logs.logger.warning("Detected Survival UPLOADED")
            player_state.uploaded = True
            return True
        else:
            has_failure()

            if is_open():
                windows.click(
                    *get_pixel_loc("first_server"),
                )
                time.sleep(0.1)

                windows.click(
                    *get_pixel_loc("join_button"),
                )
            else:
                break

    has_failure()

    return False
