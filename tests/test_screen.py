import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from source.utility import screen


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


if __name__ == "__main__":
    unittest.main()
