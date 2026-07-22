import unittest
import sys
from types import ModuleType
from types import SimpleNamespace
from unittest.mock import Mock

# The UI module imports screen-capture integrations during class construction;
# these tests exercise update state transitions without requiring the optional
# desktop capture package.
mss_stub = ModuleType("mss")
mss_stub.mss = Mock()
sys.modules.setdefault("mss", mss_stub)
sys.modules.setdefault("numpy", ModuleType("numpy"))

from source.launcher.gui import SettingsGUI
from source.launcher.utils.update_service import UpdateCheckResult, UpdateManifest


class UpdateUiTests(unittest.TestCase):
    def make_launcher(self):
        return SimpleNamespace(
            update_check_in_progress=True,
            update_auto_check_enabled=True,
            update_available=False,
            update_action_button=Mock(),
            update_status_label=Mock(),
            update_changelog_label=Mock(),
            confirm=Mock(return_value=False),
            toast=Mock(),
            auto_update_timer=Mock(),
        )

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

    def test_canceling_automatic_update_stops_periodic_checks(self):
        launcher = self.make_launcher()
        latest = UpdateManifest("1.1.0", "2026-07-22", "Release", ())
        launcher.confirm.return_value = False
        result = UpdateCheckResult(
            UpdateManifest("1.0.0", "", "", ()), latest, True
        )

        SettingsGUI._on_update_check_finished(launcher, result, True)

        self.assertFalse(launcher.update_auto_check_enabled)
        launcher.auto_update_timer.stop.assert_called_once_with()

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
        launcher.update_changelog_label.setText.assert_called_with("network unavailable")


if __name__ == "__main__":
    unittest.main()
