import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Item {
    objectName: "LogsPage"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ThemeModule.Theme.spacing.lg
        spacing: ThemeModule.Theme.spacing.md

        Text {
            text: launcherController.appTitle + " - LOGS"
            color: ThemeModule.Theme.colors.cyan
            font.pixelSize: ThemeModule.Theme.fonts.pageTitle
            font.bold: true
        }

        Flow {
            Layout.fillWidth: true
            spacing: ThemeModule.Theme.spacing.sm

            Repeater {
                model: logController.filters
                CyberButton {
                    text: modelData
                    variant: logController.currentFilter === modelData ? "primary" : "secondary"
                    onClicked: logController.setFilter(modelData)
                }
            }
            CyberButton { text: "CLEAR LOGS"; variant: "danger"; onClicked: logController.clearLogs() }
            CyberButton { text: "COPY LOGS"; variant: "primary"; onClicked: logController.copyLogs() }
        }

        Panel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            fillBody: true

            ConsoleView {
                lines: logController.lines
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }

        RowLayout {
            Layout.fillWidth: true
            CyberButton {
                text: "TEST CONSOLE COLOURS"
                variant: "secondary"
                onClicked: launcherController.checkColours()
            }
            Item { Layout.fillWidth: true }
            CyberButton {
                text: "COPY LOGS"
                variant: "primary"
                onClicked: logController.copyLogs()
            }
        }
    }
}
