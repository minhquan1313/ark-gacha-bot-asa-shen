import ctypes
from dataclasses import dataclass

import mss
import numpy as np

from source.launcher.config.constants import (
    SUPPORTED_GAME_RESOLUTIONS,
)

capture_width, capture_height = SUPPORTED_GAME_RESOLUTIONS[0]
mon = {"top": 0, "left": 0, "width": capture_width, "height": capture_height}

ENUM_CURRENT_SETTINGS = -1
DISP_CHANGE_SUCCESSFUL = 0
ERROR_SUCCESS = 0

ERROR_INSUFFICIENT_BUFFER = 122
QDC_ALL_PATHS = 0x00000001
QDC_ONLY_ACTIVE_PATHS = 0x00000002
SDC_USE_SUPPLIED_DISPLAY_CONFIG = 0x00000020
SDC_VALIDATE = 0x00000040
SDC_APPLY = 0x00000080
SDC_NO_OPTIMIZATION = 0x00000100
SDC_ALLOW_CHANGES = 0x00000400
DISPLAYCONFIG_PATH_ACTIVE = 0x00000001
DISPLAYCONFIG_SCALING_ASPECTRATIOCENTEREDMAX = 4
DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE = 1
DISPLAYCONFIG_MODE_INFO_TYPE_TARGET = 2


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


class LUID(ctypes.Structure):
    _fields_ = [
        ("LowPart", ctypes.c_uint32),
        ("HighPart", ctypes.c_int32),
    ]


class DISPLAYCONFIG_RATIONAL(ctypes.Structure):
    _fields_ = [
        ("Numerator", ctypes.c_uint32),
        ("Denominator", ctypes.c_uint32),
    ]


class DISPLAYCONFIG_2DREGION(ctypes.Structure):
    _fields_ = [
        ("cx", ctypes.c_uint32),
        ("cy", ctypes.c_uint32),
    ]


class DISPLAYCONFIG_VIDEO_SIGNAL_INFO(ctypes.Structure):
    _fields_ = [
        ("pixelRate", ctypes.c_uint64),
        ("hSyncFreq", DISPLAYCONFIG_RATIONAL),
        ("vSyncFreq", DISPLAYCONFIG_RATIONAL),
        ("activeSize", DISPLAYCONFIG_2DREGION),
        ("totalSize", DISPLAYCONFIG_2DREGION),
        ("videoStandard", ctypes.c_uint32),
        ("scanLineOrdering", ctypes.c_uint32),
    ]


class DISPLAYCONFIG_TARGET_MODE(ctypes.Structure):
    _fields_ = [("targetVideoSignalInfo", DISPLAYCONFIG_VIDEO_SIGNAL_INFO)]


class DISPLAYCONFIG_SOURCE_MODE(ctypes.Structure):
    _fields_ = [
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("pixelFormat", ctypes.c_uint32),
        ("position", POINTL),
    ]


class DISPLAYCONFIG_MODE_INFO_UNION(ctypes.Union):
    _fields_ = [
        ("targetMode", DISPLAYCONFIG_TARGET_MODE),
        ("sourceMode", DISPLAYCONFIG_SOURCE_MODE),
    ]


class DISPLAYCONFIG_MODE_INFO(ctypes.Structure):
    _anonymous_ = ("modeInfo",)
    _fields_ = [
        ("infoType", ctypes.c_uint32),
        ("id", ctypes.c_uint32),
        ("adapterId", LUID),
        ("modeInfo", DISPLAYCONFIG_MODE_INFO_UNION),
    ]


class DISPLAYCONFIG_PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", LUID),
        ("id", ctypes.c_uint32),
        ("modeInfoIdx", ctypes.c_uint32),
        ("statusFlags", ctypes.c_uint32),
    ]


class DISPLAYCONFIG_PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", LUID),
        ("id", ctypes.c_uint32),
        ("modeInfoIdx", ctypes.c_uint32),
        ("outputTechnology", ctypes.c_uint32),
        ("rotation", ctypes.c_uint32),
        ("scaling", ctypes.c_uint32),
        ("refreshRate", DISPLAYCONFIG_RATIONAL),
        ("scanLineOrdering", ctypes.c_uint32),
        ("targetAvailable", ctypes.c_int32),
        ("statusFlags", ctypes.c_uint32),
    ]


