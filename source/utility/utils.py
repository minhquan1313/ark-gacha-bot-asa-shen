import ctypes
import time

import settings
from source.ASA import config
from source.ASA.player import console
from source.launcher.utils import deposit_helper_capture
from source.logs import gachalogs as logs
from source.utility import action_gate, utils_simple

from . import local_player, windows

"""
FUNCTIONS FOR KEYBOARD 
"""
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
KEYEVENTF_KEYUP = 0x0002

keymap = {
    "backspace": 0x08,
    "tab": 0x09,
    "esc": 0x1B,
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
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "delete": 0x2E,
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
    "moveforward": "w",
    "movebackward": "s",
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


def keymap_return(key_input: str):
    """Resolve an ARK action, named key, F1-F24, or character to a virtual-key code."""
    key = key_input.lower()

    if (
        key in default_keymap
    ):  # this would only be triggered if the input.ini file is empty || base key mpa
        key = default_keymap[key]
        if key in keymap:
            return keymap[key]

    if key in keymap:
        return keymap[key]

    # For F1-F24 keys, the virtual-key codes are 0x70 through 0x87.
    if key.startswith("f") and key[1:].isdigit():
        number = int(key[1:])
        if 1 <= number <= 24:
            return 0x6F + number

    if len(key) == 1:
        result = _VkKeyScanW(key)

        vk_code = result & 0xFF

        return vk_code


def press_key(input_action):
    press_action(input_action, 0.05)


def _mouse_message(input_key, pressed):
    messages = {
        "leftmousebutton": (WM_LBUTTONDOWN, WM_LBUTTONUP),
        "rightmousebutton": (WM_RBUTTONDOWN, WM_RBUTTONUP),
        "middlemousebutton": (WM_MBUTTONDOWN, WM_MBUTTONUP),
    }
    pair = messages.get(input_key.lower())
    if pair is None:
        return None
    return pair[0 if pressed else 1]


def _mouse_lparam(hwnd):
    point = windows.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    ctypes.windll.user32.ScreenToClient(hwnd, ctypes.byref(point))
    return ((point.y & 0xFFFF) << 16) | (point.x & 0xFFFF)


def _send_mouse_button(input_key, pressed):
    flags = {
        "leftmousebutton": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
        "rightmousebutton": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
        "middlemousebutton": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
    }.get(str(input_key).lower())
    if flags is None:
        return False
    input_event = windows.INPUT(type=windows.INPUT_MOUSE)
    input_event.mi = windows.MOUSEINPUT(
        dx=0,
        dy=0,
        mouseData=0,
        dwFlags=flags[0 if pressed else 1],
        time=0,
        dwExtraInfo=0,
    )
    ctypes.windll.user32.SendInput(
        1, ctypes.byref(input_event), ctypes.sizeof(windows.INPUT)
    )
    return True


def action_down(input_action: str, *, should_pause: bool = True):
    """Send an action down event, optionally waiting for automation to resume."""
    if should_pause:
        action_gate.before_ark_action()
    input_key = local_player.get_input_settings(input_action)
    hwnd = windows.ark_hwnd()
    if _send_mouse_button(input_key, True):
        return
    mouse_message = _mouse_message(input_key, True)
    if mouse_message is not None:
        ctypes.windll.user32.PostMessageW(hwnd, mouse_message, 0, _mouse_lparam(hwnd))
        return
    vk_code = keymap_return(input_key)
    ctypes.windll.user32.PostMessageW(hwnd, WM_KEYDOWN, vk_code, 0)


def action_up(input_action):
    """Send a resolved keyboard or mouse action up event to ARK."""
    input_key = local_player.get_input_settings(input_action)
    hwnd = windows.ark_hwnd()
    if _send_mouse_button(input_key, False):
        return
    mouse_message = _mouse_message(input_key, False)
    if mouse_message is not None:
        ctypes.windll.user32.PostMessageW(hwnd, mouse_message, 0, _mouse_lparam(hwnd))
        return
    vk_code = keymap_return(input_key)
    ctypes.windll.user32.PostMessageW(hwnd, WM_KEYUP, vk_code, 0)


def key_hold_down(input_action: str, *, should_pause: bool = True):
    """Send a physical key down event, optionally waiting for automation to resume."""
    if should_pause:
        action_gate.before_ark_action()
    input_key = local_player.get_input_settings(input_action)
    vk_code = keymap_return(input_key)
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)


def key_hold_up(input_action):
    """Release a physical keyboard event started by ``key_hold_down``."""
    input_key = local_player.get_input_settings(input_action)
    vk_code = keymap_return(input_key)
    ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


