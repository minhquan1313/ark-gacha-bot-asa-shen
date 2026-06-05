import copy
import json
import math
from pathlib import Path

TRANSFER_HELPER_DIR = Path("json_files/transfer_helper")
TRANSFER_SETTINGS_PATH = TRANSFER_HELPER_DIR / "settings.json"
TRANSFER_DEDIS_PATH = TRANSFER_HELPER_DIR / "dedis.json"
TRANSFER_UI_COORDS_PATH = TRANSFER_HELPER_DIR / "ui_coords.json"

MAX_TRANSFER_ACCOUNTS = 4

DEFAULT_TRANSFER_SETTINGS = {
    "lag_offset": 1.0,
    "resource_station_yaw": 0.0,
    "destination_station_yaw": 0.0,
    "transmitter_teleport": "",
    "resource_server": "0",
    "destination_server": "0",
    "account_count": 1,
    "loop_count": 1,
    "bed_prefix": "BedPlayer",
    "bed_prefix_pad_start": 0,
    "structure_load_delay": 10,
    "transfer_retry_delay": 5,
}

DEFAULT_TRANSFER_DEDIS = {
    "teleport": "",
    "items": [
        {
            "enabled": True,
            "location": {"yaw": 0.0, "pitch": 0.0},
            "crouched": False,
        }
    ],
}

DEFAULT_TRANSFER_UI_COORDS = {
    "steam": {
        "window_title": "Steam",
        "menu": {"x": None, "y": None},
        "change_account": {"x": None, "y": None},
        "continue": {"x": None, "y": None},
        "restart_delay": 8,
        "account_slots": {
            "2": [{"x": 266, "y": 242}, {"x": 386, "y": 242}],
            "3": [
                {"x": 206, "y": 242},
                {"x": 327, "y": 242},
                {"x": 447, "y": 242},
            ],
        },
    },
    "transfer": {
        "transmitter_title_template": "assets/icons1080/transmitter_title.png",
        "not_ready_template": "assets/icons1080/transfer_not_ready_popup.png",
        "transfer_button": {"x": None, "y": None},
        "server_search": {"x": None, "y": None},
        "first_server": {"x": None, "y": None},
        "join_button": {"x": None, "y": None},
        "not_ready_ok": {"x": None, "y": None},
        "not_ready_region": {"start_x": 0, "start_y": 0, "width": 1920, "height": 1080},
    },
}


def default_transfer_settings():
    return copy.deepcopy(DEFAULT_TRANSFER_SETTINGS)


def default_transfer_dedis():
    return copy.deepcopy(DEFAULT_TRANSFER_DEDIS)


def default_transfer_ui_coords():
    return copy.deepcopy(DEFAULT_TRANSFER_UI_COORDS)


def bed_name(prefix, account_index, pad_width):
    suffix = str(int(account_index))
    pad_width = int(pad_width)
    if pad_width > 0:
        suffix = suffix.zfill(pad_width)
    return f"{prefix}{suffix}"


def suggested_loop_count(dedi_count, account_count):
    account_count = int(account_count)
    if account_count <= 0:
        raise ValueError("account_count must be at least 1.")
    return int(math.ceil((int(dedi_count) * 6) / account_count))


def load_transfer_settings(path=TRANSFER_SETTINGS_PATH, create_missing=True):
    path = Path(path)
    if not path.exists():
        settings = default_transfer_settings()
        if create_missing:
            save_transfer_settings(settings, path)
        return settings
    with path.open("r", encoding="utf-8") as file:
        return normalize_transfer_settings(json.load(file))


def save_transfer_settings(data, path=TRANSFER_SETTINGS_PATH):
    normalized = normalize_transfer_settings(data)
    _write_json(normalized, path)
    return normalized


def load_transfer_dedis(path=TRANSFER_DEDIS_PATH, create_missing=True):
    path = Path(path)
    if not path.exists():
        dedis = default_transfer_dedis()
        if create_missing:
            save_transfer_dedis(dedis, path)
        return dedis
    with path.open("r", encoding="utf-8") as file:
        return normalize_transfer_dedis(json.load(file))


def save_transfer_dedis(data, path=TRANSFER_DEDIS_PATH):
    normalized = normalize_transfer_dedis(data)
    _write_json(normalized, path)
    return normalized


def load_transfer_ui_coords(path=TRANSFER_UI_COORDS_PATH, create_missing=True):
    path = Path(path)
    if not path.exists():
        coords = default_transfer_ui_coords()
        if create_missing:
            save_transfer_ui_coords(coords, path)
        return coords
    with path.open("r", encoding="utf-8") as file:
        return normalize_transfer_ui_coords(json.load(file))


def save_transfer_ui_coords(data, path=TRANSFER_UI_COORDS_PATH):
    normalized = normalize_transfer_ui_coords(data)
    _write_json(normalized, path)
    return normalized


def load_transfer_runtime_config(create_missing=True):
    return {
        "settings": load_transfer_settings(create_missing=create_missing),
        "dedis": load_transfer_dedis(create_missing=create_missing),
        "ui_coords": load_transfer_ui_coords(create_missing=create_missing),
    }


