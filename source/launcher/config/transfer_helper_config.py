import copy
import json
import math
from pathlib import Path

from source.launcher.config.template_settings import normalize_yaw

TRANSFER_HELPER_DIR = Path("json_files/transfer_helper")
TRANSFER_SETTINGS_PATH = TRANSFER_HELPER_DIR / "settings.json"
TRANSFER_DEDIS_PATH = TRANSFER_HELPER_DIR / "dedis.json"
TRANSFER_PLAYERS_PATH = TRANSFER_HELPER_DIR / "players.json"

MAX_TRANSFER_RUNTIME_ACCOUNTS = 4
MAX_TRANSFER_PLAYER_ROWS = 99
DEFAULT_BED_NAME_PREFIX = "BBedPlayer"

DEFAULT_TRANSFER_SETTINGS = {
    "ping": 100,
    "transfer_start_mode": "default",
    "resource_station_yaw": 0.0,
    "destination_station_yaw": 0.0,
    "resource_server": "0",
    "destination_server": "0",
    "loop_count": 1,
    "structure_load_delay": 10,
    "steam_restart_interval": 30,
    "ark_window_ready_timeout": 120,
    "ark_launch_attempts": 10,
}

DEFAULT_TRANSFER_DEDIS = {
    "resource": {
        "teleport": "TRANSFER_DDEDI",
        "transmitter_teleport": "TRANSFER_TTRANS",
        "items": [],
    },
    "destination": {
        "teleport": "TRANSFER_DDEDI",
        "transmitter_teleport": "TRANSFER_TTRANS",
        "items": [],
    },
}

DEFAULT_TRANSFER_UI_COORDS = {
    "steam": {
        "window_title": "Steam",
        "restart_delay": 1,
    },
}


def default_transfer_settings():
    return copy.deepcopy(DEFAULT_TRANSFER_SETTINGS)


def default_transfer_dedis():
    return copy.deepcopy(DEFAULT_TRANSFER_DEDIS)


def default_transfer_dedi_item():
    return {"location": {"yaw": 0.0, "pitch": 0.0}, "crouched": False}


def default_transfer_ui_coords():
    return copy.deepcopy(DEFAULT_TRANSFER_UI_COORDS)


def default_transfer_players(account_count=1):
    return {
        "players": [
            {"bed_name": name, "steam_account": ""}
            for name in generated_player_bed_names(int(account_count))
        ]
    }


def generated_player_bed_names(account_count):
    names = []
    for account in range(1, int(account_count) + 1):
        candidate = f"{DEFAULT_BED_NAME_PREFIX}{account}"
        if _has_numeric_prefix_collision(candidate, names):
            candidate = f"{DEFAULT_BED_NAME_PREFIX}_{account}"
        names.append(candidate)
    return names


def player_bed_name(players, account_index):
    try:
        player = players["players"][int(account_index) - 1]
    except (KeyError, IndexError, TypeError):
        return generated_player_bed_names(int(account_index))[-1]
    name = str(player.get("bed_name", "")).strip()
    if name:
        return name
    return generated_player_bed_names(int(account_index))[-1]


def player_steam_account(players, account_index):
    try:
        player = players["players"][int(account_index) - 1]
    except (KeyError, IndexError, TypeError):
        return ""
    return str(player.get("steam_account", "")).strip()


def player_bed_name_search_conflicts(players, limit=None):
    if not isinstance(players, dict):
        players = {}
    raw_players = players.get("players", [])
    if not isinstance(raw_players, list):
        raw_players = []
    if limit is not None:
        raw_players = raw_players[: int(limit)]

    names = []
    for player in raw_players:
        if not isinstance(player, dict):
            player = {}
        names.append(str(player.get("bed_name", "")).strip())

    conflicts = {}
    for index, name in enumerate(names):
        matches = []
        if not name:
            conflicts[index] = ["empty name"]
            continue
        for other_index, other_name in enumerate(names):
            if index == other_index or not other_name:
                continue
            if other_name.startswith(name):
                matches.append(other_name)
        if matches:
            conflicts[index] = matches
    return conflicts


def player_account_count(players):
    if not isinstance(players, dict):
        return 0
    raw_players = players.get("players", [])
    if not isinstance(raw_players, list):
        return 0
    return min(len(raw_players), MAX_TRANSFER_PLAYER_ROWS)


