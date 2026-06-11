import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Item {
    RowLayout {
        anchors.fill: parent
        anchors.margins: ThemeModule.Theme.spacing.xl
        spacing: ThemeModule.Theme.spacing.xl

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: ThemeModule.Theme.spacing.lg

            Item { Layout.fillHeight: true }
            Text {
                text: "WELCOME TO\n" + launcherController.appTitle
                color: ThemeModule.Theme.colors.cyan
                font.pixelSize: ThemeModule.Theme.fonts.welcomeTitle
                font.bold: true
            }
            Text {
                text: "AUTOMATE. MANAGE. DOMINATE.\n\n" + launcherController.appName + " is your compact companion for managing automation tasks, queues, and local offline runs with style."
                color: ThemeModule.Theme.colors.muted
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Panel {
                title: "BEFORE YOU START:"
                Layout.fillWidth: true
                Text { text: "- Configure your settings"; color: ThemeModule.Theme.colors.text }
                Text { text: "- Review your station data"; color: ThemeModule.Theme.colors.text }
                Text { text: "- Review the setup guide"; color: ThemeModule.Theme.colors.text }
                Text { text: "- Save settings before starting"; color: ThemeModule.Theme.colors.text }
            }
            CyberButton {
                text: "GET STARTED >"
                variant: "primary"
                Layout.alignment: Qt.AlignRight
                onClicked: launcherController.showPage("dashboard")
            }
            Item { Layout.fillHeight: true }
        }

        Image {
            source: assetPaths.welcome
            fillMode: Image.PreserveAspectFit
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
