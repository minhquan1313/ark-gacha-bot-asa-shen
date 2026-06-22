import importlib.util
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import call, patch


def _load_console_module() -> ModuleType:
    """Load console.py without importing its application dependency graph."""
    module_path = Path(__file__).parents[1] / "source" / "ASA" / "player" / "console.py"
    spec = importlib.util.spec_from_file_location(
        "console_clipboard_under_test", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load console module for testing.")

    module = importlib.util.module_from_spec(spec)
    player = SimpleNamespace(player_state=SimpleNamespace(reset_state=lambda: None))
    logs = SimpleNamespace(gachalogs=SimpleNamespace(logger=unittest.mock.Mock()))
    utility = SimpleNamespace(template=unittest.mock.Mock(), utils=unittest.mock.Mock())
    with patch.dict(
        "sys.modules",
        {
            "source.ASA.player": player,
            "source.logs": logs,
            "source.utility": utility,
        },
    ):
        spec.loader.exec_module(module)
    return module


console = _load_console_module()


class ClipboardAccessTests(unittest.TestCase):
    def test_open_clipboard_retries_and_only_closes_after_success(self) -> None:
        contention = OSError("clipboard busy")
        with (
            patch.object(
                console.win32clipboard,
                "OpenClipboard",
                side_effect=[contention, contention, None],
            ) as open_clipboard,
            patch.object(console.win32clipboard, "CloseClipboard") as close_clipboard,
            patch.object(console.time, "sleep") as sleep,
        ):
            with console._open_clipboard():
                pass

        self.assertEqual(open_clipboard.call_count, 3)
        self.assertEqual(
            sleep.call_args_list,
            [
                call(console._clipboard_retry_delay),
                call(console._clipboard_retry_delay),
            ],
        )
        close_clipboard.assert_called_once_with()

    def test_open_clipboard_does_not_close_when_all_attempts_fail(self) -> None:
        with (
            patch.object(
                console.win32clipboard,
                "OpenClipboard",
                side_effect=OSError("clipboard busy"),
            ) as open_clipboard,
            patch.object(console.win32clipboard, "CloseClipboard") as close_clipboard,
            patch.object(console.time, "sleep"),
        ):
            with self.assertRaisesRegex(OSError, "clipboard busy"):
                with console._open_clipboard():
                    pass

        self.assertEqual(open_clipboard.call_count, console._clipboard_open_attempts)
        close_clipboard.assert_not_called()

    def test_enter_data_does_not_paste_stale_data_after_clipboard_failure(self) -> None:
        with (
            patch.object(
                console, "_open_clipboard", side_effect=OSError("clipboard busy")
            ),
            patch.object(console.pyautogui, "hotkey") as hotkey,
            patch.object(console.logs.logger, "warning") as warning,
        ):
            result = console.enter_data("ccc")

        self.assertFalse(result)
        hotkey.assert_not_called()
        warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
