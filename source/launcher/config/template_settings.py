import copy
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from source.gacha_bot.deposit_config import normalize_deposit_config
from source.launcher.config.constants import (
    DEFAULT_SETTINGS,
    TEMPLATE_REFERENCE_DEFAULTS,
    TEMPLATE_SETTING_KEYS,
)
from source.launcher.config.station_config import (
    normalize_gacha_config,
    normalize_pego_config,
)

TEMPLATE_DIRECTORY = Path("json_files/template_settings")
DEFAULT_TEMPLATE_FILENAME = "Default_Official_GBot.json"
TEMPLATE_TYPE = "template_setting"
CURRENT_TEMPLATE_VERSION = 1
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True)
class TemplateCatalog:
    """Represent templates and errors keyed by stable JSON filenames."""

    templates: dict[str, dict]
    paths: dict[str, Path]
    errors: dict[str, str]
    error_paths: dict[str, Path] = field(default_factory=dict)


def normalize_yaw(yaw: float):
    """Wrap a yaw value into the [-180, 180) range."""
    normalized = (float(yaw) + 180.0) % 360.0 - 180.0
    return round(normalized, 12)


def convert_deposit_yaw(data: dict, station_yaw: float, exporting: bool):
    """Convert deposit route yaws between absolute and station-relative values."""
    converted = copy.deepcopy(normalize_deposit_config(data))
    adjustment = -float(station_yaw) if exporting else float(station_yaw)
    for route in converted["depositCrystalData"]:
        for container in (route["dedi"]["items"], route["vault"]["items"]):
            _adjust_item_yaws(container, adjustment)  # type: ignore
    for route in converted["depositGrindableData"]:
        _adjust_item_yaws([route["grinder"]], adjustment)  # type: ignore
        _adjust_item_yaws(route["dedi"]["items"], adjustment)  # type: ignore
    return converted


def _adjust_item_yaws(items: list[dict], adjustment: float):
    """Apply a yaw adjustment to route objects in place."""
    for item in items:
        item["location"]["yaw"] = normalize_yaw(
            float(item["location"]["yaw"]) + adjustment
        )


def safe_template_filename(name: str):
    """Derive a Windows-safe JSON filename while preserving the display name."""
    raw_name = str(name).strip()
    if raw_name.lower().endswith(".json"):
        raw_name = raw_name[:-5]
    compact = re.sub(r"\s+", "_", raw_name)
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", compact).rstrip(" .")
    if not safe:
        safe = "template"
    if safe.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        safe = f"_{safe}"
    return f"{safe}.json"


def normalize_template_id(filename: str):
    """Normalize an existing template basename while preserving valid characters."""
    template_id = Path(str(filename)).name.strip()
    if not template_id:
        raise ValueError("Template filename must not be empty.")
    if not template_id.lower().endswith(".json"):
        template_id = f"{template_id}.json"
    return template_id


def normalize_template(document: object):
    """Validate and normalize a versioned template document."""
    if not isinstance(document, dict):
        raise ValueError("Template must be a JSON object.")
    name = document.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Template name must be a non-empty string.")
    if document.get("type") != TEMPLATE_TYPE:
        raise ValueError(f'Template type must be "{TEMPLATE_TYPE}".')
    version = document.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("Template version must be an integer.")
    normalizer = {1: _normalize_v1}.get(version)
    if normalizer is None:
        raise ValueError(f"Unsupported template version: {version}.")
    data, warnings = normalizer(document.get("data"))
    return (
        {
            "name": name,
            "type": TEMPLATE_TYPE,
            "version": version,
            "data": data,
        },
        warnings,
    )


