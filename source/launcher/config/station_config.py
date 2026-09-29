import json
import math
from pathlib import Path

GACHA_CONFIG_PATH = Path("json_files/gacha.json")
GACHA_COLLECT_CONFIG_PATH = Path("json_files/gacha_collect.json")
PEGO_CONFIG_PATH = Path("json_files/pego.json")
DEFAULT_PEGO_DELAY = 1600
VALID_GACHA_SIDES = {"left", "right"}

DEFAULT_PEGO_TARGET_CRYSTALS = 290
DEFAULT_PEGO_SNOW_OWLS_PER_GACHA = 5
DEFAULT_PEGO_STATION_SECONDS = 80

PEGO_CALIBRATION_CRYSTALS = 264
PEGO_CALIBRATION_GACHAS = 40
PEGO_CALIBRATION_PEGOS = 3
PEGO_CALIBRATION_DELAY = 1600
PEGO_CALIBRATION_SNOW_OWLS_PER_GACHA = 5
PEGO_CALIBRATION_STATION_SECONDS = 90


def default_gacha_entry(teleporter: str = "", side: str = "left"):
    """Create an unnamed side record; runtime owns task names."""
    return {
        "teleporter": str(teleporter),
        "side": str(side).lower(),
    }


def default_gacha_collect_entry(teleporter: str = "", side: str = "left", item: str = ""):
    """Create a collection side with empty destination by default."""
    return {
        **default_gacha_entry(teleporter, side),
        "item": str(item),
        "dedi_teleport": "",
    }


def default_pego_entry(index=1, delay=DEFAULT_PEGO_DELAY):
    return {"teleporter": f"pego{int(index)}", "delay": int(delay)}


def load_gacha_config(path=GACHA_CONFIG_PATH, create_missing=True):
    path = Path(path)
    if not path.exists():
        entries = []
        if create_missing:
            save_gacha_config(entries, path)
        return entries
    return normalize_gacha_config(_read_json_array(path, "Gacha config"))


def save_gacha_config(entries, path=GACHA_CONFIG_PATH):
    normalized = normalize_gacha_config(entries)
    _write_json_array(normalized, path)
    return normalized


def load_gacha_collect_config(path=GACHA_COLLECT_CONFIG_PATH, create_missing=True):
    path = Path(path)
    if not path.exists():
        entries = []
        if create_missing:
            save_gacha_collect_config(entries, path)
        return entries
    return normalize_gacha_collect_config(_read_json_array(path, "Gacha collect config"))


def save_gacha_collect_config(entries, path=GACHA_COLLECT_CONFIG_PATH):
    normalized = normalize_gacha_collect_config(entries)
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
    return [_normalize_gacha_entry(entry) for entry in data]


def normalize_gacha_collect_config(data):
    if not isinstance(data, list):
        raise ValueError("Gacha collect config must be a JSON array.")
    return [_normalize_gacha_collect_entry(entry) for entry in data]


def normalize_pego_config(data):
    if not isinstance(data, list):
        raise ValueError("Pego config must be a JSON array.")
    return [_normalize_pego_entry(entry, index) for index, entry in enumerate(data, 1)]


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


def next_pego_index(entries):
    """Choose the first unused default teleporter independently of runtime names."""
    used = {str(entry.get("teleporter", "")) for entry in entries}
    index = 1
    while f"pego{index}" in used:
        index += 1
    return index


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


def calculate_pego_delay(
    target_crystals: int | float,
    pego_amount: int | float,
    gacha_amount: int | float,
    snow_owls_per_gacha: int | float,
    station_seconds: int | float,
):
    """Calculate configured PEGO delay needed for the target crystal average."""
    target = _positive_float(target_crystals, "target crystals")
    pegos = _positive_float(pego_amount, "pego amount")
    gachas = _positive_float(gacha_amount, "gacha amount")
    snow_owls = _positive_float(snow_owls_per_gacha, "snow owl amount")
    station = _non_negative_float(station_seconds, "pego station seconds")
    baseline_rate = PEGO_CALIBRATION_CRYSTALS / (
        (PEGO_CALIBRATION_DELAY + PEGO_CALIBRATION_STATION_SECONDS) * (PEGO_CALIBRATION_GACHAS / PEGO_CALIBRATION_PEGOS) * PEGO_CALIBRATION_SNOW_OWLS_PER_GACHA
    )
    projected_rate = baseline_rate * (gachas / pegos) * snow_owls
    recommended = math.ceil((target / projected_rate) - station)
    if recommended < 0:
        raise ValueError("recommended delay must be zero or greater.")
    return int(recommended)


def _normalize_gacha_entry(entry: dict):
    """Ignore legacy names while preserving side-record configuration."""
    if not isinstance(entry, dict):
        entry = {}
    normalized = {
        "teleporter": str(entry.get("teleporter", "")),
        "side": str(entry.get("side", "left")).lower(),
    }
    return normalized


def _normalize_gacha_collect_entry(entry: dict):
    """Normalize collection fields without changing legacy side differences."""
    normalized = _normalize_gacha_entry(entry)
    normalized["item"] = str(entry.get("item", "")) if isinstance(entry, dict) else ""
    normalized["dedi_teleport"] = str(entry.get("dedi_teleport", "")) if isinstance(entry, dict) else ""
    return normalized


def _normalize_pego_entry(entry, index):
    if not isinstance(entry, dict):
        entry = {}
    return {
        "teleporter": str(entry.get("teleporter", f"pego{index}")),
        "delay": _int_value(entry.get("delay", DEFAULT_PEGO_DELAY), "delay"),
    }


def _int_value(value, name):
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc


def _positive_float(value: object, name: str):
    try:
        result = float(value)  # type: ignore
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive number.") from exc
    if result <= 0:
        raise ValueError(f"{name} must be a positive number.")
    return result


def _non_negative_float(value: object, name: str):
    try:
        result = float(value)  # type: ignore
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be zero or greater.") from exc
    if result < 0:
        raise ValueError(f"{name} must be zero or greater.")
    return result


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