def runtime_account_count(players):
    return min(player_account_count(players), MAX_TRANSFER_RUNTIME_ACCOUNTS)


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
        data = json.load(file)
    settings = normalize_transfer_settings(data)
    if create_missing and any(key not in data for key in DEFAULT_TRANSFER_SETTINGS):
        _write_json(settings, path)
    return settings


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


def load_transfer_ui_coords():
    return normalize_transfer_ui_coords(default_transfer_ui_coords())


def save_transfer_ui_coords(data):
    return normalize_transfer_ui_coords(data)


def load_transfer_players(
    path=TRANSFER_PLAYERS_PATH, account_count=None, create_missing=True
):
    path = Path(path)
    if not path.exists():
        account_count = 1 if account_count is None else account_count
        players = default_transfer_players(account_count)
        if create_missing:
            save_transfer_players(players, path, account_count)
        return players
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    count = player_account_count(data) if account_count is None else account_count
    return normalize_transfer_players(data, count)


def save_transfer_players(data, path=TRANSFER_PLAYERS_PATH, account_count=None):
    if account_count is None:
        account_count = player_account_count(data)
    normalized = normalize_transfer_players(data, account_count)
    _write_json(normalized, path)
    return normalized


def load_transfer_runtime_config(create_missing=True):
    legacy_transmitter_teleport = _legacy_transmitter_teleport(TRANSFER_SETTINGS_PATH)
    settings = load_transfer_settings(
        TRANSFER_SETTINGS_PATH, create_missing=create_missing
    )
    player_count_hint = (
        None
        if TRANSFER_PLAYERS_PATH.exists()
        else _old_account_count_hint(TRANSFER_SETTINGS_PATH)
    )
    dedis = load_transfer_dedis(TRANSFER_DEDIS_PATH, create_missing=create_missing)
    if legacy_transmitter_teleport:
        dedis = _migrate_legacy_transmitter_teleport(dedis, legacy_transmitter_teleport)
        if create_missing:
            save_transfer_dedis(dedis, TRANSFER_DEDIS_PATH)
    return {
        "settings": settings,
        "dedis": dedis,
        "ui_coords": load_transfer_ui_coords(),
        "players": load_transfer_players(
            TRANSFER_PLAYERS_PATH,
            account_count=player_count_hint,
            create_missing=create_missing,
        ),
    }


def normalize_transfer_settings(data):
    if not isinstance(data, dict):
        data = {}
    normalized = default_transfer_settings()
    normalized.update({key: data[key] for key in normalized if key in data})
    normalized["ping"] = _int_min(normalized["ping"], "ping", 0)
    normalized["resource_station_yaw"] = _float_value(
        normalized["resource_station_yaw"], "resource_station_yaw"
    )
    normalized["destination_station_yaw"] = _float_value(
        normalized["destination_station_yaw"], "destination_station_yaw"
    )
    normalized["transfer_start_mode"] = _transfer_start_mode(
        normalized["transfer_start_mode"]
    )
    normalized["resource_server"] = _server_number(
        normalized["resource_server"], "resource_server"
    )
    normalized["destination_server"] = _server_number(
        normalized["destination_server"], "destination_server"
    )
    normalized["loop_count"] = _int_min(normalized["loop_count"], "loop_count", 1)
    normalized["structure_load_delay"] = _int_min(
        normalized["structure_load_delay"], "structure_load_delay", 0
    )
    normalized["steam_restart_interval"] = _int_min(
        normalized["steam_restart_interval"], "steam_restart_interval", 1
    )
    normalized["ark_window_ready_timeout"] = _int_min(
        normalized["ark_window_ready_timeout"], "ark_window_ready_timeout", 1
    )
    normalized["ark_launch_attempts"] = _int_min(
        normalized["ark_launch_attempts"], "ark_launch_attempts", 1
    )
    return normalized


def normalize_transfer_players(data, account_count=1):
    if not isinstance(data, dict):
        data = {}
    raw_players = data.get("players", [])
    if not isinstance(raw_players, list):
        raw_players = []
    account_count = _int_range(
        account_count, "account_count", 0, MAX_TRANSFER_PLAYER_ROWS
    )
    generated = generated_player_bed_names(account_count)
    players = []
    for index in range(account_count):
        raw = raw_players[index] if index < len(raw_players) else {}
        if not isinstance(raw, dict):
            raw = {}
        bed_name = str(raw.get("bed_name", "")).strip()
        if not bed_name:
            bed_name = generated[index]
        steam_account = str(raw.get("steam_account", "")).strip()
        players.append({"bed_name": bed_name, "steam_account": steam_account})
    return {"players": players}


