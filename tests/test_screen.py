import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from source.utility import screen


def _user32_with_windows(windows):
    user32 = SimpleNamespace()
    titles = {hwnd: title for hwnd, title, _visible in windows}
    visible = {hwnd: is_visible for hwnd, _title, is_visible in windows}
    user32.FindWindowW = Mock(return_value=0)
    user32.IsWindowVisible = Mock(side_effect=lambda hwnd: visible.get(hwnd, False))
    user32.GetWindowTextLengthW = Mock(side_effect=lambda hwnd: len(titles.get(hwnd, "")))

    def get_window_text(hwnd: int, buffer: object, _max_count: int) -> int:
        buffer.value = titles.get(hwnd, "")
        return len(buffer.value)

    def enum_windows(callback: object, lparam: int) -> bool:
        for hwnd, _title, _visible in windows:
            if not callback(hwnd, lparam):
                break
        return True

    user32.GetWindowTextW = Mock(side_effect=get_window_text)
    user32.EnumWindows = Mock(side_effect=enum_windows)
    return user32


class ScreenTests(unittest.TestCase):
    def test_import_does_not_query_ark_window(self) -> None:
        with patch.object(screen.ctypes.windll.user32, "FindWindowW") as find_window:
            imported = importlib.reload(screen)

        find_window.assert_not_called()
        self.assertEqual(
            imported.mon,
            {"top": 0, "left": 0, "width": 1920, "height": 1080},
        )

    def test_find_screen_size_returns_none_for_missing_window(self) -> None:
        user32 = SimpleNamespace(
            FindWindowW=Mock(return_value=0),
            GetWindowRect=Mock(),
        )

        with patch.object(
            screen.ctypes,
            "windll",
            SimpleNamespace(user32=user32),
        ):
            self.assertIsNone(screen.find_screen_size())

        user32.GetWindowRect.assert_not_called()

    def test_find_screen_size_returns_none_for_failed_rectangle(self) -> None:
        user32 = SimpleNamespace(
            FindWindowW=Mock(return_value=123),
            GetWindowRect=Mock(return_value=False),
        )

        with patch.object(
            screen.ctypes,
            "windll",
            SimpleNamespace(user32=user32),
        ):
            self.assertIsNone(screen.find_screen_size())

        user32.GetWindowRect.assert_called_once()

    def test_find_screen_size_returns_window_dimensions(self) -> None:
        def set_window_rectangle(_hwnd: int, rect_pointer: object) -> bool:
            rect_pointer._obj.left = 100
            rect_pointer._obj.top = 200
            rect_pointer._obj.right = 2020
            rect_pointer._obj.bottom = 1280
            return True

        user32 = SimpleNamespace(
            FindWindowW=Mock(return_value=123),
            GetWindowRect=Mock(side_effect=set_window_rectangle),
        )

        with patch.object(
            screen.ctypes,
            "windll",
            SimpleNamespace(user32=user32),
        ):
            self.assertEqual(screen.find_screen_size(), (1920, 1080))

    def test_find_screen_size_accepts_ark_title_containing_configured_title(self) -> None:
        def set_window_rectangle(_hwnd: int, rect_pointer: object) -> bool:
            rect_pointer._obj.left = 100
            rect_pointer._obj.top = 200
            rect_pointer._obj.right = 2020
            rect_pointer._obj.bottom = 1280
            return True

        user32 = _user32_with_windows(
            [
                (111, "Other Window", True),
                (222, "ArkAscended - Build 123", True),
            ]
        )
        user32.GetWindowRect = Mock(side_effect=set_window_rectangle)

        with patch.object(
            screen.ctypes,
            "windll",
            SimpleNamespace(user32=user32),
        ):
            self.assertEqual(screen.find_screen_size(), (1920, 1080))

        user32.GetWindowRect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
