import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QMetaObject, QPoint, QPointF, Qt, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from source.launcher.constants import ASSETS
from source.launcher.controllers.launcher_controller import LauncherController
from source.launcher.controllers.log_controller import LogController
from source.launcher.controllers.queue_controller import QueueController
from source.launcher.controllers.settings_controller import SettingsController
from source.launcher.controllers.tools_controller import ToolsController
from source.launcher.controllers.helpers.auto_join_helper_controller import (
    AutoJoinHelperController,
)
from source.launcher.controllers.helpers.deposit_route_helper_controller import (
    DepositRouteHelperController,
)
from source.launcher.controllers.helpers.fertilizer_helper_controller import (
    FertilizerHelperController,
)
from source.launcher.controllers.helpers.helper_window_controller import (
    HelperWindowController,
)
from source.launcher.controllers.helpers.position_render_helper_controller import (
    PositionRenderHelperController,
)
from source.launcher.controllers.helpers.transfer_helper_controller import (
    TransferHelperController,
)


class RunningProcess:
    def poll(self):
        return None


class StoppableProcess:
    stdout = None
    pid = -1

    def __init__(self):
        self.terminated = False
        self.killed = False

    def poll(self):
        return 1 if self.terminated or self.killed else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.terminated = True
        return 1

    def kill(self):
        self.killed = True


class QmlLauncherSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle("Basic")
        cls.app = QApplication.instance() or QApplication([])

    def make_engine(self):
        settings = SettingsController()
        queue = QueueController()
        logs = LogController()
        tools = ToolsController()
        helpers = HelperWindowController()
        launcher = LauncherController(settings, logs, queue, helpers)
        auto_join = AutoJoinHelperController(launcher, settings)
        fertilizer = FertilizerHelperController(launcher)
        position = PositionRenderHelperController(launcher, settings)
        deposit = DepositRouteHelperController(launcher)
        transfer = TransferHelperController(launcher)
        engine = QQmlApplicationEngine()
        engine._controller_refs = [
            settings,
            queue,
            logs,
            tools,
            helpers,
            launcher,
            auto_join,
            fertilizer,
            position,
            deposit,
            transfer,
        ]
        context = engine.rootContext()
        context.setContextProperty("launcherController", launcher)
        context.setContextProperty("settingsController", settings)
        context.setContextProperty("logController", logs)
        context.setContextProperty("queueController", queue)
        context.setContextProperty("toolsController", tools)
        context.setContextProperty("helperWindowController", helpers)
        context.setContextProperty("autoJoinHelperController", auto_join)
        context.setContextProperty("fertilizerHelperController", fertilizer)
        context.setContextProperty("positionRenderHelperController", position)
        context.setContextProperty("depositRouteHelperController", deposit)
        context.setContextProperty("transferHelperController", transfer)
        context.setContextProperty(
            "assetPaths",
            {
                key: QUrl.fromLocalFile(os.path.abspath(path)).toString()
                for key, path in ASSETS.items()
            },
        )
        engine.load(
            QUrl.fromLocalFile(
                os.path.abspath(os.path.join("source", "launcher", "qml", "Main.qml"))
            )
        )
        return engine, launcher, helpers

    def test_main_qml_loads_with_registered_controllers(self):
        engine, launcher, _helpers = self.make_engine()

        try:
            self.assertEqual(len(engine.rootObjects()), 1)
        finally:
            launcher.shutdown()

    def test_dashboard_stats_and_key_pages_have_visible_content_objects(self):
        engine, launcher, _helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            values = [
                item.property("text")
                for item in root.findChildren(QObject, "StatCardValue")
            ]
            self.assertGreaterEqual(len([value for value in values if value != ""]), 4)
            self.assertTrue(root.findChild(QObject, "SettingsTabs"))
            self.assertTrue(root.findChild(QObject, "SetupStepsCard"))
            self.assertTrue(root.findChild(QObject, "SetupDetailCard"))
            self.assertTrue(root.findChild(QObject, "MemoryMeter"))
            self.assertTrue(root.findChild(QObject, "CpuMeter"))
            self.assertTrue(root.findChild(QObject, "AboutCard"))
            self.assertTrue(root.findChild(QObject, "UpdateCard"))
        finally:
            launcher.shutdown()

    def test_dashboard_auto_start_control_reflects_allowed_state(self):
        engine, launcher, _helpers = self.make_engine()
        root = engine.rootObjects()[0]
        settings = engine._controller_refs[0]

        try:
            settings._settings["auto_start_program"] = True
            settings._settings["server_number"] = "0"
            launcher.changed.emit()
            self.app.processEvents()
            switch = root.findChild(QObject, "AutoStartSwitch")
            hint = root.findChild(QObject, "AutoStartHint")
            self.assertFalse(switch.property("enabled"))
            self.assertFalse(switch.property("checked"))
            self.assertEqual(hint.property("text"), "Set server number first")

            settings._settings["server_number"] = "5147"
            launcher.changed.emit()
            self.app.processEvents()
            self.assertTrue(switch.property("enabled"))
            self.assertTrue(switch.property("checked"))
        finally:
            launcher.shutdown()

    def test_key_pages_render_visible_bounded_layouts(self):
        engine, launcher, _helpers = self.make_engine()
        root = engine.rootObjects()[0]
        root.show()

        try:
            launcher.showPage("settings")
            self.app.processEvents()
            QTest.qWait(50)
            tabs = root.findChild(QObject, "SettingsTabs")
            content = root.findChild(QObject, "SettingsContent")
            self.assertTrue(tabs.property("visible"))
            self.assertTrue(content.property("visible"))
            self.assertGreater(tabs.property("width"), 0)
            self.assertGreater(content.property("width"), 0)
            self.assertLessEqual(
                tabs.property("x") + tabs.property("width"),
                content.property("x"),
            )
            launcher.showPage("update")
            self.app.processEvents()
            QTest.qWait(50)
            update_card = root.findChild(QObject, "UpdateCard")
            self.assertTrue(update_card.property("visible"))
            self.assertGreater(update_card.property("width"), 0)
            self.assertGreater(update_card.property("height"), 0)
            update_latest = root.findChild(QObject, "UpdateLatest")
            self.assertIn("Manual check required", update_latest.property("text"))
            self.assertNotIn("Update available", update_latest.property("text"))
            update_detail = root.findChild(QObject, "UpdateDetail")
            self.assertIn("update endpoint", update_detail.property("text"))

            launcher.showPage("setup")
            self.app.processEvents()
            QTest.qWait(50)
            setup_steps = root.findChild(QObject, "SetupStepsCard")
            setup_detail = root.findChild(QObject, "SetupDetailCard")
            self.assertTrue(setup_steps.property("visible"))
            self.assertTrue(setup_detail.property("visible"))
            self.assertGreater(setup_steps.property("width"), 0)
            self.assertGreater(setup_detail.property("width"), 0)

            launcher.showPage("about")
            self.app.processEvents()
            QTest.qWait(50)
            about_card = root.findChild(QObject, "AboutCard")
            self.assertTrue(about_card.property("visible"))
            self.assertGreater(about_card.property("width"), 0)
            self.assertGreater(about_card.property("height"), 0)
            github_button = root.findChild(QObject, "AboutGithubButton")
            website_button = root.findChild(QObject, "AboutWebsiteButton")
            links_status = root.findChild(QObject, "AboutLinksStatus")
            self.assertTrue(github_button.property("enabled"))
            self.assertTrue(website_button.property("enabled"))
            self.assertIn("not configured", links_status.property("text"))
            dialog = root.findChild(QObject, "AppDialog")
            click_pos = github_button.mapToScene(
                QPointF(
                    github_button.property("width") / 2,
                    github_button.property("height") / 2,
                )
            )
            QTest.mouseClick(
                root,
                Qt.LeftButton,
                Qt.NoModifier,
                QPoint(int(click_pos.x()), int(click_pos.y())),
            )
            self.app.processEvents()
            QTest.qWait(50)
            self.assertTrue(dialog.property("opened"))
            self.assertEqual(dialog.property("title"), "GITHUB")
            self.assertIn("not configured", dialog.property("message"))
        finally:
            launcher.shutdown()

    def test_settings_groups_render_helper_entry_actions(self):
        engine, launcher, _helpers = self.make_engine()
        root = engine.rootObjects()[0]
        settings = engine._controller_refs[0]

        try:
            launcher.showPage("settings")
            settings.setGroup("POSITION / RENDER")
            self.app.processEvents()
            QTest.qWait(50)
            action = self.find_quick_item_text(
                root.contentItem(),
                "SettingsGroupActionButton",
                "OPEN POSITION HELPER",
            )
            self.assertIsNotNone(action)

            settings.setGroup("STORAGE")
            self.app.processEvents()
            QTest.qWait(50)
            action = self.find_quick_item_text(
                root.contentItem(),
                "SettingsGroupActionButton",
                "OPEN ROUTE HELPER",
            )
            self.assertIsNotNone(action)
        finally:
            launcher.shutdown()

    def test_settings_teleport_fields_render_copy_actions(self):
        engine, launcher, _helpers = self.make_engine()
        root = engine.rootObjects()[0]
        settings = engine._controller_refs[0]

        try:
            launcher.showPage("settings")
            settings.setGroup("GACHA")
            self.app.processEvents()
            QTest.qWait(50)
            copy_action = self.find_quick_item_text(
                root.contentItem(),
                "SettingsFieldActionButton",
                "COPY",
            )
            self.assertIsNotNone(copy_action)
            remove_action = self.find_quick_item_text(
                root.contentItem(),
                "SettingsFieldActionButton",
                "REMOVE",
            )
            self.assertIsNotNone(remove_action)
            auto_fill_action = self.find_quick_item_text(
                root.contentItem(),
                "SettingsFieldActionButton",
                "AUTO FILL",
            )
            self.assertIsNotNone(auto_fill_action)
            click_pos = auto_fill_action.mapToScene(
                QPointF(
                    auto_fill_action.property("width") / 2,
                    auto_fill_action.property("height") / 2,
                )
            )
            QTest.mouseClick(
                root,
                Qt.LeftButton,
                Qt.NoModifier,
                QPoint(int(click_pos.x()), int(click_pos.y())),
            )
            self.app.processEvents()
            QTest.qWait(50)
            dialog = root.findChild(QObject, "AppDialog")
            self.assertTrue(dialog.property("visible"))
            self.assertTrue(dialog.property("confirmMode"))
            self.assertEqual(dialog.property("title"), "Auto Fill Gacha Group")

            settings.setGroup("PEGO")
            self.app.processEvents()
            QTest.qWait(50)
            copy_action = self.find_quick_item_text(
                root.contentItem(),
                "SettingsFieldActionButton",
                "COPY",
            )
            self.assertIsNotNone(copy_action)
            remove_action = self.find_quick_item_text(
                root.contentItem(),
                "SettingsFieldActionButton",
                "REMOVE",
            )
            self.assertIsNotNone(remove_action)
        finally:
            launcher.shutdown()

    def test_settings_gacha_risky_teleporter_warning_renders(self):
        risky_entries = [
            {
                "name": "gacha_left",
                "teleporter": "GACHAPAIR2",
                "side": "left",
            },
            {
                "name": "gacha_right",
                "teleporter": "GACHAPAIR20",
                "side": "right",
            },
        ]
        with patch(
            "source.launcher.controllers.settings_controller.load_gacha_config",
            return_value=risky_entries,
        ):
            engine, launcher, _helpers = self.make_engine()
            root = engine.rootObjects()[0]
            settings = engine._controller_refs[0]

            try:
                launcher.showPage("settings")
                settings.setGroup("GACHA")
                self.app.processEvents()
                QTest.qWait(50)

                warning = self.find_quick_item_text(
                    root.contentItem(),
                    "SettingsFieldWarning",
                    "may match longer teleport names",
                )
                self.assertIsNotNone(warning)
            finally:
                launcher.shutdown()

    def test_unknown_page_name_does_not_blank_page_host(self):
        engine, launcher, _helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            launcher.showPage("logs")
            self.app.processEvents()
            logs_page = root.findChild(QObject, "LogsPage")
            self.assertTrue(logs_page.property("visible"))

            launcher.showPage("missing")
            self.app.processEvents()

            self.assertEqual(launcher.currentPage, "logs")
            self.assertTrue(logs_page.property("visible"))
        finally:
            launcher.shutdown()

    def test_settings_save_and_error_signals_surface_in_qml(self):
        engine, launcher, _helpers = self.make_engine()
        root = engine.rootObjects()[0]
        settings = engine._controller_refs[0]
        logs = engine._controller_refs[2]

        try:
            settings.saved.emit("[SUCCESS] Settings saved automatically.\n")
            settings.error.emit("Invalid Settings", "server_number must be numeric.")
            self.app.processEvents()
            QTest.qWait(50)

            dialog = root.findChild(QObject, "AppDialog")
            self.assertEqual(
                logs.lines.count("[SUCCESS] Settings saved automatically.\n"),
                1,
            )
            self.assertEqual(
                logs.lines.count(
                    "[ERROR] Invalid Settings: server_number must be numeric.\n"
                ),
                1,
            )
            self.assertTrue(dialog.property("visible"))
            self.assertEqual(dialog.property("title"), "Invalid Settings")
            self.assertEqual(dialog.property("variant"), "error")
        finally:
            launcher.shutdown()

    def test_closing_launcher_while_program_runs_requires_confirmation(self):
        engine, launcher, _helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            root.show()
            launcher.process = RunningProcess()
            launcher.changed.emit()
            self.app.processEvents()

            root.close()
            self.app.processEvents()
            QTest.qWait(50)

            dialog = root.findChild(QObject, "AppDialog")
            self.assertFalse(launcher.shutdown_started)
            self.assertTrue(root.property("visible"))
            self.assertTrue(dialog.property("visible"))
            self.assertTrue(dialog.property("confirmMode"))
            self.assertEqual(dialog.property("title"), "Stop Program And Exit")
        finally:
            launcher.process = None
            launcher.shutdown()

    def test_opening_second_helper_replaces_active_helper(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            first = root.property("activeHelperWindow")
            self.assertEqual(helpers.activeHelperName, "autoJoin")
            self.assertIsNotNone(first)

            helpers.openHelper("fertilizer", {})
            self.app.processEvents()
            second = root.property("activeHelperWindow")
            self.assertEqual(helpers.activeHelperName, "fertilizer")
            self.assertIsNotNone(second)
            self.assertIsNot(first, second)
        finally:
            launcher.shutdown()

    def test_all_helper_headers_expose_full_width_drag_area(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            for helper_name in ("autoJoin", "fertilizer", "position", "deposit", "transfer"):
                helpers.openHelper(helper_name, {})
                self.app.processEvents()
                QTest.qWait(80)
                helper = root.property("activeHelperWindow")
                top_drag_area = self.find_quick_item(
                    helper.property("contentItem"),
                    "HelperTopDragArea",
                )
                drag_area = self.find_quick_item(
                    helper.property("contentItem"),
                    "HelperHeaderDragArea",
                )
                title = self.find_quick_item(
                    helper.property("contentItem"),
                    "HelperHeaderTitle",
                )
                close_button = self.find_quick_item(
                    helper.property("contentItem"),
                    "HelperHeaderCloseButton",
                )

                self.assertIsNotNone(top_drag_area)
                self.assertIsNotNone(drag_area)
                self.assertIsNotNone(title)
                self.assertIsNotNone(close_button)
                self.assertEqual(top_drag_area.property("x"), 0)
                self.assertEqual(top_drag_area.property("y"), 0)
                self.assertAlmostEqual(
                    top_drag_area.property("width"),
                    helper.property("width"),
                    delta=1,
                )
                self.assertGreaterEqual(top_drag_area.property("height"), 8)
                self.assertEqual(drag_area.property("x"), 0)
                self.assertAlmostEqual(
                    drag_area.property("width"),
                    close_button.property("x"),
                    delta=1,
                )
                self.assertGreater(drag_area.property("width"), 0)
                if helper_name == "autoJoin":
                    self.assertGreater(
                        drag_area.property("width"),
                        title.property("implicitWidth"),
                    )
        finally:
            launcher.shutdown()

    def test_unknown_helper_name_does_not_create_default_helper(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            helpers.openHelper("missing", {})
            self.app.processEvents()

            self.assertEqual(helpers.activeHelperName, "")
            self.assertIsNone(root.property("activeHelperWindow"))
        finally:
            launcher.shutdown()

    def test_tools_helper_request_is_blocked_while_program_runs(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        tools = engine._controller_refs[3]

        try:
            launcher.process = RunningProcess()
            launcher.changed.emit()
            tools.openHelper("autoJoin")
            self.app.processEvents()
            QTest.qWait(50)

            dialog = root.findChild(QObject, "AppDialog")
            self.assertEqual(helpers.activeHelperName, "")
            self.assertIsNone(root.property("activeHelperWindow"))
            self.assertTrue(dialog.property("visible"))
            self.assertEqual(dialog.property("title"), "Stop Program First")
            self.assertEqual(dialog.property("variant"), "warning")
        finally:
            launcher.process = None
            launcher.shutdown()

    def test_payload_helper_request_is_blocked_while_program_runs(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        tools = engine._controller_refs[3]

        try:
            launcher.process = RunningProcess()
            launcher.changed.emit()
            tools.openHelperPayload(
                "deposit", {"routeKind": "grindable", "routeIndex": 0}
            )
            self.app.processEvents()
            QTest.qWait(50)

            dialog = root.findChild(QObject, "AppDialog")
            self.assertEqual(helpers.activeHelperName, "")
            self.assertIsNone(root.property("activeHelperWindow"))
            self.assertTrue(dialog.property("visible"))
            self.assertEqual(dialog.property("title"), "Stop Program First")
        finally:
            launcher.process = None
            launcher.shutdown()

    def test_helper_opens_near_launcher_right_edge(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            root.setProperty("x", 10)
            root.setProperty("y", 20)
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            helper = root.property("activeHelperWindow")
            screen = self.app.primaryScreen().availableGeometry()
            expected_x = screen.x() + screen.width() - helper.property("width") - 16
            self.assertEqual(helper.property("x"), expected_x)
            self.assertGreaterEqual(helper.property("y"), screen.y())
        finally:
            launcher.shutdown()

    def test_auto_join_helper_renders_runtime_controls(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            helper = root.property("activeHelperWindow")
            self.assertIsNotNone(helper)
            self.assertTrue(helper.findChild(QObject, "AutoJoinServerInput"))
            self.assertTrue(helper.findChild(QObject, "AutoJoinStartButton"))
        finally:
            launcher.shutdown()

    def test_worker_helper_hotkey_hint_matches_toggle_behavior(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            helper = root.property("activeHelperWindow")
            hint = helper.findChild(QObject, "HelperHotkeyHint")
            self.assertIsNotNone(hint)
            self.assertEqual(hint.property("text"), "ALT + N toggles START / STOP")
        finally:
            launcher.shutdown()

    def test_helper_dialog_requests_open_app_dialog(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        auto_join = engine._controller_refs[6]

        try:
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            auto_join.setServerNumber("not-a-server")
            auto_join.start()
            self.app.processEvents()
            QTest.qWait(50)

            dialog = root.findChild(QObject, "AppDialog")
            self.assertTrue(dialog.property("visible"))
            self.assertFalse(dialog.property("confirmMode"))
            self.assertEqual(dialog.property("title"), "Invalid Server Number")
            self.assertEqual(dialog.property("variant"), "warning")
        finally:
            launcher.shutdown()

    def test_helper_opacity_stays_full_while_hovered(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        settings = engine._controller_refs[0]

        try:
            settings._settings["helper_inactive_opacity"] = 0.3
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            helper = root.property("activeHelperWindow")
            self.assertIsNotNone(helper)
            helper.setProperty("mouseInside", True)
            self.app.processEvents()
            self.assertEqual(helper.property("opacity"), 1.0)
        finally:
            launcher.shutdown()

    def test_helper_opacity_stays_full_while_launcher_is_active(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        settings = engine._controller_refs[0]

        try:
            settings._settings["helper_inactive_opacity"] = 0.3
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            helper = root.property("activeHelperWindow")
            self.assertIsNotNone(helper)
            helper.setProperty("mouseInside", False)
            helper.setProperty("ownerActive", True)
            self.app.processEvents()
            self.assertEqual(helper.property("opacity"), 1.0)
        finally:
            launcher.shutdown()

    def test_auto_join_helper_uses_compact_running_mode(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        auto_join = engine._controller_refs[6]

        try:
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            helper = root.property("activeHelperWindow")
            idle_width = helper.property("width")
            idle_height = helper.property("height")
            auto_join.worker._process = RunningProcess()
            auto_join.worker.runningChanged.emit()
            auto_join.changed.emit()
            self.app.processEvents()
            QTest.qWait(50)

            hint = helper.findChild(QObject, "HelperHotkeyHint")
            input_field = helper.findChild(QObject, "AutoJoinServerInput")
            start_button = helper.findChild(QObject, "AutoJoinStartButton")
            screen = self.app.primaryScreen().availableGeometry()
            expected_x = screen.x() + screen.width() - helper.property("width") - 16
            self.assertLess(helper.property("width"), idle_width)
            self.assertLess(helper.property("height"), idle_height)
            self.assertLessEqual(helper.property("height"), 110)
            self.assertEqual(helper.property("x"), expected_x)
            self.assertEqual(hint.property("text"), "ALT + N stops this helper")
            self.assertFalse(input_field.property("visible"))
            self.assertFalse(start_button.property("visible"))
        finally:
            auto_join.worker._process = None
            launcher.shutdown()

    def test_fertilizer_helper_uses_compact_running_mode(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        fertilizer = engine._controller_refs[7]

        try:
            helpers.openHelper("fertilizer", {})
            self.app.processEvents()
            helper = root.property("activeHelperWindow")
            idle_height = helper.property("height")
            fertilizer.worker._process = RunningProcess()
            fertilizer.worker.runningChanged.emit()
            fertilizer.changed.emit()
            self.app.processEvents()
            QTest.qWait(50)

            hint = helper.findChild(QObject, "HelperHotkeyHint")
            start_button = helper.findChild(QObject, "FertilizerStartButton")
            self.assertLess(helper.property("height"), idle_height)
            self.assertLessEqual(helper.property("height"), 110)
            self.assertEqual(hint.property("text"), "ALT + N stops this helper")
            self.assertFalse(start_button.property("visible"))
        finally:
            fertilizer.worker._process = None
            launcher.shutdown()

    def test_closing_running_worker_helper_stops_before_clearing_active_helper(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        auto_join = engine._controller_refs[6]
        process = StoppableProcess()

        try:
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            helper = root.property("activeHelperWindow")
            self.assertIsNotNone(helper)

            auto_join.worker._process = process
            auto_join.worker.runningChanged.emit()
            auto_join.changed.emit()
            self.app.processEvents()
            helper.close()
            self.app.processEvents()
            QTest.qWait(50)

            self.assertTrue(process.terminated or process.killed)
            self.assertIsNone(auto_join.worker._process)
            self.assertEqual(helpers.activeHelperName, "")
            self.assertIsNone(root.property("activeHelperWindow"))
        finally:
            auto_join.worker._process = None
            launcher.shutdown()

    def test_opening_second_helper_waits_for_running_helper_to_close(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        auto_join = engine._controller_refs[6]
        process = StoppableProcess()

        try:
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            first = root.property("activeHelperWindow")
            self.assertIsNotNone(first)

            auto_join.worker._process = process
            auto_join.worker.runningChanged.emit()
            auto_join.changed.emit()
            self.app.processEvents()

            helpers.openHelper("fertilizer", {})
            self.app.processEvents()
            QTest.qWait(50)

            second = root.property("activeHelperWindow")
            self.assertTrue(process.terminated or process.killed)
            self.assertIsNone(auto_join.worker._process)
            self.assertEqual(helpers.activeHelperName, "fertilizer")
            self.assertIsNotNone(second)
            self.assertIsNot(first, second)
            self.assertEqual(second.property("helperTitle"), "CROP PLOT FERTILIZER REFRESH")
        finally:
            auto_join.worker._process = None
            launcher.shutdown()

    def test_runner_overlay_renders_compact_concise_log_lines(self):
        engine, launcher, _helpers = self.make_engine()
        root = engine.rootObjects()[0]
        logs = engine._controller_refs[2]

        try:
            root.show()
            launcher.process = RunningProcess()
            launcher.changed.emit()
            logs.append("[DEBUG] source.gacha_bot.deposit: hidden by row limit\n")
            logs.append("[INFO] 12:00:00 - INFO - source.logs.gachalogs - joined server\n")
            logs.append("[WARN] source.gacha_bot.render: " + ("x" * 90) + "\n")
            logs.append("[ERROR] final message\n")
            self.app.processEvents()
            QTest.qWait(50)
            overlay = root.findChild(QObject, "RunnerOverlayWindow")
            latest_logs = root.findChild(QObject, "RunnerOverlayLatestLogs")
            current = root.findChild(QObject, "RunnerOverlayCurrent")
            stats = root.findChild(QObject, "RunnerOverlayStats")
            helper_status = root.findChild(QObject, "RunnerOverlayHelperStatus")
            stop_button = root.findChild(QObject, "RunnerOverlayStopButton")
            self.assertIsNotNone(overlay)
            self.assertIsNotNone(latest_logs)
            self.assertIsNotNone(current)
            self.assertIsNotNone(stats)
            self.assertIsNotNone(helper_status)
            self.assertIsNotNone(stop_button)
            self.assertLessEqual(overlay.property("width"), 320)
            text = latest_logs.property("text")
            self.assertNotIn("[INFO]", text)
            self.assertNotIn("[WARN]", text)
            self.assertNotIn("source.gacha_bot.render", text)
            self.assertNotIn("hidden by row limit", text)
            self.assertIn("joined server", text)
            self.assertIn("final message", text)
            self.assertIn("...", text)
        finally:
            launcher.process = None
            launcher.shutdown()

    def test_runner_overlay_header_exposes_full_width_drag_area(self):
        engine, launcher, _helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            root.show()
            launcher.process = RunningProcess()
            launcher.changed.emit()
            self.app.processEvents()
            QTest.qWait(50)

            drag_area = root.findChild(QObject, "RunnerOverlayHeaderDragArea")
            stop_button = root.findChild(QObject, "RunnerOverlayStopButton")

            self.assertIsNotNone(drag_area)
            self.assertIsNotNone(stop_button)
            self.assertEqual(drag_area.property("x"), 0)
            self.assertAlmostEqual(
                drag_area.property("width"),
                stop_button.property("x"),
                delta=1,
            )
            self.assertGreater(drag_area.property("width"), 0)
        finally:
            launcher.process = None
            launcher.shutdown()

    def test_position_helper_renders_guide_action(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            helpers.openHelper("position", {})
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")
            self.assertTrue(helper.findChild(QObject, "PositionGuideButton"))
            self.assertTrue(helper.property("guideOpen"))
        finally:
            launcher.shutdown()

    def test_deposit_helper_renders_vault_item_rows(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        deposit = engine._controller_refs[9]

        try:
            deposit._config["depositCrystalData"][0]["vault"]["items"].append(
                {
                    "location": {"yaw": 0.0, "pitch": 0.0},
                    "crouched": False,
                    "items": ["riot"],
                }
            )
            deposit.changed.emit()
            helpers.openHelper("deposit", {})
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")
            item = self.find_quick_item(helper.property("contentItem"), "VaultItemValue")
            self.assertIsNotNone(item)
            self.assertEqual(item.property("text"), "riot")
        finally:
            launcher.shutdown()

    def test_editable_vault_item_combo_opens_from_input_body(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        root.show()
        deposit = engine._controller_refs[9]

        try:
            deposit._config["depositCrystalData"][0]["vault"]["items"].append(
                {
                    "location": {"yaw": 0.0, "pitch": 0.0},
                    "crouched": False,
                    "items": [],
                }
            )
            deposit.changed.emit()
            helpers.openHelper("deposit", {})
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")
            guide = helper.findChild(QObject, "DepositGuideDialog")
            if guide is not None:
                QMetaObject.invokeMethod(guide, "close")
            for row in self.find_quick_items(
                helper.property("contentItem"),
                "DepositRouteRow",
            ):
                row.setProperty("expanded", True)
            self.app.processEvents()
            QTest.qWait(50)
            scroll = self.find_quick_item(
                helper.property("contentItem"),
                "DepositRouteScroll",
            )
            self.assertIsNotNone(scroll)
            scroll.setProperty(
                "contentY",
                max(0, scroll.property("contentHeight") - scroll.property("height")),
            )
            self.app.processEvents()
            QTest.qWait(50)

            combo = self.find_visible_window_item(
                helper,
                helper.property("contentItem"),
                "VaultItemCombo",
            )
            self.assertIsNotNone(combo)
            click_pos = combo.mapToScene(
                QPointF(
                    combo.property("width") / 4,
                    combo.property("height") / 2,
                )
            )
            QTest.mouseClick(
                helper,
                Qt.LeftButton,
                Qt.NoModifier,
                QPoint(int(click_pos.x()), int(click_pos.y())),
            )
            self.app.processEvents()
            QTest.qWait(50)

            self.assertTrue(combo.property("popupOpen"))
            self.assertTrue(combo.property("inputFocused"))
        finally:
            launcher.shutdown()

    def test_deposit_helper_renders_guide_pages(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            helpers.openHelper("deposit", {})
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")
            guide_button = helper.findChild(QObject, "DepositGuideButton")
            guide_title = helper.findChild(QObject, "DepositGuideTitle")
            guide_page = helper.findChild(QObject, "DepositGuidePage")
            self.assertIsNotNone(guide_button)
            self.assertIsNotNone(guide_title)
            self.assertIsNotNone(guide_page)
            self.assertEqual(guide_title.property("text"), "STEP 1 / RENDER BED")
            self.assertEqual(guide_page.property("text"), "1 / 4")

            helper.setProperty("guideIndex", 3)
            self.app.processEvents()
            QTest.qWait(50)
            self.assertEqual(guide_title.property("text"), "STEP 4 / CAPTURE")
            self.assertEqual(guide_page.property("text"), "4 / 4")
        finally:
            launcher.shutdown()

    def test_deposit_helper_route_rows_default_collapsed(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            helpers.openHelper("deposit", {})
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")
            details = self.find_quick_item(
                helper.property("contentItem"),
                "DepositRouteRowDetails",
            )
            self.assertIsNotNone(details)
            self.assertFalse(details.property("visible"))
        finally:
            launcher.shutdown()

    def test_deposit_view_commits_visible_yaw_input(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        deposit = engine._controller_refs[9]

        try:
            deposit.launcher_controller.require_ark_window = Mock(return_value=False)
            helpers.openHelper("deposit", {})
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")
            guide = helper.findChild(QObject, "DepositGuideDialog")
            if guide is not None:
                QMetaObject.invokeMethod(guide, "close")
            for row in self.find_quick_items(
                helper.property("contentItem"),
                "DepositRouteRow",
            ):
                row.setProperty("expanded", True)
            self.app.processEvents()
            QTest.qWait(50)

            yaw_field = None
            for field in self.find_quick_items(
                helper.property("contentItem"),
                "DepositRouteValueField",
            ):
                if field.property("rowKind") == "dedi" and field.property("rowKey") == "yaw":
                    yaw_field = field
                    break
            view_button = self.find_quick_item(
                helper.property("contentItem"),
                "DepositRouteViewButton",
            )
            self.assertIsNotNone(yaw_field)
            self.assertIsNotNone(view_button)

            yaw_field.setProperty("text", "88.5")
            click_pos = view_button.mapToScene(
                QPointF(
                    view_button.property("width") / 2,
                    view_button.property("height") / 2,
                )
            )
            QTest.mouseClick(
                helper,
                Qt.LeftButton,
                Qt.NoModifier,
                QPoint(int(click_pos.x()), int(click_pos.y())),
            )
            self.app.processEvents()
            QTest.qWait(50)

            row = deposit._config["depositCrystalData"][0]["dedi"]["items"][0]
            self.assertEqual(row["location"]["yaw"], 88.5)
            deposit.launcher_controller.require_ark_window.assert_called_once_with(
                "view route location"
            )
        finally:
            launcher.shutdown()

    def test_deposit_route_action_commits_visible_teleport_input(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        deposit = engine._controller_refs[9]

        try:
            helpers.openHelper("deposit", {})
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")
            guide = helper.findChild(QObject, "DepositGuideDialog")
            if guide is not None:
                QMetaObject.invokeMethod(guide, "close")
            self.app.processEvents()
            QTest.qWait(50)

            teleport_field = self.find_quick_item(
                helper.property("contentItem"),
                "DepositTeleportField",
            )
            add_dedi_button = self.find_quick_item(
                helper.property("contentItem"),
                "DepositAddDediButton",
            )
            self.assertIsNotNone(teleport_field)
            self.assertIsNotNone(add_dedi_button)

            teleport_field.setProperty("text", "TP_COMMITTED")
            click_pos = add_dedi_button.mapToScene(
                QPointF(
                    add_dedi_button.property("width") / 2,
                    add_dedi_button.property("height") / 2,
                )
            )
            QTest.mouseClick(
                helper,
                Qt.LeftButton,
                Qt.NoModifier,
                QPoint(int(click_pos.x()), int(click_pos.y())),
            )
            self.app.processEvents()
            QTest.qWait(50)

            route = deposit._config["depositCrystalData"][0]
            self.assertEqual(route["teleport"], "TP_COMMITTED")
        finally:
            launcher.shutdown()

    def test_deposit_helper_applies_route_payload(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        deposit = engine._controller_refs[9]

        try:
            helpers.openHelper(
                "deposit",
                {"routeKind": "grindable", "routeIndex": 0},
            )
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")

            self.assertEqual(deposit.routeKind, "grindable")
            self.assertEqual(deposit.routeIndex, 0)
            self.assertIn("GRINDABLE", helper.property("helperTitle"))
        finally:
            launcher.shutdown()

    def test_tools_payload_request_opens_deposit_route(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        tools = engine._controller_refs[3]
        deposit = engine._controller_refs[9]

        try:
            tools.openHelperPayload(
                "deposit", {"routeKind": "grindable", "routeIndex": 0}
            )
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")

            self.assertEqual(helpers.activeHelperName, "deposit")
            self.assertEqual(deposit.routeKind, "grindable")
            self.assertEqual(deposit.routeIndex, 0)
            self.assertIn("GRINDABLE", helper.property("helperTitle"))
        finally:
            launcher.shutdown()

    def test_queued_deposit_helper_keeps_route_payload(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        auto_join = engine._controller_refs[6]
        deposit = engine._controller_refs[9]

        try:
            auto_join.start()
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            QTest.qWait(50)

            helpers.openHelper(
                "deposit",
                {"routeKind": "grindable", "routeIndex": 0},
            )
            self.app.processEvents()
            QTest.qWait(100)
            helper = root.property("activeHelperWindow")

            self.assertEqual(helpers.activeHelperName, "deposit")
            self.assertEqual(deposit.routeKind, "grindable")
            self.assertEqual(deposit.routeIndex, 0)
            self.assertIn("GRINDABLE", helper.property("helperTitle"))
        finally:
            launcher.shutdown()

    def test_auto_join_start_commits_visible_server_input(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        auto_join = engine._controller_refs[6]

        try:
            auto_join._can_start = Mock(return_value=False)
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")
            server_input = helper.findChild(QObject, "AutoJoinServerInput")
            start_button = helper.findChild(QObject, "AutoJoinStartButton")
            self.assertIsNotNone(server_input)
            self.assertIsNotNone(start_button)

            server_input.setProperty("text", "7777")
            click_pos = start_button.mapToScene(
                QPointF(
                    start_button.property("width") / 2,
                    start_button.property("height") / 2,
                )
            )
            QTest.mouseClick(
                helper,
                Qt.LeftButton,
                Qt.NoModifier,
                QPoint(int(click_pos.x()), int(click_pos.y())),
            )
            self.app.processEvents()
            QTest.qWait(50)

            self.assertEqual(auto_join.serverNumber, "7777")
            auto_join._can_start.assert_called_once_with("start auto join server")
        finally:
            launcher.shutdown()

    def test_transfer_helper_renders_ignored_account_warning(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        transfer = engine._controller_refs[10]

        try:
            transfer.config["players"] = {
                "players": [
                    {"bed_name": "Player1"},
                    {"bed_name": "Player2"},
                    {"bed_name": "Player3"},
                    {"bed_name": "Player4"},
                    {"bed_name": "Player5"},
                ]
            }
            transfer.configChanged.emit()
            helpers.openHelper("transfer", {})
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")
            warning = self.find_quick_item_text(
                helper.property("contentItem"),
                "TransferPlayerWarning",
                "Runtime support is limited",
            )
            self.assertIsNotNone(warning)
        finally:
            launcher.shutdown()

    def test_transfer_start_commits_visible_setting_input(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        transfer = engine._controller_refs[10]

        try:
            transfer.config["settings"].update(
                {
                    "transmitter_teleport": "TRANSFER_TTRANS",
                    "resource_server": "1001",
                    "destination_server": "1002",
                }
            )
            transfer.config["dedis"]["resource"]["items"] = [
                {"location": {"yaw": 1.0, "pitch": 2.0}, "crouched": False}
            ]
            transfer.config["dedis"]["destination"]["items"] = [
                {"location": {"yaw": 3.0, "pitch": 4.0}, "crouched": False}
            ]
            transfer.config["players"] = {"players": [{"bed_name": "Player1"}]}
            transfer._can_start = Mock(return_value=False)
            transfer.configChanged.emit()

            helpers.openHelper("transfer", {})
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")
            resource_server = None
            for field in self.find_quick_items(
                helper.property("contentItem"),
                "TransferSettingField",
            ):
                if field.property("settingKey") == "resource_server":
                    resource_server = field
                    break
            start_button = helper.findChild(QObject, "TransferStartButton")
            self.assertIsNotNone(resource_server)
            self.assertIsNotNone(start_button)

            resource_server.setProperty("text", "7777")
            click_pos = start_button.mapToScene(
                QPointF(
                    start_button.property("width") / 2,
                    start_button.property("height") / 2,
                )
            )
            QTest.mouseClick(
                helper,
                Qt.LeftButton,
                Qt.NoModifier,
                QPoint(int(click_pos.x()), int(click_pos.y())),
            )
            self.app.processEvents()
            QTest.qWait(50)

            self.assertEqual(transfer.config["settings"]["resource_server"], "7777")
        finally:
            launcher.shutdown()

    def test_transfer_add_player_commits_visible_player_input(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        transfer = engine._controller_refs[10]

        try:
            transfer.config["players"] = {"players": [{"bed_name": "OldBed"}]}
            transfer.configChanged.emit()
            helpers.openHelper("transfer", {})
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")
            player_field = self.find_quick_item(
                helper.property("contentItem"),
                "TransferPlayerField",
            )
            add_button = helper.findChild(QObject, "TransferAddPlayerButton")
            self.assertIsNotNone(player_field)
            self.assertIsNotNone(add_button)

            player_field.setProperty("text", "ManualBed")
            QMetaObject.invokeMethod(add_button, "click", Qt.DirectConnection)
            self.app.processEvents()
            QTest.qWait(50)

            players = transfer.config["players"]["players"]
            self.assertEqual(players[0]["bed_name"], "ManualBed")
            self.assertEqual(len(players), 2)
        finally:
            launcher.shutdown()

    def test_transfer_helper_collapse_and_expand_all_controls_dedi_details(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            helpers.openHelper("transfer", {})
            self.app.processEvents()
            QTest.qWait(50)
            helper = root.property("activeHelperWindow")
            collapse = helper.findChild(QObject, "TransferCollapseAllButton")
            expand = helper.findChild(QObject, "TransferExpandAllButton")
            details = self.find_quick_item(
                helper.property("contentItem"),
                "TransferDediDetails",
            )
            self.assertIsNotNone(collapse)
            self.assertIsNotNone(expand)
            self.assertIsNotNone(details)
            self.assertTrue(details.property("visible"))

            helper.setProperty("allExpanded", False)
            helper.setProperty("expandGeneration", helper.property("expandGeneration") + 1)
            self.app.processEvents()
            QTest.qWait(50)
            self.assertFalse(details.property("visible"))

            helper.setProperty("allExpanded", True)
            helper.setProperty("expandGeneration", helper.property("expandGeneration") + 1)
            self.app.processEvents()
            QTest.qWait(50)
            self.assertTrue(details.property("visible"))
        finally:
            launcher.shutdown()

    def find_quick_item(self, item, object_name):
        if item is None:
            return None
        if item.objectName() == object_name:
            return item
        for child in item.childItems():
            found = self.find_quick_item(child, object_name)
            if found is not None:
                return found
        return None

    def find_quick_items(self, item, object_name):
        if item is None:
            return []
        matches = []
        if item.objectName() == object_name:
            matches.append(item)
        for child in item.childItems():
            matches.extend(self.find_quick_items(child, object_name))
        return matches

    def find_visible_window_item(self, window, item, object_name):
        for candidate in self.find_quick_items(item, object_name):
            center = candidate.mapToScene(
                QPointF(
                    candidate.property("width") / 2,
                    candidate.property("height") / 2,
                )
            )
            if 0 <= center.x() <= window.width() and 0 <= center.y() <= window.height():
                return candidate
        return None

    def find_quick_item_text(self, item, object_name, text):
        if item is None:
            return None
        if item.objectName() == object_name and text in str(item.property("text")):
            return item
        for child in item.childItems():
            found = self.find_quick_item_text(child, object_name, text)
            if found is not None:
                return found
        return None


if __name__ == "__main__":
    unittest.main()
