import time

from source.ASA.player import console, player_state
from source.join_sim.source.menus import success
from source.logs import gachalogs as logs
from source.utility import template, utils, windows
from source.utility.structures.transmitter import transmitter

buttons = {
    "server_search_x": 1500,
    "server_search_y": 180,
    "first_server_x": 400,
    "first_server_y": 320,
    "join_button_x": 1640,
    "join_button_y": 890,
    "back_menu_x": 230,
    "back_menu_y": 895,
    "refresh_x": 994,
    "refresh_y": 896,
    "transfer_not_ready_cancel_x": 1070,
    "transfer_not_ready_cancel_y": 730,
    "failure_connection_accept_x": 849,
    "failure_connection_accept_y": 731,
    "failure_attempting_accept_x": 815,
    "failure_attempting_accept_y": 732,
}


def get_pixel_loc(location):
    return buttons.get(location)


def is_open():
    return template.check_template_no_bounds("transmitter_server_menu", 0.7)


def close():
    if is_open():
        windows.click(get_pixel_loc("back_menu_x"), get_pixel_loc("back_menu_y"))
        template.template_await_false(
            template.check_template_no_bounds, 1, "transmitter_server_menu", 0.7
        )


def is_clear_search():
    return template.check_template_no_bounds("transmitter_server_search", 0.7)


def wait_clear_search(delay=0.1):
    return template.template_await_false(
        template.check_template_no_bounds, delay, "transmitter_server_search", 0.7
    )


def is_server_list_loaded():
    return template.check_template_no_bounds("server_list_trans_loaded", 0.7)


def is_server_join_success():
    return template.check_template("server_trans_success", 0.8)


def is_join_button_visible():
    return template.check_template_no_bounds("transfer_join_button", 0.7)


def wait_server_list_loaded(delay=10):
    return template.template_await_true(
        template.check_template_no_bounds, delay, "server_list_trans_loaded", 0.7
    )


def refresh():
    if is_open():
        windows.click(get_pixel_loc("refresh_x"), get_pixel_loc("refresh_y"))


def join_server():
    if is_open():
        windows.click(get_pixel_loc("join_button_x"), get_pixel_loc("join_button_y"))


def cancel_transfer():
    if is_open():
        windows.click(
            get_pixel_loc("transfer_not_ready_cancel_x"),
            get_pixel_loc("transfer_not_ready_cancel_y"),
        )


def search_bar_search(server: str):
    if not is_open():
        return False

    windows.move_mouse(
        get_pixel_loc("server_search_x"), get_pixel_loc("server_search_y")
    )

    windows.click(get_pixel_loc("server_search_x"), get_pixel_loc("server_search_y"))
    windows.click(get_pixel_loc("server_search_x"), get_pixel_loc("server_search_y"))
    time.sleep(0.2)

    utils.ctrl_a()

    time.sleep(0.2)
    utils.write(server)
    return True


def failure_is_connection_failed():
    return template.check_template_no_bounds("transmitter_server_fail_connection", 0.7)


def failure_is_not_ready():
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
                get_pixel_loc("failure_connection_accept_x"),
                get_pixel_loc("failure_connection_accept_y"),
            )
            time.sleep(1)
        else:
            logs.logger.warning("Server connection timeout but player uploadeded")
            time.sleep(
                10
            )  # Wait 10s, maybe after 10s, the screen will turn to other server
            if is_open() or transmitter.is_open():
                console.console_write("open MainMenu")
                time.sleep(1)

    if failure_is_attempting():
        logs.logger.warning("Pressing back when player is uploading")
        windows.click(
            get_pixel_loc("failure_attempting_accept_x"),
            get_pixel_loc("failure_attempting_accept_y"),
        )
        time.sleep(1)

    if failure_is_not_ready():
        logs.logger.warning("Timer not ready")
        cancel_transfer()
        time.sleep(1)


def do_join_server(server: str):
    if not is_open():
        time.sleep(0.5)
        print("calling joined_server")
        return success.joined_server()

    timeout = utils.get_default_clock()
    while is_open() and not is_server_list_loaded() and not timeout():
        if not wait_server_list_loaded(1):
            refresh()
            player_state.check_disconnected()
    if not is_server_list_loaded():
        return False

    timeout = utils.timed_out_counter(10)
    while is_open() and is_clear_search() and not timeout():
        search_bar_search(server)
        wait_clear_search(1)
        player_state.check_disconnected()
    if is_clear_search():
        return False

    wait_server_list_loaded(1)

    windows.click(get_pixel_loc("first_server_x"), get_pixel_loc("first_server_y"))

    time.sleep(0.3)
    if not template.template_await_true(template.check_transfer_server_orange, 1):
        logs.logger.warning(
            "orange pixel for transmitter server not found likely server is shutdown"
        )
        return False
    else:
        logs.logger.debug("Orange detected, ready for transfer")
        time.sleep(0.3)
        if is_join_button_visible():
            windows.click(
                get_pixel_loc("join_button_x"), get_pixel_loc("join_button_y")
            )

            if template.template_await_true(is_server_join_success, 30):
                # raise RuntimeError("SUCCESS")
                player_state.uploaded = True
                logs.logger.warning("Detected Survival UPLOADED")

                time.sleep(3)
                search_bar_search("Joining...")
                time.sleep(10)
    return False
