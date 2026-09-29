"""Discover bundled building templates and copy them into ARK."""

import shutil
from pathlib import Path

from source.launcher import ark_game_setup

TEMPLATE_DIRECTORY = Path(__file__).resolve().parents[3] / "assets/templateHammer"
TEMPLATE_CATEGORIES = {
    "GachaBot - Gacha Pair": "Gacha",
    "GachaBot - Gacha Pair 45o": "Gacha",
    "GachaBot - Gacha Pair Enclosed": "Gacha",
    "GachaBot - Gacha Space": "Gacha",
    "[Shen] RRenderCenter": "Gacha",
    "[Shen] RRenderTop": "Gacha",
    "GachaBot - Pego": "Gacha",
    "GachaBot - Render V3": "Gacha",
    #
    "GachaBot - Transfer Base": "Transfer",
}
TOOL_CATEGORIES = {
    "Server Transfer": "Transfer",
    "Switch Steam": "Transfer",
    #
    "Auto Join Server": "QoL",
    "Crop Plot Fertilizer Refresh": "QoL",
    "Auto Fishing": "QoL",
    "Auto Baby Feeding": "QoL",
}
CATEGORIES = ("All", "Gacha", "Transfer", "QoL", "Unsorted")


def discover_templates(directory: Path = TEMPLATE_DIRECTORY):
    """Return alphabetically sorted template paths and optional preview paths."""
    return [
        (
            path,
            next(
                (path.with_suffix(ext) for ext in (".jpg", ".jpeg", ".png") if path.with_suffix(ext).is_file()),
                None,
            ),
        )
        for path in sorted(directory.glob("*.template"), key=lambda item: item.name.casefold())
        if path.is_file()
    ]


def import_template(source: Path):
    """Overwrite the selected template in the detected ARK Saved directory."""
    settings_path = Path(ark_game_setup.find_game_user_settings_path())
    destination = settings_path.parents[2] / "StructureTemplates" / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination
