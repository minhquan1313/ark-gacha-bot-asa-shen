from source.join_sim.source.utility import windows, recon_utils
from source.join_sim.source.logs import logger as logs

buttons = {
    "accept_x": 941, "accept_y": 735,
    "join_last_session_x": 937 , "join_last_session_y":945,
    "start_x":952 , "start_y": 862
}

def get_pixel_loc( location):
    return buttons.get(location)

def is_open():
    return recon_utils.check_template("join_last_session",0.7) or is_disconnected() or is_network_failure()

def is_disconnected():
    return recon_utils.check_template_no_bounds("connection_timeout",0.7)

def is_network_failure():
    return recon_utils.check_template_no_bounds("network_failure",0.7)

def click_start():
    if not is_open():
        return
    if is_disconnected():
        windows.click(get_pixel_loc("accept_x"),get_pixel_loc("accept_y"))
        recon_utils.window_still_open_no_bounds("accept",0.7,1)
    if is_network_failure():
        windows.click(get_pixel_loc("accept_x"),get_pixel_loc("accept_y"))
        recon_utils.window_still_open_no_bounds("network_failure",0.7,1)
    logs.logger.debug("clicking start")
    windows.click(get_pixel_loc("accept_x"),get_pixel_loc("accept_y")) #doesnt effect anything for backup
    windows.click(get_pixel_loc("start_x"),get_pixel_loc("start_y"))
    recon_utils.window_still_open_no_bounds("join_last_session",0.7,1)
