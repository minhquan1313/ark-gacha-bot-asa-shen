import time

from source.utility import template, utils, windows

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
}


def get_pixel_loc(location):
    return buttons.get(location)


def is_open():
    return template.check_template_no_bounds("transmitter_server_menu", 0.7)


def close():
    if is_open():
        windows.click(get_pixel_loc("back_menu_x"), get_pixel_loc("back_menu_y"))
        template.template_await_false("transmitter_server_menu", 0.7, 1)


def is_clear_search():
    return template.check_template_no_bounds("transmitter_server_search", 0.7)


def is_server_list_loaded():
    return template.check_template_no_bounds("server_list_trans_loaded", 0.7)


def is_server_join_success():
    return template.check_template_no_bounds("server_trans_success", 0.7)


def is_join_button_visible():
    return template.check_template_no_bounds("transfer_join_button", 0.7)


def now():
    return time.monotonic()


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


def do_close():
    if is_open():
        windows.click(get_pixel_loc("back_menu_x"), get_pixel_loc("back_menu_y"))


def do_join_server(server: str) -> bool:
    if not is_open():
        return False

    deadline = now() + 3
    while is_clear_search() and now() < deadline:
        search_bar_search(server)
    if not is_clear_search():
        return False

    deadline = now() + 60
    while not is_server_list_loaded() and now() < deadline:
        refresh()
        time.sleep(0.3)
    if not is_server_list_loaded():
        return False

    time.sleep(0.1)
    windows.click(get_pixel_loc("first_server_x"), get_pixel_loc("first_server_y"))

    time.sleep(0.5)
    if is_open() and is_join_button_visible():
        windows.click(get_pixel_loc("join_button_x"), get_pixel_loc("join_button_y"))
        return True
    else:
        return False
