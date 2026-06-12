import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ThemeModule.Theme.spacing.lg
        spacing: ThemeModule.Theme.spacing.md

        Text {
            text: launcherController.appTitle + " - TOOLS"
            color: ThemeModule.Theme.colors.cyan
            font.pixelSize: ThemeModule.Theme.fonts.pageTitle
            font.bold: true
        }

        GridLayout {
            columns: 2
            columnSpacing: ThemeModule.Theme.spacing.md
            rowSpacing: ThemeModule.Theme.spacing.md
            Layout.fillWidth: true

            Repeater {
                model: [
                    { "key": "autoJoin", "title": "AUTO JOIN SERVER", "body": "Retry the existing join flow until the character is detected back in-server." },
                    { "key": "transfer", "title": "SERVER TRANSFER HELPER", "body": "Move resources between servers across Steam accounts." },
                    { "key": "fertilizer", "title": "CROP PLOT FERTILIZER REFRESH", "body": "Refresh crop plot fertilizer with one quick helper." },
                    { "key": "position", "title": "POSITION / RENDER HELPER", "body": "Capture and view render yaw settings." },
                    { "key": "deposit", "title": "DEPOSIT ROUTE HELPER", "body": "Capture and tune crystal and grindable deposit route entries." }
                ]
                delegate: Panel {
                    title: modelData.title
                    Layout.fillWidth: true
                    Layout.preferredHeight: ThemeModule.Theme.size.toolCardHeight

                    Text {
                        text: modelData.body
                        color: ThemeModule.Theme.colors.muted
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Item { Layout.fillHeight: true }
                    CyberButton {
                        text: "OPEN TOOL"
                        variant: "primary"
                        Layout.alignment: Qt.AlignRight
                        onClicked: toolsController.openHelper(modelData.key)
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
