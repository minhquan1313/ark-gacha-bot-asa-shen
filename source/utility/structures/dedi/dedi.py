from source.join_sim.source.utility import recon_utils
from source.utility import template

buttons = {}


def get_pixel_loc(location):
    return buttons.get(location)


def is_open(): ...


def is_server_list_loaded(): ...
