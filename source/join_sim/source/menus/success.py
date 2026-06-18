import time

from source.join_sim.source.logs import logger as logs
from source.join_sim.source.utility import recon_utils
from source.utility import utils


def bed_spawn():
    return recon_utils.check_template_no_bounds("beds_title", 0.7)


def has_logs():
    return recon_utils.check_template_no_bounds("tribelog_check", 0.8)


def download():
    return recon_utils.check_template_no_bounds("download", 0.7)


def joined_server() -> bool:
    if bed_spawn() or download():
        logs.logger.debug("bed spawn or download detected!")
        return True

    utils.press_key("ShowTribeManager")
    time.sleep(0.5)
    if has_logs():
        logs.logger.debug("tribe log detected")
        return True
    return False
