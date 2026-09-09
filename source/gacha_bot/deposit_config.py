import json
from pathlib import Path
from typing import cast

from source.utility.types import (
    CrystalDepositRoute,
    DediStorageState,
    DepositConfig,
    DepositRouteBase,
    GrindableDepositRoute,
    GrinderStorageState,
    VaultStorageState,
)

DEDI_CONFIG_PATH = Path("json_files/dedis.json")


def deposit_destination_options(config: DepositConfig):
    """List each nonblank teleport once for the collection pair selector."""
    return list(
        dict.fromkeys(
            route["teleport"]
            for routes in (
                config["depositCrystalData"],
                config["depositGrindableData"],
                config["depositGeneralData"],
            )
            for route in routes
            if route["teleport"].strip()
        )
    )


def validate_deposit_teleports(config: DepositConfig):
    """Reject ambiguous nonblank destination names when saving configuration."""
    names = [
        route["teleport"]
        for routes in (
            config["depositCrystalData"],
            config["depositGrindableData"],
            config["depositGeneralData"],
        )
        for route in routes
        if route["teleport"].strip()
    ]
    if len(names) != len(set(names)):
        raise ValueError(
            "Dedi teleport names must be unique across Crystal, Grindable, and General dedi."
        )


def collection_destination_error(config: DepositConfig, teleport: str):
    """Explain why a selected teleport cannot receive collected materials."""
    if not teleport.strip():
        return "Select a Dedi destination."
    matches = [
        route
        for routes in (
            config["depositCrystalData"],
            config["depositGrindableData"],
            config["depositGeneralData"],
        )
        for route in routes
        if route["teleport"] == teleport
    ]
    if not matches:
        return "Station missing. Reselect Dedi."
    if len(matches) != 1:
        return "Duplicate teleport name. Rename the stations and reselect Dedi."
    if not matches[0]["dedi"]["items"]:
        return "Station has no dedis. Configure it or reselect Dedi."
    return ""


def default_deposit_config(
    crystal_teleport: str = "", grindable_teleport: str = ""
) -> DepositConfig:
    return {
        "depositCrystalData": [
            {
                "teleport": crystal_teleport,
                "check_on_every_dedi": 6,
                "dedi": {"items": []},
                "vault": {"items": []},
            }
        ],
        "depositGrindableData": [
            {
                "teleport": grindable_teleport,
                "check_on_every_dedi": 6,
                "grinder": {
                    "active": False,
                    "location": {"yaw": 0.0, "pitch": 0.0},
                    "crouched": False,
                },
                "dedi": {"items": []},
            }
        ],
        "depositGeneralData": [],
    }


def default_crystal_route() -> CrystalDepositRoute:
    return {
        "teleport": "",
        "check_on_every_dedi": 6,
        "dedi": {"items": []},
        "vault": {"items": []},
    }


def default_grindable_route() -> GrindableDepositRoute:
    return {
        "teleport": "",
        "check_on_every_dedi": 6,
        "grinder": {
            "active": False,
            "location": {"yaw": 0.0, "pitch": 0.0},
            "crouched": False,
        },
        "dedi": {"items": []},
    }


def default_general_route():
    """Create a source-material deposit station for collected items."""
    route: DepositRouteBase = {
        "teleport": "",
        "check_on_every_dedi": 6,
        "dedi": {"items": []},
    }
    return route


def default_dedi_item() -> DediStorageState:
    return {"location": {"yaw": 0.0, "pitch": 0.0}, "crouched": False}


def default_vault_item() -> VaultStorageState:
    return {"location": {"yaw": 0.0, "pitch": 0.0}, "crouched": False, "items": []}


