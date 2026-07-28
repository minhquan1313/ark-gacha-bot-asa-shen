import json
from pathlib import Path

AUTO_FEED_PATH = Path("json_files/auto_feed/data.json")
DEFAULT_AUTO_FEED = {
    "ping": 100,
    "tek_pod": True,
    "station_yaw": 0.0,
    "food_slot": -1,
    "water_slot": -1,
    "feed_cycle": 30,
    "babies": [],
}


def default_baby() -> dict:
    """Return one editable Baby entry."""
    return {
        "location": {"yaw": 0.0, "pitch": 0.0},
        "crouched": False,
        "food": "meat",
    }


def normalize_auto_feed(raw: object) -> dict:
    """Normalize the sample-shaped Auto Baby Feeding configuration."""
    source = raw if isinstance(raw, dict) else {}
    result = dict(DEFAULT_AUTO_FEED)
    result.update({key: source[key] for key in DEFAULT_AUTO_FEED if key in source})
    result["tek_pod"] = bool(result["tek_pod"])
    for key in ("station_yaw",):
        result[key] = float(result[key])
    for key in ("food_slot", "water_slot", "feed_cycle"):
        result[key] = int(result[key])
    if result["feed_cycle"] <= 0:
        raise ValueError("Feed cycle must be greater than 0 seconds.")
    for key in ("food_slot", "water_slot"):
        if result[key] == 0:
            result[key] = -1
        if result[key] != -1 and not 1 <= result[key] <= 10:
            raise ValueError(
                f"{key.replace('_', ' ').capitalize()} must be -1 or 1-10."
            )
    babies = []
    for baby in result.get("babies", []):
        if not isinstance(baby, dict):
            continue
        location = baby.get("location", {})
        babies.append(
            {
                "location": {
                    "yaw": float(location.get("yaw", 0.0)),
                    "pitch": float(location.get("pitch", 0.0)),
                },
                "crouched": bool(baby.get("crouched", False)),
                "food": str(baby.get("food", "meat")).strip() or "meat",
            }
        )
    result["babies"] = babies
    return result


def load_auto_feed() -> dict:
    """Load and normalize the persisted Auto Baby Feeding configuration."""
    try:
        raw = json.loads(AUTO_FEED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = DEFAULT_AUTO_FEED
    return normalize_auto_feed(raw)


def save_auto_feed(config: dict) -> dict:
    """Normalize and persist Auto Baby Feeding configuration immediately."""
    normalized = normalize_auto_feed(config)
    AUTO_FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTO_FEED_PATH.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    return normalized
