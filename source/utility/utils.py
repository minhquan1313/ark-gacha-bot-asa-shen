import ctypes
import time

import settings
from source.ASA.player import console
from source.logs import gachalogs as logs

from . import local_player, windows

"""
FUNCTIONS FOR KEYBOARD 
"""
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102

keymap = {
    "tab": 0x09,
    "escape": 0x1B,
    "return": 0x0D,
    "enter": 0x0D,
    "leftcontrol": 0xA2,
    "zero": 0x30,
    "one": 0x31,
    "two": 0x32,
    "three": 0x33,
    "four": 0x34,
    "five": 0x35,
    "six": 0x36,
    "seven": 0x37,
    "eight": 0x38,
    "nine": 0x39,
    "thumbmousebutton": 0x05,
    "thumbmousebutton2": 0x06,
    "spacebar": 0x20,
    "hyphen": 0xBD,
    "leftshift": 0xA0,
    "tilde": 0xC0,
}

default_keymap = {
    "use": "e",
    "consolekeys": "tilde",
    "showtribemanager": "l",
    "showmyinventory": "i",
    "accessinventory": "f",
    "dropitem": "o",
    "pausemenu": "escape",
    "reload": "r",
    "run": "leftshift",
    "crouch": "c",
    "useitem1": "one",
    "useitem2": "two",
    "useitem3": "three",
    "useitem4": "four",
    "useitem5": "five",
    "useitem6": "six",
    "useitem7": "seven",
    "useitem8": "eight",
    "useitem9": "nine",
    "useitem10": "zero",
}

_VkKeyScanW = ctypes.WINFUNCTYPE(
    ctypes.c_short,
    ctypes.c_wchar,
)(("VkKeyScanW", ctypes.windll.user32))


def keymap_return(key_input):
    key = key_input.lower()

    if (
        key in default_keymap
    ):  # this would only be triggered if the input.ini file is empty || base key mpa

        key = default_keymap[key]
        if key in keymap:
            return keymap[key]

    if key in keymap:
        return keymap[key]

    if len(key) == 1:
        result = _VkKeyScanW(key)

        vk_code = result & 0xFF

        return vk_code


def press_key(input_action):
    vk_code = keymap_return(local_player.get_input_settings(input_action))
    hwnd = windows.ark_hwnd()

    ctypes.windll.user32.PostMessageW(hwnd, WM_KEYDOWN, vk_code, 0)
    time.sleep(0.05)
    ctypes.windll.user32.PostMessageW(hwnd, WM_KEYUP, vk_code, 0)


def post_charecter(char):
    ctypes.windll.user32.PostMessageW(windows.ark_hwnd(), WM_CHAR, ord(char), 0)


def write(text):
    for c in text:
        post_charecter(c)


def ctrl_a():  # hotkey for sending ctrl a
    hwnd = windows.ark_hwnd()
    ctypes.windll.user32.SendMessageW(hwnd, WM_KEYDOWN, 0x11, 0)
    time.sleep(0.1)
    ctypes.windll.user32.SendMessageW(hwnd, WM_KEYDOWN, 0x41, 0)
    time.sleep(0.1)

    ctypes.windll.user32.SendMessageW(hwnd, WM_KEYUP, 0x41, 0)
    time.sleep(0.1)
    ctypes.windll.user32.SendMessageW(hwnd, WM_KEYUP, 0x11, 0)


def time_now():
    return time.monotonic()


def timed_out_counter(limit_seconds=3):
    timeout = time_now() + limit_seconds

    def is_excess():
        return time_now() >= timeout

    return is_excess


"""
FUNCTIONS FOR MOUSE MOVEMENT
"""

current_yaw = 0
current_pitch = 0
player_pitch_minimum = -80
player_pitch_max = 87
_CCC_NOT_PROVIDED = object()


def normalize_yaw(yaw):
    yaw = (yaw % 360 + 360) % 360
    if yaw > 180:
        yaw -= 360
    return yaw


def set_yaw(yaw):
    """
    Trigger CCC
    """

    global current_yaw
    global current_pitch
    ccc_data = console.console_ccc()
    if ccc_data is None:
        logs.logger.warning("CCC unavailable; setting yaw from cached angle")
    else:
        try:
            current_yaw = float(ccc_data[3])
            current_pitch = float(ccc_data[4])
            logs.logger.debug(f"setting yaw as {current_yaw}")
        except (IndexError, TypeError, ValueError) as e:
            logs.logger.error(f"error processing ccc yaw and pitch: {e}")

    try:  # had an issue where this was a string for some reason
        target = float(yaw)
        current = float(current_yaw)

        diff = ((target - current) + 180) % 360 - 180
        if diff < 0:
            turn_left(-diff)
        else:
            turn_right(diff)
        current_yaw = normalize_yaw(target)
    except Exception as e:
        logs.logger.error(f"error processing data into floats: {e}")


def set_pitch(pitch):
    """
    Won't trigger CCC
    """
    global current_pitch
    change = current_pitch - pitch
    if change < 0:
        turn_up(-change)
    else:
        turn_down(change)
    current_pitch = pitch


