import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from source.launcher.gui import SettingsGUI
from source.launcher.server_transfer_helper import ServerTransferHelper
from source.launcher.widgets import WrappedStatusLabel


class NegativeHeightStatusLabel(WrappedStatusLabel):
    def heightForWidth(self, width):
        return -1


class ServerTransferHelperUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_tools_page_opens_server_transfer_helper(self):
        helper = Mock()
        launcher = SimpleNamespace(
            _can_open_setup_helper=Mock(return_value=True),
            find_deposit_helper=Mock(return_value=None),
            close_external_helpers=Mock(),
            register_deposit_helper=Mock(),
        )

        with patch("source.launcher.pages.ServerTransferHelper", return_value=helper):
            SettingsGUI.open_server_transfer_helper(launcher)

        launcher.close_external_helpers.assert_called_once_with()
        launcher.register_deposit_helper.assert_called_once_with(helper)
        helper.show.assert_called_once_with()
        helper.raise_.assert_called_once_with()
        helper.activateWindow.assert_called_once_with()

    def test_running_ui_collapses_idle_form(self):
        owner = SimpleNamespace(
            styleSheet=Mock(return_value=""),
            screen=Mock(return_value=None),
            settings={"helper_inactive_opacity": 0.3},
        )

        with patch(
            "source.launcher.server_transfer_helper.load_transfer_runtime_config",
            return_value={
                "settings": {
                    "lag_offset": 1,
                    "resource_station_yaw": 0,
                    "destination_station_yaw": 0,
                    "transmitter_teleport": "",
                    "resource_server": "0",
                    "destination_server": "0",
                    "account_count": 1,
                    "loop_count": 1,
                    "bed_prefix": "BedPlayer",
                    "bed_prefix_pad_start": 0,
                    "structure_load_delay": 10,
                    "transfer_retry_delay": 5,
                },
                "dedis": {
                    "teleport": "",
                    "items": [
                        {
                            "enabled": True,
                            "location": {"yaw": 0, "pitch": 0},
                            "crouched": False,
                        }
                    ],
                },
                "ui_coords": {},
            },
        ):
            helper = ServerTransferHelper(owner)

        helper._set_running_ui(True)

        self.assertTrue(helper.idle_widget.isHidden())
        self.assertFalse(helper.running_widget.isHidden())

    def test_wrapped_status_label_ignores_negative_height_for_width(self):
        label = NegativeHeightStatusLabel("Ready.")
        label.resize(180, 20)

        label._sync_minimum_height()

        self.assertGreaterEqual(label.minimumHeight(), 0)


if __name__ == "__main__":
    unittest.main()
