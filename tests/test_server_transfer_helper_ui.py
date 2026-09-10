import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QWidget

from source.launcher import server_transfer_helper as server_transfer_helper_module
from source.launcher.auto_join_server_helper import AutoJoinServerHelper
from source.launcher.components.widgets import AnimatedButton, WrappedStatusLabel
from source.launcher.config.constants import (
    HELPER_HEIGHT,
    HELPER_WIDTH,
    MINIMAL_HELPER_RUNNING_WIDTH,
    RUNNER_WIDTH,
)
from source.launcher.deposit_route_helper import DepositRouteHelper
from source.launcher.fertilizer_refresh_helper import FertilizerRefreshHelper
from source.launcher.gui import SettingsGUI
from source.launcher.position_render_helper import PositionRenderHelper
from source.launcher.runner_overlay import RunnerOverlay
from source.launcher.server_transfer_helper import ServerTransferHelper
from source.launcher.styles import launcher_style_sheet


class NegativeHeightStatusLabel(WrappedStatusLabel):
    def heightForWidth(self, width):
        return -1


class ServerTransferHelperUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        """Prevent UI fixtures from saving test data to user transfer configuration."""
        self.config_writer_patches = [
            patch(
                "source.launcher.server_transfer_helper.save_transfer_settings",
                side_effect=lambda data, *_args, **_kwargs: data,
            ),
            patch(
                "source.launcher.server_transfer_helper.save_transfer_dedis",
                side_effect=lambda data, *_args, **_kwargs: data,
            ),
            patch(
                "source.launcher.server_transfer_helper.save_transfer_players",
                side_effect=lambda data, *_args, **_kwargs: data,
            ),
            patch(
                "source.launcher.server_transfer_helper.save_transfer_ui_coords",
                side_effect=lambda data, *_args, **_kwargs: data,
            ),
        ]
        for config_writer in self.config_writer_patches:
            config_writer.start()
            self.addCleanup(config_writer.stop)

    def test_tools_page_opens_server_transfer_helper(self):
        helper = Mock()
        launcher = SimpleNamespace(
            _can_open_setup_helper=Mock(return_value=True),
            find_deposit_helper=Mock(return_value=None),
            close_external_helpers=Mock(),
            register_deposit_helper=Mock(),
        )

        with patch(
            "source.launcher.server_transfer_helper.ServerTransferHelper", return_value=helper
        ):
            SettingsGUI.open_server_transfer_helper(launcher)

        launcher.close_external_helpers.assert_called_once_with()
        launcher.register_deposit_helper.assert_called_once_with(helper)
        helper.show.assert_called_once_with()
        helper.raise_.assert_called_once_with()
        helper.activateWindow.assert_called_once_with()

    def test_running_ui_hides_config_and_shows_transfer_overlay(self) -> None:
        owner = SimpleNamespace(
            styleSheet=Mock(return_value=""),
            screen=Mock(return_value=None),
            settings={"helper_inactive_opacity": 0.3},
            isActiveWindow=Mock(return_value=False),
        )

        with patch(
            "source.launcher.server_transfer_helper.load_transfer_runtime_config",
            return_value={
                "settings": {
                    "ping": 1,
                    "resource_station_yaw": 0,
                    "destination_station_yaw": 0,
                    "resource_server": "0",
                    "destination_server": "0",
                    "structure_load_delay": 10,
                    "transfer_retry_delay": 5,
                },
                "players": {"players": [{"bed_name": "Player1"}]},
                "dedis": {
                    "resource": {
                        "teleport": "",
                        "transmitter_teleport": "",
                        "items": [
                            {
                                "location": {"yaw": 0, "pitch": 0},
                                "crouched": False,
                            }
                        ],
                    },
                    "destination": {
                        "teleport": "",
                        "transmitter_teleport": "",
                        "items": [
                            {
                                "location": {"yaw": 0, "pitch": 0},
                                "crouched": False,
                            }
                        ],
                    },
                },
                "ui_coords": {},
            },
        ):
            helper = ServerTransferHelper(owner)

        try:
            helper._set_running_ui(True)
            self.app.processEvents()

            overlay = helper.transfer_overlay
            self.assertTrue(helper.isHidden())
            self.assertTrue(helper.idle_widget.isHidden())
            self.assertFalse(helper.running_widget.isHidden())
            self.assertIsNotNone(overlay)
            self.assertEqual(overlay.width(), RUNNER_WIDTH)
            self.assertEqual(overlay.header_title.text(), "Transfer GBot")
            self.assertLessEqual(
                overlay.header_title.fontMetrics().horizontalAdvance("Transfer GBot"),
                overlay.header_title.width(),
            )
            self.assertFalse(overlay.isHidden())
            self.assertTrue(helper.transfer_refresh_timer.isActive())
            self.assertEqual(helper.hotkey_label.text(), "ALT + N stops this helper")

            helper._set_running_ui(False)
            self.app.processEvents()

            self.assertFalse(helper.isHidden())
            self.assertFalse(helper.idle_widget.isHidden())
            self.assertTrue(helper.running_widget.isHidden())
            self.assertIsNone(helper.transfer_overlay)
            self.assertFalse(helper.transfer_refresh_timer.isActive())
            self.assertEqual(helper.width(), helper.idle_width)
            self.assertEqual(helper.hotkey_label.text(), "ALT + N toggles START / STOP")
        finally:
            helper.close()

    def test_transfer_overlay_loading_state_becomes_ready_stop_state(self) -> None:
        helper = self._transfer_helper(account_count=1)
        process = Mock()
        process.poll.return_value = None
        process.stdout = None
        helper.starting = True
        helper.worker_process = process

        try:
            helper._set_running_ui(True)
            self.app.processEvents()

            overlay = helper.transfer_overlay
            self.assertEqual(overlay.stop_button.text(), "STOP")
            self.assertTrue(overlay.stop_button.isEnabled())
            self.assertTrue(overlay.loading_spinner.timer.isActive())
            self.assertEqual(overlay.current_label._full_text, "Loading runner...")

            with patch.object(helper, "stop") as stop:
                helper.handle_hotkey()
            stop.assert_called_once_with()

            helper._handle_worker_output("__HELPER_READY__")
            self.app.processEvents()

            self.assertFalse(helper.starting)
            self.assertEqual(overlay.stop_button.text(), "STOP")
            self.assertEqual(overlay.stop_button.variant, "danger")
            self.assertTrue(overlay.stop_button.isEnabled())
            self.assertFalse(overlay.loading_spinner.timer.isActive())
        finally:
            helper.worker_process = None
            helper._set_running_ui(False)
            helper.close()

    def test_closing_transfer_helper_during_loading_terminates_worker(self) -> None:
        helper = self._transfer_helper(account_count=1)
        process = Mock()
        process.poll.return_value = None
        process.stdout = None
        helper.starting = True
        helper.worker_process = process
        helper._set_running_ui(True)

        with patch("source.launcher.helper_window.terminate_process_tree") as terminate:
            helper.close()
            self.app.processEvents()

        terminate.assert_called_once_with(process)

    def test_transfer_worker_tasks_and_statuses_refresh_overlay(self) -> None:
        helper = self._transfer_helper(account_count=1)

        try:
            helper._set_running_ui(True)
            helper.helper_log_lines = [
                "14:21:33 - INFO - helper - Account 1: joining resource server."
            ]
            helper._refresh_transfer_overlay()
            helper._handle_worker_output(
                '__HELPER_TASK_STATE__ {"running":[{"name":"Acc 1 - Join Resource - 1111"}],'
                '"active":[{"name":"Acc 1 - Verify Tribe Log","state":"READY"}],'
                '"waiting":[]}'
            )
            self.app.processEvents()

            overlay = helper.transfer_overlay
            self.assertEqual(
                overlay.current_label._full_text,
                "Acc 1 - Join Resource - 1111",
            )
            self.assertEqual(
                overlay.upcoming_labels[0]._full_text,
                "Acc 1 - Verify Tribe Log",
            )
            self.assertEqual(
                overlay.log_labels[0]._full_text,
                "33 Account 1: joining resource server.",
            )
            self.assertNotIn("HELPER_TASK_STATE", helper.running_log.toPlainText())

            with patch.object(helper, "stop") as stop:
                overlay.stop_program()
            stop.assert_called_once_with()
        finally:
            helper._set_running_ui(False)
            helper.close()

    def test_transfer_overlay_shows_paused_state_and_restores_current_task(self) -> None:
        helper = self._transfer_helper(account_count=1)
        helper.transfer_task_snapshot = {
            "running": [{"name": "Acc 1 - Join Resource - 1111"}],
            "active": [{"name": "Acc 1 - Verify Tribe Log", "state": "READY"}],
            "waiting": [],
        }

        try:
            helper._set_running_ui(True)
            helper._handle_worker_output('__RUNNER_STATE__ {"state":"PAUSED"}')
            self.app.processEvents()

            overlay = helper.transfer_overlay
            self.assertEqual(helper.runner_state, "PAUSED")
            self.assertEqual(overlay.current_label._full_text, "PAUSED")
            self.assertEqual(
                overlay.upcoming_labels[0]._full_text,
                "Acc 1 - Verify Tribe Log",
            )
            self.assertNotIn("__RUNNER_STATE__", helper.worker_debug_lines)

            helper._handle_worker_output('__RUNNER_STATE__ {"state":"RUNNING"}')
            self.app.processEvents()

            self.assertEqual(helper.runner_state, "RUNNING")
            self.assertEqual(
                overlay.current_label._full_text,
                "Acc 1 - Join Resource - 1111",
            )
        finally:
            helper._set_running_ui(False)
            helper.close()

    def test_transfer_worker_finish_restores_configuration_window(self) -> None:
        helper = self._transfer_helper(account_count=1)
        worker = Mock()
        worker.poll.return_value = 1
        worker.stdout = None

        try:
            helper._set_running_ui(True)
            helper.worker_process = worker
            helper._on_worker_finished("Failed: test failure")
            self.app.processEvents()

            self.assertIsNone(helper.worker_process)
            self.assertIsNone(helper.transfer_overlay)
            self.assertFalse(helper.transfer_refresh_timer.isActive())
            self.assertFalse(helper.isHidden())
            self.assertFalse(helper.idle_widget.isHidden())
            self.assertEqual(helper.status.text(), "Failed: test failure")
        finally:
            helper.close()

    def test_transfer_worker_finish_refreshes_current_steam_warnings(self) -> None:
        initial_accounts = [
            {"account_name": "steam1", "most_recent": True, "timestamp": 20},
            {"account_name": "steam2", "most_recent": False, "timestamp": 10},
        ]
        switched_accounts = [
            {"account_name": "steam1", "most_recent": False, "timestamp": 20},
            {"account_name": "steam2", "most_recent": True, "timestamp": 10},
        ]
        helper = self._transfer_helper(account_count=2, steam_accounts=initial_accounts)
        worker = Mock()
        worker.poll.return_value = 1
        worker.stdout = None

        try:
            helper._set_running_ui(True)
            helper.worker_process = worker
            with patch(
                "source.launcher.server_transfer_helper.load_steam_accounts",
                return_value=switched_accounts,
            ):
                helper._on_worker_finished("Stopped.")

            self.assertIn("#ff4d6d", helper.player_rows[0]["frame"].styleSheet())
            self.assertIn("Relog Steam", helper.player_rows[0]["frame"].toolTip())
            self.assertTrue(helper.player_rows[1]["switch"].isHidden())
        finally:
            helper.close()

    def test_player_rows_follow_saved_players_with_editable_names(self):
        helper = self._transfer_helper(account_count=12)

        try:
            self.assertEqual(len(helper.player_rows), 12)
            self.assertEqual(
                [row["name"].text() for row in helper.player_rows[:12]],
                [
                    "Player1",
                    "Player2",
                    "Player3",
                    "Player4",
                    "Player5",
                    "Player6",
                    "Player7",
                    "Player8",
                    "Player9",
                    "Player_10",
                    "Player_11",
                    "Player_12",
                ],
            )
            self.assertFalse(
                any(row["name"].isReadOnly() for row in helper.player_rows)
            )
            self.assertEqual(helper.player_rows[0]["steam"].currentText(), "steam1")
            self.assertEqual(helper.player_rows[1]["steam"].currentText(), "steam2")
            self.assertIn("ignored", helper.player_rows[4]["frame"].toolTip())
            self.assertIn("#ff4d6d", helper.player_rows[4]["frame"].styleSheet())

            helper._remove_player_row(helper.player_rows[-1])

            self.assertEqual(len(helper.player_rows), 11)
            self.assertEqual(helper.player_rows[-1]["label"].text(), "P11")
        finally:
            helper.close()

    def test_transfer_cards_default_expanded_and_dedi_selected(self):
        helper = self._transfer_helper(account_count=1)

        try:
            self.assertTrue(server_transfer_helper_module.DEFAULT_PANELS_EXPANDED)
            bodies = helper.findChildren(QWidget, "DepositRouteCardBody")
            self.assertGreaterEqual(len(bodies), 3)
            self.assertTrue(all(not body.isHidden() for body in bodies))
            self.assertTrue(helper.dedi_rows[0]["selected"].isChecked())
        finally:
            helper.close()

    def test_dedi_selection_syncs_without_saving_and_grays_both_rows(self):
        helper = self._transfer_helper()
        try:
            resource = helper.resource_dedi_rows[0]
            destination = helper.destination_dedi_rows[0]
            with patch.object(helper, "_persist_dedis") as save:
                resource["selected"].setChecked(False)
                for row in (resource, destination):
                    self.assertFalse(row["selected"].isChecked())
                    self.assertIn("#8a8a8a", row["frame"].styleSheet())
                    self.assertTrue(row["selected"].isEnabled())
                    helper._set_dedi_row_expanded(row, True)
                    self.assertTrue(row["details"].isEnabled())
                destination["selected"].setChecked(True)
                for row in (resource, destination):
                    self.assertTrue(row["selected"].isChecked())
                    self.assertEqual(row["frame"].styleSheet(), "")
                save.assert_not_called()
        finally:
            helper.close()

    def test_dedi_selection_survives_edits_sync_and_pair_changes(self):
        helper = self._transfer_helper()
        try:
            helper._add_synced_dedi_pair()
            helper.resource_dedi_rows[1]["selected"].setChecked(False)
            helper.resource_dedi_rows[1]["yaw"].setText("25")
            helper._persist_dedis()
            helper._calculate_dedis_from_same_structure("destination")
            helper._calculate_dedis_from_same_structure("resource")
            helper._remove_dedi_row(helper.resource_dedi_rows[0])
            helper._add_synced_dedi_pair("destination")
            for side in ("resource", "destination"):
                rows = helper._dedi_rows_for_side(side)
                self.assertFalse(rows[0]["selected"].isChecked())
                self.assertEqual(rows[0]["index_label"].text(), "D1")
                self.assertTrue(rows[1]["selected"].isChecked())
                self.assertEqual(len(helper.config["dedis"][side]["items"]), 2)
                for item in helper.config["dedis"][side]["items"]:
                    self.assertEqual(set(item), {"location", "crouched"})
        finally:
            helper.close()
        reopened = self._transfer_helper()
        try:
            self.assertTrue(reopened.resource_dedi_rows[0]["selected"].isChecked())
            self.assertTrue(reopened.destination_dedi_rows[0]["selected"].isChecked())
        finally:
            reopened.close()

    def test_multiple_resource_is_runtime_only(self):
        """Pass the checkbox through worker arguments without serializing it."""
        helper = self._transfer_helper()
        try:
            self.assertEqual(helper.multiple_resource_checkbox.text(), "Multiple resource")
            self.assertFalse(helper.multiple_resource_checkbox.isChecked())
            for enabled in (False, True):
                helper.multiple_resource_checkbox.setChecked(enabled)
                with (
                    patch("source.launcher.server_transfer_helper.missing_runtime_inputs", return_value=[]),
                    patch("source.launcher.server_transfer_helper.focus_game_window"),
                    patch.object(helper, "_write_runtime_config", wraps=helper._write_runtime_config),
                    patch.object(helper, "_start_worker") as start,
                    patch.object(helper, "_finish_worker", return_value=False),
                ):
                    helper.start()
                    expected = ["server_transfer", "--config", helper.runtime_config_path]
                    if enabled:
                        expected.append("--multiple-resource")
                    start.assert_called_once_with(*expected)
                    runtime_json = Path(helper.runtime_config_path).read_text(encoding="utf-8")
                    self.assertNotIn("multiple_resource", runtime_json)
                    self.assertNotIn("multiple_resource", json.dumps(helper.config))
                    helper._on_worker_finished("Stopped.")
                    self.assertEqual(helper.multiple_resource_checkbox.isChecked(), enabled)
        finally:
            helper.close()
        reopened = self._transfer_helper()
        try:
            self.assertFalse(reopened.multiple_resource_checkbox.isChecked())
        finally:
            reopened.close()

    def test_start_filters_only_runtime_dedis_and_preserves_selection_after_finish(self):
        helper = self._transfer_helper(dedi_items=[
            {"location": {"yaw": yaw, "pitch": 0}, "crouched": False}
            for yaw in (10, 20, 30)
        ])
        try:
            helper.destination_dedi_rows[1]["selected"].setChecked(False)
            with (
                patch("source.launcher.server_transfer_helper.missing_runtime_inputs",
                      return_value=[]) as validate,
                patch("source.launcher.server_transfer_helper.focus_game_window"),
                patch.object(helper, "_write_runtime_config", return_value="runtime.json") as write,
                patch.object(helper, "_start_worker") as start,
                patch.object(helper, "_cleanup_runtime_config"),
                patch.object(helper, "_finish_worker", return_value=False),
            ):
                helper.start()
                runtime = write.call_args.args[0]
                self.assertIs(validate.call_args.args[1], runtime["dedis"])
                start.assert_called_once_with("server_transfer", "--config", "runtime.json")
                for side in ("resource", "destination"):
                    self.assertEqual(
                        [float(item["location"]["yaw"]) for item in runtime["dedis"][side]["items"]],
                        [10, 30],
                    )
                    self.assertEqual(len(helper.config["dedis"][side]["items"]), 3)
                    self.assertEqual(len(helper._dedi_rows_for_side(side)), 3)
                    for item in runtime["dedis"][side]["items"]:
                        self.assertEqual(set(item), {"location", "crouched"})
                helper._on_worker_finished("Stopped.")
                self.assertFalse(helper.resource_dedi_rows[1]["selected"].isChecked())
                self.assertFalse(helper.destination_dedi_rows[1]["selected"].isChecked())
                helper.runtime_config_path = None
        finally:
            helper.close()

    def test_start_requires_a_checked_dedi_pair(self):
        helper = self._transfer_helper()
        try:
            helper.resource_dedi_rows[0]["selected"].setChecked(False)
            with patch.object(helper, "_start_worker") as start:
                helper.start()
            start.assert_not_called()
            self.assertEqual(helper.status.text(), "Select at least one dedi before starting.")
        finally:
            helper.close()

    def test_transfer_cards_can_default_expanded_from_code_flag(self):
        with patch(
            "source.launcher.server_transfer_helper.DEFAULT_PANELS_EXPANDED", True
        ):
            helper = self._transfer_helper(account_count=1)

        try:
            bodies = helper.findChildren(QWidget, "DepositRouteCardBody")
            toggles = [
                panel.toggle_button
                for panel in helper.findChildren(QFrame, "Panel")
                if hasattr(panel, "toggle_button")
            ]
            self.assertGreaterEqual(len(bodies), 3)
            self.assertTrue(all(not body.isHidden() for body in bodies))
            self.assertTrue(all(toggle.text() == "v" for toggle in toggles))
        finally:
            helper.close()

    def test_server_transfer_idle_height_stays_fixed_to_constructor_height(self):
        with patch(
            "source.launcher.server_transfer_helper.DEFAULT_PANELS_EXPANDED", True
        ):
            helper = self._transfer_helper(account_count=3)

        try:
            helper.show()
            self.app.processEvents()

            self.assertEqual(helper.minimumHeight(), helper.idle_min_height)
            self.assertEqual(helper.height(), helper.idle_min_height)
            self.assertGreaterEqual(helper.idle_min_height, helper.sizeHint().height())
        finally:
            helper.close()

    def test_dedi_entry_defaults_collapsed_with_summary_and_index(self):
        helper = self._transfer_helper(account_count=1)

        try:
            row = helper.dedi_rows[0]

            self.assertEqual(row["index_label"].text(), "D1")
            self.assertTrue(row["details"].isHidden())
            self.assertEqual(row["toggle"].text(), ">")
            self.assertIn("Yaw 0", row["summary"].text())
            self.assertIn("Pitch 0", row["summary"].text())
            self.assertIn("Crouch off", row["summary"].text())
        finally:
            helper.close()

    def test_transfer_helper_renders_resource_and_destination_dedi_sections(self):
        helper = self._transfer_helper(account_count=1)

        try:
            button_texts = [
                button.text() for button in helper.findChildren(AnimatedButton)
            ]
            titles = [
                label.text()
                for label in helper.findChildren(QLabel, "SettingsDividerLabel")
            ]
            panels = helper.findChildren(QFrame, "HelperPanel")
            resource_panel = next(
                panel
                for panel in panels
                if any(
                    label.text() == "Resource"
                    for label in panel.findChildren(QLabel, "SettingsDividerLabel")
                )
            )
            destination_panel = next(
                panel
                for panel in panels
                if any(
                    label.text() == "Destinate"
                    for label in panel.findChildren(QLabel, "SettingsDividerLabel")
                )
            )

            self.assertNotIn("EXPAND ALL", button_texts)
            self.assertNotIn("COLLAPSE ALL", button_texts)
            self.assertIn("Resource", titles)
            self.assertIn("Destinate", titles)
            self.assertNotIn("Resource Dedis", titles)
            self.assertNotIn("Destination Dedis", titles)
            self.assertNotIn("transmitter_teleport", helper.setting_fields)
            self.assertIn(
                helper.setting_fields["resource_server"],
                resource_panel.findChildren(QWidget),
            )
            self.assertIn(
                helper.setting_fields["destination_server"],
                destination_panel.findChildren(QWidget),
            )
            self.assertIn(
                helper.resource_transmitter_teleport,
                resource_panel.findChildren(QWidget),
            )
            self.assertIn(
                helper.destination_transmitter_teleport,
                destination_panel.findChildren(QWidget),
            )
            self.assertEqual(len(helper.resource_dedi_rows), 1)
            self.assertEqual(len(helper.destination_dedi_rows), 1)
        finally:
            helper.close()

    def test_dedi_entry_expands_to_current_controls(self):
        helper = self._transfer_helper(account_count=1)

        try:
            row = helper.dedi_rows[0]

            helper._toggle_dedi_row(row)

            self.assertFalse(row["details"].isHidden())
            self.assertEqual(row["toggle"].text(), "v")
            self.assertIs(row["yaw"].parent(), row["details"])
            self.assertIs(row["pitch"].parent(), row["details"])
            self.assertIs(row["crouched"].parent(), row["details"])
        finally:
            helper.close()

    def test_player_name_edit_saves_to_players_json(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_players",
            side_effect=lambda data, account_count=1: data,
        ) as save_players:
            helper = self._transfer_helper(account_count=2)

            try:
                helper.player_rows[0]["name"].setText("ManualBed")
                helper._save_players_from_rows()

                save_players.assert_called_with(
                    {
                        "players": [
                            {"bed_name": "ManualBed", "steam_account": "steam1"},
                            {"bed_name": "Player2", "steam_account": "steam2"},
                        ]
                    }
                )
            finally:
                helper.close()

    def test_add_player_button_appends_and_saves_players_json(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_players",
            side_effect=lambda data, account_count=None: data,
        ) as save_players:
            helper = self._transfer_helper(account_count=1)

            try:
                helper._add_player_row_from_button()

                self.assertEqual(len(helper.player_rows), 2)
                save_players.assert_called_with(
                    {
                        "players": [
                            {"bed_name": "Player1", "steam_account": "steam1"},
                            {"bed_name": "BBedPlayer2", "steam_account": ""},
                        ]
                    }
                )
            finally:
                helper.close()

    def test_remove_player_blocks_last_row(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_players",
            side_effect=lambda data, account_count=None: data,
        ):
            helper = self._transfer_helper(account_count=1)

            try:
                helper._remove_player_row(helper.player_rows[0])

                self.assertEqual(len(helper.player_rows), 1)
                self.assertEqual(helper.status.text(), "At least one player row is required.")
            finally:
                helper.close()

    def test_transfer_helper_normalizes_empty_player_config_to_one_row(self):
        helper = self._transfer_helper(account_count=0)

        try:
            self.assertEqual(len(helper.player_rows), 1)
            self.assertEqual(helper.player_rows[0]["name"].text(), "BBedPlayer1")
        finally:
            helper.close()

    def test_start_blocks_invalid_ark_window_before_worker(self):
        helper = self._transfer_helper(account_count=1)
        helper.owner.require_ark_window.return_value = False
        helper.owner.last_ark_window_error = "ArkAscended must run at 1920x1080."

        try:
            with (
                patch.object(helper, "_current_config", return_value=helper.config),
                patch(
                    "source.launcher.server_transfer_helper.missing_runtime_inputs",
                    return_value=[],
                ),
                patch(
                    "source.launcher.server_transfer_helper.focus_game_window"
                ) as focus,
            ):
                helper.start()

            self.assertIsNone(helper.worker_process)
            focus.assert_not_called()
            self.assertIn("1920x1080", helper.status.text())
        finally:
            helper.close()

    def test_start_focus_failure_does_not_start_worker(self):
        helper = self._transfer_helper(account_count=1)

        try:
            with (
                patch.object(helper, "_current_config", return_value=helper.config),
                patch(
                    "source.launcher.server_transfer_helper.missing_runtime_inputs",
                    return_value=[],
                ),
                patch(
                    "source.launcher.server_transfer_helper.focus_game_window",
                    side_effect=RuntimeError("unable to focus Ark"),
                ) as focus,
            ):
                helper.start()

            self.assertIsNone(helper.worker_process)
            focus.assert_called_once_with(center_cursor_when_switching=True)
            self.assertEqual(helper.status.text(), "Cannot start: unable to focus Ark")
        finally:
            helper.close()

    def test_transfer_worker_start_failure_restores_config_and_cleans_runtime_file(
        self,
    ):
        helper = self._transfer_helper(account_count=1)

        try:
            with (
                patch.object(helper, "_current_config", return_value=helper.config),
                patch(
                    "source.launcher.server_transfer_helper.missing_runtime_inputs",
                    return_value=[],
                ),
                patch("source.launcher.server_transfer_helper.focus_game_window"),
                patch.object(
                    helper, "_write_runtime_config", return_value="runtime.json"
                ),
                patch.object(
                    helper,
                    "_start_worker",
                    side_effect=OSError("worker unavailable"),
                ),
                patch.object(helper, "_cleanup_runtime_config") as cleanup,
            ):
                helper.start()

            self.assertFalse(helper.starting)
            self.assertFalse(helper.running_ui_active)
            self.assertFalse(helper.isHidden())
            self.assertEqual(helper.start_stop_button.text(), "START")
            self.assertEqual(
                helper.status.text(),
                "Cannot start transfer helper: worker unavailable",
            )
            cleanup.assert_called_once_with()
        finally:
            helper.close()

    def test_hotkey_stops_running_transfer_helper(self):
        helper = self._transfer_helper(account_count=1)
        worker = Mock()
        worker.poll.return_value = None
        worker.stdout = None
        helper.worker_process = worker

        try:
            with patch("source.launcher.helper_window.terminate_process_tree"):
                helper.handle_hotkey()

            self.assertEqual(helper.running_summary.text(), "Stopping...")
            self.assertFalse(helper.running_stop_button.isEnabled())
        finally:
            worker.poll.return_value = 1
            helper.close()

    def test_player_search_prefix_conflict_gets_warning_outline(self):
        helper = self._transfer_helper(
            account_count=2, player_names=["Player1", "Player10"]
        )

        try:
            self.assertIn("#ffb020", helper.player_rows[0]["frame"].styleSheet())
            self.assertIn(
                'Searching "Player1" may also match: Player10',
                helper.player_rows[0]["frame"].toolTip(),
            )
            self.assertEqual(helper.player_rows[1]["frame"].styleSheet(), "")
        finally:
            helper.close()

    def test_player_search_duplicate_conflict_gets_warning_outline(self):
        helper = self._transfer_helper(
            account_count=2, player_names=["Player2", "Player2"]
        )

        try:
            self.assertIn("#ffb020", helper.player_rows[0]["frame"].styleSheet())
            self.assertIn("#ffb020", helper.player_rows[1]["frame"].styleSheet())
        finally:
            helper.close()

    def test_player_search_warning_clears_after_unique_edit(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_players",
            side_effect=lambda data, account_count=1: data,
        ):
            helper = self._transfer_helper(
                account_count=2, player_names=["Player2", "Player2"]
            )

            try:
                helper.player_rows[1]["name"].setText("Player3")
                helper._save_players_from_rows()

                self.assertEqual(helper.player_rows[0]["frame"].styleSheet(), "")
                self.assertEqual(helper.player_rows[1]["frame"].styleSheet(), "")
            finally:
                helper.close()

    def test_player_steam_duplicate_gets_red_outline_and_blocks_start(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_players",
            side_effect=lambda data, account_count=1: data,
        ):
            helper = self._transfer_helper(account_count=2)

            try:
                helper.player_rows[1]["steam"].setCurrentText("steam1")
                helper._sync_player_search_warnings()

                self.assertIn("#ff4d6d", helper.player_rows[1]["frame"].styleSheet())
                self.assertIn(
                    "duplicates player 1", helper.player_rows[1]["frame"].toolTip()
                )

                helper.start()

                self.assertEqual(
                    helper.status.text(), "Player Steam accounts are not ready."
                )
                helper.owner.dialog.assert_called_once()
            finally:
                helper.close()

    def test_player_one_non_recent_steam_account_gets_red_outline(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_players",
            side_effect=lambda data, account_count=1: data,
        ):
            helper = self._transfer_helper(account_count=2)

            try:
                helper.player_rows[0]["steam"].setCurrentText("steam2")
                helper._sync_player_search_warnings()

                self.assertIn("#ff4d6d", helper.player_rows[0]["frame"].styleSheet())
                self.assertIn("Relog Steam", helper.player_rows[0]["frame"].toolTip())
                self.assertFalse(helper.player_rows[0]["switch"].isHidden())
            finally:
                helper.close()

    def test_player_switch_buttons_show_for_non_current_steam_accounts(self):
        helper = self._transfer_helper(account_count=3)

        try:
            self.assertTrue(helper.player_rows[0]["switch"].isHidden())
            self.assertFalse(helper.player_rows[1]["switch"].isHidden())
            self.assertFalse(helper.player_rows[2]["switch"].isHidden())
        finally:
            helper.close()

    def test_player_switch_button_hides_for_empty_steam_account(self):
        helper = self._transfer_helper(account_count=2)

        try:
            helper.player_rows[1]["steam"].setCurrentText("")
            helper._sync_player_search_warnings()

            self.assertTrue(helper.player_rows[1]["switch"].isHidden())
        finally:
            helper.close()

    def test_player_two_switch_starts_worker_for_player_two_steam(self):
        helper = self._transfer_helper(account_count=2)

        try:
            with (
                patch(
                    "source.launcher.server_transfer_helper.loginusers_path",
                    return_value=Path("C:/Steam/config/loginusers.vdf"),
                ),
                patch.object(helper, "_start_worker") as start_worker,
            ):
                helper.player_rows[1]["switch"].click()

            start_worker.assert_called_once_with(
                "switch_steam",
                "--account",
                "steam2",
                "--loginusers",
                str(Path("C:/Steam/config/loginusers.vdf").resolve()),
            )
            self.assertTrue(helper.switching_player_steam)
            self.assertFalse(helper.player_rows[1]["switch"].isEnabled())
            self.assertFalse(helper.start_stop_button.isEnabled())
        finally:
            helper._restore_after_player_steam_switch()
            helper.close()

    def test_player_switch_success_refreshes_accounts_and_starts_game(self):
        initial_accounts = [
            {"account_name": "steam1", "most_recent": True, "timestamp": 20},
            {"account_name": "steam2", "most_recent": False, "timestamp": 10},
        ]
        switched_accounts = [
            {"account_name": "steam1", "most_recent": False, "timestamp": 20},
            {"account_name": "steam2", "most_recent": True, "timestamp": 10},
        ]
        helper = self._transfer_helper(
            account_count=2,
            steam_accounts=initial_accounts,
        )
        worker = Mock()
        worker.poll.return_value = 0
        worker.stdout = None
        helper.worker_process = worker
        helper.switching_player_steam = True
        helper.pending_switch_account = "steam2"
        helper.pending_switch_row = helper.player_rows[1]

        try:
            with (
                patch(
                    "source.launcher.server_transfer_helper.load_steam_accounts",
                    return_value=switched_accounts,
                ) as load_accounts,
                patch(
                    "source.launcher.server_transfer_helper.QTimer.singleShot"
                ) as single_shot,
            ):
                helper._on_worker_finished("Steam restarted for steam2.")

            load_accounts.assert_called()
            self.assertEqual(helper.config["steam_accounts"], switched_accounts)
            self.assertTrue(helper.player_rows[1]["switch"].isHidden())
            self.assertFalse(helper.player_rows[0]["switch"].isHidden())
            single_shot.assert_called_once_with(0, helper.owner.start_game)
        finally:
            helper.close()

    def test_start_reloads_steam_accounts_before_player_one_validation(self):
        initial_accounts = [
            {"account_name": "steam1", "most_recent": True, "timestamp": 20},
            {"account_name": "steam2", "most_recent": False, "timestamp": 10},
            {"account_name": "steam3", "most_recent": False, "timestamp": 5},
        ]
        stale_accounts = [
            {"account_name": "steam1", "most_recent": False, "timestamp": 20},
            {"account_name": "steam2", "most_recent": False, "timestamp": 10},
            {"account_name": "steam3", "most_recent": True, "timestamp": 5},
        ]
        with patch(
            "source.launcher.server_transfer_helper.load_steam_accounts",
            return_value=stale_accounts,
        ):
            helper = self._transfer_helper(
                account_count=3,
                steam_accounts=initial_accounts,
                keep_steam_accounts_patch=False,
            )

            try:
                written_configs = []

                def write_config(config):
                    written_configs.append(config)
                    return "runtime.json"

                with (
                    patch.object(
                        helper, "_confirm_start_from_current_player", return_value=True
                    ) as confirm,
                    patch(
                        "source.launcher.server_transfer_helper.missing_runtime_inputs",
                        return_value=[],
                    ),
                    patch("source.launcher.server_transfer_helper.focus_game_window"),
                    patch.object(
                        helper, "_write_runtime_config", side_effect=write_config
                    ),
                    patch.object(helper, "_start_worker") as start_worker,
                ):
                    helper.start()

                confirm.assert_called_once_with(3)
                self.assertEqual(written_configs[0]["start_account"], 3)
                self.assertNotIn("start_account", helper.config)
                start_worker.assert_called_once_with(
                    "server_transfer", "--config", "runtime.json"
                )
                self.assertTrue(helper.starting)
                self.assertIn("#ff4d6d", helper.player_rows[0]["frame"].styleSheet())
                self.assertIn("Relog Steam", helper.player_rows[0]["frame"].toolTip())
            finally:
                helper.close()

    def test_start_from_current_player_cancel_does_not_start_worker(self):
        initial_accounts = [
            {"account_name": "steam1", "most_recent": True, "timestamp": 20},
            {"account_name": "steam2", "most_recent": False, "timestamp": 10},
            {"account_name": "steam3", "most_recent": False, "timestamp": 5},
        ]
        current_accounts = [
            {"account_name": "steam1", "most_recent": False, "timestamp": 20},
            {"account_name": "steam2", "most_recent": False, "timestamp": 10},
            {"account_name": "steam3", "most_recent": True, "timestamp": 5},
        ]
        with patch(
            "source.launcher.server_transfer_helper.load_steam_accounts",
            return_value=current_accounts,
        ):
            helper = self._transfer_helper(
                account_count=3,
                steam_accounts=initial_accounts,
                keep_steam_accounts_patch=False,
            )

            try:
                with (
                    patch.object(
                        helper,
                        "_confirm_start_from_current_player",
                        return_value=False,
                    ) as confirm,
                    patch(
                        "source.launcher.server_transfer_helper.missing_runtime_inputs",
                        return_value=[],
                    ),
                    patch.object(helper, "_write_runtime_config") as write_config,
                    patch.object(helper, "_start_worker") as start_worker,
                ):
                    helper.start()

                confirm.assert_called_once_with(3)
                self.assertEqual(helper.status.text(), "Start canceled.")
                write_config.assert_not_called()
                start_worker.assert_not_called()
            finally:
                helper.close()

    def test_start_blocks_when_current_steam_is_not_configured_player(self):
        initial_accounts = [
            {"account_name": "steam1", "most_recent": True, "timestamp": 20},
            {"account_name": "steam2", "most_recent": False, "timestamp": 10},
        ]
        current_accounts = [
            {"account_name": "steam1", "most_recent": False, "timestamp": 20},
            {"account_name": "steam2", "most_recent": False, "timestamp": 10},
            {"account_name": "steamX", "most_recent": True, "timestamp": 30},
        ]
        with patch(
            "source.launcher.server_transfer_helper.load_steam_accounts",
            return_value=current_accounts,
        ):
            helper = self._transfer_helper(
                account_count=2,
                steam_accounts=initial_accounts,
                keep_steam_accounts_patch=False,
            )

            try:
                with (
                    patch.object(helper, "_confirm_start_from_current_player") as confirm,
                    patch.object(helper, "_start_worker") as start_worker,
                ):
                    helper.start()

                self.assertEqual(
                    helper.status.text(), "Player Steam accounts are not ready."
                )
                confirm.assert_not_called()
                start_worker.assert_not_called()
            finally:
                helper.close()

    def test_transfer_helper_expand_and_collapse_all_affects_panels_and_dedis(self):
        helper = self._transfer_helper(account_count=1)

        try:
            helper.set_all_collapsible_expanded(False)

            self.assertTrue(
                all(panel.body_widget.isHidden() for panel in helper.collapsible_panels)
            )
            self.assertTrue(
                all(
                    row["details"].isHidden()
                    for row in helper.resource_dedi_rows + helper.destination_dedi_rows
                )
            )

            helper.set_all_collapsible_expanded(True)

            self.assertTrue(
                all(
                    not panel.body_widget.isHidden()
                    for panel in helper.collapsible_panels
                )
            )
            self.assertTrue(
                all(
                    not row["details"].isHidden()
                    for row in helper.resource_dedi_rows + helper.destination_dedi_rows
                )
            )
        finally:
            helper.close()

    def test_ignored_player_row_keeps_red_outline_when_name_conflicts(self):
        helper = self._transfer_helper(
            account_count=5,
            player_names=["Player1", "Player2", "Player3", "Player4", "Player1"],
        )

        try:
            self.assertIn("#ff4d6d", helper.player_rows[4]["frame"].styleSheet())
            self.assertIn("ignored", helper.player_rows[4]["frame"].toolTip())
            self.assertIn(
                'Searching "Player1" may also match: Player1',
                helper.player_rows[4]["frame"].toolTip(),
            )
        finally:
            helper.close()

    def test_start_blocks_runtime_player_search_conflicts(self):
        with (
            patch(
                "source.launcher.server_transfer_helper.save_transfer_settings",
                side_effect=lambda data: data,
            ),
            patch(
                "source.launcher.server_transfer_helper.save_transfer_dedis",
                side_effect=lambda data: data,
            ),
            patch(
                "source.launcher.server_transfer_helper.save_transfer_players",
                side_effect=lambda data, account_count=1: data,
            ),
        ):
            helper = self._transfer_helper(
                account_count=2, player_names=["Player1", "Player10"]
            )

            try:
                helper.start()

                helper.owner.dialog.assert_called_once()
                self.assertIn("Player1", helper.owner.dialog.call_args.args[1])
                self.assertIn("Player10", helper.owner.dialog.call_args.args[1])
                self.assertEqual(
                    helper.status.text(),
                    "Player bed/teleport names are not search-safe.",
                )
            finally:
                helper.close()

    def test_start_blocks_when_ignored_row_conflicts_with_runtime_row(self):
        helper = self._transfer_helper(
            account_count=5,
            player_names=["Player1", "Player2", "Player3", "Player4", "Player10"],
        )

        try:
            helper.start()

            helper.owner.dialog.assert_called_once()
            self.assertIn("Player1", helper.owner.dialog.call_args.args[1])
            self.assertIn("Player10", helper.owner.dialog.call_args.args[1])
        finally:
            helper.close()

    def test_setting_edit_persists_without_account_count(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_settings",
            side_effect=lambda data: data,
        ) as save_settings:
            helper = self._transfer_helper(account_count=2)

            try:
                helper.setting_fields["resource_server"].setText("1234")
                helper.setting_fields["destination_server"].setText("5678")
                helper._persist_settings()

                saved = save_settings.call_args.args[0]
                self.assertEqual(saved["resource_server"], "1234")
                self.assertEqual(saved["destination_server"], "5678")
                self.assertNotIn("account_count", saved)
            finally:
                helper.close()

    def test_dedi_edit_persists_to_dedis_json(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_dedis",
            side_effect=lambda data: data,
        ) as save_dedis:
            helper = self._transfer_helper(account_count=1)

            try:
                helper.dedi_rows[0]["yaw"].setText("44")
                helper._persist_dedis()

                self.assertEqual(
                    save_dedis.call_args.args[0]["resource"]["items"][0]["location"][
                        "yaw"
                    ],
                    "44",
                )
            finally:
                helper.close()

    def test_transmitter_fields_persist_to_dedis_json_independently(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_dedis",
            side_effect=lambda data: data,
        ) as save_dedis:
            helper = self._transfer_helper(account_count=1)

            try:
                helper.resource_transmitter_teleport.setText("RESOURCE_TX")
                helper.destination_transmitter_teleport.setText("DEST_TX")
                helper._persist_dedis()

                saved = save_dedis.call_args.args[0]
                self.assertEqual(
                    saved["resource"]["transmitter_teleport"], "RESOURCE_TX"
                )
                self.assertEqual(
                    saved["destination"]["transmitter_teleport"], "DEST_TX"
                )
            finally:
                helper.close()

    def test_destination_dedi_edit_persists_independently(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_dedis",
            side_effect=lambda data: data,
        ) as save_dedis:
            helper = self._transfer_helper(account_count=1)

            try:
                helper.destination_dedi_rows[0]["yaw"].setText("88")
                helper._persist_dedis()

                self.assertEqual(
                    save_dedis.call_args.args[0]["destination"]["items"][0]["location"][
                        "yaw"
                    ],
                    "88",
                )
                self.assertEqual(
                    save_dedis.call_args.args[0]["resource"]["items"][0]["location"][
                        "yaw"
                    ],
                    "0.0",
                )
            finally:
                helper.close()

    def test_same_structure_calculate_buttons_are_available_above_transmitter(self):
        helper = self._transfer_helper(account_count=1)

        try:
            resource_button = helper.resource_same_structure_calculate
            destination_button = helper.destination_same_structure_calculate

            self.assertEqual(resource_button.text(), "Sync")
            self.assertEqual(destination_button.text(), "Sync")
            self.assertEqual(
                resource_button.toolTip(),
                server_transfer_helper_module.SAME_STRUCTURE_TOOLTIP,
            )
            self.assertEqual(
                destination_button.toolTip(),
                server_transfer_helper_module.SAME_STRUCTURE_TOOLTIP,
            )
            self.assertEqual(
                helper.resource_same_structure_description.text(),
                server_transfer_helper_module.SAME_STRUCTURE_TOOLTIP,
            )
            self.assertEqual(
                helper.destination_same_structure_description.text(),
                server_transfer_helper_module.SAME_STRUCTURE_TOOLTIP,
            )
            self.assertLess(
                self._body_layout_index(resource_button),
                self._labeled_row_index(resource_button, "Transmitter"),
            )
            self.assertLess(
                self._body_layout_index(destination_button),
                self._labeled_row_index(destination_button, "Transmitter"),
            )
        finally:
            helper.close()

    def test_destination_same_structure_calculate_updates_and_saves_rows(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_dedis",
            side_effect=lambda data: data,
        ) as save_dedis:
            helper = self._transfer_helper(account_count=1)

            try:
                helper.setting_fields["resource_station_yaw"].setText("10")
                helper.setting_fields["destination_station_yaw"].setText("20")
                helper.dedi_rows[0]["yaw"].setText("50")
                helper.dedi_rows[0]["pitch"].setText("10")
                helper.dedi_rows[0]["crouched"].setChecked(True)
                helper.resource_transmitter_teleport.setText("RESOURCE_TRANS")
                helper.destination_transmitter_teleport.setText("DEST_OLD")
                helper.resource_dedi_teleport.setText("RESOURCE_TELEPORT")
                helper.destination_dedi_teleport.setText("DEST_TELEPORT")
                helper.destination_dedi_rows[0]["yaw"].setText("0")
                helper.destination_dedi_rows[0]["pitch"].setText("0")
                save_dedis.reset_mock()

                helper.destination_same_structure_calculate.click()

                destination = helper.destination_dedi_rows[0]
                self.assertEqual(destination["yaw"].text(), "60.0")
                self.assertEqual(destination["pitch"].text(), "10.0")
                self.assertTrue(destination["crouched"].isChecked())
                self.assertEqual(
                    helper.destination_transmitter_teleport.text(), "RESOURCE_TRANS"
                )
                self.assertEqual(
                    helper.destination_dedi_teleport.text(), "DEST_TELEPORT"
                )
                self.assertEqual(
                    destination["summary"].text(),
                    "Yaw 60.0 | Pitch 10.0 | Crouch on",
                )
                self.assertEqual(
                    save_dedis.call_args.args[0]["destination"]["items"][0],
                    {
                        "location": {"yaw": "60.0", "pitch": "10.0"},
                        "crouched": True,
                    },
                )
                self.assertEqual(
                    save_dedis.call_args.args[0]["destination"][
                        "transmitter_teleport"
                    ],
                    "RESOURCE_TRANS",
                )
                self.assertEqual(
                    helper.status.text(),
                    "Destination dedis calculated from resource structure.",
                )

                destination["yaw"].setText("88")
                helper._persist_dedis()

                self.assertEqual(
                    save_dedis.call_args.args[0]["destination"]["items"][0][
                        "location"
                    ]["yaw"],
                    "88",
                )
            finally:
                helper.close()

    def test_resource_same_structure_calculate_updates_and_saves_rows(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_dedis",
            side_effect=lambda data: data,
        ) as save_dedis:
            helper = self._transfer_helper(account_count=1)

            try:
                helper.setting_fields["resource_station_yaw"].setText("10")
                helper.setting_fields["destination_station_yaw"].setText("20")
                helper.destination_dedi_rows[0]["yaw"].setText("60")
                helper.destination_dedi_rows[0]["pitch"].setText("-5")
                helper.destination_dedi_rows[0]["crouched"].setChecked(True)
                helper.destination_transmitter_teleport.setText("DEST_TRANS")
                helper.resource_transmitter_teleport.setText("RESOURCE_OLD")
                helper.destination_dedi_teleport.setText("DEST_TELEPORT")
                helper.resource_dedi_teleport.setText("RESOURCE_TELEPORT")
                helper.dedi_rows[0]["yaw"].setText("0")
                helper.dedi_rows[0]["pitch"].setText("0")
                save_dedis.reset_mock()

                helper.resource_same_structure_calculate.click()

                resource = helper.resource_dedi_rows[0]
                self.assertEqual(resource["yaw"].text(), "50.0")
                self.assertEqual(resource["pitch"].text(), "-5.0")
                self.assertTrue(resource["crouched"].isChecked())
                self.assertEqual(
                    helper.resource_transmitter_teleport.text(), "DEST_TRANS"
                )
                self.assertEqual(
                    helper.resource_dedi_teleport.text(), "RESOURCE_TELEPORT"
                )
                self.assertEqual(
                    resource["summary"].text(),
                    "Yaw 50.0 | Pitch -5.0 | Crouch on",
                )
                self.assertEqual(
                    save_dedis.call_args.args[0]["resource"]["items"][0],
                    {
                        "location": {"yaw": "50.0", "pitch": "-5.0"},
                        "crouched": True,
                    },
                )
                self.assertEqual(
                    save_dedis.call_args.args[0]["resource"][
                        "transmitter_teleport"
                    ],
                    "DEST_TRANS",
                )
                self.assertEqual(
                    helper.status.text(),
                    "Resource dedis calculated from destination structure.",
                )
            finally:
                helper.close()

    def test_dedi_summary_updates_after_edit_and_crouch_toggle(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_dedis",
            side_effect=lambda data: data,
        ):
            helper = self._transfer_helper(account_count=1)

            try:
                row = helper.dedi_rows[0]
                row["yaw"].setText("44")
                row["pitch"].setText("-5")
                row["crouched"].setChecked(True)
                helper._sync_dedi_summary(row)

                self.assertEqual(row["summary"].text(), "Yaw 44 | Pitch -5 | Crouch on")
            finally:
                helper.close()

    def test_dedi_delete_reindexes_remaining_rows(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_dedis",
            side_effect=lambda data: data,
        ):
            helper = self._transfer_helper(
                account_count=1,
                dedi_items=[
                    {"location": {"yaw": 1, "pitch": 2}, "crouched": False},
                    {"location": {"yaw": 3, "pitch": 4}, "crouched": True},
                ],
            )

            try:
                helper._remove_dedi_row(helper.dedi_rows[0])

                self.assertEqual(len(helper.dedi_rows), 1)
                self.assertEqual(helper.dedi_rows[0]["index_label"].text(), "D1")
                self.assertIn("Yaw 3", helper.dedi_rows[0]["summary"].text())
            finally:
                helper.close()

    def test_transfer_helper_preloads_capture_view_dependencies(self):
        with patch(
            "source.launcher.server_transfer_helper.preload_capture_view_dependencies"
        ) as preload:
            helper = self._transfer_helper(account_count=1)

        try:
            preload.assert_called_once_with()
        finally:
            helper.close()

    def test_transfer_helper_open_survives_capture_preload_validation_failure(self):
        with patch(
            "source.launcher.server_transfer_helper.preload_capture_view_dependencies",
            side_effect=RuntimeError("ARK missing"),
        ):
            helper = self._transfer_helper(account_count=1)

        try:
            self.assertEqual(helper.status.text(), "Capture preload skipped: ARK missing")
        finally:
            helper.close()

    def test_wrapped_status_label_ignores_negative_height_for_width(self):
        label = NegativeHeightStatusLabel("Ready.")
        label.resize(180, 20)

        label._sync_minimum_height()

        self.assertGreaterEqual(label.minimumHeight(), 0)

    def _body_layout_index(self, widget):
        return widget.parentWidget().layout().indexOf(widget)

    def _labeled_row_index(self, widget, label_text):
        layout = widget.parentWidget().layout()
        for index in range(layout.count()):
            child_layout = layout.itemAt(index).layout()
            if child_layout is None:
                continue
            for child_index in range(child_layout.count()):
                child = child_layout.itemAt(child_index).widget()
                if isinstance(child, QLabel) and child.text() == label_text:
                    return index
        self.fail(f"{label_text} row not found.")

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
            start_game=Mock(),
        )

    def _transfer_helper(
        self,
        account_count=1,
        player_names=None,
        dedi_items=None,
        steam_accounts=None,
        keep_steam_accounts_patch=True,
    ):
        owner = self._worker_owner()
        if player_names is None:
            player_names = [
                "Player1",
                "Player2",
                "Player3",
                "Player4",
                "Player5",
                "Player6",
                "Player7",
                "Player8",
                "Player9",
                "Player_10",
                "Player_11",
                "Player_12",
            ][:account_count]
        if dedi_items is None:
            dedi_items = [
                {
                    "location": {"yaw": 0, "pitch": 0},
                    "crouched": False,
                }
            ]
        if steam_accounts is None:
            steam_accounts = [
                {
                    "account_name": f"steam{i}",
                    "most_recent": i == 1,
                    "timestamp": 20 - i,
                }
                for i in range(1, 13)
            ]
        steam_accounts_patch = patch(
            "source.launcher.server_transfer_helper.load_steam_accounts",
            return_value=steam_accounts,
        )
        if keep_steam_accounts_patch:
            steam_accounts_patch.start()
            self.addCleanup(steam_accounts_patch.stop)
        config = {
            "settings": {
                "ping": 1,
                "resource_station_yaw": 0,
                "destination_station_yaw": 0,
                "resource_server": "0",
                "destination_server": "0",
                "structure_load_delay": 10,
                "transfer_retry_delay": 5,
                "steam_restart_interval": 30,
            },
            "players": {
                "players": [
                    {"bed_name": name, "steam_account": f"steam{index + 1}"}
                    for index, name in enumerate(player_names[:account_count])
                ]
            },
            "dedis": {
                "resource": {
                    "teleport": "",
                    "transmitter_teleport": "",
                    "items": dedi_items,
                },
                "destination": {
                    "teleport": "",
                    "transmitter_teleport": "",
                    "items": [
                        {
                            "location": dict(item.get("location", {})),
                            "crouched": bool(item.get("crouched", False)),
                        }
                        for item in dedi_items
                    ],
                },
            },
            "ui_coords": {},
        }
        with patch(
            "source.launcher.server_transfer_helper.load_transfer_runtime_config",
            return_value=config,
        ):
            if keep_steam_accounts_patch:
                return ServerTransferHelper(owner)
            with steam_accounts_patch:
                return ServerTransferHelper(owner)

    def test_transfer_settings_include_steam_restart_interval(self) -> None:
        helper = self._transfer_helper(account_count=1)
        try:
            self.assertEqual(
                helper.setting_fields["steam_restart_interval"].text(), "30"
            )
        finally:
            helper.close()

    def test_transfer_start_mode_defaults_to_default(self) -> None:
        helper = self._transfer_helper(account_count=1)
        try:
            mode = helper.setting_fields["transfer_start_mode"]
            self.assertEqual(mode.currentData(), "default")
            self.assertIn("Recommended", mode.toolTip())
            self.assertEqual(mode.toolTip(), helper.transfer_start_mode_label.toolTip())
            self.assertEqual(
                mode.toolTip(),
                helper.transfer_start_mode_description.text(),
            )

            mode.setCurrentIndex(mode.findData("destinate"))

            self.assertIn("Optional", mode.toolTip())
            self.assertEqual(mode.toolTip(), helper.transfer_start_mode_label.toolTip())
            self.assertEqual(
                mode.toolTip(),
                helper.transfer_start_mode_description.text(),
            )
        finally:
            helper.close()

    def test_transfer_start_mode_persists_destinate(self) -> None:
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_settings",
            side_effect=lambda data, *_args, **_kwargs: data,
        ) as save_settings:
            helper = self._transfer_helper(account_count=1)
            try:
                mode = helper.setting_fields["transfer_start_mode"]
                mode.setCurrentIndex(mode.findData("destinate"))
                helper._persist_settings()
            finally:
                helper.close()

        self.assertEqual(
            save_settings.call_args.args[0]["transfer_start_mode"], "destinate"
        )

    def test_auto_join_running_ui_shrinks_and_restores(self):
        with patch(
            "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            helper = AutoJoinServerHelper(self._worker_owner())

        try:
            helper.setStyleSheet(launcher_style_sheet())
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
            self.assertFalse(helper.start_stop_button.isHidden())
            self.assertFalse(helper.status.isHidden())

            helper._set_running_ui(False)
            self.app.processEvents()

            self.assertEqual(helper.width(), helper.idle_width)
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

    def test_auto_join_uses_last_history_server_in_editable_dropdown(self):
        with (
            patch(
                "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
                return_value=False,
            ),
            patch(
                "source.launcher.auto_join_server_helper.load_auto_join_servers",
                return_value=["5147", "6049"],
            ),
        ):
            helper = AutoJoinServerHelper(self._worker_owner())

        try:
            self.assertTrue(helper.server_field.isEditable())
            self.assertEqual(
                [
                    helper.server_field.itemText(index)
                    for index in range(helper.server_field.count())
                ],
                ["5147", "6049"],
            )
            self.assertEqual(helper.server_field.currentText(), "6049")
        finally:
            helper.close()

    def test_auto_join_uses_default_server_when_history_is_empty(self):
        with (
            patch(
                "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
                return_value=False,
            ),
            patch(
                "source.launcher.auto_join_server_helper.load_auto_join_servers",
                return_value=[],
            ),
            patch(
                "source.launcher.auto_join_server_helper.settings.server_number",
                "7777",
            ),
        ):
            helper = AutoJoinServerHelper(self._worker_owner())

        try:
            self.assertEqual(helper.server_field.currentText(), "7777")
            self.assertEqual(helper.server_field.count(), 0)
        finally:
            helper.close()

    def test_auto_join_popup_x_deletes_row_without_starting(self):
        with (
            patch(
                "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
                return_value=False,
            ),
            patch(
                "source.launcher.auto_join_server_helper.load_auto_join_servers",
                return_value=["5147", "6049"],
            ),
        ):
            helper = AutoJoinServerHelper(self._worker_owner())

        try:
            helper.show()
            helper.server_field.showPopup()
            self.app.processEvents()
            first_index = helper.server_field.model().index(0, 0)
            first_row = helper.server_field.view().visualRect(first_index)
            delete_position = first_row.center()
            delete_position.setX(first_row.right() - 8)

            with (
                patch(
                    "source.launcher.auto_join_server_helper.forget_auto_join_server",
                    return_value=["6049"],
                ) as forget_server,
                patch.object(helper, "start") as start,
            ):
                QTest.mouseClick(
                    helper.server_field.view().viewport(),
                    Qt.MouseButton.LeftButton,
                    pos=delete_position,
                )
                self.app.processEvents()

            forget_server.assert_called_once_with("5147")
            start.assert_not_called()
            self.assertEqual(helper.server_field.currentText(), "6049")
            self.assertTrue(helper.server_field.view().isVisible())
        finally:
            helper.server_field.hidePopup()
            helper.close()

    def test_auto_join_popup_server_text_still_selects_row(self):
        with (
            patch(
                "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
                return_value=False,
            ),
            patch(
                "source.launcher.auto_join_server_helper.load_auto_join_servers",
                return_value=["5147", "6049"],
            ),
        ):
            helper = AutoJoinServerHelper(self._worker_owner())

        try:
            helper.show()
            helper.server_field.showPopup()
            self.app.processEvents()
            first_index = helper.server_field.model().index(0, 0)
            row_rect = helper.server_field.view().visualRect(first_index)
            select_position = row_rect.center()
            select_position.setX(row_rect.left() + 8)

            QTest.mouseClick(
                helper.server_field.view().viewport(),
                Qt.MouseButton.LeftButton,
                pos=select_position,
            )
            self.app.processEvents()

            self.assertEqual(helper.server_field.currentText(), "5147")
        finally:
            helper.server_field.hidePopup()
            helper.close()

    def test_auto_join_deleting_current_server_uses_latest_remaining(self):
        with (
            patch(
                "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
                return_value=False,
            ),
            patch(
                "source.launcher.auto_join_server_helper.load_auto_join_servers",
                return_value=["5147", "6049"],
            ),
        ):
            helper = AutoJoinServerHelper(self._worker_owner())

        try:
            with patch(
                "source.launcher.auto_join_server_helper.forget_auto_join_server",
                return_value=["5147"],
            ):
                helper._delete_saved_server(1)

            self.assertEqual(helper.server_field.currentText(), "5147")
        finally:
            helper.server_field.hidePopup()
            helper.close()

    def test_auto_join_deleting_final_server_uses_default(self):
        with (
            patch(
                "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
                return_value=False,
            ),
            patch(
                "source.launcher.auto_join_server_helper.load_auto_join_servers",
                return_value=["5147"],
            ),
        ):
            helper = AutoJoinServerHelper(self._worker_owner())

        try:
            with (
                patch(
                    "source.launcher.auto_join_server_helper.forget_auto_join_server",
                    return_value=[],
                ),
                patch(
                    "source.launcher.auto_join_server_helper.settings.server_number",
                    "7777",
                ),
            ):
                helper._delete_saved_server(0)

            self.assertEqual(helper.server_field.count(), 0)
            self.assertEqual(helper.server_field.currentText(), "7777")
        finally:
            helper.close()

    def test_auto_join_invalid_server_does_not_update_history(self):
        owner = self._worker_owner()
        with patch(
            "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            helper = AutoJoinServerHelper(owner)

        try:
            helper.server_field.setCurrentText("invalid")
            with patch(
                "source.launcher.auto_join_server_helper.remember_auto_join_server"
            ) as remember_server:
                helper.start()

            remember_server.assert_not_called()
            owner.dialog.assert_called_once()
        finally:
            helper.close()

    def test_auto_join_starting_state_becomes_ready_stop_state(self):
        with patch(
            "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            helper = AutoJoinServerHelper(self._worker_owner())
        process = Mock()
        process.poll.return_value = None
        process.stdout = None

        def launch_worker(*_args):
            helper._set_running_ui(True)
            helper.worker_process = process

        try:
            helper.server_field.setCurrentText("5147")
            with (
                patch("source.launcher.auto_join_server_helper.focus_game_window"),
                patch(
                    "source.launcher.auto_join_server_helper.remember_auto_join_server",
                    return_value=["6049", "5147"],
                ) as remember_server,
                patch.object(helper, "_start_worker", side_effect=launch_worker),
            ):
                helper.start()

            remember_server.assert_called_once_with("5147")
            self.assertEqual(helper.server_field.currentText(), "5147")
            self.assertTrue(helper.starting)
            self.assertEqual(helper.start_stop_button.text(), "STOP")
            self.assertTrue(helper.start_stop_button.isEnabled())
            self.assertTrue(helper.helper_log_overlay.loading_active)

            with patch.object(helper, "stop") as stop:
                helper.handle_hotkey()
            stop.assert_called_once_with()

            helper._handle_worker_output("__HELPER_READY__")
            self.app.processEvents()

            self.assertFalse(helper.starting)
            self.assertEqual(helper.start_stop_button.text(), "STOP")
            self.assertEqual(helper.start_stop_button.variant, "danger")
            self.assertTrue(helper.start_stop_button.isEnabled())
            self.assertFalse(helper.helper_log_overlay.loading_active)
        finally:
            helper.worker_process = None
            helper.close()

    def test_generic_helper_overlay_shows_paused_state_after_ready(self):
        with patch(
            "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            helper = AutoJoinServerHelper(self._worker_owner())

        try:
            helper._set_running_ui(True)
            overlay = helper.helper_log_overlay
            helper._handle_worker_output('__RUNNER_STATE__ {"state":"PAUSED"}')
            self.app.processEvents()

            self.assertTrue(overlay.loading_active)
            self.assertFalse(overlay.current_label.isHidden())
            self.assertEqual(overlay.current_label._full_text, "Loading helper...")

            helper._handle_worker_output("__HELPER_READY__")
            self.app.processEvents()

            self.assertFalse(overlay.loading_active)
            self.assertFalse(overlay.current_label.isHidden())
            self.assertEqual(overlay.current_label._full_text, "PAUSED")
            self.assertNotIn("__RUNNER_STATE__", helper.worker_debug_lines)

            helper._handle_worker_output('__RUNNER_STATE__ {"state":"RUNNING"}')
            self.app.processEvents()

            self.assertTrue(overlay.current_label.isHidden())
            self.assertEqual(helper.runner_state, "RUNNING")

            helper._handle_worker_output('__RUNNER_STATE__ {"state":"INVALID"}')
            helper._handle_worker_output("__RUNNER_STATE__ invalid")
            self.app.processEvents()

            self.assertEqual(helper.runner_state, "RUNNING")
            self.assertFalse(helper.worker_debug_lines)
        finally:
            helper.close()

    def test_auto_join_afk_join_defaults_enabled_and_passes_flag(self):
        with patch(
            "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            helper = AutoJoinServerHelper(self._worker_owner())

        try:
            self.assertTrue(helper.afk_join_switch.isChecked())
            helper.server_field.setCurrentText("5147")
            with (
                patch("source.launcher.auto_join_server_helper.focus_game_window"),
                patch(
                    "source.launcher.auto_join_server_helper.remember_auto_join_server",
                    return_value=["5147"],
                ),
                patch(
                    "source.launcher.auto_join_server_helper.save_auto_join_afk_join"
                ) as save_afk,
                patch.object(helper, "_start_worker") as start_worker,
            ):
                helper.start()

            save_afk.assert_called_once_with(True)
            start_worker.assert_called_once_with(
                "auto_join_server", "--server", "5147", "--afk-join"
            )
        finally:
            helper.close()

    def test_auto_join_afk_join_reload_on_show(self):
        with (
            patch(
                "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
                return_value=False,
            ),
            patch(
                "source.launcher.auto_join_server_helper.load_auto_join_afk_join",
                return_value=False,
            ),
        ):
            helper = AutoJoinServerHelper(self._worker_owner())

        try:
            helper.afk_join_switch.setChecked(True)
            with patch(
                "source.launcher.auto_join_server_helper.load_auto_join_afk_join",
                return_value=False,
            ) as load_afk:
                helper.show()
                self.app.processEvents()

            load_afk.assert_called_once_with()
            self.assertFalse(helper.afk_join_switch.isChecked())
        finally:
            helper.close()

    def test_auto_join_afk_join_disabled_passes_no_afk_flag(self):
        with patch(
            "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            helper = AutoJoinServerHelper(self._worker_owner())

        try:
            helper.afk_join_switch.setChecked(False)
            helper.server_field.setCurrentText("5147")
            with (
                patch("source.launcher.auto_join_server_helper.focus_game_window"),
                patch(
                    "source.launcher.auto_join_server_helper.remember_auto_join_server",
                    return_value=["5147"],
                ),
                patch(
                    "source.launcher.auto_join_server_helper.save_auto_join_afk_join"
                ) as save_afk,
                patch.object(helper, "_start_worker") as start_worker,
            ):
                helper.start()

            save_afk.assert_called_once_with(False)
            start_worker.assert_called_once_with(
                "auto_join_server", "--server", "5147", "--no-afk-join"
            )
        finally:
            helper.close()

    def test_auto_join_startup_failure_restores_start_button(self):
        with patch(
            "source.launcher.auto_join_server_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            helper = AutoJoinServerHelper(self._worker_owner())

        try:
            helper.server_field.setCurrentText("5147")
            with (
                patch("source.launcher.auto_join_server_helper.focus_game_window"),
                patch(
                    "source.launcher.auto_join_server_helper.remember_auto_join_server",
                    return_value=["5147"],
                ),
                patch.object(
                    helper,
                    "_start_worker",
                    side_effect=OSError("worker unavailable"),
                ),
            ):
                helper.start()

            self.assertFalse(helper.starting)
            self.assertEqual(helper.start_stop_button.text(), "START")
            self.assertTrue(helper.start_stop_button.isEnabled())
            self.assertEqual(helper.status.text(), "Cannot start: worker unavailable")
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
            self.assertFalse(helper.start_stop_button.isHidden())
            self.assertFalse(helper.status.isHidden())

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

    def test_fertilizer_starting_state_becomes_ready_stop_state(self):
        with patch(
            "source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            helper = FertilizerRefreshHelper(self._worker_owner())
        process = Mock()
        process.poll.return_value = None
        process.stdout = None

        def launch_worker(*_args):
            helper._set_running_ui(True)
            helper.worker_process = process

        try:
            with (
                patch("source.launcher.fertilizer_refresh_helper.focus_game_window"),
                patch.object(helper, "_start_worker", side_effect=launch_worker),
            ):
                helper.start()

            self.assertTrue(helper.starting)
            self.assertEqual(helper.start_stop_button.text(), "STOP")
            self.assertTrue(helper.start_stop_button.isEnabled())
            self.assertTrue(helper.helper_log_overlay.loading_active)

            with patch.object(helper, "stop") as stop:
                helper.handle_hotkey()
            stop.assert_called_once_with()

            helper._handle_worker_output("__HELPER_READY__")
            self.app.processEvents()

            self.assertFalse(helper.starting)
            self.assertEqual(helper.start_stop_button.text(), "STOP")
            self.assertEqual(helper.start_stop_button.variant, "danger")
            self.assertTrue(helper.start_stop_button.isEnabled())
            self.assertFalse(helper.helper_log_overlay.loading_active)
        finally:
            helper.worker_process = None
            helper.close()

    def test_fertilizer_startup_failure_restores_start_button(self):
        with patch(
            "source.launcher.fertilizer_refresh_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            helper = FertilizerRefreshHelper(self._worker_owner())

        try:
            with (
                patch("source.launcher.fertilizer_refresh_helper.focus_game_window"),
                patch.object(
                    helper,
                    "_start_worker",
                    side_effect=OSError("worker unavailable"),
                ),
            ):
                helper.start()

            self.assertFalse(helper.starting)
            self.assertEqual(helper.start_stop_button.text(), "START")
            self.assertTrue(helper.start_stop_button.isEnabled())
            self.assertEqual(helper.status.text(), "Cannot start: worker unavailable")
        finally:
            helper.close()

    def test_runner_overlay_uses_fixed_width_and_dynamic_content_height(self) -> None:
        owner = SimpleNamespace(
            screen=Mock(return_value=None),
            stop_program=Mock(),
        )
        overlay = RunnerOverlay(owner)

        try:
            overlay.show()
            self.app.processEvents()
            overlay.refresh({"running": [], "active": [], "waiting": []})
            self.app.processEvents()
            idle_height = overlay.height()

            overlay.refresh(
                {
                    "running": [{"name": "pego 1"}],
                    "active": [
                        {"name": "task 2", "execution_time": 0, "state": "READY"},
                        {"name": "task 3", "execution_time": 0, "state": "READY"},
                        {"name": "task 4", "execution_time": 0, "state": "READY"},
                    ],
                    "waiting": [],
                },
                [
                    "09:03:41 - DEBUG - open - open inventory 1/3",
                    "09:03:43 - DEBUG - open - open inventory 2/3",
                    "09:03:45 - DEBUG - open - open inventory 3/3",
                ],
            )
            self.app.processEvents()
            content_height = overlay.height()

            self.assertEqual(overlay.width(), RUNNER_WIDTH)
            self.assertEqual(overlay.minimumWidth(), RUNNER_WIDTH)
            self.assertEqual(overlay.maximumWidth(), RUNNER_WIDTH)
            self.assertGreater(content_height, idle_height)
            self.assertGreaterEqual(idle_height, HELPER_HEIGHT)
            self.assertEqual(
                [label.text() for label in overlay.upcoming_labels],
                ["task 2", "task 3", "task 4"],
            )
            self.assertEqual(
                [label._full_text for label in overlay.log_labels],
                [
                    "45 open inventory 3/3",
                    "43 open inventory 2/3",
                    "41 open inventory 1/3",
                ],
            )
            self.assertFalse(overlay.log_divider.isHidden())

            overlay.refresh({"running": [], "active": [], "waiting": []})
            self.app.processEvents()

            self.assertEqual(overlay.width(), RUNNER_WIDTH)
            self.assertEqual(overlay.height(), idle_height)
            self.assertTrue(overlay.log_divider.isHidden())
            self.assertTrue(all(label.isHidden() for label in overlay.log_labels))
        finally:
            overlay.close()

    def test_runner_overlay_loading_mode_is_spinner_only_and_idempotent(self) -> None:
        owner = SimpleNamespace(
            screen=Mock(return_value=None),
            stop_program=Mock(),
        )
        overlay = RunnerOverlay(owner)

        try:
            overlay.show()
            overlay.refresh_loading(
                ["09:03:45 - DEBUG - open - should stay hidden while loading"]
            )
            self.app.processEvents()
            loading_height = overlay.height()

            self.assertTrue(overlay.loading_spinner.timer.isActive())
            self.assertFalse(overlay.loading_spinner.isHidden())
            self.assertEqual(overlay.current_label._full_text, "Loading runner...")
            self.assertTrue(all(label.isHidden() for label in overlay.upcoming_labels))
            self.assertTrue(overlay.log_divider.isHidden())
            self.assertTrue(all(label.isHidden() for label in overlay.log_labels))

            with patch.object(overlay.loading_spinner.timer, "start") as start:
                overlay.refresh_loading()

            start.assert_not_called()
            self.assertEqual(overlay.height(), loading_height)

            overlay.refresh({"running": [{"name": "pego 1"}], "active": [], "waiting": []})
            self.app.processEvents()

            self.assertFalse(overlay.loading_spinner.timer.isActive())
            self.assertTrue(overlay.loading_spinner.isHidden())
            self.assertEqual(overlay.current_label._full_text, "pego 1")
        finally:
            overlay.close()

    def test_runner_overlay_elides_logs_updates_clock_and_stabilizes_geometry(
        self,
    ) -> None:
        owner = SimpleNamespace(
            screen=Mock(return_value=None),
            stop_program=Mock(),
        )
        overlay = RunnerOverlay(owner)
        long_current_task = (
            "currently running a very long task name that cannot fit inside the overlay"
        )
        long_upcoming_tasks = [
            "upcoming task one with a very long name that cannot fit inside the overlay",
            "upcoming task two with a very long name that cannot fit inside the overlay",
            "upcoming task three with a very long name that cannot fit inside the overlay",
        ]
        snapshot = {
            "running": [{"name": long_current_task}],
            "active": [
                {"name": name, "execution_time": 0, "state": "READY"}
                for name in long_upcoming_tasks
            ],
            "waiting": [],
        }
        long_log = (
            "16:07:33 - DEBUG - join_server - joining a server with a very long "
            "description that cannot fit inside the runner overlay"
        )

        try:
            overlay.show()
            with patch(
                "source.launcher.runner_overlay.time.strftime", return_value="14:21:04"
            ):
                overlay.refresh(snapshot, [long_log])
            self.app.processEvents()

            label = overlay.log_labels[0]
            self.assertEqual(overlay.clock_label.text(), "14:21:04")
            self.assertIs(overlay.clock_label.parent(), overlay.header_frame)
            self.assertGreater(
                overlay.clock_label.geometry().top(),
                overlay.header_title.geometry().top(),
            )
            self.assertFalse(label.wordWrap())
            self.assertTrue(label.text().startswith("33 joining"))
            self.assertTrue(label.text().endswith("..."))
            self.assertLessEqual(
                label.fontMetrics().horizontalAdvance(label.text()),
                label.contentsRect().width(),
            )
            task_labels = [overlay.current_label, *overlay.upcoming_labels]
            for task_label, full_text in zip(
                task_labels,
                [long_current_task, *long_upcoming_tasks],
            ):
                self.assertFalse(task_label.wordWrap())
                self.assertEqual(task_label._full_text, full_text)
                self.assertTrue(task_label.text().endswith("..."))
                self.assertLessEqual(
                    task_label.fontMetrics().horizontalAdvance(task_label.text()),
                    task_label.contentsRect().width(),
                )

            stable_geometry = overlay.geometry()
            for _ in range(3):
                with patch(
                    "source.launcher.runner_overlay.time.strftime",
                    return_value="14:21:04",
                ):
                    overlay.refresh(snapshot, [long_log])
                self.app.processEvents()
                self.assertEqual(overlay.geometry(), stable_geometry)

            overlay.refresh(
                snapshot,
                ["16:07:33 - DEBUG - join_server - short message"],
            )
            self.app.processEvents()
            self.assertEqual(label.text(), "33 short message")
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
                "depositGeneralData": [{
                    "teleport": "CRAFT1", "check_on_every_dedi": 3,
                    "dedi": {"items": [{"location": {"yaw": 3.0, "pitch": 4.0}, "crouched": False}]},
                }],
            },
            craft_config={"generalCraftData": [{
                "teleport": "CRAFT1", "check_on_every_dedi": 3,
                "crafters": [{"location": {"yaw": 1.0, "pitch": 2.0}, "crouched": False, "item": "polymer"}],
                "dedi": {"items": []},
            }]},
            save_deposit_routes=Mock(return_value=True),
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

    def test_general_and_craft_helpers_edit_and_save_separate_configs(self):
        owner = self._owner()
        owner.save_craft_routes = Mock(return_value=True)
        with patch(
            "source.launcher.deposit_route_helper.register_alt_n_hotkey",
            return_value=False,
        ):
            craft = DepositRouteHelper(owner, "craft", 0)
            general = DepositRouteHelper(owner, "general", 0)
        try:
            self.assertEqual(craft._title(), "General Craft: CRAFT1")
            self.assertEqual(general._title(), "General dedi: CRAFT1")
            self.assertEqual([(row.kind, row.index) for row in craft.row_widgets], [("crafter", 0)])
            self.assertEqual([(row.kind, row.index) for row in general.row_widgets], [("dedi", 0)])
            crafted = craft.add_entry("dedi")
            self.assertIsNotNone(crafted)
            self.assertEqual(len(craft.route()["dedi"]["items"]), 1)
            self.assertEqual(len(general.route()["dedi"]["items"]), 1)
            owner.save_craft_routes.assert_called_once_with(show_log=False)
            owner.save_deposit_routes.assert_not_called()
            craft.update_crafter_item(craft.route()["crafters"][0], SimpleNamespace(text=lambda: "element"))
            self.assertEqual(craft.route()["crafters"][0]["item"], "element")
            self.assertNotIn("active", craft.route()["crafters"][0])
            general.update_float(general.route()["dedi"]["items"][0], "yaw", SimpleNamespace(text=lambda: "42"))
            owner.save_deposit_routes.assert_called_once_with(show_log=False)
            self.assertEqual(craft.route()["dedi"]["items"][0]["location"]["yaw"], 0)
            self.assertEqual(general.route()["dedi"]["items"][0]["location"]["yaw"], 42)
            craft.delete_entry("crafter", 0)
            self.assertEqual(craft.route()["crafters"], [])
        finally:
            craft.close()
            general.close()


if __name__ == "__main__":
    unittest.main()
