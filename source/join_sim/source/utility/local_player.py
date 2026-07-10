import os
import re
import time
from pathlib import Path

import psutil

ark_path: Path | None = None


def path(process_name):
    print("finding path now sim " + process_name)
    for proc in psutil.process_iter(attrs=["name", "exe"]):
        if proc.info["name"] == process_name:
            exe_path = proc.info["exe"]
            return Path(exe_path)


def get_base_path():
    global ark_path
    try:
        if ark_path is None:
            ark_exe_path = path("ArkAscended.exe")
            if ark_exe_path is None:
                raise FileNotFoundError("ArkAscended.exe process was not found")
            base_path = ark_exe_path.parents[3]
            ark_path = base_path
        return ark_path
    except Exception as e:
        print(f"{e} PLEASE OPEN UP ARK TO FIX THIS ERROR THEN RESTART THE SCRIPT")
        time.sleep(10)
        raise RuntimeError(
            f"{e} PLEASE OPEN UP ARK TO FIX THIS ERROR THEN RESTART THE SCRIPT"
        ) from e


def get_user_settings(setting_name):
    base_path = get_base_path()

    settings_path = os.path.join(
        base_path, "ShooterGame", "Saved", "Config", "Windows", "GameUserSettings.ini"
    )
    if not os.path.exists(settings_path):
        raise FileNotFoundError(f"Settings file not found: {settings_path}")

    with open(settings_path, "r") as file:
        for line in file:
            if setting_name in line:
                key, value = line.strip().split("=")
                return value


def required_user_setting(setting_name: str):
    value = get_user_settings(setting_name)
    if value is None:
        raise KeyError(f"User setting not found: {setting_name}")
    return value


def get_look_lr_sens():
    return float(required_user_setting("LookLeftRightSensitivity"))


def get_look_ud_sens():
    return float(required_user_setting("LookUpDownSensitivity"))


def get_fov():
    return float(required_user_setting("FOVMultiplier"))


def get_input_settings(input_name):
    base_path = get_base_path()

    input_path = os.path.join(
        base_path, "ShooterGame", "Saved", "Config", "Windows", "input.ini"
    )

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input settings file not found: {input_path}")

    with open(input_path, "r") as file:
        if input_name == "ConsoleKeys":
            for line in file:
                if input_name in line:
                    name, value = line.strip().split("=")
                    return value

        for line in file:
            match = re.match(
                r'ActionMappings=\(ActionName="([^"]+)",.*Key=([A-Za-z0-9_]+)\)',
                line.strip(),
            )
            if match:
                action_name = match.group(1)
                key = match.group(2)

                if action_name == input_name:
                    return key

    return input_name
