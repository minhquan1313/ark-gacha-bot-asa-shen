import os
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from source.launcher.constants import ASSETS
from source.launcher.controllers.launcher_controller import LauncherController
from source.launcher.controllers.log_controller import LogController
from source.launcher.controllers.queue_controller import QueueController
from source.launcher.controllers.settings_controller import SettingsController
from source.launcher.controllers.tools_controller import ToolsController


def run():
    app = QGuiApplication(sys.argv)
    if os.path.exists(ASSETS["logo"]):
        app.setWindowIcon(QIcon(ASSETS["logo"]))
    QQuickStyle.setStyle("Basic")

    settings_controller = SettingsController()
    queue_controller = QueueController()
    log_controller = LogController()
    tools_controller = ToolsController()
    launcher_controller = LauncherController(
        settings_controller, log_controller, queue_controller
    )

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("launcherController", launcher_controller)
    context.setContextProperty("settingsController", settings_controller)
    context.setContextProperty("logController", log_controller)
    context.setContextProperty("queueController", queue_controller)
    context.setContextProperty("toolsController", tools_controller)
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
    exit_code = app.exec()
    launcher_controller.shutdown()
    return exit_code
