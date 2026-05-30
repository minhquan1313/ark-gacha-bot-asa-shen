import json
from pathlib import Path

DEDI_CONFIG_PATH = Path("json_files/dedis.json")


def default_deposit_config(crystal_teleport="", grindable_teleport=""):
    return {
        "depositCrystalData": [
            {
                "teleport": crystal_teleport,
                "dedi": {"items": []},
                "vault": {"items": []},
            }
        ],
        "depositGrindableData": [
            {
                "teleport": grindable_teleport,
                "grinder": {
                    "active": False,
                    "location": {"yaw": 0.0, "pitch": 0.0},
                    "crouched": False,
                },
                "dedi": {"items": []},
            }
        ],
    }


def default_crystal_route():
    return {
        "teleport": "",
        "dedi": {"items": []},
        "vault": {"items": []},
    }


def default_grindable_route():
    return {
        "teleport": "",
        "grinder": {
            "active": False,
            "location": {"yaw": 0.0, "pitch": 0.0},
            "crouched": False,
        },
        "dedi": {"items": []},
    }


def default_dedi_item():
    return {"location": {"yaw": 0.0, "pitch": 0.0}, "crouched": False}


def default_vault_item():
    return {"location": {"yaw": 0.0, "pitch": 0.0}, "items": []}


def normalize_deposit_config(data):
    if not isinstance(data, dict):
        raise ValueError("Deposit route config must be a JSON object.")

    crystal_routes = data.get("depositCrystalData")
    grindable_routes = data.get("depositGrindableData")
    if not isinstance(crystal_routes, list) or len(crystal_routes) == 0:
        raise ValueError("depositCrystalData must be a non-empty array.")
    if not isinstance(grindable_routes, list) or len(grindable_routes) == 0:
        raise ValueError("depositGrindableData must be a non-empty array.")

    return {
        "depositCrystalData": [
            _normalize_crystal_route(route) for route in crystal_routes
        ],
        "depositGrindableData": [
            _normalize_grindable_route(route) for route in grindable_routes
        ],
    }


def load_deposit_config(
    path=DEDI_CONFIG_PATH,
    crystal_teleport="",
    grindable_teleport="",
    create_missing=True,
    raise_on_missing=False,
):
    path = Path(path)
    if not path.exists():
        config = default_deposit_config(crystal_teleport, grindable_teleport)
        if create_missing:
            save_deposit_config(config, path)
        if raise_on_missing:
            raise FileNotFoundError(
                f"{path} was missing. A default file was created; configure it before running deposit."
            )
        return config

    with path.open("r", encoding="utf-8") as file:
        return normalize_deposit_config(json.load(file))


def save_deposit_config(data, path=DEDI_CONFIG_PATH):
    path = Path(path)
    normalized = normalize_deposit_config(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(normalized, file, indent=2)
    return normalized


def _normalize_crystal_route(route):
    if not isinstance(route, dict):
        route = {}
    return {
        "teleport": str(route.get("teleport", "")),
        "dedi": {"items": _normalize_object_items(route.get("dedi", {}))},
        "vault": {"items": _normalize_vault_items(route.get("vault", {}))},
    }


def _normalize_grindable_route(route):
    if not isinstance(route, dict):
        route = {}
    return {
        "teleport": str(route.get("teleport", "")),
        "grinder": _normalize_grinder(route.get("grinder", {})),
        "dedi": {"items": _normalize_object_items(route.get("dedi", {}))},
    }


def _normalize_object_items(container):
    if not isinstance(container, dict):
        return []
    items = container.get("items", [])
    if not isinstance(items, list):
        return []
    return [_normalize_object(item) for item in items]


def _normalize_vault_items(container):
    if not isinstance(container, dict):
        return []
    items = container.get("items", [])
    if not isinstance(items, list):
        return []
    return [_normalize_vault(item) for item in items]


def _normalize_grinder(item):
    if not isinstance(item, dict):
        item = {}
    normalized = _normalize_object(item)
    normalized["active"] = bool(item.get("active", False))
    return {
        "active": normalized["active"],
        "location": normalized["location"],
        "crouched": normalized["crouched"],
    }


def _normalize_object(item):
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


def _normalize_vault(item):
    normalized = _normalize_object(item)
    raw_items = item.get("items", []) if isinstance(item, dict) else []
    if not isinstance(raw_items, list):
        raw_items = []
    normalized["items"] = [
        str(value).strip() for value in raw_items if str(value).strip()
    ]
    return normalized


def _float_value(value, name):
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a float number.") from exc
