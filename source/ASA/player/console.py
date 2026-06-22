import contextlib
import threading
import time
from collections.abc import Iterator

import pyautogui
import win32clipboard

import settings
import source.ASA.config
from source.ASA.player import player_state
from source.logs import gachalogs as logs
from source.utility import template, utils

_clipboard_lock = threading.Lock()
_clipboard_open_timeout = 3
_clipboard_retry_delay = 0.05


@contextlib.contextmanager
def _open_clipboard() -> Iterator[None]:
    """Open the shared Windows clipboard with bounded contention retries."""
    with _clipboard_lock:
        dl = utils.get_default_clock(_clipboard_open_timeout)
        is_dled = dl()
        while not is_dled:
            is_dled = dl()
            try:
                win32clipboard.OpenClipboard()
                break
            except Exception:
                if is_dled:
                    raise
                time.sleep(_clipboard_retry_delay)

        try:
            yield
        finally:
            win32clipboard.CloseClipboard()


def is_open():
    return template.console_strip_check(
        template.console_strip_bottom()
    ) or template.console_strip_check(template.console_strip_middle())


def enter_data(data: str) -> bool:
    logs.logger.debug(f"using clipboard to put {data} into the console")
    try:
        with _open_clipboard():
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(data, win32clipboard.CF_TEXT)
    except Exception as e:
        logs.logger.warning(f"Unable to write to clipboard: {e}")
        return False

    pyautogui.hotkey("ctrl", "v")
    return True


def console_reset():
    # Open console
    utils.press_key("ConsoleKeys")
    time.sleep(0.2)
    # Append "`" character into the console, in case the console already contain old value
    # so maybe it contains "ccc" from previous ccc, but somehow failed to submit, here we
    # add "c" -> "cccc" then we submit, that's a wrong console command so it execute nothing -> SAFE RESET CONSOLE
    pyautogui.press("c")
    time.sleep(0.1)
    utils.press_key("Enter")
    time.sleep(0.3)


def console_ccc(reset_state_before_capture: bool = True) -> list[str] | None:
    data = None
    attempts = 0
    while data is None:
        attempts += 1
        logs.logger.debug(
            f"trying to get ccc data {attempts} / {source.ASA.config.console_ccc_attempts}"
        )
        if reset_state_before_capture:
            player_state.reset_state()  # reset state at the start to make sure we can open up the console window
        count = 0
        while not is_open():
            count += 1
            # OPEN AGAIN
            utils.press_key("ConsoleKeys")
            template.template_await_true(is_open, 1)
            if not is_open():
                console_reset()

            if count >= source.ASA.config.console_open_attempts:
                logs.logger.error(f"console didnt open after {count} attempts")
                break
        if is_open():
            middle = template.console_strip_check(template.console_strip_middle())
            if attempts >= source.ASA.config.console_ccc_attempts:
                command_entered = console_write("ccc")
            else:
                command_entered = enter_data("ccc")
                if command_entered:
                    close_console(middle)

            if not command_entered:
                if attempts >= source.ASA.config.console_ccc_attempts:
                    logs.logger.error(
                        f"CCC could not access the clipboard after {attempts} attempts"
                    )
                    console_reset()
                    break
                continue

            time.sleep(
                0.1 * settings.lag_offset
            )  # slow to try and prevent opening clipboard to empty data
            try:
                with _open_clipboard():
                    data = win32clipboard.GetClipboardData()
                    win32clipboard.EmptyClipboard()
            except Exception as e:
                logs.logger.warning(f"Unable to read from clipboard: {e}")
                data = None

            try:
                ccc_data = data.split()
                float(ccc_data[3])
                float(ccc_data[4])
            except (AttributeError, IndexError, TypeError, ValueError):
                logs.logger.warning(f"CCC returned invalid clipboard data: {data!r}")
                data = None

        if data is None and attempts >= source.ASA.config.console_ccc_attempts:
            logs.logger.error(
                f"CCC is still returning invalid data after {attempts} attempts"
            )
            # When somehow console has some weird value command already there, and the compare function of is_open will never return true,
            # then we have to try and open the console with the key press then press Enter to clear that current command
            # so the command console will be clear and ready for the is_open to check again.
            console_reset()
            # Enter current command to clear it and also close console
            break
    if data is not None:
        ccc_data = data.split()
        return ccc_data
    return data


def console_write(text: str) -> bool:
    attempts = 0
    while not is_open():
        console_reset()
        attempts += 1

        utils.press_key("ConsoleKeys")
        template.template_await_true(is_open, 1)
        if attempts >= source.ASA.config.console_open_attempts:
            logs.logger.error(
                f"console didnt open after {attempts} attempts unable to input {text}"
            )
            break

    if is_open():
        middle = template.console_strip_check(template.console_strip_middle())
        if not enter_data(text):
            return False
        close_console(middle)
        time.sleep(
            0.1 * settings.lag_offset
        )  # slow to try and prevent opening clipboard to empty data
        return True
    return False


def close_console(middle):
    """
    middle bar console has to have been entered in 2 times
    before typing we check again for the console location just to make sure
    """
    time.sleep(0.1 * settings.lag_offset)
    utils.press_key("Enter")

    if middle:
        logs.logger.warning(
            "middle console open if this is happening alot something should be changed"
        )
        time.sleep(0.1 * settings.lag_offset)
        utils.press_key("Enter")
