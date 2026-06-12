import QtQuick
import "../pages"

Item {
    id: host

    WelcomePage { anchors.fill: parent; visible: launcherController.currentPage === "welcome" }
    DashboardPage { anchors.fill: parent; visible: launcherController.currentPage === "dashboard" }
    SetupPage { anchors.fill: parent; visible: launcherController.currentPage === "setup" }
    SettingsPage { anchors.fill: parent; visible: launcherController.currentPage === "settings" }
    LogsPage { anchors.fill: parent; visible: launcherController.currentPage === "logs" }
    ToolsPage { anchors.fill: parent; visible: launcherController.currentPage === "tools" }
    UpdatePage { anchors.fill: parent; visible: launcherController.currentPage === "update" }
    AboutPage { anchors.fill: parent; visible: launcherController.currentPage === "about" }
}
