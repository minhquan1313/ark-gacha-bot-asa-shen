"""Capture approved Settings pages without starting automation or saving edits."""

# ruff: noqa: E402

import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from source.launcher.components.gallery import CoverGallery
from source.launcher.components.settings_sections import SettingsSectionHeader
from source.launcher.gui import SettingsGUI


def main():
    """Save native or offscreen screenshots using real persisted field values."""
    app = QApplication.instance() or QApplication([])
    for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "consola.ttf"):
        path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))
    with (
        patch.object(SettingsGUI, "_finish_startup"),
        patch.object(
            SettingsGUI, "persist_settings_from_visible_fields", return_value=False
        ),
        patch.object(SettingsGUI, "_automatic_update_check"),
        patch.object(CoverGallery, "run_work"),
    ):
        window = SettingsGUI()
        output = ROOT / ".artifacts" / "settings"
        output.mkdir(parents=True, exist_ok=True)
        window.show_page("settings")
        window.show()
        for width, height in ((1200, 800), (1536, 1024), (1920, 1080), (2560, 1440)):
            window.resize(width, height)
            for group in ("SERVER", "STATIONS"):
                window._render_settings_group(group)
                window.settings_form_area.verticalScrollBar().setValue(0)
                QTest.qWait(140)
                suffix = (
                    f"{os.environ.get('QT_SCALE_FACTOR', '1')}-{app.platformName()}"
                )
                path = output / f"{group.lower()}-{width}x{height}-{suffix}.png"
                window.grab().save(str(path))
                headers = window.settings_form.findChildren(SettingsSectionHeader)
                print(
                    path.name,
                    "headers",
                    [h.height() for h in headers],
                    "scroll",
                    window.settings_form_area.verticalScrollBar().maximum(),
                )
                if (
                    group == "STATIONS"
                    and window.settings_form_area.verticalScrollBar().maximum()
                ):
                    window.settings_form_area.verticalScrollBar().setValue(
                        window.settings_form_area.verticalScrollBar().maximum()
                    )
                    QTest.qWait(40)
                    window.grab().save(str(path.with_stem(path.stem + "-bottom")))
        window.close()
        app.processEvents()


if __name__ == "__main__":
    main()