class DISPLAYCONFIG_PATH_INFO(ctypes.Structure):
    _fields_ = [
        ("sourceInfo", DISPLAYCONFIG_PATH_SOURCE_INFO),
        ("targetInfo", DISPLAYCONFIG_PATH_TARGET_INFO),
        ("flags", ctypes.c_uint32),
    ]


class DISPLAYCONFIG_DEVICE_INFO_HEADER(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("size", ctypes.c_uint32),
        ("adapterId", LUID),
        ("id", ctypes.c_uint32),
    ]


class DISPLAYCONFIG_TARGET_DEVICE_NAME(ctypes.Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("flags", ctypes.c_uint32),
        ("outputTechnology", ctypes.c_uint32),
        ("edidManufactureId", ctypes.c_uint16),
        ("edidProductCodeId", ctypes.c_uint16),
        ("connectorInstance", ctypes.c_uint32),
        ("monitorFriendlyDeviceName", ctypes.c_wchar * 64),
        ("monitorDevicePath", ctypes.c_wchar * 128),
    ]


def _query_display_config(flags: int):
    """Query active or all Windows paths, retrying if the display list changes."""
    user32 = ctypes.windll.user32

    for _ in range(5):
        path_count = ctypes.c_uint32()
        mode_count = ctypes.c_uint32()
        result = user32.GetDisplayConfigBufferSizes(
            flags,
            ctypes.byref(path_count),
            ctypes.byref(mode_count),
        )
        if result != ERROR_SUCCESS:
            raise RuntimeError(f"Unable to size the display configuration. Windows result: {result}")

        paths = (DISPLAYCONFIG_PATH_INFO * path_count.value)()
        modes = (DISPLAYCONFIG_MODE_INFO * mode_count.value)()
        result = user32.QueryDisplayConfig(
            flags,
            ctypes.byref(path_count),
            paths,
            ctypes.byref(mode_count),
            modes,
            None,
        )
        if result == ERROR_SUCCESS:
            return paths, path_count.value, modes, mode_count.value
        if result != ERROR_INSUFFICIENT_BUFFER:
            raise RuntimeError(f"Unable to query the display configuration. Windows result: {result}")

    raise RuntimeError("The display configuration changed repeatedly while being queried.")


def _query_active_display_config():
    """Return the current desktop's active paths and modes."""
    return _query_display_config(QDC_ONLY_ACTIVE_PATHS)


def _get_monitor_device_path(target: DISPLAYCONFIG_PATH_TARGET_INFO):
    """Read the monitor's device path using its current Windows connection."""
    request = DISPLAYCONFIG_TARGET_DEVICE_NAME()
    request.header.type = 2  # DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME
    request.header.size = ctypes.sizeof(request)
    request.header.adapterId = target.adapterId
    request.header.id = target.id
    result = ctypes.windll.user32.DisplayConfigGetDeviceInfo(ctypes.byref(request))
    if result != ERROR_SUCCESS or not request.monitorDevicePath:
        raise RuntimeError(f"Unable to identify a connected monitor. Windows result: {result}")
    return request.monitorDevicePath


def _display_key(info: DISPLAYCONFIG_PATH_SOURCE_INFO | DISPLAYCONFIG_PATH_TARGET_INFO):
    """Identify a live source or target within the current Windows query only."""
    return info.adapterId.LowPart, info.adapterId.HighPart, info.id


def _structure_to_dict(value: ctypes.Structure):
    """Serialize a display-mode payload as readable integer fields, without handles."""
    fields = {}
    for field_definition in value._fields_:
        name = field_definition[0]
        field = getattr(value, name)
        fields[name] = _structure_to_dict(field) if isinstance(field, ctypes.Structure) else field
    return fields


def _structure_from_dict(structure_type: type[ctypes.Structure], values: dict):
    """Decode a display-mode payload, rejecting missing fields and out-of-range values."""
    if not isinstance(values, dict) or set(values) != {field_definition[0] for field_definition in structure_type._fields_}:
        raise ValueError("Unexpected display mode fields")
    result = structure_type()
    for field_definition in structure_type._fields_:
        name = field_definition[0]
        field_type = field_definition[1]
        value = values[name]
        if issubclass(field_type, ctypes.Structure):
            value = _structure_from_dict(field_type, value)
        elif type(value) is not int:
            raise ValueError(f"Invalid display mode value: {name}")
        setattr(result, name, value)
        if not isinstance(value, ctypes.Structure) and getattr(result, name) != value:
            raise ValueError(f"Invalid display mode value: {name}")
    return result


