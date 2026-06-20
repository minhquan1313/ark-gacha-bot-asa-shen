import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QSizePolicy, QWidget

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
from source.launcher import server_transfer_helper as server_transfer_helper_module
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
                    "loop_count": 1,
                    "structure_load_delay": 10,
                    "transfer_retry_delay": 5,
                },
                "players": {"players": [{"bed_name": "Player1"}]},
                "dedis": {
                    "teleport": "",
                    "items": [
                        {
                            "location": {"yaw": 0, "pitch": 0},
                            "crouched": False,
                        }
                    ],
                },
                "ui_coords": {},
            },
        ):
            helper = ServerTransferHelper(owner)

        with patch.object(
            helper, "setFixedWidth", wraps=helper.setFixedWidth
        ) as set_fixed_width:
            helper._set_running_ui(True)

        self.assertTrue(helper.idle_widget.isHidden())
        self.assertFalse(helper.running_widget.isHidden())
        self.assertEqual(helper.width(), helper.idle_width)
        set_fixed_width.assert_called_once_with(helper.idle_width)
        self.assertEqual(helper.hotkey_label.text(), "ALT + N stops this helper")

        helper._set_running_ui(False)

        self.assertFalse(helper.idle_widget.isHidden())
        self.assertTrue(helper.running_widget.isHidden())
        self.assertEqual(helper.width(), helper.idle_width)
        self.assertEqual(helper.hotkey_label.text(), "ALT + N toggles START / STOP")

    def test_player_rows_follow_account_count_with_editable_names(self):
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

            helper.setting_fields["account_count"].setText("2")
            helper._refresh_player_rows()

            self.assertEqual(
                [row["name"].text() for row in helper.player_rows],
                ["Player1", "Player2"],
            )
        finally:
            helper.close()

    def test_transfer_cards_default_collapsed_and_dedi_has_no_enabled_switch(self):
        helper = self._transfer_helper(account_count=1)

        try:
            self.assertTrue(server_transfer_helper_module.DEFAULT_PANELS_EXPANDED)
            bodies = helper.findChildren(QWidget, "DepositRouteCardBody")
            self.assertGreaterEqual(len(bodies), 3)
            self.assertTrue(all(not body.isHidden() for body in bodies))
            self.assertNotIn("enabled", helper.dedi_rows[0])
            self.assertEqual(
                helper.loop_hint.text(), "1 dedi x 1 account = 6 suggested loop(s)."
            )
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
            titles = [label.text() for label in helper.findChildren(QLabel, "PanelTitle")]

            self.assertIn("RESOURCE DEDIS", titles)
            self.assertIn("DESTINATION DEDIS", titles)
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
                    },
                    account_count=2,
                )
            finally:
                helper.close()

    def test_account_count_edit_resizes_and_saves_players_json(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_players",
            side_effect=lambda data, account_count=1: data,
        ) as save_players:
            helper = self._transfer_helper(account_count=1)

            try:
                helper.setting_fields["account_count"].setText("3")
                helper._refresh_player_rows(persist=True)

                self.assertEqual(len(helper.player_rows), 3)
                save_players.assert_called_with(
                    {
                        "players": [
                            {"bed_name": "Player1", "steam_account": "steam1"},
                            {"bed_name": "BBedPlayer2", "steam_account": ""},
                            {"bed_name": "BBedPlayer3", "steam_account": ""},
                        ]
                    },
                    account_count=3,
                )
            finally:
                helper.close()

    def test_account_count_zero_resets_players_json(self):
        with patch(
            "source.launcher.server_transfer_helper.save_transfer_players",
            side_effect=lambda data, account_count=1: data,
        ) as save_players:
            helper = self._transfer_helper(account_count=1)

            try:
                helper.setting_fields["account_count"].setText("0")
                helper._refresh_player_rows(persist=True)

                self.assertEqual(helper.player_rows, [])
                save_players.assert_called_with({"players": []}, account_count=0)
                self.assertEqual(
                    helper.loop_hint.text(),
                    "1 dedi x 0 account = no runnable accounts.",
                )
            finally:
                helper.close()

    def test_start_blocks_zero_players_before_runtime_validation(self):
        helper = self._transfer_helper(account_count=0)

        try:
            helper.start()

            helper.owner.dialog.assert_called_once()
            self.assertEqual(helper.status.text(), "Add at least one player before starting.")
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
            finally:
                helper.close()

    def test_transfer_helper_expand_and_collapse_all_affects_panels_and_dedis(self):
        helper = self._transfer_helper(account_count=1)

        try:
            helper.set_all_collapsible_expanded(False)

            self.assertTrue(all(panel.body_widget.isHidden() for panel in helper.collapsible_panels))
            self.assertTrue(all(row["details"].isHidden() for row in helper.resource_dedi_rows + helper.destination_dedi_rows))

            helper.set_all_collapsible_expanded(True)

            self.assertTrue(all(not panel.body_widget.isHidden() for panel in helper.collapsible_panels))
            self.assertTrue(all(not row["details"].isHidden() for row in helper.resource_dedi_rows + helper.destination_dedi_rows))
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
                helper._persist_settings()

                saved = save_settings.call_args.args[0]
                self.assertEqual(saved["resource_server"], "1234")
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
                    save_dedis.call_args.args[0]["resource"]["items"][0]["location"]["yaw"],
                    "44",
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
                    save_dedis.call_args.args[0]["destination"]["items"][0][
                        "location"
                    ]["yaw"],
                    "88",
                )
                self.assertEqual(
                    save_dedis.call_args.args[0]["resource"]["items"][0][
                        "location"
                    ]["yaw"],
                    "0.0",
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
            "source.launcher.deposit_helper_capture.validate_ark_window",
            side_effect=RuntimeError("ARK missing"),
        ):
            helper = self._transfer_helper(account_count=1)

        try:
            self.assertEqual(helper.status.text(), "Ready.")
        finally:
            helper.close()

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

    def _transfer_helper(self, account_count=1, player_names=None, dedi_items=None):
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
        steam_accounts = [
            {"account_name": f"steam{i}", "most_recent": i == 1, "timestamp": 20 - i}
            for i in range(1, 13)
        ]
        with (
            patch(
                "source.launcher.server_transfer_helper.load_transfer_runtime_config",
                return_value={
                    "settings": {
                        "lag_offset": 1,
                        "resource_station_yaw": 0,
                        "destination_station_yaw": 0,
                        "transmitter_teleport": "",
                        "resource_server": "0",
                        "destination_server": "0",
                        "loop_count": 1,
                        "structure_load_delay": 10,
                        "transfer_retry_delay": 5,
                    },
                    "players": {
                        "players": [
                            {"bed_name": name, "steam_account": f"steam{index + 1}"}
                            for index, name in enumerate(player_names[:account_count])
                        ]
                    },
                    "dedis": {
                        "teleport": "",
                        "items": dedi_items,
                    },
                    "ui_coords": {},
                },
            ),
            patch(
                "source.launcher.server_transfer_helper.load_steam_accounts",
                return_value=steam_accounts,
            ),
        ):
            return ServerTransferHelper(owner)

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

            self.assertEqual(overlay.width(), 200)
            self.assertEqual(overlay.minimumWidth(), 200)
            self.assertEqual(overlay.maximumWidth(), 200)
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
