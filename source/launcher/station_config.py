import json
from pathlib import Path

GACHA_CONFIG_PATH = Path("json_files/gacha.json")
PEGO_CONFIG_PATH = Path("json_files/pego.json")
GACHA_PAIR_PREFIX = "GACHAPAIR"
DEFAULT_PEGO_DELAY = 1600
VALID_GACHA_SIDES = {"left", "right"}


def default_gacha_entry(name="", teleporter="", side="left"):
    return {
        "name": str(name),
        "teleporter": str(teleporter),
        "side": str(side).lower(),
    }


def default_pego_entry(index=1, delay=DEFAULT_PEGO_DELAY):
    name = f"pego{int(index)}"
    return {"name": name, "teleporter": name, "delay": int(delay)}


def load_gacha_config(path=GACHA_CONFIG_PATH, create_missing=True):
    path = Path(path)
    if not path.exists():
        entries = default_gacha_pair()
        if create_missing:
            save_gacha_config(entries, path)
        return entries
    return normalize_gacha_config(_read_json_array(path, "Gacha config"))


def save_gacha_config(entries, path=GACHA_CONFIG_PATH):
    normalized = normalize_gacha_config(entries)
    _write_json_array(normalized, path)
    return normalized


def load_pego_config(path=PEGO_CONFIG_PATH, create_missing=True):
    path = Path(path)
    if not path.exists():
        entries = [default_pego_entry()]
        if create_missing:
            save_pego_config(entries, path)
        return entries
    return normalize_pego_config(_read_json_array(path, "Pego config"))


def save_pego_config(entries, path=PEGO_CONFIG_PATH):
    normalized = normalize_pego_config(entries)
    _write_json_array(normalized, path)
    return normalized


def normalize_gacha_config(data):
    if not isinstance(data, list):
        raise ValueError("Gacha config must be a JSON array.")
    return [_normalize_gacha_entry(entry, index) for index, entry in enumerate(data, 1)]


def normalize_pego_config(data):
    if not isinstance(data, list):
        raise ValueError("Pego config must be a JSON array.")
    return [_normalize_pego_entry(entry, index) for index, entry in enumerate(data, 1)]


def default_gacha_pair(prefix=GACHA_PAIR_PREFIX, index=1):
    teleporter = f"{prefix}_{int(index)}"
    return [
        default_gacha_entry(f"{teleporter}_left", teleporter, "left"),
        default_gacha_entry(f"{teleporter}_right", teleporter, "right"),
    ]


def grouped_gacha_entries(entries):
    groups = []
    by_teleporter = {}
    for index, entry in enumerate(entries):
        teleporter = str(entry.get("teleporter", ""))
        if teleporter not in by_teleporter:
            by_teleporter[teleporter] = []
            groups.append((teleporter, by_teleporter[teleporter]))
        by_teleporter[teleporter].append((index, entry))
    return groups


def next_gacha_teleporter(entries, prefix=GACHA_PAIR_PREFIX, exclude_teleporter=None):
    existing = {
        str(entry.get("teleporter", ""))
        for entry in entries
        if str(entry.get("teleporter", "")) != str(exclude_teleporter)
    }
    for index in range(1, 1000):
        candidate = f"{prefix}_{index}"
        if candidate not in existing:
            return candidate
    raise ValueError("No available gacha teleporter name from 1 to 999.")


def next_gacha_name(entries):
    return f"gacha{_next_index(entries, 'gacha')}"


def next_pego_index(entries):
    return _next_index(entries, "pego")


def missing_gacha_side(group_entries):
    used = {
        str(entry.get("side", "")).lower()
        for entry in group_entries
        if str(entry.get("side", "")).lower() in VALID_GACHA_SIDES
    }
    if "left" not in used:
        return "left"
    if "right" not in used:
        return "right"
    return None


def auto_fill_gacha_group(group_entries, teleporter=None):
    sides = ["left", "right"]
    for entry, side in zip(group_entries[:2], sides):
        if teleporter is not None:
            entry["teleporter"] = str(teleporter)
        entry["side"] = side
        entry["name"] = gacha_name_from_teleporter(entry.get("teleporter", ""), side)


def gacha_name_from_teleporter(teleporter, side):
    return f"{str(teleporter)}_{str(side).lower()}"


def risky_teleporter_names(entries):
    teleporters = sorted({str(entry.get("teleporter", "")) for entry in entries})
    risky = set()
    for base in teleporters:
        if not base or not base[-1:].isdigit():
            continue
        for other in teleporters:
            if base == other or not other.startswith(base):
                continue
            suffix = other[len(base) :]
            if suffix[:1].isdigit():
                risky.add(base)
                risky.add(other)
    return risky


def set_all_pego_delays(entries, delay):
    delay = int(delay)
    for entry in entries:
        entry["delay"] = delay


def _normalize_gacha_entry(entry, index):
    if not isinstance(entry, dict):
        entry = {}
    normalized = {
        "name": str(entry.get("name", f"gacha{index}")),
        "teleporter": str(entry.get("teleporter", "")),
        "side": str(entry.get("side", "left")).lower(),
    }
    depo_tp = str(entry.get("depo_tp", "")).strip()
    if depo_tp:
        normalized["depo_tp"] = depo_tp
    resource_type = str(entry.get("resource_type", "")).strip()
    if resource_type.lower() == "collect":
        normalized["resource_type"] = resource_type
    return normalized


def _normalize_pego_entry(entry, index):
    if not isinstance(entry, dict):
        entry = {}
    return {
        "name": str(entry.get("name", f"pego{index}")),
        "teleporter": str(entry.get("teleporter", f"pego{index}")),
        "delay": _int_value(entry.get("delay", DEFAULT_PEGO_DELAY), "delay"),
    }


def _next_index(entries, prefix):
    used = set()
    for entry in entries:
        name = str(entry.get("name", ""))
        if not name.startswith(prefix):
            continue
        suffix = name[len(prefix) :]
        if suffix.isdigit():
            used.add(int(suffix))
    index = 1
    while index in used:
        index += 1
    return index


def _int_value(value, name):
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc


def _read_json_array(path, label):
    with Path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{label} must be a JSON array.")
    return data


def _write_json_array(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