def _normalize_v1(raw_data: object):
    """Normalize the version 1 main-bot template payload."""
    if not isinstance(raw_data, dict):
        raise ValueError("Template data must be a JSON object.")
    raw_settings = raw_data.get("settings")
    if not isinstance(raw_settings, dict):
        raise ValueError("Template settings must be a JSON object.")
    warnings: list[str] = []
    if "station_yaw" in raw_settings:
        warnings.append("Ignored local-only station_yaw.")
    settings = {
        key: _normalize_setting_value(key, raw_settings.get(key))
        for key in TEMPLATE_SETTING_KEYS
    }
    try:
        dedis = normalize_deposit_config(raw_data.get("dedis"))
        gacha = normalize_gacha_config(raw_data.get("gacha"))
        pego = normalize_pego_config(raw_data.get("pego"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid template data: {exc}") from exc
    return {
        "settings": settings,
        "dedis": dedis,
        "gacha": gacha,
        "pego": pego,
    }, warnings


def _normalize_setting_value(key: str, value: object):
    """Normalize one required template setting using its current runtime type."""
    if key not in DEFAULT_SETTINGS:
        raise ValueError(f"Unknown template setting: {key}.")
    if value is None:
        raise ValueError(f"Template setting is missing: {key}.")
    default = DEFAULT_SETTINGS[key]
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise ValueError(f"Template setting {key} must be true or false.")
        return value
    if isinstance(default, int):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Template setting {key} must be an integer.")
        return value
    if isinstance(default, float):
        if isinstance(value, bool):
            raise ValueError(f"Template setting {key} must be a number.")
        try:
            return float(value)  # type: ignore
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Template setting {key} must be a number.") from exc
    return str(value)


def build_template(
    name: str,
    settings: dict,
    dedis: dict,
    gacha: list[dict],
    pego: list[dict],
):
    """Build a normalized v1 snapshot from current effective configuration."""
    document = {
        "name": str(name),
        "type": TEMPLATE_TYPE,
        "version": CURRENT_TEMPLATE_VERSION,
        "data": {
            "settings": {key: settings[key] for key in TEMPLATE_SETTING_KEYS},
            "dedis": convert_deposit_yaw(dedis, float(settings["station_yaw"]), True),
            "gacha": copy.deepcopy(gacha),
            "pego": copy.deepcopy(pego),
        },
    }
    return normalize_template(document)[0]


def read_template(path: str | Path):
    """Read and validate one template JSON file."""
    with Path(path).open("r", encoding="utf-8") as file:
        return normalize_template(json.load(file))


def scan_templates(directory: str | Path = TEMPLATE_DIRECTORY):
    """Scan a template directory without allowing one bad file to hide others."""
    directory = Path(directory)
    templates: dict[str, dict] = {}
    paths: dict[str, Path] = {}
    errors: dict[str, str] = {}
    error_paths: dict[str, Path] = {}
    if not directory.exists():
        return TemplateCatalog(templates, paths, errors, error_paths)
    template_paths = (
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() == ".json"
    )
    for path in sorted(template_paths, key=lambda item: item.name.casefold()):
        template_id = path.name
        try:
            with path.open("r", encoding="utf-8") as file:
                raw = json.load(file)
            template, _warnings = normalize_template(raw)
            templates[template_id] = template
            paths[template_id] = path
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors[template_id] = str(exc)
            error_paths[template_id] = path
    return TemplateCatalog(templates, paths, errors, error_paths)


def write_template(
    template: dict,
    template_id: str,
    directory: str | Path = TEMPLATE_DIRECTORY,
    replaced_path: str | Path | None = None,
):
    """Atomically write a normalized template and remove a replaced old path."""
    normalized, _warnings = normalize_template(template)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / normalize_template_id(template_id)
    temporary = destination.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(normalized, file, indent=2)
    os.replace(temporary, destination)
    if replaced_path is not None:
        old_path = Path(replaced_path)
        if old_path != destination and old_path.exists():
            old_path.unlink()
    return destination


def next_unique_template_filename(template_id: str, catalog: TemplateCatalog):
    """Append underscores until a template filename is unique."""
    candidate = safe_template_filename(template_id)
    used_filenames = {
        *[name.casefold() for name in catalog.templates],
        *[name.casefold() for name in catalog.errors],
    }
    while candidate.casefold() in used_filenames:
        candidate = f"{Path(candidate).stem}_.json"
    return candidate


def resolve_template_reference(reference: str, catalog: TemplateCatalog):
    """Resolve filename IDs and legacy stem/name references to a stable ID."""
    reference = str(reference)
    if not reference:
        return "", ""
    exact_ids = [
        template_id
        for template_id in (*catalog.templates, *catalog.errors)
        if template_id.casefold() == reference.casefold()
    ]
    if len(exact_ids) == 1:
        return exact_ids[0], ""
    stem_ids = [
        template_id
        for template_id in (*catalog.templates, *catalog.errors)
        if Path(template_id).stem.casefold() == reference.casefold()
    ]
    if len(stem_ids) == 1:
        return stem_ids[0], ""
    name_ids = [
        template_id
        for template_id, template in catalog.templates.items()
        if str(template["name"]).casefold() == reference.casefold()
    ]
    if len(name_ids) == 1:
        return name_ids[0], ""
    if len(stem_ids) > 1 or len(name_ids) > 1:
        return None, f'Legacy template reference "{reference}" is ambiguous.'
    return None, f'Template "{reference}" cannot be found.'


def migrate_template_references(settings: dict, catalog: TemplateCatalog):
    """Migrate legacy template assignments to complete filename IDs."""
    migrated = copy.deepcopy(settings)
    errors: dict[str, str] = {}
    for key in TEMPLATE_REFERENCE_DEFAULTS:
        reference = str(migrated.get(key, ""))
        resolved, error = resolve_template_reference(reference, catalog)
        if resolved is not None:
            migrated[key] = resolved
        elif error:
            errors[reference] = error
    return migrated, errors
