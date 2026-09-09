import pyautogui

from source.utility import action_gate


def click(*args, **kwargs):
    """Click inside ARK after checking whether recovery is needed."""
    action_gate.before_ark_action()
    return pyautogui.click(*args, **kwargs)


def press(*args, **kwargs):
    """Press an ARK key after checking whether recovery is needed."""
    action_gate.before_ark_action()
    return pyautogui.press(*args, **kwargs)


def key_down(*args, **kwargs):
    """Press and hold an ARK key after checking its game state."""
    action_gate.before_ark_action()
    return pyautogui.keyDown(*args, **kwargs)


def key_up(*args, **kwargs):
    """Release an ARK key without waiting on the state gate."""
    return pyautogui.keyUp(*args, **kwargs)


def right_click(*args, **kwargs):
    """Right-click inside ARK after checking whether recovery is needed."""
    action_gate.before_ark_action()
    return pyautogui.rightClick(*args, **kwargs)


def hotkey(*args, **kwargs):
    """Send an ARK hotkey after checking whether recovery is needed."""
    action_gate.before_ark_action()
    return pyautogui.hotkey(*args, **kwargs)


def move_to(*args, **kwargs):
    """Move the pointer for an ARK interaction after checking game state."""
    action_gate.before_ark_action()
    return pyautogui.moveTo(*args, **kwargs)
