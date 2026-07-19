import time
from typing import TypeAlias, cast

import pyautogui

import source.logs.gachalogs as logs
from source.ASA.player import player_state
from source.launcher.utils import deposit_helper_capture
from source.utility import template, utils, utils_simple
from source.utility.types import RoiRegion, RoiRegionKey

LBound: TypeAlias = tuple[template.TBound, template.TBound]

CLICK_INTERVAL = 0.2
KEY_PRESS_INTERVAL = 0.1
RESULT_DELAY = 0.5
POLL_INTERVAL = 0.01

FISHING_KEY_TEMPLATES: dict[RoiRegionKey, str] = {
    "fishing_press_q": "q",
    "fishing_press_w": "w",
    "fishing_press_e": "e",
    "fishing_press_a": "a",
    "fishing_press_s": "s",
    "fishing_press_d": "d",
    "fishing_press_z": "z",
    "fishing_press_x": "x",
    # "fishing_press_c": "c",
}
FISHING_RESULT_TEMPLATES: list[RoiRegionKey] = [
    #
    "fishing_failed",
    "fishing_success",
]
FISHING_RESULT_REGION: RoiRegion = {
    "start_x": 512,
    "start_y": 255,
    "width": 888,
    "height": 270,
}
blue_b: LBound = ((90, 30, 200), (100, 255, 255))

FISHING_PRESS_TEMPLATE: list[RoiRegionKey] = [
    "fishing_press_prompt",
    "fishing_press_q",
    "fishing_press_w",
    "fishing_press_e",
    "fishing_press_a",
    "fishing_press_s",
    "fishing_press_d",
    "fishing_press_z",
    "fishing_press_x",
    # "fishing_press_c",
]
FISHING_PRESS_REGION: RoiRegion = {
    "start_x": 550,
    "start_y": 750,
    "width": 800,
    "height": 300,
}
white_b: LBound = ((0, 0, 200), (255, 10, 255))

PRESS_KEY_THRESHOLD = 0.97

registered = False


def register_template_roi():
    """Register placeholder fishing ROIs for later manual configuration."""
    global registered
    if registered:
        return

    registered = True
    # template.IS_DEBUG = True
    # template.DEBUG_ITEM = [k for k in FISHING_KEY_TEMPLATES]
    # template.reset_debug_folder()

    template.register_roi(
        {k: FISHING_RESULT_REGION.copy() for k in FISHING_RESULT_TEMPLATES},
        blue_b[0],
        blue_b[1],
    )

    template.register_roi(
        {k: FISHING_PRESS_REGION.copy() for k in FISHING_PRESS_TEMPLATE},
        white_b[0],
        white_b[1],
    )

    template.templates_preload([k for k in FISHING_KEY_TEMPLATES])


def is_key_prompt():
    return bool(template.check_template("fishing_press_prompt", 0.7))


def is_success():
    return bool(template.check_template("fishing_success", 0.7))


def is_failed():
    return bool(template.check_template("fishing_failed", 0.7))


def is_fishing_done():
    return is_success() or is_failed()


def check_press_key(name: RoiRegionKey):
    return template.check_template(name, PRESS_KEY_THRESHOLD)


def _cast_until_prompt():
    """Click repeatedly until the fishing key prompt appears."""
    logs.logger.info("Casting...")
    while not is_key_prompt():
        player_state.check_disconnected()

        pyautogui.click()
        time.sleep(CLICK_INTERVAL)


def _find_requested_key():
    """Return the first visible fishing key template and mapped key."""
    t_name = template.check_templates(
        "fishing_press_prompt", [k for k in FISHING_KEY_TEMPLATES], PRESS_KEY_THRESHOLD
    )
    if t_name is not None:
        z = FISHING_KEY_TEMPLATES.get(t_name)
        return t_name, cast(str, z)
    return None


def _press_requested_key(
    template_name: RoiRegionKey,
    key: str,
):
    """Press a requested fishing key until its template disappears."""
    utils.press_key(key)
    time.sleep(KEY_PRESS_INTERVAL)

    while check_press_key(template_name):
        utils.press_key(key)
        time.sleep(KEY_PRESS_INTERVAL)


def _wait_for_result():
    """Handle requested keys until fishing succeeds or fails."""
    logs.logger.info("Waiting for fishing prompt...")

    dl = utils_simple.get_default_clock(3)

    while not dl():
        if player_state.check_disconnected():
            return

        if is_fishing_done():
            logs.logger.info("Fishing done.")
            return

        requested_key = _find_requested_key()
        if requested_key is not None:
            logs.logger.info(f"requested_key {requested_key[1]}")
            _press_requested_key(*requested_key)
            dl.reset()
            continue

        time.sleep(POLL_INTERVAL)


def run_auto_fishing(infinite: bool):
    """Run one fishing result, or continue until stopped when infinite is enabled."""

    register_template_roi()

    player_state.human.crouched = False
    player_state.reset_state()

    while True:
        deposit_helper_capture.focus_game_window()

        _cast_until_prompt()
        _wait_for_result()
        time.sleep(RESULT_DELAY)

        if not infinite:
            return
