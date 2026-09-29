"""Behavior and layout checks for the dashboard-only redesign."""

import copy
import os
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from source.launcher.components.dashboard import DashboardConsole
from source.launcher.components.gallery import CoverGallery
from source.launcher.config.constants import DEFAULT_SETTINGS, MAX_LAUNCHER_LOG_LINES
from source.launcher.gui import SettingsGUI
from source.launcher.gui_parts.logs import LogsGuiMixin


class DashboardRedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "consola.ttf"):
            path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))

    def window(self, callbacks: tuple[str, ...] = ()):
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        settings["server_number"] = "5147"
        patches = [
            patch.object(SettingsGUI, "_finish_startup"),
            patch.object(
                SettingsGUI, "persist_settings_from_visible_fields", return_value=False
            ),
            patch.object(SettingsGUI, "_automatic_update_check"),
            patch.object(SettingsGUI, "_start_update_check"),
            patch.object(CoverGallery, "run_work"),
            patch("source.launcher.gui.load_settings", return_value=settings),
        ]
        patches.extend(patch.object(SettingsGUI, name) for name in callbacks)
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        window = SettingsGUI()
        self.addCleanup(window.close)
        window.show_page("dashboard")
        window.show()
        QTest.qWait(40)
        return window

    def test_reference_geometry_and_compact_reflow(self):
        window = self.window()
        for width, height in ((1200, 800), (1536, 1024), (900, 800), (1200, 800)):
            window.resize(width, height)
            QTest.qWait(40)
            viewport = window.pages["dashboard"].viewport()
            self.assertLessEqual(window.dashboard_content.width(), viewport.width())
            if width >= 1200:
                cards = window.dashboard_stat_cards
                self.assertLessEqual(
                    max(c.width() for c in cards) - min(c.width() for c in cards), 1
                )
                self.assertEqual(len({c.y() for c in cards}), 1)
                self.assertAlmostEqual(
                    window.dashboard_actions_card.width()
                    / window.dashboard_console_panel.width(),
                    26 / 74,
                    delta=0.025,
                )
                self.assertEqual(
                    window.pages["dashboard"].verticalScrollBar().maximum(), 0
                )
            else:
                self.assertGreater(
                    window.dashboard_console_panel.y(),
                    window.dashboard_actions_card.y(),
                )

    def test_click_connections_and_conditional_restore(self):
        window = self.window(
            (
                "toggle_program",
                "start_game",
                "start_game_with_display_settings",
                "restore_game_settings",
                "clear_game_restore_settings",
                "clear_logs",
            )
        )
        window.start_stop_button.click()
        window.toggle_program.assert_called_once()
        window.start_game_button.setVisible(True)
        window.start_game_button.click()
        window.start_game.assert_called_once()
        window.start_game_button.customContextMenuRequested.emit(QPoint())
        window.start_game_with_display_settings.assert_called_once()
        with patch(
            "source.launcher.gui_parts.settings_state.ark_game_setup.restore_state_exists",
            return_value=False,
        ):
            window._update_game_restore_button_visibility()
            self.assertTrue(window.restore_game_settings_button.isHidden())
        with patch(
            "source.launcher.gui_parts.settings_state.ark_game_setup.restore_state_exists",
            return_value=True,
        ):
            window._update_game_restore_button_visibility()
            self.assertFalse(window.restore_game_settings_button.isHidden())
            window.restore_game_settings_button.click()
            window.restore_game_settings_button.customContextMenuRequested.emit(
                QPoint()
            )
        window.restore_game_settings.assert_called_once()
        window.clear_game_restore_settings.assert_called_once()
        window.dashboard_clear_button.click()
        window.clear_logs.assert_called_once()
        self.assertIn("Shift + Alt + N", window.start_stop_button.toolTip())
        self.assertIn("primary monitor", window.start_game_button.toolTip())
        self.assertIn("Right-click", window.restore_game_settings_button.toolTip())

    def test_runner_button_states_and_navigation(self):
        window = self.window()
        window.program_stopping = True
        window._update_start_stop_button()
        self.assertEqual(window.start_stop_button.text(), "STOPPING...")
        self.assertFalse(window.start_stop_button.isEnabled())
        window.program_stopping = False
        window.runner_loading = True
        window._update_start_stop_button()
        self.assertEqual(window.start_stop_button.variant, "danger")
        window.runner_loading = False
        window._update_start_stop_button()
        self.assertEqual(window.start_stop_button.text(), "START GBOT")
        for name, button in window.nav_buttons.items():
            button.click()
            self.assertIs(window.stack.currentWidget(), window.pages[name])
            self.assertTrue(button.isChecked())
            if name != "dashboard":
                self.assertNotIn("DashboardPage", window.pages[name].styleSheet())

    def test_auto_start_persistence_and_server_gate(self):
        window = self.window()
        with patch("source.launcher.gui_parts.settings_state.save_settings") as save:
            self.assertFalse(hasattr(window, "auto_start_switch"))
            window.toggle_auto_start_program(True)
            self.assertTrue(window.settings["auto_start_program"])
            self.assertTrue(window.form_values["auto_start_program"])
            save.assert_called_once()
        window.settings["server_number"] = "0"
        window._update_auto_start_switch()
        self.assertFalse(window._is_auto_start_allowed())
        self.assertFalse(hasattr(window, "auto_start_hint"))

    def test_real_metrics_and_readiness(self):
        window = self.window()
        window.queue_snapshot = {
            "running": [{"name": "one"}],
            "active": [{"name": "two"}],
            "waiting": [{"name": "three"}],
        }
        with patch(
            "source.launcher.gui_parts.runtime.find_window_size", return_value=None
        ):
            window._tick()
        self.assertEqual(window.server_value.text(), "5147")
        self.assertEqual(window.active_value.text(), "2")
        self.assertEqual(window.waiting_value.text(), "1")
        self.assertIn("ARK NOT FOUND", window.dashboard_hero.status_label.text())
        self.assertEqual(
            window.memory_percent_value.text(), f"{window.memory_meter.percent}%"
        )

    def test_worker_log_burst_is_coalesced_and_shutdown_is_safe(self):
        window = self.window()
        QTest.qWait(40)
        heartbeat = []
        with patch.object(
            window.dashboard_log,
            "update_records",
            wraps=window.dashboard_log.update_records,
        ) as update:
            worker = threading.Thread(
                target=lambda: [
                    window.log_bridge.line.emit(f"[INFO] record {i}\n")
                    for i in range(MAX_LAUNCHER_LOG_LINES + 10)
                ]
            )
            worker.start()
            worker.join()
            QTimer.singleShot(0, lambda: heartbeat.append(True))
            QTest.qWait(150)
            self.assertTrue(heartbeat)
            self.assertLessEqual(len(window.log_lines), MAX_LAUNCHER_LOG_LINES)
            self.assertEqual(len(window.dashboard_log.records), 18)
            self.assertIn("record 2009", window.dashboard_log.toPlainText())
            self.assertLess(update.call_count, 10)
        window.append_log("[INFO] pending at close\n")
        window.close()
        QTest.qWait(40)
        self.assertTrue(window.shutdown_started)


class IncrementalDashboardConsoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.console = DashboardConsole()
        self.console.resize(300, 110)
        self.console.show()
        self.addCleanup(self.console.close)
        self.formatter = lambda lines: "<br>".join(
            LogsGuiMixin._escape(line) for line in lines
        )

    def update(self, records: list[str]):
        self.console.update_records(records, self.formatter)
        QApplication.processEvents()

    def test_multiline_trimming_filter_reset_and_literal_html(self):
        self.update(["one\ntwo\n", "keep <tag> & value\n"])
        self.update(["keep <tag> & value\n", "new\nlast\n"])
        self.assertEqual(self.console.toPlainText(), "keep <tag> & value\nnew\nlast")
        self.update(["[QUEUE] ready\n"])
        self.assertEqual(self.console.toPlainText(), "[QUEUE] ready")
        self.update([])
        self.assertEqual(self.console.toPlainText(), "")

    def test_append_keeps_selection_and_manual_scroll(self):
        self.update([f"line {i}" for i in range(18)])
        self.console.set_auto_scroll(False)
        cursor = self.console.textCursor()
        cursor.setPosition(7)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
        )
        self.console.setTextCursor(cursor)
        selected = cursor.selectedText()
        self.console.verticalScrollBar().setValue(0)
        with patch.object(self.console, "setHtml") as replace:
            self.update([f"line {i}" for i in range(1, 19)])
            replace.assert_not_called()
        self.assertEqual(self.console.textCursor().selectedText(), selected)
        self.assertEqual(self.console.verticalScrollBar().value(), 0)
        self.console.copy()
        self.assertEqual(QApplication.clipboard().text(), selected)
        self.console.set_auto_scroll(True)
        self.assertEqual(
            self.console.verticalScrollBar().value(),
            self.console.verticalScrollBar().maximum(),
        )