def normalize_transfer_dedis(data):
    if not isinstance(data, dict):
        data = {}
    if "resource" in data or "destination" in data:
        dedis = {
            "resource": _normalize_dedi_route(data.get("resource", {})),
            "destination": _normalize_dedi_route(data.get("destination", {})),
        }
        _sync_dedi_route_lengths(dedis)
        return dedis
    route = _normalize_dedi_route(data)
    return {
        "resource": copy.deepcopy(route),
        "destination": copy.deepcopy(route),
    }


def calculate_same_structure_destination_dedis(
    dedis: dict,
    resource_station_yaw: float,
    destination_station_yaw: float,
    target_side: str = "destination",
):
    """Calculate dedis from the opposite side for matching outposts.

    Example: resource yaw 50 at station yaw 10 becomes destination yaw 60
    when destination station yaw is 20.
    """
    if target_side not in {"resource", "destination"}:
        raise ValueError("target_side must be resource or destination.")
    calculated = normalize_transfer_dedis(dedis)
    station_yaws = {
        "resource": float(resource_station_yaw),
        "destination": float(destination_station_yaw),
    }
    source_side = "resource" if target_side == "destination" else "destination"
    adjustment = station_yaws[target_side] - station_yaws[source_side]
    target_items = calculated[target_side]["items"]
    for index, source_item in enumerate(calculated[source_side]["items"]):
        target_items[index] = {
            "location": {
                "yaw": normalize_yaw(
                    float(source_item["location"]["yaw"]) + adjustment
                ),
                "pitch": float(source_item["location"]["pitch"]),
            },
            "crouched": bool(source_item.get("crouched", False)),
        }
    return calculated


def _normalize_dedi_route(data):
    if not isinstance(data, dict):
        data = {}
    teleport = str(data.get("teleport", "")).strip()
    transmitter_teleport = str(data.get("transmitter_teleport", "")).strip()
    raw_items = data.get("items", [])
    if not isinstance(raw_items, list):
        raw_items = []
    items = [_normalize_dedi_item(item) for item in raw_items]
    return {
        "teleport": teleport,
        "transmitter_teleport": transmitter_teleport,
        "items": items,
    }


def _sync_dedi_route_lengths(dedis):
    resource_items = dedis["resource"]["items"]
    destination_items = dedis["destination"]["items"]
    target_count = max(len(resource_items), len(destination_items))
    for items in (resource_items, destination_items):
        while len(items) < target_count:
            items.append(default_transfer_dedi_item())


def normalize_transfer_ui_coords(data):
    if not isinstance(data, dict):
        data = {}
    normalized = default_transfer_ui_coords()
    steam = data.get("steam", {})
    if isinstance(steam, dict):
        _deep_update(normalized["steam"], steam)
    return normalized


def transfer_dedi_route(dedis, side):
    if not isinstance(dedis, dict):
        dedis = {}
    route = dedis.get(side, {})
    if not isinstance(route, dict):
        route = {}
    if "resource" not in dedis and "destination" not in dedis:
        route = dedis
    return _normalize_dedi_route(route)


def active_transfer_dedis(dedis, side=None):
    if side is not None:
        return list(transfer_dedi_route(dedis, side).get("items", []))
    if isinstance(dedis, dict) and ("resource" in dedis or "destination" in dedis):
        return list(transfer_dedi_route(dedis, "resource").get("items", []))
    return list(dedis.get("items", []))


def missing_runtime_inputs(
    settings,
    dedis,
    ui_coords_or_players=None,
    players=None,
    steam_accounts=None,
    start_account=1,
):
    if players is None and _looks_like_players(ui_coords_or_players):
        players = ui_coords_or_players
    missing = []
    if settings.get("resource_server") == "0":
        missing.append("settings.resource_server")
    if settings.get("destination_server") == "0":
        missing.append("settings.destination_server")
    if settings.get("resource_server") == settings.get("destination_server"):
        missing.append("settings.destination_server must differ from resource_server")
    if player_account_count(players) < 1:
        missing.append("players must include at least one player")
    missing.extend(
        steam_account_assignment_issues(
            players, steam_accounts, start_account=start_account
        )
    )
    resource_dedis = transfer_dedi_route(dedis, "resource")
    destination_dedis = transfer_dedi_route(dedis, "destination")
    if not resource_dedis.get("teleport"):
        missing.append("dedis.resource.teleport")
    if not resource_dedis.get("transmitter_teleport"):
        missing.append("dedis.resource.transmitter_teleport")
    if not active_transfer_dedis(dedis, "resource"):
        missing.append("dedis.resource.items must include at least one dedi")
    if not destination_dedis.get("teleport"):
        missing.append("dedis.destination.teleport")
    if not destination_dedis.get("transmitter_teleport"):
        missing.append("dedis.destination.transmitter_teleport")
    if not active_transfer_dedis(dedis, "destination"):
        missing.append("dedis.destination.items must include at least one dedi")

    return missing


