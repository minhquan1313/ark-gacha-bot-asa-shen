import json
import os

from source.launcher.constants import DEFAULT_SETTINGS, SETTINGS_FILE


def _normalize_settings(data):
    normalized = DEFAULT_SETTINGS.copy()
    normalized.update(data)
    normalized["helper_inactive_opacity"] = max(
        0.1, min(1.0, float(normalized.get("helper_inactive_opacity", 0.3)))
    )
    return normalized


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return _normalize_settings(data)


def save_settings(data):
    data = _normalize_settings(data)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
