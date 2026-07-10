import json
from pathlib import Path

from source.utility.types import DepositConfig

VAULT_ITEMS_FILE = Path("json_files/vault_items.json")
DEFAULT_VAULT_ITEMS = ["riot", "assault", "gate", "tree"]


def load_vault_items(
    deposit_config: DepositConfig | None = None, path: str | Path = VAULT_ITEMS_FILE
):
    path = Path(path)
    items = []
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, list):
            items.extend(str(item).strip() for item in data if str(item).strip())
    else:
        items.extend(DEFAULT_VAULT_ITEMS)

    items.extend(_deposit_config_items(deposit_config))
    return sorted(set(items), key=str.lower)


def save_vault_items(items, path=VAULT_ITEMS_FILE):
    path = Path(path)
    values = sorted(
        {str(item).strip() for item in items if str(item).strip()}, key=str.lower
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(values, file, indent=2)
    return values


def add_vault_item(
    item: object,
    deposit_config: DepositConfig | None = None,
    path: str | Path = VAULT_ITEMS_FILE,
):
    value = str(item).strip()
    if not value:
        return load_vault_items(deposit_config, path)
    items = load_vault_items(deposit_config, path)
    items.append(value)
    return save_vault_items(items, path)


def _deposit_config_items(deposit_config: DepositConfig | None):
    if not isinstance(deposit_config, dict):
        return []
    values = []
    for route in deposit_config["depositCrystalData"]:
        for vault_item in route["vault"]["items"]:
            values.extend(vault_item["items"])
    return [str(item).strip() for item in values if str(item).strip()]
