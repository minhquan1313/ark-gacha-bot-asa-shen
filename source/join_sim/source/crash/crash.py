import time

import psutil
import win32process

from source.join_sim.source.logs import logger as logs
from source.launcher import ark_game_setup
from source.launcher.utils import system
from source.launcher.utils.deposit_helper_capture import focus_game_window
from source.utility import utils, windows

appid = "2399830"
crash_process: psutil.Process | None = None
REOPEN_RETRY_DELAY_SECONDS = 10
ARK_WINDOW_READY_TIMEOUT_SECONDS = 120
ARK_WINDOW_POLL_SECONDS = 1
ARK_FOCUS_DELAY_SECONDS = 3


def detect_crash():
    global crash_process
    for proc in psutil.process_iter(attrs=["name", "exe"]):
        if proc.info["name"] == "CrashReportClient.exe":
            crash_process = proc
            logs.logger.critical("Crash detected", stack_info=True)
            return True
    return False


def close_game():
    try:
        global crash_process
        if crash_process:
            print("terminating crash process")
            logs.logger.critical("terminating crash process")
            crash_process.terminate()
            crash_process = None

        _, pid = win32process.GetWindowThreadProcessId(windows.ark_hwnd())
        process = psutil.Process(pid)
        if process:
            process.terminate()
            logs.logger.critical(f"game with pid {pid} terminated")
    except psutil.NoSuchProcess:
        logs.logger.critical("process not found")
    except psutil.AccessDenied:
        logs.logger.critical("no permissions to terminate")
    except Exception as e:
        logs.logger.critical(f"error: {e}")


def _process_running(process_name):
    for proc in psutil.process_iter(attrs=["name"]):
        try:
            if str(proc.info.get("name", "")).lower() == process_name.lower():
                return True
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return False


def _wait_for_usable_ark_window(timeout_seconds: float) -> None:
    """Wait until ARK has a valid window, then focus it and skip the intro."""
    deadline = utils.timed_out_counter(timeout_seconds)
    last_error: RuntimeError | None = None

    while not deadline():
        if _process_running(ark_game_setup.ARK_PROCESS_NAME):
            try:
                _window_size = system.validate_ark_window()
                time.sleep(ARK_FOCUS_DELAY_SECONDS)
                focus_game_window(center_cursor_when_switching=True)
                return
            except RuntimeError as exc:
                last_error = exc
                logs.logger.warning(f"ARK window is not ready: {exc}")
        time.sleep(ARK_WINDOW_POLL_SECONDS)

    if last_error is not None:
        raise RuntimeError(f"ARK window did not become usable: {last_error}")
    raise RuntimeError("ARK process did not produce a usable window.")


def re_open_game() -> None:
    """Restart ARK until its window can be validated and focused."""
    attempt = 1

    while True:
        close_game()
        ark_game_setup.kill_running_ark()
        time.sleep(REOPEN_RETRY_DELAY_SECONDS)

        try:
            ark_game_setup.launch_ark_through_steam()
            _wait_for_usable_ark_window(ARK_WINDOW_READY_TIMEOUT_SECONDS)
            return
        except Exception as exc:
            message = f"ARK reopen attempt {attempt} failed: {exc}"
            logs.logger.warning(message)
            attempt += 1
