import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QUrl
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
            self.assertFalse(github_button.property("enabled"))
            self.assertFalse(website_button.property("enabled"))
            self.assertIn("not configured", links_status.property("text"))
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

    def test_helper_opens_near_launcher_right_edge(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            root.setProperty("x", 10)
            root.setProperty("y", 20)
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            helper = root.property("activeHelperWindow")
            expected_x = root.property("x") + root.property("width") - helper.property("width") - 16
            self.assertEqual(helper.property("x"), expected_x)
            self.assertGreaterEqual(helper.property("y"), root.property("y") + 16)
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

    def test_auto_join_helper_uses_compact_running_mode(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]
        auto_join = engine._controller_refs[6]

        try:
            helpers.openHelper("autoJoin", {})
            self.app.processEvents()
            helper = root.property("activeHelperWindow")
            idle_width = helper.property("width")
            auto_join.worker._process = RunningProcess()
            auto_join.worker.runningChanged.emit()
            auto_join.changed.emit()
            self.app.processEvents()
            QTest.qWait(50)

            hint = helper.findChild(QObject, "HelperHotkeyHint")
            input_field = helper.findChild(QObject, "AutoJoinServerInput")
            start_button = helper.findChild(QObject, "AutoJoinStartButton")
            expected_x = root.property("x") + root.property("width") - helper.property("width") - 16
            self.assertLess(helper.property("width"), idle_width)
            self.assertEqual(helper.property("x"), expected_x)
            self.assertEqual(hint.property("text"), "ALT + N stops this helper")
            self.assertFalse(input_field.property("visible"))
            self.assertFalse(start_button.property("visible"))
        finally:
            auto_join.worker._process = None
            launcher.shutdown()

    def test_runner_overlay_renders_latest_five_log_lines(self):
        engine, launcher, _helpers = self.make_engine()
        root = engine.rootObjects()[0]
        logs = engine._controller_refs[2]

        try:
            for index in range(6):
                logs.append(f"[INFO] line {index}\n")
            self.app.processEvents()
            latest_logs = root.findChild(QObject, "RunnerOverlayLatestLogs")
            self.assertIsNotNone(latest_logs)
            text = latest_logs.property("text")
            self.assertNotIn("line 0", text)
            self.assertIn("line 1", text)
            self.assertIn("line 5", text)
        finally:
            launcher.shutdown()

    def test_position_helper_renders_guide_action(self):
        engine, launcher, helpers = self.make_engine()
        root = engine.rootObjects()[0]

        try:
            helpers.openHelper("position", {})
            self.app.processEvents()
            helper = root.property("activeHelperWindow")
            self.assertTrue(helper.findChild(QObject, "PositionGuideButton"))
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
