import time
from typing import Callable

import settings
from source.ASA.player import player_state
from source.ASA.strucutres import inventory, teleporter
from source.logs import gachalogs as logs
from source.utility import utils, utils_simple
from source.utility.types import ObjectAim, ObjectTurn


class ObjectViewMetaData:
    crouch_data: bool

    yaw: float = 0.0
    pit: float = 0.0

    t_up: float = 0.0
    t_do: float = 0.0
    t_le: float = 0.0
    t_ri: float = 0.0

    def __init__(
        self,
        crouched=False,
        *,
        turn_data: ObjectTurn | None = None,
        precise_data: ObjectAim | None = None,
    ):
        self.crouch_data = crouched

        self.yaw = settings.station_yaw

        if precise_data is not None:
            self.yaw = precise_data.get("yaw")
            self.pitch = precise_data.get("pitch")
            self.look = self._look_precise
        elif turn_data is not None:
            self.t_up = turn_data.get("up", 0.0)
            self.t_do = turn_data.get("down", 0.0)
            self.t_le = turn_data.get("left", 0.0)
            self.t_ri = turn_data.get("right", 0.0)
            self.look = self._look_turn
        else:
            raise ValueError("Require turn_data or precise_data")

    def look(self):
        pass

    def crouch(self):
        h = player_state.human
        h.crouch() if self.crouch_data else h.reset_crouch()

    def _look_turn(self):
        self.crouch()

        utils.zero_center_no_ccc()

        if self.t_up:
            utils.turn_up(self.t_up)
        if self.t_do:
            utils.turn_down(self.t_do)
        if self.t_le:
            utils.turn_left(self.t_le)
        if self.t_ri:
            utils.turn_right(self.t_ri)

        time.sleep(0.2)

    def _look_precise(self):
        self.crouch()

        utils.turn_to(self.yaw, self.pit)

        time.sleep(0.2)


def open_structure_and_check(
    teleport: str,
    view_data: ObjectViewMetaData,
    is_open: Callable[..., bool] = inventory.is_open,
    *,
    name="Object",
    attempt_limit: int = 0,
    time_limit: int = 0,
):

    check_with_time = False
    check_with_attempt = False

    if attempt_limit:
        check_with_attempt = True

    temp = utils_simple.get_default_timeout_value()
    if time_limit:
        check_with_time = True
        temp = time_limit

    dl = utils_simple.get_default_clock(temp)

    view_data.look()
    inventory.open()

    attempt = 0
    while not is_open():
        attempt += 1

        if (check_with_attempt and attempt > attempt_limit) or (check_with_time and dl()):
            logs.logger.error(f"{name} at {teleport} failed to access after {attempt} attempts")
            return False

        inventory.open()
        if is_open():
            return True
        else:
            logs.logger.debug(f"{name} at {teleport} could not be accessed, retrying {attempt}{f' / {attempt_limit}' if attempt_limit else ' inf'}")

            player_state.check_state()
            teleporter.teleport_not_default(teleport)
            utils.get_yaw_pitch()
            view_data.look()

    return True