def _looks_like_players(value):
    return isinstance(value, dict) and "players" in value


def steam_account_assignment_issues(players=None, steam_accounts=None, start_account=1):
    try:
        start_account = int(start_account)
    except (TypeError, ValueError):
        start_account = 1
    if not isinstance(players, dict):
        players = {}
    raw_players = players.get("players", [])
    if not isinstance(raw_players, list):
        raw_players = []
    account_names = _steam_account_names(steam_accounts)
    most_recent = _most_recent_steam_account(steam_accounts)
    issues = []
    seen = {}
    for index, player in enumerate(raw_players[:MAX_TRANSFER_RUNTIME_ACCOUNTS], 1):
        if not isinstance(player, dict):
            player = {}
        account_name = str(player.get("steam_account", "")).strip()
        if not account_name:
            issues.append(f"players[{index}].steam_account is required")
            continue
        if account_names and account_name not in account_names:
            issues.append(f"players[{index}].steam_account is not available in Steam")
        if account_name in seen:
            issues.append(
                f"players[{index}].steam_account duplicates player {seen[account_name]}"
            )
        else:
            seen[account_name] = index
        if index == start_account and most_recent and account_name != most_recent:
            issues.append(
                f"players[{index}].steam_account must match Steam MostRecent account"
            )
    return issues


def _normalize_dedi_item(item):
    if not isinstance(item, dict):
        item = {}
    location = item.get("location", {})
    if not isinstance(location, dict):
        location = {}
    return {
        "location": {
            "yaw": _float_value(location.get("yaw", 0.0), "yaw"),
            "pitch": _float_value(location.get("pitch", 0.0), "pitch"),
        },
        "crouched": bool(item.get("crouched", False)),
    }


def _steam_account_names(steam_accounts):
    if not isinstance(steam_accounts, list):
        return set()
    names = set()
    for account in steam_accounts:
        if not isinstance(account, dict):
            continue
        name = str(account.get("account_name", "")).strip()
        if name:
            names.add(name)
    return names


def _most_recent_steam_account(steam_accounts):
    if not isinstance(steam_accounts, list):
        return ""
    for account in steam_accounts:
        if not isinstance(account, dict):
            continue
        if account.get("most_recent"):
            return str(account.get("account_name", "")).strip()
    return ""


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


def _old_account_count_hint(path):
    path = Path(path)
    if not path.exists():
        return 1
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return 1
    if not isinstance(data, dict) or "account_count" not in data:
        return 1
    try:
        return _int_range(
            data["account_count"], "account_count", 1, MAX_TRANSFER_PLAYER_ROWS
        )
    except ValueError:
        return 1


def _legacy_transmitter_teleport(path: object):
    path = Path(path)
    if not path.exists():
        return ""
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("transmitter_teleport", "")).strip()


def _migrate_legacy_transmitter_teleport(dedis: dict, transmitter_teleport: str):
    dedis = normalize_transfer_dedis(dedis)
    for side in ("resource", "destination"):
        if not dedis[side].get("transmitter_teleport"):
            dedis[side]["transmitter_teleport"] = transmitter_teleport
    return dedis


def _has_numeric_prefix_collision(candidate, existing_names):
    for existing in existing_names:
        if not candidate.startswith(existing):
            continue
        suffix = candidate[len(existing) :]
        if suffix[:1].isdigit():
            return True
    return False


def _float_value(value, name):
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc


def _transfer_start_mode(value: object):
    value = str(value).strip().lower()
    if value in {"default", "destinate"}:
        return value
    return "default"


def _positive_float(value, name):
    value = _float_value(value, name)
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0.")
    return value


def _int_min(value, name, minimum):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer.")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{name} must be an integer.")
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
