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
QDC_ONLY_ACTIVE_PATHS = 0x00000002
SDC_USE_SUPPLIED_DISPLAY_CONFIG = 0x00000020
SDC_APPLY = 0x00000080
SDC_NO_OPTIMIZATION = 0x00000100
SDC_ALLOW_CHANGES = 0x00000400
DISPLAYCONFIG_PATH_ACTIVE = 0x00000001
DISPLAYCONFIG_SCALING_ASPECTRATIOCENTEREDMAX = 4
DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE = 1


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


def _query_active_display_config():
    user32 = ctypes.windll.user32

    for _ in range(5):
        path_count = ctypes.c_uint32()
        mode_count = ctypes.c_uint32()
        result = user32.GetDisplayConfigBufferSizes(
            QDC_ONLY_ACTIVE_PATHS,
            ctypes.byref(path_count),
            ctypes.byref(mode_count),
        )
        if result != ERROR_SUCCESS:
            raise RuntimeError(
                f"Unable to size the active display configuration. Windows result: {result}"
            )

        paths = (DISPLAYCONFIG_PATH_INFO * path_count.value)()
        modes = (DISPLAYCONFIG_MODE_INFO * mode_count.value)()
        result = user32.QueryDisplayConfig(
            QDC_ONLY_ACTIVE_PATHS,
            ctypes.byref(path_count),
            paths,
            ctypes.byref(mode_count),
            modes,
            None,
        )
        if result == ERROR_SUCCESS:
            return paths, path_count.value, modes, mode_count.value
        if result != ERROR_INSUFFICIENT_BUFFER:
            raise RuntimeError(
                f"Unable to query the active display configuration. Windows result: {result}"
            )

    raise RuntimeError(
        "The display configuration changed repeatedly while being queried."
    )


def _find_primary_source_path(paths, path_count, modes, mode_count):
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

    if fallback is not None:
        return fallback

    raise RuntimeError("Unable to locate an active display source mode.")


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

    flags = (
        SDC_APPLY
        | SDC_USE_SUPPLIED_DISPLAY_CONFIG
        | SDC_ALLOW_CHANGES
        | SDC_NO_OPTIMIZATION
    )
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
