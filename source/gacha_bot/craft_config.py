import json
from pathlib import Path

from source.gacha_bot.deposit_config import (
    _normalize_object,
    default_general_route,
    normalize_general_route,
)
from source.utility.types import CraftConfig, CrafterStorageState, CraftRoute

CRAFT_CONFIG_PATH = Path("json_files/craft.json")
DEFAULT_CRAFT_DELAY = 180


def default_crafter():
    """Create one crafter's aim, stance, and item settings."""
    crafter: CrafterStorageState = {
        "location": {"yaw": 0.0, "pitch": 0.0},
        "crouched": False,
        "item": "",
    }
    return crafter


def default_craft_route():
    """Create a shared teleport and output dedis with one initial crafter."""
    route: CraftRoute = {
        **default_general_route(),
        "delay": DEFAULT_CRAFT_DELAY,
        "crafters": [default_crafter()],
    }
    return route


def normalize_craft_config(data: object):
    """Normalize crafters and output dedis for each craft station."""
    if not isinstance(data, dict) or not isinstance(data.get("generalCraftData"), list):
        raise ValueError("generalCraftData must be an array.")
    routes: list[CraftRoute] = []
    for raw in data["generalCraftData"]:
        if not isinstance(raw, dict):
            raw = {}
        crafters = raw.get("crafters")
        if not isinstance(crafters, list):
            raise ValueError("Craft entry crafters must be an array.")
        normalized_crafters: list[CrafterStorageState] = []
        delay = raw.get("delay", DEFAULT_CRAFT_DELAY)
        if isinstance(delay, bool) or not isinstance(delay, int) or delay < 0:
            raise ValueError("Craft delay must be a non-negative integer in seconds.")
        for crafter in crafters:
            if not isinstance(crafter, dict):
                crafter = {}
            normalized_crafters.append(
                {
                    **_normalize_object(crafter),
                    "item": str(crafter.get("item", "")),
                }
            )
        routes.append(
            {
                **normalize_general_route(raw),
                "delay": delay,
                "crafters": normalized_crafters,
            }
        )
    config: CraftConfig = {"generalCraftData": routes}
    return config


def load_craft_config(path: str | Path = CRAFT_CONFIG_PATH, create_missing: bool = True):
    """Validate routes and persist missing delays while preserving unrelated data."""
    path = Path(path)
    if not path.exists():
        config: CraftConfig = {"generalCraftData": []}
        if create_missing:
            save_craft_config(config, path)
        return config
    with path.open(encoding="utf-8") as file:
        raw = json.load(file)
    config = normalize_craft_config(raw)
    missing = [route for route in raw["generalCraftData"] if "delay" not in route]
    if missing:
        for route in missing:
            route["delay"] = DEFAULT_CRAFT_DELAY
        with path.open("w", encoding="utf-8") as file:
            json.dump(raw, file, indent=2)
    return config


def save_craft_config(data: object, path: str | Path = CRAFT_CONFIG_PATH):
    """Persist normalized craft stations independently from deposit stations."""
    config = normalize_craft_config(data)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(config, file, indent=2)
    return config


def valid_craft_route(route: CraftRoute):
    """Require enough information to run a crafter and deposit its output."""
    return bool(route["teleport"].strip() and any(crafter["item"].strip() for crafter in route["crafters"]) and route["dedi"]["items"])
