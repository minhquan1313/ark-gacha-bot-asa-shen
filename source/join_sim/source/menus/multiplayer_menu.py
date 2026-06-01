from source.join_sim.source.utility import windows, recon_utils , utils
import pyautogui
import time
from source.join_sim.source.logs import logger as logs

buttons = {
    "search_x": 1672, "search_y": 195,
    "first_server_x": 1672, "first_server_y": 328,
    "join_x": 1672, "join_y": 945,
    "refresh_x": 930, "refresh_y": 937,
    "back_x": 172, "back_y": 885,
    "cancel_x":1069,"cancel_y":727,
    "red_okay_x":952,"red_okay_y":660,
    "mod_join_x":525,"mod_join_y":937
}

def get_pixel_loc( location):
    return buttons.get(location)

def is_open():
    return recon_utils.check_template_no_bounds("multiplayer", 0.7) 

def clear_search():
    return recon_utils.check_template_no_bounds("search",0.7)

def mod_menu():
    return recon_utils.check_template_no_bounds("req_mods",0.7)
    
def join_button():
    return recon_utils.check_template_no_bounds("join_button",0.7)

def search_bar_search(server:str):
    if is_open():
        windows.move_mouse(get_pixel_loc("search_x"), get_pixel_loc("search_y"))
        windows.click(get_pixel_loc("search_x"), get_pixel_loc("search_y"))
        windows.click(get_pixel_loc("search_x"), get_pixel_loc("search_y"))
        time.sleep(0.2)
        utils.ctrl_a()
        time.sleep(0.2)
        utils.write(server)

def exit_menu():
    if is_open():
        windows.click(get_pixel_loc("back_x"),get_pixel_loc("back_y"))
        recon_utils.window_still_open_no_bounds("multiplayer",0.7,1)

def refresh():
    if is_open():
        windows.click(get_pixel_loc("refresh_x"),get_pixel_loc("refresh_y"))
        
def join_server(server:str):
    if mod_menu():
        logs.logger.debug("mod menu open waiting")
        return
    
    if is_open():
        logs.logger.debug("joining server")
        search_bar_search(server)
        time.sleep(1)
        windows.click(get_pixel_loc("first_server_x"), get_pixel_loc("first_server_y"))
        time.sleep(0.5)
        if is_open() and join_button():
            windows.click(get_pixel_loc("join_x"), get_pixel_loc("join_y"))
        
