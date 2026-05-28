import json
import os

from source.launcher.constants import DEFAULT_SETTINGS, SETTINGS_FILE


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    merged = DEFAULT_SETTINGS.copy()
    merged.update(data)
    return merged


def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
