import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from source.launcher.transfer_helper_config import (
    normalize_transfer_dedis,
    normalize_transfer_players,
    normalize_transfer_settings,
)
from source.gacha_bot.deposit_config import default_deposit_config, normalize_deposit_config
from source.launcher.controllers.helpers.auto_join_helper_controller import (
    AutoJoinHelperController,
)
from source.launcher.controllers.helpers.fertilizer_helper_controller import (
    FertilizerHelperController,
)
from source.launcher.controllers.helpers.helper_window_controller import (
    HelperWindowController,
)


def _runtime_config():
    return {
        "settings": normalize_transfer_settings(
            {
                "resource_server": "1",
                "destination_server": "2",
                "transmitter_teleport": "TX",
            }
        ),
        "dedis": normalize_transfer_dedis(
            {
                "resource": {"teleport": "SRC", "items": []},
                "destination": {"teleport": "DST", "items": []},
            }
        ),
        "ui_coords": {},
        "players": normalize_transfer_players(
            {"players": [{"bed_name": "Player1"}]}, 1
        ),
    }


class QmlHelperControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle("Basic")
        cls.app = QApplication.instance() or QApplication([])

    def make_transfer_controller(self):
        from source.launcher.controllers.helpers import transfer_helper_controller

        launcher = SimpleNamespace(
            is_running=Mock(return_value=False),
            program_stopping=False,
            require_ark_window=Mock(return_value=True),
        )
        config = _runtime_config()
        patches = [
            patch.object(
                transfer_helper_controller,
                "load_transfer_runtime_config",
                return_value=config,
            ),
            patch.object(
                transfer_helper_controller,
                "save_transfer_players",
                side_effect=lambda data, account_count=1: normalize_transfer_players(
                    data, account_count
                ),
            ),
            patch.object(
                transfer_helper_controller,
                "save_transfer_settings",
                side_effect=normalize_transfer_settings,
            ),
            patch.object(
                transfer_helper_controller,
                "save_transfer_dedis",
                side_effect=normalize_transfer_dedis,
            ),
        ]
        started = [patcher.start() for patcher in patches]
        self.addCleanup(lambda: [patcher.stop() for patcher in patches])
        controller = transfer_helper_controller.TransferHelperController(launcher)
        return controller, launcher, started

    def make_auto_join_controller(self):
        launcher = SimpleNamespace(
            is_running=Mock(return_value=False),
            program_stopping=False,
            require_ark_window=Mock(return_value=True),
        )
        settings = SimpleNamespace(serverNumber="5147", setValue=Mock())
        return AutoJoinHelperController(launcher, settings), settings

    def test_worker_helper_stop_keeps_finished_status(self):
        launcher = SimpleNamespace(
            is_running=Mock(return_value=False),
            program_stopping=False,
            require_ark_window=Mock(return_value=True),
        )
        controller = FertilizerHelperController(launcher)

        controller.worker._process = SimpleNamespace(poll=Mock(return_value=None), stdout=None)

        with patch(
            "source.launcher.services.worker_process_service.terminate_process_tree"
        ):
            controller.stop()

        self.assertEqual(controller.status, "Stopped.")

    def test_auto_join_valid_server_edit_persists_to_launcher_settings(self):
        controller, settings = self.make_auto_join_controller()

        controller.setServerNumber(" 1234 ")

        self.assertEqual(controller.serverNumber, "1234")
        settings.setValue.assert_called_once_with("server_number", "1234")

    def test_auto_join_invalid_server_edit_does_not_overwrite_settings(self):
        controller, settings = self.make_auto_join_controller()

        controller.setServerNumber("abc")

        self.assertEqual(controller.serverNumber, "abc")
        settings.setValue.assert_not_called()

    def test_transfer_controller_account_count_resize_uses_helper_defaults(self):
        controller, _launcher, _patches = self.make_transfer_controller()

        controller.resizePlayers(3)

        self.assertEqual(
            controller.config["players"],
            {
                "players": [
                    {"bed_name": "Player1"},
                    {"bed_name": "BBedPlayer2"},
                    {"bed_name": "BBedPlayer3"},
                ]
            },
        )

    def test_transfer_controller_copies_player_name(self):
        controller, _launcher, _patches = self.make_transfer_controller()

        controller.copyPlayerName(0)

        self.assertEqual(QApplication.clipboard().text(), "Player1")

    def test_transfer_controller_rejects_unknown_player_index(self):
        controller, _launcher, _patches = self.make_transfer_controller()
        QApplication.clipboard().setText("unchanged")
        original = [dict(player) for player in controller.config["players"]["players"]]

        controller.updatePlayer("bed_name", -1, "Changed")
        controller.removePlayer(4)
        controller.copyPlayerName(4)

        self.assertEqual(controller.config["players"]["players"], original)
        self.assertEqual(QApplication.clipboard().text(), "unchanged")
        self.assertEqual(controller.status, "Unknown transfer player index.")

    def test_transfer_controller_capture_setting_yaw_persists_yaw_only(self):
        controller, launcher, _patches = self.make_transfer_controller()

        with patch(
            "source.launcher.controllers.helpers.transfer_helper_controller.capture_ccc_yaw_pitch",
            return_value=(123.45, 67.89),
        ):
            controller.captureSettingYaw("resource_station_yaw")

        launcher.require_ark_window.assert_called_once_with("capture transfer yaw")
        self.assertEqual(controller.config["settings"]["resource_station_yaw"], 123.45)

    def test_transfer_invalid_setting_does_not_mutate_active_config(self):
        controller, _launcher, _patches = self.make_transfer_controller()
        original_loop_count = controller.config["settings"]["loop_count"]
        dialogs = []
        controller.dialogRequested.connect(
            lambda title, message, variant: dialogs.append((title, message, variant))
        )

        with patch(
            "source.launcher.controllers.helpers.transfer_helper_controller.save_transfer_settings",
            side_effect=ValueError("loop_count must be an integer."),
        ):
            controller.updateSetting("loop_count", "bad")

        self.assertEqual(controller.config["settings"]["loop_count"], original_loop_count)
        self.assertEqual(
            dialogs,
            [
                (
                    "Invalid Transfer Settings",
                    "loop_count must be an integer.",
                    "error",
                )
            ],
        )
        self.assertEqual(
            controller.status,
            "Settings save failed: loop_count must be an integer.",
        )

    def test_transfer_loop_hint_uses_runtime_account_cap(self):
        controller, _launcher, _patches = self.make_transfer_controller()
        controller.config["dedis"]["resource"]["items"] = [
            {"location": {"yaw": 0, "pitch": 0}, "crouched": False}
            for _ in range(5)
        ]
        controller.config["players"] = normalize_transfer_players(
            {"players": [{"bed_name": f"Player{i}"} for i in range(1, 6)]},
            5,
        )

        self.assertIn("5 dedi x 4 account", controller.loopHint)
        self.assertIn("Only first 4 account(s) run", controller.loopHint)

    def test_transfer_player_conflict_after_runtime_cap_does_not_block_start(self):
        controller, _launcher, _patches = self.make_transfer_controller()
        controller.config["players"] = normalize_transfer_players(
            {
                "players": [
                    {"bed_name": "Player1"},
                    {"bed_name": "Player2"},
                    {"bed_name": "Player3"},
                    {"bed_name": "Player4"},
                    {"bed_name": "Player"},
                ]
            },
            5,
        )
        controller.config["dedis"]["resource"]["items"] = [
            {"location": {"yaw": 0, "pitch": 0}, "crouched": False}
        ]
        controller.config["dedis"]["destination"]["items"] = [
            {"location": {"yaw": 0, "pitch": 0}, "crouched": False}
        ]
        dialogs = []
        controller.dialogRequested.connect(
            lambda title, message, variant: dialogs.append((title, message, variant))
        )

        with (
            patch(
                "source.launcher.controllers.helpers.transfer_helper_controller.missing_runtime_inputs",
                return_value=[],
            ),
            patch.object(controller, "_can_start", return_value=False) as can_start,
        ):
            controller.start()

        can_start.assert_called_once_with("start server transfer")
        self.assertEqual(dialogs, [])

    def test_transfer_controller_blocks_removing_last_dedi(self):
        controller, _launcher, _patches = self.make_transfer_controller()
        controller.config["dedis"]["resource"]["items"] = [
            {"location": {"yaw": 0, "pitch": 0}, "crouched": False}
        ]

        controller.removeDedi("resource", 0)

        self.assertEqual(len(controller.config["dedis"]["resource"]["items"]), 1)
        self.assertEqual(controller.status, "At least one transfer dedi row is required.")

    def test_transfer_controller_rejects_unknown_dedi_side(self):
        controller, launcher, _patches = self.make_transfer_controller()
        original = controller.config["dedis"].copy()

        controller.setTeleport("missing", "TP")
        controller.addDedi("missing")
        controller.removeDedi("missing", 0)
        controller.updateDedi("missing", 0, "yaw", "1")
        controller.captureDedi("missing", 0)
        controller.viewDedi("missing", 0)

        self.assertEqual(controller.config["dedis"], original)
        self.assertEqual(controller.status, "Unknown transfer dedi side.")
        launcher.require_ark_window.assert_not_called()

    def test_transfer_controller_rejects_unknown_dedi_index_before_ark_focus(self):
        controller, launcher, _patches = self.make_transfer_controller()
        controller.config["dedis"]["resource"]["items"] = [
            {"location": {"yaw": 1, "pitch": 2}, "crouched": False}
        ]
        original = [dict(item) for item in controller.config["dedis"]["resource"]["items"]]

        controller.removeDedi("resource", 3)
        controller.updateDedi("resource", 3, "yaw", "99")
        controller.captureDedi("resource", 3)
        controller.viewDedi("resource", 3)

        self.assertEqual(controller.config["dedis"]["resource"]["items"], original)
        self.assertEqual(controller.status, "Unknown transfer dedi index.")
        launcher.require_ark_window.assert_not_called()

    def make_deposit_controller(self):
        from source.launcher.controllers.helpers import deposit_route_helper_controller

        launcher = SimpleNamespace(require_ark_window=Mock(return_value=True))
        config = default_deposit_config("CRYSTAL", "GRIND")
        patches = [
            patch.object(
                deposit_route_helper_controller,
                "load_deposit_config",
                return_value=config,
            ),
            patch.object(
                deposit_route_helper_controller,
                "save_deposit_config",
                side_effect=normalize_deposit_config,
            ),
            patch.object(
                deposit_route_helper_controller,
                "add_vault_item",
                side_effect=lambda _item, _config: [],
            ),
        ]
        [patcher.start() for patcher in patches]
        self.addCleanup(lambda: [patcher.stop() for patcher in patches])
        controller = deposit_route_helper_controller.DepositRouteHelperController(
            launcher
        )
        return controller, launcher

    def test_deposit_controller_capture_new_dedi_appends_captured_row(self):
        controller, launcher = self.make_deposit_controller()

        with patch(
            "source.launcher.controllers.helpers.deposit_route_helper_controller.capture_ccc_yaw_pitch",
            return_value=(11.5, 22.5),
        ):
            controller.captureNewRow("dedi")

        launcher.require_ark_window.assert_called_once_with("capture route location")
        row = controller._config["depositCrystalData"][0]["dedi"]["items"][0]
        self.assertEqual(row["location"], {"yaw": 11.5, "pitch": 22.5})

    def test_deposit_controller_add_vault_item_uses_known_item_list(self):
        controller, _launcher = self.make_deposit_controller()
        controller.addRow("vault")

        controller.addVaultItem(0, "riot")

        row = controller._config["depositCrystalData"][0]["vault"]["items"][0]
        self.assertEqual(row["items"], ["riot"])

    def test_deposit_controller_removes_vault_item(self):
        controller, _launcher = self.make_deposit_controller()
        controller.addRow("vault")
        controller.addVaultItem(0, "riot")
        controller.addVaultItem(0, "hide")

        controller.removeVaultItem(0, 0)

        row = controller._config["depositCrystalData"][0]["vault"]["items"][0]
        self.assertEqual(row["items"], ["hide"])

    def test_deposit_controller_rejects_unknown_row_kind(self):
        controller, _launcher = self.make_deposit_controller()

        controller.addRow("banana")

        route = controller._config["depositCrystalData"][0]
        self.assertEqual(route["dedi"]["items"], [])
        self.assertEqual(route["vault"]["items"], [])
        self.assertEqual(controller.status, "Unknown deposit row type.")

    def test_deposit_controller_rejects_invalid_row_indexes(self):
        controller, launcher = self.make_deposit_controller()
        controller.addRow("dedi")
        original_rows = list(controller._config["depositCrystalData"][0]["dedi"]["items"])

        controller.removeRow("dedi", "bad")
        controller.updateRow("dedi", "bad", "yaw", "12")
        controller.captureRow("dedi", "bad")
        controller.viewRow("dedi", "bad")

        self.assertEqual(
            controller._config["depositCrystalData"][0]["dedi"]["items"],
            original_rows,
        )
        self.assertEqual(controller.status, "Unknown deposit row index.")
        launcher.require_ark_window.assert_not_called()

    def test_deposit_controller_rejects_invalid_vault_indexes(self):
        controller, _launcher = self.make_deposit_controller()
        controller.addRow("vault")
        controller.addVaultItem(0, "riot")
        original_items = list(
            controller._config["depositCrystalData"][0]["vault"]["items"][0]["items"]
        )

        controller.addVaultItem("bad", "hide")
        controller.removeVaultItem("bad", 0)
        controller.removeVaultItem(0, "bad")

        vault_row = controller._config["depositCrystalData"][0]["vault"]["items"][0]
        self.assertEqual(vault_row["items"], original_items)
        self.assertEqual(controller.status, "Unknown vault item index.")

    def test_deposit_controller_adds_routes_and_blocks_last_route_removal(self):
        controller, _launcher = self.make_deposit_controller()

        self.assertFalse(controller.canRemoveRoute)

        controller.addRoute("crystal")

        self.assertTrue(controller.canRemoveRoute)
        self.assertEqual(controller.routeKind, "crystal")
        self.assertEqual(len(controller._config["depositCrystalData"]), 2)

        controller.removeCurrentRoute()

        self.assertFalse(controller.canRemoveRoute)
        self.assertEqual(len(controller._config["depositCrystalData"]), 1)

        controller.removeCurrentRoute()

        self.assertEqual(len(controller._config["depositCrystalData"]), 1)
        self.assertEqual(controller.status, "At least one route of each type is required.")

    def test_deposit_controller_rejects_unknown_route_kind(self):
        controller, _launcher = self.make_deposit_controller()

        controller.selectRoute("banana", 0)

        self.assertEqual(controller.routeKind, "crystal")
        self.assertEqual(controller.routeIndex, 0)
        self.assertEqual(controller.status, "Unknown deposit route type.")

    def test_deposit_controller_rejects_unknown_route_index(self):
        controller, _launcher = self.make_deposit_controller()

        controller.selectRoute("grindable", 99)

        self.assertEqual(controller.routeKind, "crystal")
        self.assertEqual(controller.routeIndex, 0)
        self.assertEqual(controller.status, "Unknown deposit route index.")

    def test_helper_hotkey_toggles_worker_helper_and_focuses_plain_helper(self):
        controller = HelperWindowController()
        toggles = []
        focuses = []
        controller.toggleRequested.connect(toggles.append)
        controller.focusRequested.connect(lambda: focuses.append(True))

        controller.openHelper("autoJoin", {})
        controller.handleHotkey()
        controller.openHelper("position", {})
        controller.handleHotkey()

        self.assertEqual(toggles, ["autoJoin"])
        self.assertEqual(focuses, [True])

    def test_helper_controller_ignores_unknown_helper_names(self):
        controller = HelperWindowController()
        requested = []
        closed = []
        controller.helperRequested.connect(
            lambda name, payload: requested.append((name, payload))
        )
        controller.closeRequested.connect(lambda: closed.append(True))

        controller.openHelper("autoJoin", {})
        controller.openHelper("missing", {})

        self.assertEqual(controller.activeHelperName, "autoJoin")
        self.assertEqual(requested, [("autoJoin", {})])
        self.assertEqual(closed, [])

    def test_helper_close_clears_hotkey_dispatch_state(self):
        controller = HelperWindowController()
        toggles = []
        controller.toggleRequested.connect(toggles.append)

        controller.openHelper("fertilizer", {})
        controller.closeActiveHelper()
        controller.handleHotkey()

        self.assertEqual(controller.activeHelperName, "")
        self.assertEqual(toggles, [])

    def test_helper_hotkey_registers_and_unregisters_with_window(self):
        controller = HelperWindowController()
        window = SimpleNamespace(winId=Mock(return_value=1234))

        with (
            patch(
                "source.launcher.controllers.helpers.helper_window_controller.ctypes"
            ) as ctypes_module,
            patch(
                "source.launcher.controllers.helpers.helper_window_controller.register_alt_n_hotkey",
                return_value=True,
            ) as register,
            patch(
                "source.launcher.controllers.helpers.helper_window_controller.unregister_hotkey"
            ) as unregister,
        ):
            ctypes_module.windll = object()
            controller.registerWindow(window)
            self.assertTrue(controller.hotkeyRegistered)
            register.assert_called_once_with(1234, controller.hotkeyId)

            controller.shutdown()

        unregister.assert_called_once_with(1234, controller.hotkeyId)
        self.assertFalse(controller.hotkeyRegistered)
