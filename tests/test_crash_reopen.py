import importlib
import sys
import types
import unittest
from unittest.mock import Mock, call, patch


def _module(name: str, **attributes: object) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


class _Process:
    def __init__(self, _pid: int = 0) -> None:
        self.info = {"name": ""}

    def terminate(self) -> None:
        return None


psutil_module = _module(
    "psutil",
    Process=_Process,
    NoSuchProcess=type("NoSuchProcess", (Exception,), {}),
    AccessDenied=type("AccessDenied", (Exception,), {}),
    process_iter=Mock(return_value=[]),
)
pyautogui_module = _module("pyautogui", click=Mock())
win32process_module = _module(
    "win32process", GetWindowThreadProcessId=Mock(return_value=(0, 0))
)
logger_module = _module(
    "source.join_sim.source.logs.logger",
    logger=types.SimpleNamespace(critical=Mock(), warning=Mock()),
)
ark_setup_module = _module(
    "source.launcher.ark_game_setup",
    ARK_PROCESS_NAME="ArkAscended.exe",
    kill_running_ark=Mock(),
    launch_ark_through_steam=Mock(),
)
system_module = _module("source.launcher.utils.system", validate_ark_window=Mock())
capture_module = _module(
    "source.launcher.utils.deposit_helper_capture", focus_game_window=Mock()
)
windows_module = _module("source.utility.windows", ark_hwnd=Mock(return_value=0))

sys.modules.pop("source.join_sim.source.crash.crash", None)
with patch.dict(
    sys.modules,
    {
        "psutil": psutil_module,
        "pyautogui": pyautogui_module,
        "win32process": win32process_module,
        "source.join_sim.source.logs.logger": logger_module,
        "source.launcher.ark_game_setup": ark_setup_module,
        "source.launcher.utils.system": system_module,
        "source.launcher.utils.deposit_helper_capture": capture_module,
        "source.utility.windows": windows_module,
    },
):
    crash = importlib.import_module("source.join_sim.source.crash.crash")


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: int | float) -> None:
        self.value += float(seconds)


class CrashReopenTests(unittest.TestCase):
    def test_wait_for_usable_window_validates_focuses_and_clicks_center(self):
        clock = FakeClock()
        with (
            patch.object(crash.time, "monotonic", side_effect=clock.now),
            patch.object(crash.time, "sleep", side_effect=clock.sleep),
            patch.object(crash, "_process_running", return_value=True),
            patch.object(crash.system, "validate_ark_window", return_value=(1920, 1080)),
            patch.object(crash, "focus_game_window") as focus,
            patch.object(crash.pyautogui, "click") as click,
        ):
            crash._wait_for_usable_ark_window(10)

        focus.assert_called_once_with(center_cursor_when_switching=True)
        click.assert_called_once_with(960, 540)

    def test_reopen_retries_full_sequence_until_window_is_usable(self):
        events = []
        wait = Mock(
            side_effect=[RuntimeError("window unavailable"), None]
        )

        with (
            patch.object(crash, "close_game", side_effect=lambda: events.append("close")),
            patch.object(
                crash.ark_game_setup,
                "kill_running_ark",
                side_effect=lambda: events.append("kill"),
            ),
            patch.object(
                crash.ark_game_setup,
                "launch_ark_through_steam",
                side_effect=lambda: events.append("launch"),
            ),
            patch.object(crash.time, "sleep", side_effect=lambda _seconds: events.append("delay")),
            patch.object(crash, "_wait_for_usable_ark_window", wait),
            patch.object(crash.logs.logger, "warning") as warning,
        ):
            crash.re_open_game()

        self.assertEqual(
            events,
            ["close", "kill", "delay", "launch"] * 2,
        )
        self.assertEqual(
            wait.call_args_list,
            [
                call(crash.ARK_WINDOW_READY_TIMEOUT_SECONDS),
                call(crash.ARK_WINDOW_READY_TIMEOUT_SECONDS),
            ],
        )
        warning.assert_called_once_with(
            "ARK reopen attempt 1 failed: window unavailable"
        )

    def test_launch_exception_is_reported_and_retried(self):
        launch = Mock(side_effect=[OSError("Steam unavailable"), None])

        with (
            patch.object(crash, "close_game"),
            patch.object(crash.ark_game_setup, "kill_running_ark"),
            patch.object(crash.ark_game_setup, "launch_ark_through_steam", launch),
            patch.object(crash.time, "sleep"),
            patch.object(crash, "_wait_for_usable_ark_window") as wait,
            patch.object(crash.logs.logger, "warning") as warning,
        ):
            crash.re_open_game()

        self.assertEqual(launch.call_count, 2)
        wait.assert_called_once_with(crash.ARK_WINDOW_READY_TIMEOUT_SECONDS)
        warning.assert_called_once_with(
            "ARK reopen attempt 1 failed: Steam unavailable"
        )


if __name__ == "__main__":
    unittest.main()
