import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Window {
    id: helper

    property string helperTitle: "HELPER"
    property string helperBody: ""
    property var controller
    default property alias content: helperBodyColumn.data
    property string statusText: "Ready."
    property bool running: false
    property bool contentFill: false
    property string hotkeyHint: "ALT + N focuses this helper"
    property bool stopControllerOnClose: true
    property bool mouseInside: false
    property bool compactWhenRunning: false
    property bool showStatus: true
    property int idleWidth: ThemeModule.Theme.size.helperWidth
    property int idleHeight: ThemeModule.Theme.size.helperHeight

    width: compactWhenRunning && running ? ThemeModule.Theme.size.helperRunningWidth : idleWidth
    height: compactWhenRunning && running
        ? Math.max(ThemeModule.Theme.size.helperRunningMinHeight, helperContent.implicitHeight + ThemeModule.Theme.spacing.lg * 2)
        : idleHeight
    minimumWidth: compactWhenRunning && running ? ThemeModule.Theme.size.helperRunningWidth : idleWidth
    minimumHeight: compactWhenRunning && running ? ThemeModule.Theme.size.helperRunningMinHeight : ThemeModule.Theme.size.helperHeight
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"
    opacity: active || mouseInside ? 1.0 : settingsController.helperInactiveOpacity

    onClosing: {
        if (stopControllerOnClose && controller && controller.running) {
            controller.stop();
        }
    }

    Rectangle {
        anchors.fill: parent
        color: ThemeModule.Theme.colors.panel
        border.color: ThemeModule.Theme.colors.borderActive
        border.width: ThemeModule.Theme.border.thin
        radius: ThemeModule.Theme.radius.md

        ColumnLayout {
            id: helperContent
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
                    elide: Text.ElideRight

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
                objectName: "HelperHotkeyHint"
                text: helper.hotkeyHint
                color: ThemeModule.Theme.colors.muted
                font.family: ThemeModule.Theme.fonts.mono
            }

            Text {
                visible: helper.helperBody.length > 0
                text: helper.helperBody
                color: ThemeModule.Theme.colors.text
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            ColumnLayout {
                id: helperBodyColumn
                spacing: ThemeModule.Theme.spacing.sm
                Layout.fillWidth: true
                Layout.fillHeight: helper.contentFill
            }

            Text {
                visible: helper.showStatus
                text: helper.statusText
                color: ThemeModule.Theme.colors.muted
                font.family: ThemeModule.Theme.fonts.mono
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }

        HoverHandler {
            onHoveredChanged: helper.mouseInside = hovered
        }
    }
}
