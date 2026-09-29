"""Isolated Logs design preview; generated records never reach application log files.

Run: venv/Scripts/python.exe tests/logs_preview.py
Use --interactive to inspect the real shell with temporary sample logs.
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if "--interactive" not in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from source.launcher.gui import SettingsGUI
from source.launcher.components.gallery import CoverGallery
from logs_sample_data import sample_lines


def main():
    """Capture the actual page using only a temporary preview-data file."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "consola.ttf"):
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    with (
        tempfile.TemporaryDirectory() as directory,
        patch.object(SettingsGUI, "_finish_startup"),
        patch.object(SettingsGUI, "persist_settings_from_visible_fields", return_value=False),
        patch.object(SettingsGUI, "_automatic_update_check"),
        patch.object(CoverGallery, "run_work"),
    ):
        window = SettingsGUI()
        page = window.logs_page
        path = Path(directory) / "preview-only.log"
        path.write_text("".join(sample_lines(6500)), encoding="utf-8")
        page.store.path = path
        # Clear/Open in this preview are scoped to the temporary file, never the real one.
        page.clear_button.clicked.disconnect()
        page.clear_button.clicked.connect(lambda: (path.write_text("", encoding="utf-8"), page.store.reload()))
        page.open_button.clicked.disconnect()
        page.open_button.clicked.connect(lambda: window.dialog("Design preview", "This preview uses a temporary sample log file.", "info"))
        window.queue_snapshot = {"running": [{"name": "Craft.GACHA"}], "active": [{"name": "Gacha.LEFT"}], "waiting": [{"name": "Pego"}] * 12}
        window.show_page("logs")
        window.show()
        page.store.start()
        if args.interactive:
            QTimer.singleShot(100, page.tick)
            app.exec()
        else:
            for _ in range(100):
                if page.store.ready:
                    break
                QTest.qWait(20)
            output = ROOT / ".artifacts/logs"
            output.mkdir(parents=True, exist_ok=True)
            scale = os.environ.get("QT_SCALE_FACTOR", "1")
            for width, height in ((1200, 800), (1536, 1024)):
                window.resize(width, height)
                QTest.qWait(100)
                page.tick()
                page.switches["Auto-scroll"].setChecked(True)
                page.table.scrollToBottom()
                QTest.qWait(40)
                window.grab().save(str(output / f"logs-{width}x{height}-{scale}.png"))
            window.resize(1200, 800)
            page.switches["Auto-scroll"].setChecked(False)
            page.table.scrollTo(page.model.index(20, 0), page.table.ScrollHint.PositionAtTop)
            page.store.older()
            QTest.qWait(220)
            window.grab().save(str(output / f"logs-history-{scale}.png"))
            page.filters.more.showMenu()
            QTest.qWait(60)
            window.grab().save(str(output / f"logs-filters-{scale}.png"))
            page.filters.menu.hide()
            page.search.setText("Event")
            QTest.qWait(270)
            window.grab().save(str(output / f"logs-search-{scale}.png"))
        window.close()
        app.processEvents()


if __name__ == "__main__":
    main()