def _monitor_settings(
    path: DISPLAYCONFIG_PATH_INFO,
    modes: ctypes.Array,
    mode_count: int,
    device_path: str,
    group: int,
):
    """Extract monitor settings while discarding session-specific Windows identifiers."""
    source_index = int(path.sourceInfo.modeInfoIdx)
    target_index = int(path.targetInfo.modeInfoIdx)
    if (
        source_index >= mode_count
        or target_index >= mode_count
        or modes[source_index].infoType != DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE
        or modes[target_index].infoType != DISPLAYCONFIG_MODE_INFO_TYPE_TARGET
    ):
        raise ValueError("Missing source or target mode in display snapshot")
    return {
        "device_path": device_path,
        "group": group,
        "source_mode": _structure_to_dict(modes[source_index].sourceMode),
        "rotation": int(path.targetInfo.rotation),
        "scaling": int(path.targetInfo.scaling),
        "refresh_rate": _structure_to_dict(path.targetInfo.refreshRate),
        "scan_line_ordering": int(path.targetInfo.scanLineOrdering),
        "target_mode": _structure_to_dict(modes[target_index].targetMode),
    }


def _connected_display_paths():
    """Group connected targets by monitor device path and their available live sources."""
    paths, path_count, _, _ = _query_display_config(QDC_ALL_PATHS)
    target_names = {}
    monitor_targets = {}
    connected = {}
    for path in paths[:path_count]:
        if not path.targetInfo.targetAvailable:
            continue
        target = _display_key(path.targetInfo)
        if target not in target_names:
            name = _get_monitor_device_path(path.targetInfo).casefold()
            if name in monitor_targets and monitor_targets[name] != target:
                raise RuntimeError(f"Ambiguous monitor device path: {name}")
            target_names[target] = name
            monitor_targets[name] = target
        connected.setdefault(target_names[target], {})[_display_key(path.sourceInfo)] = path
    return connected


def _find_primary_source_path(paths, path_count, modes, mode_count, strict: bool = False):
    fallback = None

    for index in range(path_count):
        path = paths[index]
        if not path.flags & DISPLAYCONFIG_PATH_ACTIVE:
            continue

        source_index = int(path.sourceInfo.modeInfoIdx)
        if source_index >= mode_count:
            continue

        mode = modes[source_index]
        if mode.infoType != DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE:
            continue

        if fallback is None:
            fallback = (path, mode)

        if mode.sourceMode.position.x == 0 and mode.sourceMode.position.y == 0:
            return path, mode

    if fallback is not None and not strict:
        return fallback

    raise RuntimeError("Unable to locate the primary display source mode.")


def capture_display_config():
    """Save monitor identities and settings, without persisting Windows session IDs."""
    paths, path_count, modes, mode_count = _query_active_display_config()
    groups = {}
    monitors = []
    for path in paths[:path_count]:
        group = groups.setdefault(_display_key(path.sourceInfo), len(groups))
        monitors.append(
            _monitor_settings(
                path,
                modes,
                mode_count,
                _get_monitor_device_path(path.targetInfo),
                group,
            )
        )
    if not monitors:
        raise RuntimeError("No active monitors were found to save.")
    return {"version": 1, "monitors": monitors}


def _legacy_monitor_settings(snapshot: dict, connected: dict):
    """Recover an old single-monitor backup using settings only, never its saved IDs."""
    if len(snapshot["paths"]) != 1 or len(connected) != 1:
        raise RuntimeError("This older development backup has no monitor identities. Automatic recovery requires one saved monitor and one connected monitor. The backup has been kept.")
    records = []
    for key, record_type in (
        ("paths", DISPLAYCONFIG_PATH_INFO),
        ("modes", DISPLAYCONFIG_MODE_INFO),
    ):
        decoded = [bytes.fromhex(value) for value in snapshot[key]]
        if any(len(value) != ctypes.sizeof(record_type) for value in decoded):
            raise ValueError("Unexpected display record size")
        records.append((record_type * len(decoded))(*(record_type.from_buffer_copy(value) for value in decoded)))
    paths, modes = records
    return [_monitor_settings(paths[0], modes, len(modes), next(iter(connected)), 0)]


