import json
from pathlib import Path

from source.join_sim.source.server_number import normalize_server_number

AUTO_JOIN_SERVER_FILE = Path("json_files/auto_join/server.json")
DEFAULT_AFK_JOIN = False


def _load_data(path: str | Path):
    """Load the auto-join JSON object or return an empty object."""
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_servers(values: object):
    """Normalize valid server numbers while retaining latest-occurrence order."""
    normalized: list[str] = []
    if not isinstance(values, list):
        return normalized

    for value in values:
        try:
            server = normalize_server_number(value)
        except ValueError:
            continue
        if server in normalized:
            normalized.remove(server)
        normalized.append(server)
    return normalized


def _write_data(servers: list[str], afk_join: bool, path: str | Path):
    """Write the complete auto-join state to disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump({"last_join": servers, "afk_join": afk_join}, file, indent=2)


def load_auto_join_servers(path: str | Path = AUTO_JOIN_SERVER_FILE):
    """Load valid auto-join server history in least-to-most-recent order."""
    return _normalize_servers(_load_data(path).get("last_join"))


def load_auto_join_afk_join(path: str | Path = AUTO_JOIN_SERVER_FILE):
    """Load the persisted AFK Join preference, defaulting to enabled."""
    value = _load_data(path).get("afk_join", DEFAULT_AFK_JOIN)
    return value if isinstance(value, bool) else DEFAULT_AFK_JOIN


def save_auto_join_servers(
    servers: list[str], path: str | Path = AUTO_JOIN_SERVER_FILE
):
    """Save normalized, unique auto-join server history."""
    normalized = _normalize_servers(servers)
    afk_join = load_auto_join_afk_join(path)
    _write_data(normalized, afk_join, path)
    return normalized


def save_auto_join_afk_join(afk_join: bool, path: str | Path = AUTO_JOIN_SERVER_FILE):
    """Save the AFK Join preference while preserving server history."""
    servers = load_auto_join_servers(path)
    _write_data(servers, bool(afk_join), path)
    return bool(afk_join)


def remember_auto_join_server(server: object, path: str | Path = AUTO_JOIN_SERVER_FILE):
    """Move a valid server to the end of the auto-join history."""
    normalized = normalize_server_number(server)
    servers = load_auto_join_servers(path)
    if normalized in servers:
        servers.remove(normalized)
    servers.append(normalized)
    return save_auto_join_servers(servers, path)


def forget_auto_join_server(server: object, path: str | Path = AUTO_JOIN_SERVER_FILE):
    """Remove a valid server from the auto-join history when present."""
    normalized = normalize_server_number(server)
    servers = load_auto_join_servers(path)
    if normalized not in servers:
        return servers
    servers.remove(normalized)
    return save_auto_join_servers(servers, path)
