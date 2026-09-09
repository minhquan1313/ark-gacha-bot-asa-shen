import json
from pathlib import Path

from source.gacha_bot.deposit_config import (
    _normalize_object,
    default_general_route,
    normalize_general_route,
)
from source.utility.types import CraftConfig, CrafterStorageState, CraftRoute

CRAFT_CONFIG_PATH = Path("json_files/craft.json")


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
                "crafters": normalized_crafters,
            }
        )
    config: CraftConfig = {"generalCraftData": routes}
    return config


def load_craft_config(
    path: str | Path = CRAFT_CONFIG_PATH, create_missing: bool = True
):
    """Load the current craft station format without rewriting existing files."""
    path = Path(path)
    if not path.exists():
        config: CraftConfig = {"generalCraftData": []}
        if create_missing:
            save_craft_config(config, path)
        return config
    with path.open(encoding="utf-8") as file:
        raw = json.load(file)
    config = normalize_craft_config(raw)
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
    return bool(
        route["teleport"].strip()
        and any(crafter["item"].strip() for crafter in route["crafters"])
        and route["dedi"]["items"]
    )