def _assign_desktop_sources(candidates: dict):
    """Match each desktop group to a distinct live source, allowing clone members to share."""
    owners = {}

    def assign(group: int, visited: set):
        """Find a free source, relocating an earlier desktop assignment when needed."""
        for source in candidates[group]:
            if source in visited:
                continue
            visited.add(source)
            if source not in owners or assign(owners[source], visited):
                owners[source] = group
                return True
        return False

    for group in sorted(candidates, key=lambda key: len(candidates[key])):
        if not assign(group, set()):
            raise RuntimeError("The saved desktop layout has no available display connections.")
    return {group: source for source, group in owners.items()}


def _build_display_config(monitors: list, connected: dict):
    """Build fresh native paths from monitor identity and saved mode payloads."""
    groups = {}
    candidates = {}
    names = set()
    for monitor in monitors:
        if not isinstance(monitor, dict) or not isinstance(monitor["device_path"], str):
            raise ValueError("Missing or invalid monitor device path")
        name = monitor["device_path"].casefold()
        group = monitor["group"]
        if not name or name in names or type(group) is not int or group < 0:
            raise ValueError("Duplicate monitor identity or invalid desktop group")
        names.add(name)
        if name not in connected:
            raise RuntimeError(f"Saved monitor is not connected or its device path changed: {name}")
        source = _structure_from_dict(DISPLAYCONFIG_SOURCE_MODE, monitor["source_mode"])
        if source.width == 0 or source.height == 0:
            raise ValueError("Saved display resolution must be positive")
        if group in groups:
            if bytes(groups[group]) != bytes(source):
                raise ValueError("Duplicated monitors have conflicting desktop settings")
            candidates[group] = [key for key in candidates[group] if key in connected[name]]
        else:
            groups[group] = source
            candidates[group] = list(connected[name])
    if sum(mode.position.x == 0 and mode.position.y == 0 for mode in groups.values()) != 1:
        raise ValueError("Saved layout must have one primary desktop at (0, 0)")
    assignments = _assign_desktop_sources(candidates)
    source_indices = {group: index for index, group in enumerate(groups)}
    paths = (DISPLAYCONFIG_PATH_INFO * len(monitors))()
    modes = (DISPLAYCONFIG_MODE_INFO * (len(groups) + len(monitors)))()
    for index, monitor in enumerate(monitors):
        group = monitor["group"]
        live = connected[monitor["device_path"].casefold()][assignments[group]]
        path = paths[index]
        # Only use identities and connection type from today's query. Inactive
        # paths have no valid mode data, so rebuild every mode from saved settings.
        path.flags = DISPLAYCONFIG_PATH_ACTIVE
        path.sourceInfo.adapterId = live.sourceInfo.adapterId
        path.sourceInfo.id = live.sourceInfo.id
        path.sourceInfo.modeInfoIdx = source_indices[group]
        path.targetInfo.adapterId = live.targetInfo.adapterId
        path.targetInfo.id = live.targetInfo.id
        path.targetInfo.outputTechnology = live.targetInfo.outputTechnology
        path.targetInfo.targetAvailable = live.targetInfo.targetAvailable
        path.targetInfo.modeInfoIdx = len(groups) + index
        for key, field in (
            ("rotation", "rotation"),
            ("scaling", "scaling"),
            ("scan_line_ordering", "scanLineOrdering"),
        ):
            value = monitor[key]
            if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
                raise ValueError(f"Invalid display mode value: {key}")
            setattr(path.targetInfo, field, value)
        path.targetInfo.refreshRate = _structure_from_dict(DISPLAYCONFIG_RATIONAL, monitor["refresh_rate"])
        source_mode = modes[path.sourceInfo.modeInfoIdx]
        source_mode.infoType = DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE
        source_mode.adapterId = live.sourceInfo.adapterId
        source_mode.id = live.sourceInfo.id
        source_mode.sourceMode = groups[group]
        target_mode = modes[path.targetInfo.modeInfoIdx]
        target_mode.infoType = DISPLAYCONFIG_MODE_INFO_TYPE_TARGET
        target_mode.adapterId = live.targetInfo.adapterId
        target_mode.id = live.targetInfo.id
        target_mode.targetMode = _structure_from_dict(DISPLAYCONFIG_TARGET_MODE, monitor["target_mode"])
    return paths, modes


