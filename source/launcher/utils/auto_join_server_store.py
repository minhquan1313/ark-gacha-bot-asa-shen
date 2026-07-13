import json
from pathlib import Path

from source.join_sim.source.server_number import normalize_server_number

AUTO_JOIN_SERVER_FILE = Path("json_files/auto_join/server.json")


def load_auto_join_servers(path: str | Path = AUTO_JOIN_SERVER_FILE):
    """Load valid auto-join server history in least-to-most-recent order."""
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []

    if not isinstance(data, dict) or not isinstance(data.get("last_join"), list):
        return []

    servers = []
    for value in data["last_join"]:
        try:
            server = normalize_server_number(value)
        except ValueError:
            continue
        if server in servers:
            servers.remove(server)
        servers.append(server)
    return servers


def save_auto_join_servers(
    servers: list[object], path: str | Path = AUTO_JOIN_SERVER_FILE
):
    """Save normalized, unique auto-join server history."""
    normalized: list[str] = []
    for value in servers:
        try:
            server = normalize_server_number(value)
        except ValueError:
            continue
        if server in normalized:
            normalized.remove(server)
        normalized.append(server)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump({"last_join": normalized}, file, indent=2)
    return normalized


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
