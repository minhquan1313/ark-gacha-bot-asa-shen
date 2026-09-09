import inspect
import os
import unittest
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
from unittest.mock import Mock, patch

# The UI module imports screen-capture integrations during class construction;
# these tests exercise update state transitions without requiring the optional
# desktop capture package.
mss_stub = ModuleType("mss")
mss_stub.mss = Mock()
sys.modules.setdefault("mss", mss_stub)
sys.modules.setdefault("numpy", ModuleType("numpy"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QFrame, QPushButton, QVBoxLayout, QWidget
from source.launcher.gui import SettingsGUI
from source.launcher.gui_parts.window import WindowGuiMixin
from source.launcher.utils.update_service import UpdateCheckResult, UpdateManifest
from source.launcher.utils.update_schedule import UpdateSchedule


class UpdateUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_launcher(self):
        launcher = SimpleNamespace(
            update_check_in_progress=True,
            update_auto_check_enabled=True,
            update_available=False,
            update_action_button=Mock(),
            update_status_label=Mock(),
            update_changelog_label=Mock(),
            confirm=Mock(return_value=False),
            toast=Mock(),
            auto_update_timer=Mock(),
            _format_manifest_notes=SettingsGUI._format_manifest_notes,
            update_schedule=Mock(),
        )
        launcher._set_update_notes = launcher.update_changelog_label.setText
        return launcher

    def test_available_update_switches_action_button(self):
        launcher = self.make_launcher()
        latest = UpdateManifest("1.1.0", "2026-07-22", "Release", ("New feature",))
        result = UpdateCheckResult(
            UpdateManifest("1.0.0", "", "", ()), latest, True
        )

        SettingsGUI._on_update_check_finished(launcher, result, False)

        self.assertTrue(launcher.update_available)
        launcher.update_action_button.setText.assert_called_with("UPDATE")
        launcher.update_action_button.setEnabled.assert_called_with(True)
        launcher.update_status_label.setText.assert_called_with(
            "UPDATE AVAILABLE\nVersion: 1.1.0"
        )
        launcher.update_changelog_label.setText.assert_called_with(
            "Release\nReleased: 2026-07-22\n- New feature"
        )

    def test_no_update_renders_local_manifest_and_hides_status(self):
        launcher = self.make_launcher()
        current = UpdateManifest(
            "1.0.0", "2026-07-20", "Installed release", ("Local change",)
        )
        remote = UpdateManifest(
            "1.0.0", "2026-07-22", "Remote release", ("Remote change",)
        )
        result = UpdateCheckResult(current, remote, False)

        SettingsGUI._on_update_check_finished(launcher, result, False)

        launcher.update_status_label.hide.assert_called_once_with()
        launcher.update_changelog_label.setText.assert_called_with(
            "Installed release\nReleased: 2026-07-20\n- Local change"
        )
        launcher.update_action_button.setText.assert_called_with("CHECK UPDATE")

    def test_update_card_has_expanding_width_capped_at_400(self):
        source = inspect.getsource(SettingsGUI._update_page)

        self.assertIn("card.setMinimumWidth(0)", source)
        self.assertIn("card.setMaximumWidth(400)", source)
        self.assertIn("QSizePolicy.Policy.Expanding", source)
        self.assertIn("QSizePolicy.Policy.Preferred", source)

    def test_canceling_automatic_update_keeps_daily_checks(self):
        launcher = self.make_launcher()
        latest = UpdateManifest("1.1.0", "2026-07-22", "Release", ())
        launcher.confirm.return_value = False
        result = UpdateCheckResult(
            UpdateManifest("1.0.0", "", "", ()), latest, True
        )

        SettingsGUI._on_update_check_finished(launcher, result, True)

        self.assertTrue(launcher.update_auto_check_enabled)
        launcher.auto_update_timer.stop.assert_not_called()

    def test_check_error_restores_manual_check_button(self):
        launcher = self.make_launcher()
        result = UpdateCheckResult(
            UpdateManifest("1.0.0", "", "", ()),
            UpdateManifest("1.0.0", "", "", ()),
            False,
            "network unavailable",
        )

        SettingsGUI._on_update_check_finished(launcher, result, False)

        launcher.update_action_button.setText.assert_called_with("CHECK UPDATE")
        launcher.update_action_button.setEnabled.assert_called_with(True)
        launcher.update_changelog_label.setText.assert_called_with("network unavailable\n\nDetails: check logs file")

    def test_daily_check_waits_for_startup(self):
        launcher = self.make_launcher()
        launcher.startup_complete = False
        launcher._start_update_check = Mock()
        SettingsGUI._automatic_update_check(launcher)
        launcher._start_update_check.assert_not_called()
        launcher.startup_complete = True
        SettingsGUI._automatic_update_check(launcher)
        launcher._start_update_check.assert_called_once_with(automatic=True)

    def test_failed_attempt_and_manual_check_share_the_daily_schedule(self):
        launcher = self.make_launcher()
        launcher.update_check_in_progress = False
        launcher._run_update_check = Mock()
        launcher._start_update_check = lambda **kwargs: SettingsGUI._start_update_check(launcher, **kwargs)
        now = datetime(2026, 9, 7, 23, 59, 59).astimezone()
        with tempfile.TemporaryDirectory() as directory, \
                patch("source.launcher.pages.logs_tools.datetime") as clock, \
                patch("source.launcher.pages.logs_tools.threading.Thread") as thread:
            launcher.update_schedule = UpdateSchedule(Path(directory) / "check.json")
            clock.now.return_value = now
            SettingsGUI._automatic_update_check(launcher)
            self.assertEqual(thread.call_count, 1)
            manifest = UpdateManifest("1.0.0", "", "", ())
            SettingsGUI._on_update_check_finished(
                launcher, UpdateCheckResult(manifest, manifest, False, "offline"), True
            )
            SettingsGUI._automatic_update_check(launcher)
            self.assertEqual(thread.call_count, 1)
            clock.now.return_value = now + timedelta(seconds=1)
            SettingsGUI._start_update_check(launcher, automatic=False)
            self.assertEqual(thread.call_count, 2)
            launcher.update_check_in_progress = False
            SettingsGUI._automatic_update_check(launcher)
            self.assertEqual(thread.call_count, 2)
            clock.now.return_value = now + timedelta(days=3)
            SettingsGUI._automatic_update_check(launcher)
            self.assertEqual(thread.call_count, 3)

    def test_cache_failure_logs_once_and_does_not_retry_today(self):
        launcher = self.make_launcher()
        launcher.update_check_in_progress = False
        launcher._run_update_check = Mock()
        launcher.append_log = Mock()
        launcher._start_update_check = lambda **kwargs: SettingsGUI._start_update_check(launcher, **kwargs)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(Path, "replace", side_effect=OSError("read only")), \
                patch("source.launcher.pages.logs_tools.threading.Thread") as thread:
            launcher.update_schedule = UpdateSchedule(Path(directory) / "check.json")
            SettingsGUI._automatic_update_check(launcher)
            launcher.update_check_in_progress = False
            SettingsGUI._automatic_update_check(launcher)
            thread.assert_called_once()
            launcher.append_log.assert_called_once()

    def test_update_check_dispatches_to_daemon_worker(self):
        launcher = self.make_launcher()
        launcher.update_check_in_progress = False
        launcher._run_update_check = Mock()

        with patch("source.launcher.pages.logs_tools.threading.Thread") as thread:
            SettingsGUI._start_update_check(launcher, automatic=True)

        thread.assert_called_once_with(
            target=launcher._run_update_check,
            args=(True,),
            daemon=True,
        )
        thread.return_value.start.assert_called_once_with()

    def test_overlapping_or_shutdown_checks_are_ignored(self):
        launcher = self.make_launcher()
        launcher.update_check_in_progress = True

        with patch("source.launcher.pages.logs_tools.threading.Thread") as thread:
            SettingsGUI._start_update_check(launcher, automatic=True)

        thread.assert_not_called()

        launcher.update_check_in_progress = False
        launcher.shutdown_started = True
        with patch("source.launcher.pages.logs_tools.threading.Thread") as thread:
            SettingsGUI._start_update_check(launcher, automatic=True)

        thread.assert_not_called()

    def test_late_result_after_shutdown_does_not_touch_ui(self):
        launcher = self.make_launcher()
        launcher.shutdown_started = True
        result = UpdateCheckResult(
            UpdateManifest("1.0.0", "", "", ()),
            UpdateManifest("1.1.0", "", "Remote", ()),
            True,
        )

        SettingsGUI._on_update_check_finished(launcher, result, True)

        self.assertFalse(launcher.update_check_in_progress)
        launcher.update_status_label.setText.assert_not_called()
        launcher.update_changelog_label.setText.assert_not_called()
        launcher.confirm.assert_not_called()

    def test_update_page_starts_with_local_manifest_notes(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)

        def make_panel(title=None):
            panel = QFrame()
            panel_layout = QVBoxLayout(panel)
            if title:
                panel_layout.addWidget(QLabel(title))
            return panel, panel_layout

        launcher = SimpleNamespace(
            _page=Mock(return_value=(page, page_layout)),
            _page_title=Mock(return_value=QLabel()),
            _panel=Mock(side_effect=make_panel),
            _button=Mock(side_effect=lambda text, variant: QPushButton(text)),
            _handle_update_action=Mock(),
            _format_manifest_notes=SettingsGUI._format_manifest_notes,
        )
        local = UpdateManifest("1.0.0", "2026-07-20", "Installed", ("Local fix",))

        with patch("source.launcher.pages.logs_tools.load_manifest", return_value=local):
            launcher._set_update_notes = lambda text: SettingsGUI._set_update_notes(launcher, text)
            SettingsGUI._update_page(launcher)

        self.assertEqual(launcher.update_current_label.text(), "Version: 1.0.0")
        self.assertEqual(
            "\n".join(label.text() for label in launcher.update_changelog_label.findChildren(QLabel)),
            "Installed\nReleased: 2026-07-20\n- Local fix",
        )

    def test_page_open_during_check_keeps_notes_and_shows_checking_state(self):
        launcher = self.make_launcher()
        launcher.update_check_in_progress = True

        with patch("source.launcher.pages.logs_tools.threading.Thread") as thread:
            SettingsGUI._start_update_check(launcher)

        thread.assert_not_called()
        launcher.update_action_button.setText.assert_called_with("CHECKING...")
        launcher.update_status_label.show.assert_called_once_with()
        launcher.update_status_label.setText.assert_called_with("CHECKING FOR UPDATE...")


if __name__ == "__main__":
    unittest.main()
