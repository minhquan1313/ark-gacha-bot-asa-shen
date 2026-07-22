import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPOSITORY_ROOT / "manifest.json"
UPDATER_PATH = REPOSITORY_ROOT / "updater.bat"
UPDATE_BRANCH = "stable_to_play"
UPDATE_AVAILABLE_CODE = 10
VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class UpdateManifest:
    """Validated release information read from manifest.json."""

    version: str
    released_at: str
    title: str
    changelog: tuple[str, ...]


@dataclass(frozen=True)
class UpdateCheckResult:
    """Result of one updater check and its optional remote release metadata."""

    current: UpdateManifest
    latest: UpdateManifest
    update_available: bool
    error: str = ""
    version_is_newer: bool = False


def _version_tuple(version: str) -> tuple[int, int, int]:
    """Normalize a semantic version for comparison."""
    match = VERSION_PATTERN.fullmatch(version.strip().lstrip("vV"))
    if match is None:
        raise ValueError(f"Invalid version: {version}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def _manifest_from_document(document: dict, source: str) -> UpdateManifest:
    """Validate one manifest document and convert it to an immutable model."""
    if not isinstance(document, dict):
        raise ValueError(f"{source} must contain a JSON object.")
    version = document.get("version")
    released_at = document.get("released_at", "")
    title = document.get("title", "")
    changelog = document.get("changelog", [])
    if not isinstance(version, str):
        raise ValueError(f"{source} is missing a string version.")
    _version_tuple(version)
    if not isinstance(released_at, str) or not isinstance(title, str):
        raise ValueError(f"{source} has invalid release metadata.")
    if not isinstance(changelog, list) or not all(
        isinstance(item, str) for item in changelog
    ):
        raise ValueError(f"{source} changelog must be a list of strings.")
    return UpdateManifest(version, released_at, title, tuple(changelog))


def load_manifest(path: Path = MANIFEST_PATH) -> UpdateManifest:
    """Load and validate a manifest file."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load {path.name}: {exc}") from exc
    return _manifest_from_document(document, str(path))


def _run_updater(mode: str) -> subprocess.CompletedProcess[str]:
    """Run updater.bat and return its captured Windows command result."""
    return subprocess.run(
        ["cmd", "/c", str(UPDATER_PATH), mode],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _load_remote_manifest() -> UpdateManifest:
    """Read manifest metadata from the fetched remote branch."""
    result = subprocess.run(
        ["git", "show", f"origin/{UPDATE_BRANCH}:manifest.json"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "Remote manifest is unavailable.")
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Remote manifest is invalid: {exc}") from exc
    return _manifest_from_document(document, "Remote manifest")


def check_for_update() -> UpdateCheckResult:
    """Fetch update metadata and report whether updater.bat found new commits."""
    try:
        current = load_manifest()
    except ValueError as exc:
        invalid_manifest = UpdateManifest("0.0.0", "", "", ())
        return UpdateCheckResult(invalid_manifest, invalid_manifest, False, str(exc))
    try:
        updater_result = _run_updater("/check")
        if updater_result.returncode not in (0, UPDATE_AVAILABLE_CODE):
            message = updater_result.stderr.strip() or updater_result.stdout.strip()
            raise RuntimeError(message or "The updater could not check for updates.")
        latest = _load_remote_manifest()
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as exc:
        return UpdateCheckResult(current, current, False, str(exc))

    return UpdateCheckResult(
        current=current,
        latest=latest,
        update_available=updater_result.returncode == UPDATE_AVAILABLE_CODE,
        version_is_newer=_version_tuple(latest.version)
        > _version_tuple(current.version),
    )
