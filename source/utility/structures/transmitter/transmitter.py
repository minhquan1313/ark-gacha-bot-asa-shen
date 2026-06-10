from source.utility import template, windows

buttons = {
    "transfer_to_another_server_button_x": 960,
    "transfer_to_another_server_button_y": 790,
    "back_x": 1800,
    "back_y": 66,
}


def get_pixel_loc(location):
    return buttons.get(location)


def is_open():
    return template.check_template_no_bounds("transmitter_inv", 0.7)


def close():
    if is_open():
        windows.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))
        template.template_await_false("transmitter_inv", 0.7, 1)


def open_transfer_server_list():
    if is_open():
        windows.click(
            get_pixel_loc("transfer_to_another_server_button_x"),
            get_pixel_loc("transfer_to_another_server_button_y"),
        )