def normalize_deposit_config(data: object) -> DepositConfig:
    if not isinstance(data, dict):
        raise ValueError("Deposit route config must be a JSON object.")

    crystal_routes = data.get("depositCrystalData")
    grindable_routes = data.get("depositGrindableData")
    general_routes = data.get("depositGeneralData")
    if not isinstance(crystal_routes, list):
        raise ValueError("depositCrystalData must be an array.")
    if not isinstance(grindable_routes, list):
        raise ValueError("depositGrindableData must be an array.")
    if not isinstance(general_routes, list):
        raise ValueError("depositGeneralData must be an array.")

    normalized = {
        "depositCrystalData": [
            _normalize_crystal_route(route) for route in crystal_routes
        ],
        "depositGrindableData": [
            _normalize_grindable_route(route) for route in grindable_routes
        ],
        "depositGeneralData": [
            normalize_general_route(route) for route in general_routes
        ],
    }
    return cast(DepositConfig, normalized)


def load_deposit_config(
    path: str | Path = DEDI_CONFIG_PATH,
    crystal_teleport: str = "",
    grindable_teleport: str = "",
    create_missing: bool = True,
    raise_on_missing: bool = False,
) -> DepositConfig:
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
        raw_data = cast(object, json.load(file))
        normalized = normalize_deposit_config(raw_data)
    return normalized


def save_deposit_config(
    data: object, path: str | Path = DEDI_CONFIG_PATH
) -> DepositConfig:
    path = Path(path)
    normalized = normalize_deposit_config(data)
    validate_deposit_teleports(normalized)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(normalized, file, indent=2)
    return normalized


def _normalize_crystal_route(route: object) -> CrystalDepositRoute:
    if not isinstance(route, dict):
        route = {}
    return {
        "teleport": str(route.get("teleport", "")),
        "check_on_every_dedi": _positive_int_value(
            route.get("check_on_every_dedi", 6), "check_on_every_dedi"
        ),
        "dedi": {"items": _normalize_object_items(route.get("dedi", {}))},
        "vault": {"items": _normalize_vault_items(route.get("vault", {}))},
    }


def _normalize_grindable_route(route: object) -> GrindableDepositRoute:
    if not isinstance(route, dict):
        route = {}
    return {
        "teleport": str(route.get("teleport", "")),
        "check_on_every_dedi": _positive_int_value(
            route.get("check_on_every_dedi", 6), "check_on_every_dedi"
        ),
        "grinder": _normalize_grinder(route.get("grinder", {})),
        "dedi": {"items": _normalize_object_items(route.get("dedi", {}))},
    }


def normalize_general_route(route: object):
    """Normalize the shared teleport and dedi fields of a station."""
    if not isinstance(route, dict):
        route = {}
    normalized: DepositRouteBase = {
        "teleport": str(route.get("teleport", "")),
        "check_on_every_dedi": _positive_int_value(
            route.get("check_on_every_dedi", 6), "check_on_every_dedi"
        ),
        "dedi": {"items": _normalize_object_items(route.get("dedi", {}))},
    }

    return normalized


def _normalize_object_items(container: object) -> list[DediStorageState]:
    if not isinstance(container, dict):
        return []
    items = container.get("items", [])
    if not isinstance(items, list):
        return []
    return [_normalize_object(item) for item in items]


def _normalize_vault_items(container: object) -> list[VaultStorageState]:
    if not isinstance(container, dict):
        return []
    items = container.get("items", [])
    if not isinstance(items, list):
        return []
    return [_normalize_vault(item) for item in items]


def _normalize_grinder(item: object):
    if not isinstance(item, dict):
        item = {}
    normalized = _normalize_object(item)
    obj: GrinderStorageState = {
        "active": bool(item.get("active", False)),
        "location": normalized["location"],
        "crouched": normalized["crouched"],
    }
    return obj


def _normalize_object(item: object) -> DediStorageState:
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


def _normalize_vault(item: object):
    normalized = _normalize_object(item)
    raw_items = item.get("items", []) if isinstance(item, dict) else []
    if not isinstance(raw_items, list):
        raw_items = []

    vault_normalize: VaultStorageState = {
        **normalized,
        "items": [
            #
            str(value).strip()
            for value in raw_items
            if str(value).strip()
        ],
    }
    return vault_normalize


def _float_value(value: any, name: str):  # type: ignore
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a float number.") from exc


def _positive_int_value(value: any, name: str):  # type: ignore
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    if normalized <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return normalized