def press_action(input_action, hold_duration=0.05):
    """Send one resolved action press with a configurable down/up delay."""
    action_gate.before_ark_action()
    action_down(input_action)
    try:
        time.sleep(hold_duration)
    finally:
        action_up(input_action)


def post_charecter(char):
    action_gate.before_ark_action()
    ctypes.windll.user32.PostMessageW(windows.ark_hwnd(), WM_CHAR, ord(char), 0)


def write(text):
    action_gate.before_ark_action()
    for c in text:
        post_charecter(c)


def ctrl_a():  # hotkey for sending ctrl a
    action_gate.before_ark_action()
    hwnd = windows.ark_hwnd()
    ctypes.windll.user32.SendMessageW(hwnd, WM_KEYDOWN, 0x11, 0)
    time.sleep(0.1)
    ctypes.windll.user32.SendMessageW(hwnd, WM_KEYDOWN, 0x41, 0)
    time.sleep(0.1)

    ctypes.windll.user32.SendMessageW(hwnd, WM_KEYUP, 0x41, 0)
    time.sleep(0.1)
    ctypes.windll.user32.SendMessageW(hwnd, WM_KEYUP, 0x11, 0)


def close_ark_with_console_exit():
    """Try closing a visible ARK window through the in-game console."""

    for attempt in range(1, config.console_open_attempts + 1):
        hwnd = windows.ark_hwnd()
        if not hwnd or not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True

        logs.logger.debug(
            f"closing ARK with console exit {attempt} / {config.console_open_attempts}"
        )
        try:
            deposit_helper_capture.focus_game_window(center_cursor_when_switching=True)
            # player_state.reset_state()
            if not console.console_write("exit"):
                logs.logger.warning("ARK console did not accept the exit command")
        except Exception as e:
            logs.logger.warning(f"ARK exit command failed: {e}")

    dl = utils_simple.get_default_clock(5)
    while not dl():
        hwnd = windows.ark_hwnd()
        if not hwnd or not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True
        else:
            time.sleep(0.2)

    logs.logger.warning("ARK did not close gracefully; forcing shutdown")
    return False


"""
FUNCTIONS FOR MOUSE MOVEMENT
"""

current_yaw = 0.0
current_pitch = 0.0
player_pitch_minimum = -80.0
player_pitch_max = 87.0
was_initialized = False
_CCC_NOT_PROVIDED = object()


def normalize_yaw(yaw: float):
    yaw = (yaw % 360 + 360) % 360
    if yaw > 180:
        yaw -= 360
    return yaw


def set_yaw(yaw, ccc_data=_CCC_NOT_PROVIDED):
    """
    Trigger CCC if ccc not provided
    """

    global current_yaw

    if ccc_data is _CCC_NOT_PROVIDED or not isinstance(ccc_data, tuple):
        ccc_data = get_yaw_pitch_as_ccc_data()
    if ccc_data is None:
        logs.logger.warning("CCC unavailable; unable to zero pitch")
        return False

    try:  # had an issue where this was a string for some reason
        target = float(yaw)
        current = float(ccc_data[3])
        diff = ((target - current) + 180) % 360 - 180
        if diff < 0:
            turn_left(-diff)
        else:
            turn_right(diff)
        current_yaw = normalize_yaw(target)
        return True
    except Exception as e:
        logs.logger.error(f"error processing data into floats: {e}")
    return False


def set_pitch(pitch: float, ccc_data=_CCC_NOT_PROVIDED):
    """
    Trigger CCC if ccc not provided
    """
    global current_pitch

    if ccc_data is _CCC_NOT_PROVIDED or not isinstance(ccc_data, tuple):
        ccc_data = get_yaw_pitch_as_ccc_data()
    if ccc_data is None:
        logs.logger.warning("CCC unavailable; unable to zero pitch")
        return False

    try:  # had an issue where this was a string for some reason
        target = float(pitch)
        current = float(ccc_data[4])

        change = current - target
        if change < 0:
            turn_up(-change)
        else:
            turn_down(change)
        current_pitch = pitch
        return True
    except Exception as e:
        logs.logger.error(f"error processing data into floats: {e}")
    return False


def yaw_zero(ccc_data=_CCC_NOT_PROVIDED):
    """
    Trigger CCC if ccc not provided

    Will trigger MOSTLY
    """

    global current_yaw

    if ccc_data is _CCC_NOT_PROVIDED:
        ccc_data = get_yaw_pitch_as_ccc_data()
    if ccc_data is None:
        logs.logger.warning("CCC unavailable; unable to zero yaw")
        return False
    try:
        set_yaw(0, ccc_data)
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
        ccc_data = get_yaw_pitch_as_ccc_data()
    if ccc_data is None:
        logs.logger.warning("CCC unavailable; unable to zero pitch")
        return False
    try:
        set_pitch(0, ccc_data)

        return True
    except (IndexError, TypeError, ValueError) as e:
        logs.logger.error(f"error processing ccc_data[4]: {e}")
        return False


