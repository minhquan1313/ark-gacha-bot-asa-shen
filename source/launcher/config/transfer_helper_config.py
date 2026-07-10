import copy
import json
import math
from pathlib import Path
from typing import cast

from source.launcher.config.template_settings import normalize_yaw
from source.utility.types import (
    DediStorageState,
    SteamAccountState,
    TransferDediRoute,
    TransferDedisConfig,
    TransferPlayersConfig,
    TransferRuntimeConfig,
    TransferSettings,
    TransferStartMode,
    TransferUiCoords,
)

TRANSFER_HELPER_DIR = Path("json_files/transfer_helper")
TRANSFER_SETTINGS_PATH = TRANSFER_HELPER_DIR / "settings.json"
TRANSFER_DEDIS_PATH = TRANSFER_HELPER_DIR / "dedis.json"
TRANSFER_PLAYERS_PATH = TRANSFER_HELPER_DIR / "players.json"

MAX_TRANSFER_RUNTIME_ACCOUNTS = 4
MAX_TRANSFER_PLAYER_ROWS = 99
DEFAULT_BED_NAME_PREFIX = "BBedPlayer"

DEFAULT_TRANSFER_SETTINGS: TransferSettings = {
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

DEFAULT_TRANSFER_DEDIS: TransferDedisConfig = {
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

DEFAULT_TRANSFER_UI_COORDS: TransferUiCoords = {
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
    v: DediStorageState = {"location": {"yaw": 0.0, "pitch": 0.0}, "crouched": False}
    return v


def default_transfer_ui_coords():
    return copy.deepcopy(DEFAULT_TRANSFER_UI_COORDS)


def default_transfer_players(account_count=1):
    v: TransferPlayersConfig = {
        "players": [
            {"bed_name": name, "steam_account": ""}
            for name in generated_player_bed_names(int(account_count))
        ]
    }
    return v


def generated_player_bed_names(account_count: int):
    names: list[str] = []
    for account in range(1, int(account_count) + 1):
        candidate = f"{DEFAULT_BED_NAME_PREFIX}{account}"
        if _has_numeric_prefix_collision(candidate, names):
            candidate = f"{DEFAULT_BED_NAME_PREFIX}_{account}"
        names.append(candidate)
    return names


def player_bed_name(players: TransferPlayersConfig, account_index: int):
    try:
        player = players["players"][int(account_index) - 1]
    except (KeyError, IndexError, TypeError):
        return generated_player_bed_names(int(account_index))[-1]
    name = str(player.get("bed_name", "")).strip()
    if name:
        return name
    return generated_player_bed_names(int(account_index))[-1]


def player_steam_account(players: TransferPlayersConfig, account_index: int):
    try:
        player = players["players"][int(account_index) - 1]
    except (KeyError, IndexError, TypeError):
        return ""
    return str(player.get("steam_account", "")).strip()


def player_bed_name_search_conflicts(
    players: TransferPlayersConfig, limit: int | None = None
):
    if not isinstance(players, dict):
        players = {}
    raw_players = players.get("players", [])
    if not isinstance(raw_players, list):
        raw_players = []
    if limit is not None:
        raw_players = raw_players[: int(limit)]

    names: list[str] = []
    for player in raw_players:
        if not isinstance(player, dict):
            player = {}
        names.append(str(player.get("bed_name", "")).strip())

    conflicts: dict[int, list[str]] = {}
    for index, name in enumerate(names):
        matches: list[str] = []
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


def player_account_count(players: TransferPlayersConfig | object):
    if not isinstance(players, dict):
        return 0
    raw_players = players.get("players", [])
    if not isinstance(raw_players, list):
        return 0
    return min(len(raw_players), MAX_TRANSFER_PLAYER_ROWS)


def runtime_account_count(players: TransferPlayersConfig | object):
    return min(player_account_count(players), MAX_TRANSFER_RUNTIME_ACCOUNTS)


def suggested_loop_count(dedi_count: int, account_count: int):
    account_count = int(account_count)
    if account_count <= 0:
        raise ValueError("account_count must be at least 1.")
    return int(math.ceil((int(dedi_count) * 6) / account_count))


def load_transfer_settings(
    path: str | Path = TRANSFER_SETTINGS_PATH, create_missing: bool = True
):
    path = Path(path)
    if not path.exists():
        settings = default_transfer_settings()
        if create_missing:
            save_transfer_settings(settings, path)
        return settings
    with path.open("r", encoding="utf-8") as file:
        data = cast(object, json.load(file))
    settings = normalize_transfer_settings(data)
    if create_missing and (
        not isinstance(data, dict)
        or any(key not in data for key in DEFAULT_TRANSFER_SETTINGS)
    ):
        _write_json(settings, path)
    return settings


def save_transfer_settings(data: object, path: str | Path = TRANSFER_SETTINGS_PATH):
    normalized = normalize_transfer_settings(data)
    _write_json(normalized, path)
    return normalized


def load_transfer_dedis(
    path: str | Path = TRANSFER_DEDIS_PATH, create_missing: bool = True
):
    path = Path(path)
    if not path.exists():
        dedis = default_transfer_dedis()
        if create_missing:
            save_transfer_dedis(dedis, path)
        return dedis
    with path.open("r", encoding="utf-8") as file:
        data = cast(object, json.load(file))
    return normalize_transfer_dedis(data)


def save_transfer_dedis(data: object, path: str | Path = TRANSFER_DEDIS_PATH):
    normalized = normalize_transfer_dedis(data)
    _write_json(normalized, path)
    return normalized


def load_transfer_ui_coords():
    return normalize_transfer_ui_coords(default_transfer_ui_coords())


def save_transfer_ui_coords(data: object):
    return normalize_transfer_ui_coords(data)


def load_transfer_players(
    path: str | Path = TRANSFER_PLAYERS_PATH,
    account_count: int | None = None,
    create_missing: bool = True,
):
    path = Path(path)
    if not path.exists():
        account_count = 1 if account_count is None else account_count
        players = default_transfer_players(account_count)
        if create_missing:
            save_transfer_players(players, path, account_count)
        return players
    with path.open("r", encoding="utf-8") as file:
        data = cast(object, json.load(file))
    count = player_account_count(data) if account_count is None else account_count
    return normalize_transfer_players(data, count)


def save_transfer_players(
    data: object,
    path: str | Path = TRANSFER_PLAYERS_PATH,
    account_count: int | None = None,
):
    if account_count is None:
        account_count = player_account_count(data)
    normalized = normalize_transfer_players(data, account_count)
    _write_json(normalized, path)
    return normalized


def load_transfer_runtime_config(create_missing: bool = True):
    settings = load_transfer_settings(
        TRANSFER_SETTINGS_PATH, create_missing=create_missing
    )
    player_count_hint = (
        None
        if TRANSFER_PLAYERS_PATH.exists()
        else _old_account_count_hint(TRANSFER_SETTINGS_PATH)
    )
    dedis = load_transfer_dedis(TRANSFER_DEDIS_PATH, create_missing=create_missing)

    v: TransferRuntimeConfig = {
        "settings": settings,
        "dedis": dedis,
        "ui_coords": load_transfer_ui_coords(),
        "players": load_transfer_players(
            TRANSFER_PLAYERS_PATH,
            account_count=player_count_hint,
            create_missing=create_missing,
        ),
    }

    return v


def normalize_transfer_runtime_config(data: object):
    if not isinstance(data, dict):
        data = {}
    config: TransferRuntimeConfig = {
        "settings": normalize_transfer_settings(data.get("settings", {})),
        "dedis": normalize_transfer_dedis(data.get("dedis", {})),
        "ui_coords": normalize_transfer_ui_coords(data.get("ui_coords", {})),
        "players": normalize_transfer_players(
            data.get("players", {}),
            player_account_count(data.get("players", {})),
        ),
    }
    steam_accounts = _normalize_steam_accounts(data.get("steam_accounts", []))
    if steam_accounts:
        config["steam_accounts"] = steam_accounts
    if "start_account" in data:
        try:
            config["start_account"] = _int_min(
                data["start_account"], "start_account", 1
            )
        except ValueError:
            config["start_account"] = 1
    return config


def normalize_transfer_settings(data: object):
    if not isinstance(data, dict):
        data = {}
    normalized = default_transfer_settings()
    normalized.update({key: data[key] for key in normalized if key in data})  # type: ignore
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
    return cast(TransferSettings, normalized)


def normalize_transfer_players(data: object, account_count: int = 1):
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
    v: TransferPlayersConfig = {"players": players}
    return v


def normalize_transfer_dedis(data: object):
    # TransferDedisConfig
    if not isinstance(data, dict):
        data = {}
    if "resource" in data or "destination" in data:
        dedis: TransferDedisConfig = {
            "resource": _normalize_dedi_route(data.get("resource", {})),
            "destination": _normalize_dedi_route(data.get("destination", {})),
        }
        _sync_dedi_route_lengths(dedis)
        return dedis
    route = _normalize_dedi_route(data)

    v: TransferDedisConfig = {
        "resource": copy.deepcopy(route),
        "destination": copy.deepcopy(route),
    }

    return v


def calculate_same_structure_destination_dedis(
    dedis: object,
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


def _normalize_dedi_route(data: object):
    # TransferDediRoute
    if not isinstance(data, dict):
        data = {}
    teleport = str(data.get("teleport", "")).strip()
    transmitter_teleport = str(data.get("transmitter_teleport", "")).strip()
    raw_items = data.get("items", [])
    if not isinstance(raw_items, list):
        raw_items = []
    items = [_normalize_dedi_item(item) for item in raw_items]

    v: TransferDediRoute = {
        "teleport": teleport,
        "transmitter_teleport": transmitter_teleport,
        "items": items,
    }
    return v


def _sync_dedi_route_lengths(dedis: TransferDedisConfig):
    resource_items = dedis["resource"]["items"]
    destination_items = dedis["destination"]["items"]
    target_count = max(len(resource_items), len(destination_items))
    for items in (resource_items, destination_items):
        while len(items) < target_count:
            items.append(default_transfer_dedi_item())


def normalize_transfer_ui_coords(data: object):
    if not isinstance(data, dict):
        data = {}
    normalized = default_transfer_ui_coords()
    steam = data.get("steam", {})
    n_steam = normalized["steam"]
    if isinstance(steam, dict):
        n_steam.update(steam)
    return cast(TransferUiCoords, normalized)


def transfer_dedi_route(dedis: TransferDedisConfig | object, side: str):
    if not isinstance(dedis, dict):
        dedis = {}
    route = dedis.get(side, {})
    if not isinstance(route, dict):
        route = {}
    if "resource" not in dedis and "destination" not in dedis:
        route = dedis
    return _normalize_dedi_route(route)


def active_transfer_dedis(dedis: TransferDedisConfig | object, side: str | None = None):
    def_items: list[DediStorageState] = []

    if side is not None:
        return transfer_dedi_route(dedis, side).get("items", def_items)

    if not isinstance(dedis, dict):
        return def_items

    if "resource" in dedis or "destination" in dedis:
        return transfer_dedi_route(dedis, "resource").get("items", def_items)

    items = dedis.get("items")

    if not isinstance(items, list):
        return def_items

    return cast(list[DediStorageState], items)


def missing_runtime_inputs(
    settings: TransferSettings | object,
    dedis: TransferDedisConfig | object,
    ui_coords_or_players: object = None,
    players: TransferPlayersConfig | object = None,
    steam_accounts: list[SteamAccountState] | object = None,
    start_account: int = 1,
):
    if players is None and _looks_like_players(ui_coords_or_players):
        players = ui_coords_or_players
    missing = []
    if settings.get("resource_server") == "0":  # type: ignore
        missing.append("settings.resource_server")
    if settings.get("destination_server") == "0":  # type: ignore
        missing.append("settings.destination_server")
    if settings.get("resource_server") == settings.get("destination_server"):  # type: ignore
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


def steam_account_assignment_issues(
    players: TransferPlayersConfig | object = None,
    steam_accounts: list[SteamAccountState] | object = None,
    start_account: int = 1,
):
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


def _normalize_dedi_item(item: object) -> DediStorageState:
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


def _steam_account_names(steam_accounts: list[SteamAccountState] | object):
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


def _most_recent_steam_account(steam_accounts: list[SteamAccountState] | object):
    if not isinstance(steam_accounts, list):
        return ""
    for account in steam_accounts:
        if not isinstance(account, dict):
            continue
        if account.get("most_recent"):
            return str(account.get("account_name", "")).strip()
    return ""


def _write_json(data: object, path: str | Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def _old_account_count_hint(path: str | Path):
    path = Path(path)
    if not path.exists():
        return 1
    try:
        with path.open("r", encoding="utf-8") as file:
            data = cast(object, json.load(file))
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


def _normalize_steam_accounts(data: object) -> list[SteamAccountState]:
    if not isinstance(data, list):
        return []
    accounts = []
    for account in data:
        if not isinstance(account, dict):
            continue
        account_name = str(account.get("account_name", "")).strip()
        if not account_name:
            continue
        accounts.append(
            {
                "account_name": account_name,
                "most_recent": bool(account.get("most_recent", False)),
                "timestamp": _numeric_timestamp(account.get("timestamp", 0)),
            }
        )
    return accounts


def _has_numeric_prefix_collision(candidate: str, existing_names: list[str]):
    for existing in existing_names:
        if not candidate.startswith(existing):
            continue
        suffix = candidate[len(existing) :]
        if suffix[:1].isdigit():
            return True
    return False


def _float_value(value: object, name: str):
    try:
        return float(value)  # type: ignore
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc


def _transfer_start_mode(value: object):
    value = str(value).strip().lower()
    if value in {"default", "destinate"}:
        return cast(TransferStartMode, value)
    return "default"


def _positive_float(value: object, name: str):
    value = _float_value(value, name)
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0.")
    return value


def _int_min(value: object, name: str, minimum: int):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer.")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{name} must be an integer.")
    try:
        value = int(value)  # type: ignore
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return value


def _int_range(value: object, name: str, minimum: int, maximum: int):
    value = _int_min(value, name, minimum)
    if value > maximum:
        raise ValueError(f"{name} must be at most {maximum}.")
    return value


def _numeric_timestamp(value: object):
    try:
        return int(value)  # type: ignore
    except (TypeError, ValueError):
        try:
            return float(value)  # type: ignore
        except (TypeError, ValueError):
            return 0


def _server_number(value: object, name: str):
    value = str(value).strip()
    if not value or not value.isdigit():
        raise ValueError(f"{name} must be a number.")
    return value
