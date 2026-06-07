import ctypes
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None


RESTORE_STATE_PATH = Path("json_files/ark_start_game_restore.json")
CONFIG_BACKUP_PATH = Path("json_files/GameUserSettings.ini.backup")
ARK_PROCESS_NAME = "ArkAscended.exe"
ARK_STEAM_URL = "steam://rungameid/2399830"
ARK_INSTALL_DIR_NAME = "ARK Survival Ascended"
GAME_SETTINGS_RELATIVE_PATH = Path(
    "ShooterGame/Saved/Config/Windows/GameUserSettings.ini"
)

TARGET_GAME_SETTINGS = {
    "ResolutionSizeX": "1920",
    "ResolutionSizeY": "1080",
    "FoliageInteractionQuantityLimit": "0.500000",
    "GraphicsQuality": "5",
    "bEnableFootstepParticles": "False",
    "AdvancedGraphicsQuality": "0",
    "MasterAudioVolume": "0.050000",
    "FoliageInteractionDistanceLimit": "0.500000",
    "FOVMultiplier": "1.000000",
    "FoliageInteractionDistance": "0.010000",
    "bEnableFluidInteraction": "False",
    "GUI3DWidgetQuality": "0.000000",
    "bThirdPersonPlayer": "False",
    "FrameGenerationMethod": "0",
}

ENUM_CURRENT_SETTINGS = -1
DISP_CHANGE_SUCCESSFUL = 0
DM_PELSWIDTH = 0x80000
DM_PELSHEIGHT = 0x100000
DM_DISPLAYFREQUENCY = 0x400000


@dataclass(frozen=True)
class DisplayMode:
    width: int
    height: int
    frequency: int


class POINTL(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", ctypes.c_ushort),
        ("dmDriverVersion", ctypes.c_ushort),
        ("dmSize", ctypes.c_ushort),
        ("dmDriverExtra", ctypes.c_ushort),
        ("dmFields", ctypes.c_ulong),
        ("dmPosition", POINTL),
        ("dmDisplayOrientation", ctypes.c_ulong),
        ("dmDisplayFixedOutput", ctypes.c_ulong),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", ctypes.c_ushort),
        ("dmBitsPerPel", ctypes.c_ulong),
        ("dmPelsWidth", ctypes.c_ulong),
        ("dmPelsHeight", ctypes.c_ulong),
        ("dmDisplayFlags", ctypes.c_ulong),
        ("dmDisplayFrequency", ctypes.c_ulong),
        ("dmICMMethod", ctypes.c_ulong),
        ("dmICMIntent", ctypes.c_ulong),
        ("dmMediaType", ctypes.c_ulong),
        ("dmDitherType", ctypes.c_ulong),
        ("dmReserved1", ctypes.c_ulong),
        ("dmReserved2", ctypes.c_ulong),
        ("dmPanningWidth", ctypes.c_ulong),
        ("dmPanningHeight", ctypes.c_ulong),
    ]


def restore_state_exists(state_path=RESTORE_STATE_PATH):
    return Path(state_path).exists()


def parse_steam_library_paths(vdf_text):
    paths = []
    for match in re.finditer(r'"path"\s+"((?:\\.|[^"\\])*)"', vdf_text):
        raw_path = match.group(1)
        paths.append(Path(raw_path.replace("\\\\", "\\")))
    return paths


def find_running_steam_dir():
    if psutil is None:
        raise RuntimeError("psutil is required to locate running steam.exe.")

    for proc in psutil.process_iter(attrs=["name", "exe"]):
        try:
            name = proc.info.get("name") or ""
            exe = proc.info.get("exe")
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
        if name.lower() == "steam.exe" and exe:
            return Path(exe).parent

    raise RuntimeError("steam.exe is not running.")


def find_game_user_settings_path(steam_dir=None):
    steam_root = Path(steam_dir) if steam_dir is not None else find_running_steam_dir()
    library_vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    if not library_vdf.exists():
        raise RuntimeError(f"Steam library file was not found: {library_vdf}")

    library_paths = parse_steam_library_paths(
        library_vdf.read_text(encoding="utf-8", errors="replace")
    )
    if not library_paths:
        raise RuntimeError(f"No Steam library paths were found in {library_vdf}")

    for library_path in library_paths:
        ark_dir = library_path / "steamapps" / "common" / ARK_INSTALL_DIR_NAME
        if not ark_dir.exists():
            continue
        settings_path = ark_dir / GAME_SETTINGS_RELATIVE_PATH
        try:
            with settings_path.open("r", encoding="utf-8", errors="replace"):
                return settings_path
        except OSError:
            continue

    raise RuntimeError("ARK Survival Ascended GameUserSettings.ini was not found.")


