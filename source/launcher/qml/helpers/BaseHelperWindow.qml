import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Window {
    id: helper

    property string helperTitle: "HELPER"
    property string helperBody: "This helper has been migrated to the QML shell. Runtime wiring is handled by Python controllers."

    width: ThemeModule.Theme.size.helperWidth
    height: ThemeModule.Theme.size.helperHeight
    minimumWidth: ThemeModule.Theme.size.helperWidth
    minimumHeight: ThemeModule.Theme.size.helperHeight
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"

    Rectangle {
        anchors.fill: parent
        color: ThemeModule.Theme.colors.panel
        border.color: ThemeModule.Theme.colors.borderActive
        border.width: ThemeModule.Theme.border.thin
        radius: ThemeModule.Theme.radius.md

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: ThemeModule.Theme.spacing.md
            spacing: ThemeModule.Theme.spacing.sm

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: helper.helperTitle
                    color: ThemeModule.Theme.colors.text
                    font.pixelSize: ThemeModule.Theme.fonts.sectionHeading
                    font.bold: true
                    Layout.fillWidth: true

                    MouseArea {
                        anchors.fill: parent
                        onPressed: helper.startSystemMove()
                    }
                }
                IconButton {
                    text: "X"
                    variant: "danger"
                    onClicked: helper.close()
                }
            }

            Text {
                text: "ALT + N focuses this helper"
                color: ThemeModule.Theme.colors.muted
                font.family: ThemeModule.Theme.fonts.mono
            }

            Text {
                text: helper.helperBody
                color: ThemeModule.Theme.colors.text
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.fillHeight: true
            }

            CyberButton {
                text: "READY"
                variant: "primary"
                Layout.fillWidth: true
            }
        }
    }
}
