import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPOSITORY_ROOT / "manifest.json"
UPDATER_PATH = REPOSITORY_ROOT / "updater.bat"
UPDATE_AVAILABLE_CODE = 10
VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
MANIFEST_BEGIN_MARKER = "UPDATE_MANIFEST_BEGIN"
MANIFEST_END_MARKER = "UPDATE_MANIFEST_END"


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


def _decode_output(value: bytes | str | None) -> str:
    """Decode updater output without relying on the Windows console codec."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    return str(value)


def _run_updater(mode: str) -> subprocess.CompletedProcess[bytes]:
    """Run updater.bat and return its captured raw Windows command result."""
    return subprocess.run(
        ["cmd", "/c", str(UPDATER_PATH), mode],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=False,
        timeout=120,
        check=False,
    )


def _load_remote_manifest(updater_output: bytes | str | None) -> UpdateManifest:
    """Parse remote manifest metadata emitted by updater.bat."""
    updater_output = _decode_output(updater_output)
    if not updater_output:
        raise ValueError("Updater returned no output for the remote manifest.")
    lines = updater_output.splitlines()
    try:
        start = lines.index(MANIFEST_BEGIN_MARKER) + 1
        end = lines.index(MANIFEST_END_MARKER, start)
    except ValueError as exc:
        raise ValueError("Updater did not return a remote manifest.") from exc
    if start == end:
        raise ValueError("Updater returned an empty remote manifest.")
    try:
        document = json.loads("\n".join(lines[start:end]))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Remote manifest is invalid: {exc}") from exc
    return _manifest_from_document(document, "Remote manifest")


def check_for_update() -> UpdateCheckResult:
    """Fetch update metadata and report whether updater.bat found new commits."""
    try:
        current = load_manifest()
    except Exception as exc:
        invalid_manifest = UpdateManifest("0.0.0", "", "", ())
        return UpdateCheckResult(invalid_manifest, invalid_manifest, False, str(exc))
    try:
        updater_result = _run_updater("/check")
        stdout = _decode_output(getattr(updater_result, "stdout", None))
        stderr = _decode_output(getattr(updater_result, "stderr", None))
        returncode = getattr(updater_result, "returncode", None)
        if returncode not in (0, UPDATE_AVAILABLE_CODE):
            message = stderr.strip() or stdout.strip()
            raise RuntimeError(message or "The updater could not check for updates.")
        latest = _load_remote_manifest(stdout)
    except Exception as exc:
        return UpdateCheckResult(current, current, False, str(exc))

    return UpdateCheckResult(
        current=current,
        latest=latest,
        update_available=returncode == UPDATE_AVAILABLE_CODE,
        version_is_newer=_version_tuple(latest.version)
        > _version_tuple(current.version),
    )
