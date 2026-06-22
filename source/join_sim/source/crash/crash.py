import os
import subprocess
import time

import psutil
import win32process

from source.join_sim.source.logs import logger as logs
from source.join_sim.source.utility import local_player, recon_utils
from source.utility import windows

appid = "2399830"
crash_process: psutil.Process | None = None


def detect_crash():
    global crash_process
    for proc in psutil.process_iter(attrs=["name", "exe"]):
        if proc.info["name"] == "CrashReportClient.exe":
            crash_process = proc
            logs.logger.critical("Crash detected")
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


def launch_game_with_steam():
    steam_path = local_player.path("steam.exe")
    if os.path.exists(steam_path):
        subprocess.run([steam_path, f"steam://run/{appid}"])
        logs.logger.critical(f"launching game with appid {appid} via steam")
    else:
        logs.logger.critical(
            "steam exe not found at the expected location cannot relaunch game"
        )


def re_open_game():
    close_game()
    time.sleep(10)
    launch_game_with_steam()
    recon_utils.template_sleep_no_bounds("join_last_session", 0.7, 60)


def crash_rejoin():
    if detect_crash():
        close_game()
        time.sleep(10)
        launch_game_with_steam()
        recon_utils.template_sleep_no_bounds("join_last_session", 0.7, 60)
