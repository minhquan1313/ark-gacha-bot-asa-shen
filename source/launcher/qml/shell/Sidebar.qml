import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Rectangle {
    id: sidebar

    property bool narrow: false
    property var pages: [
        { "key": "dashboard", "label": narrow ? "DASH" : "DASHBOARD" },
        { "key": "setup", "label": "SETUP" },
        { "key": "settings", "label": narrow ? "SET" : "SETTINGS" },
        { "key": "logs", "label": "LOGS" },
        { "key": "tools", "label": "TOOLS" },
        { "key": "update", "label": narrow ? "UPDATE" : "CHECK UPDATE" },
        { "key": "about", "label": "ABOUT" }
    ]

    width: narrow ? ThemeModule.Theme.size.sidebarNarrowWidth : ThemeModule.Theme.size.sidebarWidth
    color: ThemeModule.Theme.colors.sidebar

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ThemeModule.Theme.spacing.md
        spacing: ThemeModule.Theme.spacing.sm

        Image {
            source: assetPaths.logo
            fillMode: Image.PreserveAspectFit
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: narrow ? ThemeModule.Theme.size.sidebarLogoNarrow : ThemeModule.Theme.size.sidebarLogo
            Layout.preferredHeight: narrow ? ThemeModule.Theme.size.sidebarLogoNarrow : ThemeModule.Theme.size.sidebarLogo
        }

        Text {
            visible: !narrow
            text: launcherController.appTitle
            color: ThemeModule.Theme.colors.text
            font.pixelSize: ThemeModule.Theme.fonts.nav
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
        }

        Item { Layout.preferredHeight: ThemeModule.Theme.spacing.md }

        Repeater {
            model: sidebar.pages
            delegate: CyberButton {
                text: modelData.label
                variant: launcherController.currentPage === modelData.key ? "primary" : "secondary"
                Layout.fillWidth: true
                onClicked: launcherController.showPage(modelData.key)
            }
        }

        Item { Layout.fillHeight: true }

        CyberButton {
            text: "MUSIC: OFF"
            variant: "secondary"
            Layout.fillWidth: true
        }

        Text {
            text: "BUILD 1.0.0"
            color: ThemeModule.Theme.colors.muted
            font.family: ThemeModule.Theme.fonts.mono
            Layout.fillWidth: true
        }

        Text {
            text: "STATUS: READY"
            color: ThemeModule.Theme.colors.green
            font.family: ThemeModule.Theme.fonts.mono
            font.bold: true
            Layout.fillWidth: true
        }
    }
}