def normalize_transfer_settings(data):
    if not isinstance(data, dict):
        data = {}
    normalized = default_transfer_settings()
    normalized.update({key: data[key] for key in normalized if key in data})
    normalized["lag_offset"] = _positive_float(normalized["lag_offset"], "lag_offset")
    normalized["resource_station_yaw"] = _float_value(
        normalized["resource_station_yaw"], "resource_station_yaw"
    )
    normalized["destination_station_yaw"] = _float_value(
        normalized["destination_station_yaw"], "destination_station_yaw"
    )
    normalized["transmitter_teleport"] = str(normalized["transmitter_teleport"]).strip()
    normalized["resource_server"] = _server_number(
        normalized["resource_server"], "resource_server"
    )
    normalized["destination_server"] = _server_number(
        normalized["destination_server"], "destination_server"
    )
    normalized["account_count"] = _int_range(
        normalized["account_count"], "account_count", 1, MAX_TRANSFER_ACCOUNTS
    )
    normalized["loop_count"] = _int_min(normalized["loop_count"], "loop_count", 1)
    normalized["bed_prefix"] = str(normalized["bed_prefix"])
    normalized["bed_prefix_pad_start"] = _int_min(
        normalized["bed_prefix_pad_start"], "bed_prefix_pad_start", 0
    )
    normalized["structure_load_delay"] = _int_min(
        normalized["structure_load_delay"], "structure_load_delay", 0
    )
    normalized["transfer_retry_delay"] = _int_min(
        normalized["transfer_retry_delay"], "transfer_retry_delay", 1
    )
    return normalized


def normalize_transfer_dedis(data):
    if not isinstance(data, dict):
        data = {}
    teleport = str(data.get("teleport", "")).strip()
    raw_items = data.get("items", [])
    if not isinstance(raw_items, list):
        raw_items = []
    items = [_normalize_dedi_item(item) for item in raw_items]
    if not items:
        items = default_transfer_dedis()["items"]
    return {"teleport": teleport, "items": items}


def normalize_transfer_ui_coords(data):
    if not isinstance(data, dict):
        data = {}
    normalized = default_transfer_ui_coords()
    _deep_update(normalized, data)
    return normalized


def active_transfer_dedis(dedis):
    return [item for item in dedis.get("items", []) if item.get("enabled", True)]


def displayed_account_order(account_count, current_account):
    accounts = list(range(1, int(account_count) + 1))
    current_account = int(current_account)
    if current_account not in accounts:
        return accounts
    return [current_account] + [
        account for account in accounts if account != current_account
    ]


def account_slot_for_target(ui_coords, account_count, current_account, target_account):
    if int(target_account) == int(current_account):
        return None
    order = displayed_account_order(account_count, current_account)
    try:
        slot_index = order.index(int(target_account))
    except ValueError as exc:
        raise ValueError("target_account is outside account_count.") from exc
    slots = (
        ui_coords.get("steam", {}).get("account_slots", {}).get(str(account_count), [])
    )
    if slot_index >= len(slots):
        raise ValueError(
            f"Steam account slot map for {account_count} accounts is incomplete."
        )
    slot = slots[slot_index]
    if not _coord_complete(slot):
        raise ValueError(f"Steam account slot {slot_index + 1} is missing x/y.")
    return slot


def missing_runtime_inputs(settings, dedis, ui_coords, project_root=None):
    project_root = Path(project_root or ".")
    missing = []
    if not settings.get("transmitter_teleport"):
        missing.append("settings.transmitter_teleport")
    if settings.get("resource_server") == "0":
        missing.append("settings.resource_server")
    if settings.get("destination_server") == "0":
        missing.append("settings.destination_server")
    if settings.get("resource_server") == settings.get("destination_server"):
        missing.append("settings.destination_server must differ from resource_server")
    if not dedis.get("teleport"):
        missing.append("dedis.teleport")
    if not active_transfer_dedis(dedis):
        missing.append("dedis.items must include at least one enabled dedi")

    steam = ui_coords.get("steam", {})
    if int(settings.get("account_count", 1)) > 1:
        for key in ("menu", "change_account", "continue"):
            if not _coord_complete(steam.get(key, {})):
                missing.append(f"ui_coords.steam.{key}.x/y")
        account_count = int(settings["account_count"])
        slots = steam.get("account_slots", {}).get(str(account_count), [])
        if len(slots) < account_count:
            missing.append(f"ui_coords.steam.account_slots.{account_count}")
        else:
            for index, slot in enumerate(slots[:account_count], 1):
                if not _coord_complete(slot):
                    missing.append(
                        f"ui_coords.steam.account_slots.{account_count}[{index}].x/y"
                    )

    transfer = ui_coords.get("transfer", {})
    for key in (
        "transfer_button",
        "server_search",
        "first_server",
        "join_button",
        "not_ready_ok",
    ):
        if not _coord_complete(transfer.get(key, {})):
            missing.append(f"ui_coords.transfer.{key}.x/y")

    for key in ("transmitter_title_template", "not_ready_template"):
        template_path = str(transfer.get(key, "")).strip()
        if not template_path:
            missing.append(f"ui_coords.transfer.{key}")
            continue
        if not (project_root / template_path).exists():
            missing.append(f"{template_path} file")

    return missing


def _normalize_dedi_item(item):
    if not isinstance(item, dict):
        item = {}
    location = item.get("location", {})
    if not isinstance(location, dict):
        location = {}
    return {
        "enabled": bool(item.get("enabled", True)),
        "location": {
            "yaw": _float_value(location.get("yaw", 0.0), "yaw"),
            "pitch": _float_value(location.get("pitch", 0.0), "pitch"),
        },
        "crouched": bool(item.get("crouched", False)),
    }


def _write_json(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def _deep_update(target, source):
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


def _coord_complete(value):
    if not isinstance(value, dict):
        return False
    return value.get("x") is not None and value.get("y") is not None


def _float_value(value, name):
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc


def _positive_float(value, name):
    value = _float_value(value, name)
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0.")
    return value


def _int_min(value, name, minimum):
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return value


def _int_range(value, name, minimum, maximum):
    value = _int_min(value, name, minimum)
    if value > maximum:
        raise ValueError(f"{name} must be at most {maximum}.")
    return value


def _server_number(value, name):
    value = str(value).strip()
    if not value or not value.isdigit():
        raise ValueError(f"{name} must be a number.")
    return value
