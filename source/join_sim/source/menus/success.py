import time

from source.ASA.player import player_state
from source.ASA.strucutres import bed
from source.join_sim.source import main as join_sim
from source.join_sim.source.logs import logger as logs
from source.join_sim.source.utility import recon_utils
from source.utility import utils


def bed_spawn():
    return bed.is_open() if not player_state.uploaded else bed.is_open_respawn()


def has_logs():
    return recon_utils.check_template_no_bounds("tribelog_check", 0.8)


def download():
    return recon_utils.check_template_no_bounds("download", 0.7)


was_has_logs = False


def joined_server():
    global was_has_logs
    was_has_logs = False

    if bed_spawn() or download():
        logs.logger.debug("bed spawn or download detected!")
        join_sim.should_click = True
        return True

    utils.press_key("ShowTribeManager")
    time.sleep(0.5)
    if has_logs():
        join_sim.should_click = True
        was_has_logs = True
        logs.logger.debug("tribe log detected")
        return True
    return False