def restore_display_config(snapshot: dict):
    """Resolve saved monitors against live connections, validate, then restore their layout."""
    try:
        if snapshot["version"] != 1:
            raise ValueError("Unsupported display snapshot version")
        connected = _connected_display_paths()
        monitors = snapshot.get("monitors")
        if "monitors" not in snapshot:
            monitors = _legacy_monitor_settings(snapshot, connected)
        if not isinstance(monitors, list) or not monitors:
            raise ValueError("Empty or invalid monitor list")
        paths, modes = _build_display_config(monitors, connected)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid saved display configuration: {exc}") from exc

    for action, flag in (("validate", SDC_VALIDATE), ("restore", SDC_APPLY)):
        result = ctypes.windll.user32.SetDisplayConfig(
            len(paths),
            paths,
            len(modes),
            modes,
            flag | SDC_USE_SUPPLIED_DISPLAY_CONFIG,
        )
        if result != ERROR_SUCCESS:
            raise RuntimeError(f"Unable to {action} the saved monitor layout. Windows result: {result}")


def keep_primary_display_only():
    """Disable other active targets, retaining the first target of the primary source."""
    paths, path_count, modes, mode_count = _query_active_display_config()
    primary, _ = _find_primary_source_path(paths, path_count, modes, mode_count, strict=True)
    if path_count == 1:
        return

    selected = (DISPLAYCONFIG_PATH_INFO * 1)(primary)
    result = ctypes.windll.user32.SetDisplayConfig(
        1,
        selected,
        mode_count,
        modes,
        SDC_APPLY | SDC_USE_SUPPLIED_DISPLAY_CONFIG,
    )
    if result != ERROR_SUCCESS:
        raise RuntimeError(f"Unable to disable secondary monitors. Windows result: {result}")

    active_paths, active_count, active_modes, active_mode_count = _query_active_display_config()
    active, _ = _find_primary_source_path(active_paths, active_count, active_modes, active_mode_count, strict=True)
    expected = primary.targetInfo
    actual = active.targetInfo
    if active_count != 1 or (
        actual.adapterId.LowPart,
        actual.adapterId.HighPart,
        actual.id,
    ) != (expected.adapterId.LowPart, expected.adapterId.HighPart, expected.id):
        raise RuntimeError("Windows did not leave only the selected primary monitor active.")


def get_current_display_mode():
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Display mode changes are only supported on Windows.")

    mode = DEVMODEW()
    mode.dmSize = ctypes.sizeof(DEVMODEW)
    if not ctypes.windll.user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(mode)):
        raise RuntimeError("Unable to read the current display mode.")
    return DisplayMode(
        width=int(mode.dmPelsWidth),
        height=int(mode.dmPelsHeight),
        frequency=int(mode.dmDisplayFrequency),
    )


def apply_display_mode(display_mode):
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Display mode changes are only supported on Windows.")

    paths, path_count, modes, mode_count = _query_active_display_config()
    path, source_mode_info = _find_primary_source_path(
        paths,
        path_count,
        modes,
        mode_count,
    )

    source_mode_info.sourceMode.width = int(display_mode.width)
    source_mode_info.sourceMode.height = int(display_mode.height)
    path.targetInfo.scaling = DISPLAYCONFIG_SCALING_ASPECTRATIOCENTEREDMAX

    flags = SDC_APPLY | SDC_USE_SUPPLIED_DISPLAY_CONFIG | SDC_ALLOW_CHANGES | SDC_NO_OPTIMIZATION
    result = ctypes.windll.user32.SetDisplayConfig(
        path_count,
        paths,
        mode_count,
        modes,
        flags,
    )
    if result != ERROR_SUCCESS:
        raise RuntimeError(f"Unable to change display mode. Windows result: {result}")


def get_screen_roi(start_x, start_y, width, height):
    region = {"top": start_y, "left": start_x, "width": width, "height": height}
    with mss.mss() as sct:
        screenshot = sct.grab(region)
        return np.array(screenshot)


if __name__ == "__main__":
    pass
