"""Capture the real dashboard with automation and settings writes disabled.

Run from the repository root: python tests/dashboard_preview.py
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

from source.launcher.components.gallery import CoverGallery
from source.launcher.gui import SettingsGUI


def main():
    """Save review images using real local settings and system metric samples."""
    app = QApplication.instance() or QApplication([])
    # The offscreen Windows plugin does not discover system fonts itself.
    for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "consola.ttf"):
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    with (
        patch.object(SettingsGUI, "_finish_startup"),
        patch.object(
            SettingsGUI, "persist_settings_from_visible_fields", return_value=False
        ),
        patch.object(SettingsGUI, "_automatic_update_check"),
        patch.object(CoverGallery, "run_work"),
    ):
        window = SettingsGUI()
        window.load_previous_logs()
        output = ROOT / ".artifacts" / "dashboard"
        output.mkdir(parents=True, exist_ok=True)
        for width, height in ((1200, 800), (1536, 1024), (1920, 1080), (2560, 1440), (900, 800)):
            window.resize(width, height)
            window.show_page("dashboard")
            window.show()
            QTest.qWait(120)
            window._tick()
            QTest.qWait(60)
            suffix = os.environ.get("QT_SCALE_FACTOR", "1")
            platform = app.platformName()
            path = output / f"dashboard-{width}x{height}-scale{suffix}-{platform}.png"
            window.grab().save(str(path))
            print(path)
            print(
                "window",
                window.size().toTuple(),
                "sidebar",
                window.sidebar.width(),
                "hero",
                window.dashboard_hero.size().toTuple(),
                "stat",
                window.dashboard_server_card.size().toTuple(),
                "actions",
                window.dashboard_actions_card.size().toTuple(),
                "console",
                window.dashboard_console_panel.size().toTuple(),
            )
        if app.platformName() == "windows":
            window.resize(1200, 800)
            QTest.qWait(40)
            geometry = window.geometry()
            window.title_bar.maximize_button.click()
            QTest.qWait(40)
            assert window.is_custom_maximized
            assert window.geometry() == window.screen().availableGeometry()
            window.title_bar.maximize_button.click()
            QTest.qWait(40)
            assert window.geometry() == geometry
            QTest.mouseDClick(window.title_bar, Qt.MouseButton.LeftButton, pos=QPoint(300, 20))
            assert window.is_custom_maximized
            window.title_bar.maximize_button.click()
            window.title_bar.minimize_button.click()
            QTest.qWait(40)
            assert window.isMinimized()
            window.showNormal()
            QTest.qWait(40)
            assert not window.isMinimized()
            assert window._resize_hit_test(QPoint(1, 1)) is not None
            assert window._resize_hit_test(QPoint(window.width() - 1, window.height() - 1)) is not None
            print("Native maximize/work area, restore, double-click, minimize, and resize hit tests passed.")
        window.close()
        app.processEvents()


if __name__ == "__main__":
    main()