def yaw_zero(ccc_data=_CCC_NOT_PROVIDED):
    """
    Trigger CCC if ccc not provided

    Will trigger MOSTLY
    """

    global current_yaw

    if ccc_data is _CCC_NOT_PROVIDED:
        ccc_data = console.console_ccc()
    if ccc_data is None:
        logs.logger.warning("CCC unavailable; unable to zero yaw")
        return False
    try:
        if float(ccc_data[3]) > 0:
            turn_left(float(ccc_data[3]))
        else:
            turn_right(-float(ccc_data[3]))
        current_yaw = 0
        return True
    except (IndexError, TypeError, ValueError) as e:
        logs.logger.error(f"error processing ccc_data[3]: {e}")
        return False


def pitch_zero(ccc_data=_CCC_NOT_PROVIDED):
    """
    Trigger CCC if ccc not provided

    Will trigger MOSTLY
    """

    global current_pitch

    if ccc_data is _CCC_NOT_PROVIDED:
        ccc_data = console.console_ccc()
    if ccc_data is None:
        logs.logger.warning("CCC unavailable; unable to zero pitch")
        return False
    try:
        if float(ccc_data[4]) > 0:
            turn_down(float(ccc_data[4]))
        else:
            turn_up(-float(ccc_data[4]))
        current_pitch = 0
        return True
    except (IndexError, TypeError, ValueError) as e:
        logs.logger.error(f"error processing ccc_data[4]: {e}")
        return False


def zero_center(target_yaw=settings.station_yaw):
    """
    Trigger CCC

    Will set yaw to settings.station_yaw by default and pitch to 0.
    So player should be aiming at the desired center view
    """

    logs.logger.debug("setting view angles back to station_yaw and pitch 0")

    global current_yaw
    global current_pitch

    ccc_data = console.console_ccc()
    if ccc_data is None:
        logs.logger.warning("CCC unavailable; setting yaw from cached angle")
    else:
        try:
            current_yaw = float(ccc_data[3])
            current_pitch = float(ccc_data[4])
            logs.logger.debug(f"setting yaw as {current_yaw}")
        except (IndexError, TypeError, ValueError) as e:
            logs.logger.error(f"error processing ccc yaw and pitch: {e}")

    try:  # had an issue where this was a string for some reason
        pitch_zero(ccc_data)

        target = float(target_yaw)
        current = float(current_yaw)

        diff = ((target - current) + 180) % 360 - 180
        if diff < 0:
            turn_left(-diff)
        else:
            turn_right(diff)
        current_yaw = normalize_yaw(target)
    except Exception as e:
        logs.logger.error(f"error processing data into floats: {e}")


def zero():
    """
    Trigger CCC
    """

    logs.logger.debug("setting view angles back to 0")
    global current_yaw
    global current_pitch
    ccc_data = console.console_ccc()
    if ccc_data is None:
        logs.logger.warning("CCC unavailable; unable to zero view angles")
        return False

    yaw_zeroed = yaw_zero(ccc_data)
    pitch_zeroed = pitch_zero(ccc_data)
    return yaw_zeroed and pitch_zeroed


def get_yaw_pitch():
    """
    Trigger CCC
    """

    global current_pitch
    global current_yaw
    ccc_data = console.console_ccc()
    if ccc_data is None:
        raise RuntimeError("CCC unavailable; unable to read yaw and pitch")
    current_yaw = float(ccc_data[3])
    current_pitch = float(ccc_data[4])
    return ccc_data[3], ccc_data[4]  # yaw , pitch


def turn_right(degrees):
    """
    Won't trigger CCC

    Args:
        degrees (float): Must be positive number
    """

    global current_yaw
    windows.turn(degrees, 0)
    current_yaw = float(current_yaw)
    current_yaw = normalize_yaw(current_yaw + degrees)


def turn_left(degrees):
    """
    Won't trigger CCC

    Args:
        degrees (float): Must be positive number
    """

    global current_yaw
    windows.turn(-degrees, 0)
    current_yaw = float(current_yaw)
    current_yaw = normalize_yaw(current_yaw + (-degrees))


def turn_down(degrees):
    """
    Won't trigger CCC

    Args:
        degrees (float): Must be positive number
    """

    global current_pitch
    current_pitch = float(current_pitch)
    allowed = min(abs(player_pitch_minimum - current_pitch), degrees)
    windows.turn(0, allowed)
    current_pitch -= allowed


def turn_up(degrees):
    """
    Won't trigger CCC

    Args:
        degrees (float): Must be positive number
    """

    global current_pitch
    current_pitch = float(current_pitch)
    allowed = min(abs(player_pitch_max - current_pitch), degrees)
    windows.turn(0, -allowed)
    current_pitch += allowed


def turn_to(yaw, pitch):
    """
    Won't trigger CCC

    Args:
        yaw (float): ccc[3]
        pitch (float): ccc[4]
    """

    global current_yaw
    global current_pitch
    inital_pitch = current_pitch
    inital_yaw = current_yaw

    diff_yaw = ((yaw - inital_yaw) + 180) % 360 - 180
    if diff_yaw < 0:
        turn_left(-diff_yaw)
    else:
        turn_right(diff_yaw)
    current_yaw = yaw
    diff_pitch = pitch - inital_pitch
    if diff_pitch > 0:
        turn_up(diff_pitch)
    else:
        turn_down(-diff_pitch)
    current_pitch = pitch
