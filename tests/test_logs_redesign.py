"""Model, history, search, and visual tests for the dedicated Logs page."""

import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from test_dashboard_redesign import DashboardRedesignTests
from source.launcher.utils.log_records import read_page, parse_record


from logs_sample_data import sample_lines


class LogReaderTests(unittest.TestCase):
    def test_reverse_paging_utf8_duplicates_and_multiline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "logs.txt"
            content = sample_lines(4200)
            content[2199] = "16:20:00 - ERROR - worker - Unicode: tiếng Việt 😀\nTraceback (most recent call last):\n  failure()\nValueError: broken\n"
            content[2200] = content[2201] = "16:20:01 - INFO - worker - duplicate\n"
            path.write_text("".join(content), encoding="utf-8")
            end = path.stat().st_size
            records, oldest = read_page(path, end, 1, threading.Event())
            self.assertEqual(len(records), 2000)
            self.assertEqual(records[0].message, "duplicate")
            self.assertNotEqual(records[0].identity, records[1].identity)
            older, boundary = read_page(path, oldest, 1, threading.Event())
            self.assertEqual(len(older), 2000)
            self.assertIn("ValueError: broken", older[-1].message)
            self.assertIn("tiếng Việt 😀", older[-1].message)
            first, start = read_page(path, boundary, 1, threading.Event())
            self.assertEqual(len(first), 200)
            self.assertEqual(start, 0)
            self.assertEqual(len({r.identity for r in first + older + records}), 4200)

    def test_unknown_text_and_severity_are_preserved(self):
        record = parse_record("16:25:55 - INFO - worker - no ERROR occurred", ("x", 1), (1, 0))
        self.assertEqual(record.level, "INFO")
        self.assertEqual(record.source, "worker")
        unknown = parse_record("unstructured text", ("x", 2), (2, 0))
        self.assertEqual(unknown.timestamp, "—")
        self.assertEqual(unknown.raw, "unstructured text")


class LogsPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        DashboardRedesignTests.setUpClass()

    def wait_for(self, predicate, timeout=5000):
        for _ in range(timeout // 20):
            if predicate():
                return
            QTest.qWait(20)
        self.fail("Timed out waiting for asynchronous Logs state")

    def window(self, count=4200):
        window = DashboardRedesignTests.window(self, ("clear_logs", "open_logs"))
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "logs.txt"
        path.write_text("".join(sample_lines(count)), encoding="utf-8")
        page = window.logs_page
        page.store.path = path
        window.show_page("logs")
        window.resize(1200, 800)
        page.store.start()
        self.wait_for(lambda: page.store.ready)
        return window, page, path

    def test_history_search_preserves_anchor_and_selection(self):
        window, page, path = self.window()
        self.assertEqual(len(page.browsing), 2000)
        page.switches["Auto-scroll"].setChecked(False)
        page.restoring = True
        page.table.scrollTo(page.model.index(10, 0), page.table.ScrollHint.PositionAtTop)
        page.restoring = False
        anchor = page._anchor()
        page.table.selectRow(10)
        selected = page.model.records[10].identity
        page.store.older()
        self.wait_for(lambda: len(page.browsing) == 4000)
        self.assertEqual(page._anchor(), anchor)
        self.assertEqual(page.model.records[page.table.selectionModel().selectedRows()[0].row()].identity, selected)
        page.search.setText("Event")
        QTest.qWait(210)
        anchor = page._anchor()
        self.wait_for(lambda: not page.searching and len(page.model.records) == 4200)
        self.assertEqual(page._anchor(), anchor)
        self.assertEqual(len(page.browsing), 4000)
        page.search.setText("Event 00001")
        self.wait_for(lambda: not page.searching and len(page.model.records) == 1)
        self.assertIn("00001", page.model.records[0].message)
        page.search.clear()
        QTest.qWait(260)
        self.assertEqual(page._anchor(), anchor)

    def test_pause_append_rotation_and_stale_search(self):
        window, page, path = self.window()
        page.switches["Live stream"].setChecked(False)
        with path.open("a", encoding="utf-8") as file:
            file.write("17:00:00 - ERROR - live - new arrival\n")
        page.store.refresh()
        self.wait_for(lambda: bool(page.pending))
        self.assertEqual(len(page.model.records), 2000)
        page.switches["Live stream"].setChecked(True)
        self.assertEqual(len(page.model.records), 2001)
        page.search.setText("Event")
        QTest.qWait(220)
        page.search.setText("new arrival")
        self.wait_for(lambda: not page.searching and len(page.model.records) == 1)
        self.assertEqual(page.model.records[0].message, "new arrival")
        path.write_text("18:00:00 - INFO - rotation - replaced\n", encoding="utf-8")
        page.store.refresh()
        self.wait_for(lambda: len(page.browsing) == 1 and next(iter(page.browsing.values())).message == "replaced")
        page.search.clear()
        QTest.qWait(260)
        self.assertEqual(len(page.model.records), 1)

    def test_filters_controls_geometry_and_captures(self):
        window, page, path = self.window(120)
        page.clear_button.click()
        window.clear_logs.assert_called_once()
        page.open_button.click()
        window.open_logs.assert_called_once()
        page.filters.choose("ERROR")
        self.assertTrue(all(r.level == "ERROR" for r in page.model.records))
        page.filters.choose("ALL")
        page.switches["Errors only"].setChecked(True)
        self.assertTrue(all(r.level in {"ERROR", "CRITICAL"} for r in page.model.records))
        page.switches["Errors only"].setChecked(False)
        page.switches["Compact mode"].setChecked(True)
        self.assertEqual(page.table.verticalHeader().defaultSectionSize(), 22)
        page.switches["Compact mode"].setChecked(False)
        QTest.keyClick(page, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(page.search.hasFocus())
        output = Path(".artifacts/logs")
        output.mkdir(parents=True, exist_ok=True)
        scale = os.environ.get("QT_SCALE_FACTOR", "1")
        for width, height in ((1200, 800), (1536, 1024)):
            window.resize(width, height)
            QTest.qWait(100)
            self.assertTrue(page.rect().contains(page.console.geometry()))
            self.assertEqual(page.table.horizontalScrollBar().maximum(), 0)
            self.assertTrue(page.filters.buttons["ALL"].isVisible())
            self.assertTrue(page.filters.buttons[page.filters.current].isVisible())
            window.grab().save(str(output / f"logs-{width}x{height}-{scale}.png"))
        window.resize(1200, 800)
        page.filters.choose("CRITICAL")
        QTest.qWait(50)
        self.assertTrue(page.filters.buttons["CRITICAL"].isVisible())
        self.assertTrue(page.filters.more.isVisible())
        self.assertTrue(page.filters.menu.actions())

    def test_queue_and_running_do_not_change_dashboard_filter(self):
        window, page, path = self.window(10)
        window.queue_snapshot = {"running": [{"name": "Craft.GACHA"}], "active": [], "waiting": [{"name": "Pego", "execution_time": 0}]}
        page.filters.choose("QUEUE")
        self.assertEqual(window.current_filter, "ALL")
        self.assertTrue(all(r.level == "QUEUE" for r in page.model.records))
        page.filters.choose("RUNNING")
        self.assertTrue(any("Craft.GACHA" in r.message for r in page.model.records))
        page.tick()
        self.assertEqual(page.metrics[3].value.text(), "1")
        self.assertEqual(page.metrics[4].value.text(), "1")

    def test_clear_cancels_search_and_file_errors_are_retryable(self):
        from unittest.mock import patch
        from source.launcher.gui_parts.logs import LogsGuiMixin

        window, page, path = self.window()
        page.search.setText("Event")
        QTest.qWait(210)
        with patch("source.launcher.gui_parts.logs.GACHA_LOG_FILE", str(path)):
            LogsGuiMixin.clear_logs(window)
        self.wait_for(lambda: page.store.ready and not page.store.busy)
        QTest.qWait(200)
        self.assertEqual(path.read_bytes(), b"")
        self.assertEqual(len(page.model.records), 0)
        self.assertEqual(len(page.browsing), 0)
        path.unlink()
        page.store.refresh()
        self.wait_for(lambda: "unavailable" in page.console.history.text())
        self.assertTrue(page.search.isEnabled())
        path.write_text("19:00:00 - INFO - retry - restored\n", encoding="utf-8")
        self.wait_for(lambda: len(page.browsing) == 1)
        with patch.object(Path, "open", side_effect=PermissionError("test permission denied")):
            page.store.refresh()
            self.wait_for(lambda: "permission denied" in page.console.history.text())
        self.assertEqual(len(page.browsing), 1)
        page.search.setText("restored")
        self.wait_for(lambda: len(page.model.records) == 1 and not page.searching)

    def test_burst_search_keeps_event_loop_responsive_and_copy_details(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QDialog, QTextEdit
        import time

        window, page, path = self.window()
        beats = []
        timer = QTimer(page)
        timer.setInterval(10)
        timer.timeout.connect(lambda: beats.append(time.monotonic()))
        timer.start()
        with path.open("a", encoding="utf-8") as file:
            file.writelines(sample_lines(5000))
        page.store.refresh()
        self.wait_for(lambda: len(page.browsing) == 7000, 10000)
        self.assertGreater(len(beats), 10)
        page.search.setText("Event")
        self.wait_for(lambda: len(page.model.records) == 9200 and not page.searching, 10000)
        self.assertLess(max(b - a for a, b in zip(beats, beats[1:])), 0.5)
        timer.stop()
        page.table.selectRow(0)
        page.table.setFocus()
        QTest.keyClick(page.table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(QApplication.clipboard().text(), page.model.records[0].raw)
        page._details(page.model.index(0, 0))
        QTest.qWait(30)
        dialog = page.findChild(QDialog)
        self.assertEqual(dialog.findChild(QTextEdit).toPlainText(), page.model.records[0].raw)
        dialog.close()

    def test_partial_line_update_and_same_size_replacement(self):
        window, page, path = self.window(1)
        original = path.read_bytes()
        path.write_bytes(b"20:00:00 - INFO - worker - " + "tiếng".encode("utf-8")[:-1])
        page.store.refresh()
        self.wait_for(lambda: len(page.browsing) == 1 and "worker" in next(iter(page.browsing.values())).source)
        with path.open("ab") as file:
            file.write("tiếng".encode("utf-8")[-1:] + b"\n")
        page.store.refresh()
        self.wait_for(lambda: next(iter(page.browsing.values())).message == "tiếng")
        self.assertEqual(len(page.model.records), 1)
        replacement = path.with_suffix(".new")
        replacement.write_bytes(original)
        replacement.replace(path)
        page.store.refresh()
        self.wait_for(lambda: bool(page.browsing) and "Event" in next(iter(page.browsing.values())).message)

    def test_startup_local_records_follow_loaded_file_history(self):
        from source.launcher.utils.log_records import parse_record
        window,page,path=self.window(4)
        page.store.stop()
        page._reset()
        page.store.end=0
        page.append_local('[INFO] startup message')
        page.table.selectRow(0)
        page.store.end=300
        records=[parse_record('16:00:00 - INFO - file - older',('file',0,0),(0,0))]
        page._received(records,'initial')
        self.assertEqual(page.model.records[-1].message,'startup message')
        self.assertEqual(page.model.records[0].message,'older')
        self.assertEqual(page.model.records[page.table.selectionModel().selectedRows()[0].row()].message,'startup message')
