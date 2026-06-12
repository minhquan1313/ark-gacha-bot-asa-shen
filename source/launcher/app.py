import os
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from source.launcher.constants import ASSETS, LAUNCHER_LOG_FILE
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
from source.launcher.controllers.launcher_controller import LauncherController
from source.launcher.controllers.log_controller import LogController
from source.launcher.controllers.queue_controller import QueueController
from source.launcher.controllers.settings_controller import SettingsController
from source.launcher.controllers.tools_controller import ToolsController


def run():
    app = QApplication(sys.argv)
    if os.path.exists(ASSETS["logo"]):
        app.setWindowIcon(QIcon(ASSETS["logo"]))
    QQuickStyle.setStyle("Basic")

    settings_controller = SettingsController()
    queue_controller = QueueController()
    log_controller = LogController(LAUNCHER_LOG_FILE)
    tools_controller = ToolsController()
    helper_window_controller = HelperWindowController()
    launcher_controller = LauncherController(
        settings_controller,
        log_controller,
        queue_controller,
        helper_window_controller,
    )
    auto_join_helper_controller = AutoJoinHelperController(
        launcher_controller, settings_controller
    )
    fertilizer_helper_controller = FertilizerHelperController(launcher_controller)
    position_render_helper_controller = PositionRenderHelperController(
        launcher_controller, settings_controller
    )
    deposit_route_helper_controller = DepositRouteHelperController(launcher_controller)
    transfer_helper_controller = TransferHelperController(launcher_controller)

    for helper_controller in (
        auto_join_helper_controller,
        fertilizer_helper_controller,
        position_render_helper_controller,
        deposit_route_helper_controller,
        transfer_helper_controller,
    ):
        helper_controller.dialogRequested.connect(launcher_controller.dialogRequested)

    engine = QQmlApplicationEngine()
    engine._controller_refs = [
        settings_controller,
        queue_controller,
        log_controller,
        tools_controller,
        helper_window_controller,
        launcher_controller,
        auto_join_helper_controller,
        fertilizer_helper_controller,
        position_render_helper_controller,
        deposit_route_helper_controller,
        transfer_helper_controller,
    ]
    context = engine.rootContext()
    context.setContextProperty("launcherController", launcher_controller)
    context.setContextProperty("settingsController", settings_controller)
    context.setContextProperty("logController", log_controller)
    context.setContextProperty("queueController", queue_controller)
    context.setContextProperty("toolsController", tools_controller)
    context.setContextProperty("helperWindowController", helper_window_controller)
    context.setContextProperty("autoJoinHelperController", auto_join_helper_controller)
    context.setContextProperty(
        "fertilizerHelperController", fertilizer_helper_controller
    )
    context.setContextProperty(
        "positionRenderHelperController", position_render_helper_controller
    )
    context.setContextProperty(
        "depositRouteHelperController", deposit_route_helper_controller
    )
    context.setContextProperty("transferHelperController", transfer_helper_controller)
    asset_urls = {
        key: QUrl.fromLocalFile(os.path.abspath(path)).toString()
        for key, path in ASSETS.items()
    }
    context.setContextProperty("assetPaths", asset_urls)

    qml_path = os.path.join(os.path.dirname(__file__), "qml", "Main.qml")
    engine.load(QUrl.fromLocalFile(qml_path))
    if not engine.rootObjects():
        return 1

    log_controller.loadPreviousLogs()
    launcher_controller.scheduleAutoStart()
    exit_code = app.exec()
    launcher_controller.shutdown()
    return exit_code