def zero_center_no_ccc():
    """
    Won't trigger CCC

    Should only be used after multiple dedi interaction, turn to dedi, then go back without doing ccc(for quicker process)
    """

    turn_to(settings.station_yaw, 0)


def zero_opposite_no_ccc():
    """
    Won't trigger CCC
    """
    turn_to(settings.station_yaw + 180, 0)


def zero_opposite(target_yaw: float | None = None, target_pitch: float | None = None):
    """
    Trigger CCC

    Will set yaw to opposite of settings.station_yaw by default and pitch to 0.
    So player should be aiming at the opposite of zero_center()
    """

    logs.logger.debug("setting view angles back to station_yaw and pitch 0")

    global current_yaw
    global current_pitch

    if target_yaw is None:
        target_yaw = settings.station_yaw + 180
    if target_pitch is None:
        target_pitch = 0

    ccc_data = get_yaw_pitch_as_ccc_data()
    if ccc_data is None:
        logs.logger.warning("CCC unavailable; unable to zero pitch")
        return False

    try:
        set_pitch(target_pitch, ccc_data)

        target = float(target_yaw)
        set_yaw(target, ccc_data)
    except Exception as e:
        logs.logger.error(f"error processing data into floats: {e}")


def zero_center(target_yaw: float | None = None, target_pitch: float | None = None):
    """
    Trigger CCC

    Will set yaw to settings.station_yaw by default and pitch to 0.
    So player should be aiming at the desired center view
    """

    logs.logger.debug("setting view angles back to station_yaw and pitch 0")

    global current_yaw
    global current_pitch

    if target_yaw is None:
        target_yaw = settings.station_yaw
    if target_pitch is None:
        target_pitch = 0

    ccc_data = get_yaw_pitch_as_ccc_data()
    if ccc_data is None:
        logs.logger.warning("CCC unavailable; unable to zero pitch")
        return False

    try:
        set_pitch(target_pitch, ccc_data)

        target = float(target_yaw)
        set_yaw(target, ccc_data)
    except Exception as e:
        logs.logger.error(f"error processing data into floats: {e}")


def get_yaw_pitch(use_cache=True, reset_state=True):
    """
    Trigger CCC
    """
    global current_yaw
    global current_pitch
    ccc_data = console.console_ccc(reset_state)
    # print(
    #     "🚀 ~ utils.py:363 ~ get_yaw_pitch ~ ccc_data:",
    #     ccc_data,
    #     type(ccc_data).__name__,
    # )

    if ccc_data is None:
        if use_cache:
            logs.logger.warning("CCC unavailable; setting yaw from cached angle")
        else:
            return None
    else:
        try:
            current_yaw = float(ccc_data[3])
            current_pitch = float(ccc_data[4])
        except (IndexError, TypeError, ValueError) as e:
            logs.logger.error(f"error processing ccc yaw and pitch: {e}")
    return current_yaw, current_pitch  # yaw , pitch


def get_yaw_pitch_as_ccc_data():
    """
    Trigger CCC
    """
    data = get_yaw_pitch()

    if data is None:
        return None

    y, p = data
    return (0, 0, 0, y, p)  # yaw , pitch


def turn_right(degrees):
    """
    Won't trigger CCC

    Args:
        degrees (float): Must be positive number
    """

    global current_yaw
    global was_initialized
    if not was_initialized:
        get_yaw_pitch()
        was_initialized = True

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
    global was_initialized
    if not was_initialized:
        get_yaw_pitch()
        was_initialized = True

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
    global was_initialized
    if not was_initialized:
        get_yaw_pitch()
        was_initialized = True

    current_pitch = float(current_pitch)
    allowed = int(min(abs(player_pitch_minimum - current_pitch), degrees))
    windows.turn(0, allowed)
    current_pitch -= allowed


def turn_up(degrees):
    """
    Won't trigger CCC

    Args:
        degrees (float): Must be positive number
    """

    global current_pitch
    global was_initialized
    if not was_initialized:
        get_yaw_pitch()
        was_initialized = True

    current_pitch = float(current_pitch)
    allowed = int(min(abs(player_pitch_max - current_pitch), degrees))
    windows.turn(0, -allowed)
    current_pitch += allowed


def turn_to(yaw: float, pitch: float):
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
