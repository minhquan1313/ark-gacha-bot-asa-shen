import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from source.launcher.constants import ASSETS
from source.launcher.controllers.launcher_controller import LauncherController
from source.launcher.controllers.log_controller import LogController
from source.launcher.controllers.queue_controller import QueueController
from source.launcher.controllers.settings_controller import SettingsController
from source.launcher.controllers.tools_controller import ToolsController


class QmlLauncherSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle("Basic")
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_main_qml_loads_with_registered_controllers(self):
        settings = SettingsController()
        queue = QueueController()
        logs = LogController()
        tools = ToolsController()
        launcher = LauncherController(settings, logs, queue)
        engine = QQmlApplicationEngine()
        context = engine.rootContext()
        context.setContextProperty("launcherController", launcher)
        context.setContextProperty("settingsController", settings)
        context.setContextProperty("logController", logs)
        context.setContextProperty("queueController", queue)
        context.setContextProperty("toolsController", tools)
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

        try:
            self.assertEqual(len(engine.rootObjects()), 1)
        finally:
            launcher.shutdown()


if __name__ == "__main__":
    unittest.main()