def get_current_display_mode():
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Display mode changes are only supported on Windows.")

    mode = DEVMODEW()
    mode.dmSize = ctypes.sizeof(DEVMODEW)
    if not ctypes.windll.user32.EnumDisplaySettingsW(
        None, ENUM_CURRENT_SETTINGS, ctypes.byref(mode)
    ):
        raise RuntimeError("Unable to read the current display mode.")
    return DisplayMode(
        width=int(mode.dmPelsWidth),
        height=int(mode.dmPelsHeight),
        frequency=int(mode.dmDisplayFrequency),
    )


def apply_display_mode(display_mode):
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Display mode changes are only supported on Windows.")

    mode = DEVMODEW()
    mode.dmSize = ctypes.sizeof(DEVMODEW)
    mode.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT | DM_DISPLAYFREQUENCY
    mode.dmPelsWidth = int(display_mode.width)
    mode.dmPelsHeight = int(display_mode.height)
    mode.dmDisplayFrequency = int(display_mode.frequency)
    result = ctypes.windll.user32.ChangeDisplaySettingsW(ctypes.byref(mode), 0)
    if result != DISP_CHANGE_SUCCESSFUL:
        raise RuntimeError(f"Unable to change display mode. Windows result: {result}")


def load_restore_state(state_path=RESTORE_STATE_PATH):
    with Path(state_path).open("r", encoding="utf-8") as file:
        return json.load(file)


def save_restore_state_once(
    settings_path, state_path=RESTORE_STATE_PATH, backup_path=CONFIG_BACKUP_PATH
):
    state_path = Path(state_path)
    if state_path.exists():
        return load_restore_state(state_path)

    state_path.parent.mkdir(parents=True, exist_ok=True)
    display_mode = get_current_display_mode()
    state = {
        "display_mode": asdict(display_mode),
        "settings_path": str(Path(settings_path)),
        "backup_path": str(Path(backup_path)),
    }
    with state_path.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)
    return state


def backup_game_settings_once(settings_path, backup_path=CONFIG_BACKUP_PATH):
    backup_path = Path(backup_path)
    if backup_path.exists():
        return backup_path
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(settings_path, backup_path)
    return backup_path


def patch_game_settings(settings_path, target_settings=TARGET_GAME_SETTINGS):
    settings_path = Path(settings_path)
    lines = settings_path.read_text(encoding="utf-8", errors="replace").splitlines()
    remaining = dict(target_settings)
    updated_lines = []

    for line in lines:
        stripped = line.strip()
        if "=" not in stripped or stripped.startswith((";", "#", "[")):
            updated_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            prefix = line[: len(line) - len(line.lstrip())]
            updated_lines.append(f"{prefix}{key}={remaining.pop(key)}")
        else:
            updated_lines.append(line)

    for key, value in remaining.items():
        updated_lines.append(f"{key}={value}")

    settings_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def kill_running_ark():
    # from source.join_sim.source.crash.crash import close_game

    # close_game()
    subprocess.run(
        ["taskkill", "/f", "/im", ARK_PROCESS_NAME],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def launch_ark_through_steam():
    subprocess.Popen(["cmd", "/c", "start", "", ARK_STEAM_URL])


def prepare_and_launch_game():
    settings_path = find_game_user_settings_path()
    if restore_state_exists():
        state = load_restore_state()
        backup_path = Path(state.get("backup_path", CONFIG_BACKUP_PATH))
        if not backup_path.exists():
            raise RuntimeError(
                f"GameUserSettings.ini backup was not found: {backup_path}"
            )
    else:
        backup_game_settings_once(settings_path, CONFIG_BACKUP_PATH)
        state = save_restore_state_once(settings_path, backup_path=CONFIG_BACKUP_PATH)
    original_mode = state["display_mode"]
    apply_display_mode(
        DisplayMode(width=1920, height=1080, frequency=int(original_mode["frequency"]))
    )
    kill_running_ark()
    patch_game_settings(settings_path)
    launch_ark_through_steam()
    return settings_path


def clear_restore_state(state_path=RESTORE_STATE_PATH):
    state_path = Path(state_path)
    backup_path = None
    if state_path.exists():
        try:
            backup_path = load_restore_state(state_path).get("backup_path")
        except (OSError, json.JSONDecodeError):
            backup_path = str(CONFIG_BACKUP_PATH)
        state_path.unlink()

    for candidate in (backup_path, CONFIG_BACKUP_PATH):
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            path.unlink()


def restore_game_settings(state_path=RESTORE_STATE_PATH):
    state = load_restore_state(state_path)
    settings_path = Path(state["settings_path"])
    backup_path = Path(state["backup_path"])

    kill_running_ark()

    display = state["display_mode"]
    apply_display_mode(
        DisplayMode(
            width=int(display["width"]),
            height=int(display["height"]),
            frequency=int(display["frequency"]),
        )
    )

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    if backup_path.exists():
        shutil.copy2(backup_path, settings_path)
    clear_restore_state(state_path)
    return settings_path
