import json
import os
from pathlib import Path

from source.launcher.config.constants import (
    DEFAULT_SETTINGS,
    PHONE_MINIMUM_SIZE,
    SETTINGS_FILE,
    TEMPLATE_REFERENCE_DEFAULTS,
)


def _normalize_settings(data: dict):
    normalized = DEFAULT_SETTINGS.copy()
    normalized.update({key: data[key] for key in DEFAULT_SETTINGS if key in data})
    normalized.update(
        {
            key: str(data.get(key, default))
            for key, default in TEMPLATE_REFERENCE_DEFAULTS.items()
        }
    )
    normalized["helper_inactive_opacity"] = max(
        0.1, min(1.0, float(normalized.get("helper_inactive_opacity", 0.3)))
    )
    normalized["ping"] = max(0, _int_value(normalized["ping"], "ping"))
    normalized["iguanadon_seed_throw_amount"] = max(
        0, int(normalized["iguanadon_seed_throw_amount"])
    )
    normalized["time_to_reberry"] = max(0, int(normalized["time_to_reberry"]))
    normalized["launcher_width"] = max(
        PHONE_MINIMUM_SIZE[0], int(normalized["launcher_width"])
    )
    normalized["launcher_height"] = max(
        PHONE_MINIMUM_SIZE[1], int(normalized["launcher_height"])
    )
    return normalized


def _int_value(value: object, name: str):
    """Parse a whole-number setting without truncating floats."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer.")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{name} must be an integer.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc


def load_settings(path: str | Path = SETTINGS_FILE):
    """Load normalized launcher settings and template assignments."""
    path = Path(path)
    if not path.exists():
        save_settings(DEFAULT_SETTINGS, path)
        return _normalize_settings(DEFAULT_SETTINGS)

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return _normalize_settings(data)


def save_settings(data: dict, path: str | Path = SETTINGS_FILE):
    """Normalize and atomically persist launcher settings."""
    data = _normalize_settings(data)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    with temporary_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(temporary_path, path)
    return data
