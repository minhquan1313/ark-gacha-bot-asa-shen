import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from source.launcher.auto_join_server_helper import AutoJoinServerHelper
from source.launcher.constants import (
    HELPER_HEIGHT,
    HELPER_WIDTH,
    MINIMAL_HELPER_RUNNING_WIDTH,
)
from source.launcher.deposit_route_helper import DepositRouteHelper
from source.launcher.fertilizer_refresh_helper import FertilizerRefreshHelper
from source.launcher.gui import SettingsGUI
from source.launcher.position_render_helper import PositionRenderHelper
from source.launcher.runner_overlay import RunnerOverlay
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
        self.assertTrue(helper.running_widget.isHidden())
        self.assertEqual(helper.width(), MINIMAL_HELPER_RUNNING_WIDTH)
        self.assertEqual(helper.hotkey_label.text(), "ALT + N stops this helper")

        helper._set_running_ui(False)

        self.assertFalse(helper.idle_widget.isHidden())
        self.assertTrue(helper.running_widget.isHidden())
        self.assertEqual(helper.width(), 560)
        self.assertEqual(helper.hotkey_label.text(), "ALT + N toggles START / STOP")

    def test_wrapped_status_label_ignores_negative_height_for_width(self):
        label = NegativeHeightStatusLabel("Ready.")
        label.resize(180, 20)

        label._sync_minimum_height()

        self.assertGreaterEqual(label.minimumHeight(), 0)

    def _worker_owner(self):
        return SimpleNamespace(
            styleSheet=Mock(return_value=""),
            screen=Mock(return_value=None),
            settings={"helper_inactive_opacity": 0.3},
            isActiveWindow=Mock(return_value=False),
            is_program_running=Mock(return_value=False),
            program_stopping=False,
            require_ark_window=Mock(return_value=True),
            last_ark_window_error="",
            dialog=Mock(),
        )

    def test_auto_join_running_ui_shrinks_and_restores(self):
        with patch(
            "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            helper = AutoJoinServerHelper(self._worker_owner())

        try:
            helper.show()
            self.app.processEvents()
            idle_height = helper.height()

            helper._set_running_ui(True)
            self.app.processEvents()

            self.assertEqual(helper.width(), MINIMAL_HELPER_RUNNING_WIDTH)
            self.assertLess(helper.height(), idle_height)
            self.assertEqual(helper.height(), helper.sizeHint().height())
            self.assertTrue(helper.description.isHidden())
            self.assertTrue(helper.server_row_widget.isHidden())
            self.assertTrue(helper.start_stop_button.isHidden())
            self.assertTrue(helper.status.isHidden())

            helper._set_running_ui(False)
            self.app.processEvents()

            self.assertEqual(helper.width(), 320)
            self.assertEqual(helper.height(), idle_height)
            self.assertEqual(helper.minimumHeight(), helper.idle_min_height)
            self.assertFalse(helper.description.isHidden())
            self.assertFalse(helper.server_row_widget.isHidden())
            self.assertFalse(helper.start_stop_button.isHidden())
            self.assertFalse(helper.status.isHidden())
            helper.adjustSize()
            self.app.processEvents()
            self.assertGreaterEqual(helper.height(), helper.idle_min_height)
        finally:
            helper.close()

    def test_fertilizer_running_ui_restores_width_constraints_before_showing_body(self):
        with patch(
            "source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            helper = FertilizerRefreshHelper(self._worker_owner())

        try:
            helper.show()
            self.app.processEvents()
            idle_height = helper.height()

            self.assertEqual(helper.width(), HELPER_WIDTH)
            self.assertGreaterEqual(idle_height, HELPER_HEIGHT)
            self.assertGreater(idle_height, HELPER_HEIGHT)

            helper._set_running_ui(True)
            self.app.processEvents()

            self.assertEqual(helper.width(), MINIMAL_HELPER_RUNNING_WIDTH)
            self.assertLess(helper.height(), idle_height)
            self.assertTrue(helper.description.isHidden())
            self.assertTrue(helper.start_stop_button.isHidden())
            self.assertTrue(helper.status.isHidden())

            helper._set_running_ui(False)
            self.app.processEvents()

            self.assertEqual(helper.width(), HELPER_WIDTH)
            self.assertEqual(helper.height(), idle_height)
            self.assertEqual(helper.minimumWidth(), HELPER_WIDTH)
            self.assertEqual(helper.maximumWidth(), HELPER_WIDTH)
            self.assertEqual(helper.minimumHeight(), HELPER_HEIGHT)
            self.assertFalse(helper.description.isHidden())
            self.assertFalse(helper.start_stop_button.isHidden())
            self.assertFalse(helper.status.isHidden())
        finally:
            helper.close()

    def test_runner_overlay_uses_fixed_width_and_content_driven_height_floor(self):
        owner = SimpleNamespace(
            screen=Mock(return_value=None),
            stop_program=Mock(),
        )
        overlay = RunnerOverlay(owner)

        try:
            overlay.show()
            self.app.processEvents()
            initial_height = overlay.height()

            overlay.refresh({"running": [], "active": [], "waiting": []})
            self.app.processEvents()

            self.assertEqual(overlay.width(), 360)
            self.assertEqual(overlay.minimumWidth(), 360)
            self.assertEqual(overlay.maximumWidth(), 360)
            self.assertGreaterEqual(overlay.height(), HELPER_HEIGHT)
            self.assertLess(overlay.height(), initial_height)
        finally:
            overlay.close()


class SharedHelperWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _owner(self):
        return SimpleNamespace(
            styleSheet=Mock(return_value=""),
            screen=Mock(return_value=None),
            settings={"helper_inactive_opacity": 0.3, "station_yaw": 0.0},
            isActiveWindow=Mock(return_value=False),
            forget_deposit_helper=Mock(),
            deposit_config={
                "depositCrystalData": [
                    {
                        "teleport": "T1",
                        "dedi": {"items": []},
                        "vault": {"items": []},
                    }
                ],
                "depositGrindableData": [],
            },
            form_values={},
            fields={},
            persist_settings_from_visible_fields=Mock(),
            _render_settings_group=Mock(),
        )

    def test_setup_helpers_use_shared_focus_opacity_and_close_cleanup(self):
        owner = self._owner()
        with (
            patch(
                "source.launcher.deposit_route_helper.register_alt_n_hotkey",
                return_value=False,
            ),
            patch(
                "source.launcher.position_render_helper.register_alt_n_hotkey",
                return_value=False,
            ),
        ):
            helpers = [
                DepositRouteHelper(owner, "crystal", 0),
                PositionRenderHelper(owner),
            ]

        for helper in helpers:
            try:
                helper.refocus_helper = Mock()
                helper.handle_hotkey()
                helper.refocus_helper.assert_called_once_with()

                guide = Mock()
                guide.isActiveWindow.return_value = True
                guide.mouse_inside = False
                helper.guide = guide
                helper.sync_window_opacity()
                self.assertEqual(helper.windowOpacity(), 1.0)

                helper.close()
                owner.forget_deposit_helper.assert_any_call(helper)
                guide.close.assert_called_once_with()
            finally:
                try:
                    helper.close()
                except RuntimeError:
                    pass


if __name__ == "__main__":
    unittest.main()
