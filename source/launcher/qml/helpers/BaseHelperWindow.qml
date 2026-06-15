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
    property bool ownerActive: false
    property bool compactWhenRunning: false
    property bool showStatus: true
    property bool closeWhenStopped: false
    property int idleWidth: ThemeModule.Theme.size.helperWidth
    property int idleHeight: ThemeModule.Theme.size.helperHeight
    readonly property bool bodySlotVisible: !(compactWhenRunning && running)

    signal helperClosed()

    width: compactWhenRunning && running ? ThemeModule.Theme.size.helperRunningWidth : idleWidth
    height: compactWhenRunning && running
        ? Math.max(ThemeModule.Theme.size.helperRunningMinHeight, helperContent.implicitHeight + ThemeModule.Theme.spacing.lg * 2)
        : idleHeight
    minimumWidth: compactWhenRunning && running ? ThemeModule.Theme.size.helperRunningWidth : idleWidth
    minimumHeight: compactWhenRunning && running ? ThemeModule.Theme.size.helperRunningMinHeight : ThemeModule.Theme.size.helperHeight
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"
    opacity: active || mouseInside || ownerActive ? 1.0 : settingsController.helperInactiveOpacity

    onClosing: {
        if (stopControllerOnClose && controller && controller.running) {
            close.accepted = false;
            if (!closeWhenStopped) {
                closeWhenStopped = true;
                Qt.callLater(function() {
                    if (helper.controller && helper.controller.running) {
                        helper.controller.stop();
                    }
                });
            }
        } else {
            helperClosed();
        }
    }

    Connections {
        target: helper.controller
        function onChanged() {
            if (helper.closeWhenStopped && helper.controller && !helper.controller.running) {
                helper.closeWhenStopped = false;
                helper.close();
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: ThemeModule.Theme.colors.panelStrong
        border.color: ThemeModule.Theme.colors.borderActive
        border.width: ThemeModule.Theme.border.thin
        radius: ThemeModule.Theme.radius.md

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: ThemeModule.Theme.border.thin
            height: ThemeModule.Theme.border.active
            color: ThemeModule.Theme.colors.cyan
            opacity: 0.85
            radius: ThemeModule.Theme.radius.sm
        }

        MouseArea {
            objectName: "HelperTopDragArea"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: ThemeModule.Theme.spacing.md
            acceptedButtons: Qt.LeftButton
            onPressed: helper.startSystemMove()
        }

        ColumnLayout {
            id: helperContent
            anchors.fill: parent
            anchors.margins: ThemeModule.Theme.spacing.md
            spacing: ThemeModule.Theme.spacing.sm

            Item {
                objectName: "HelperHeader"
                Layout.fillWidth: true
                implicitHeight: Math.max(headerTitle.implicitHeight, closeButton.implicitHeight)

                MouseArea {
                    objectName: "HelperHeaderDragArea"
                    anchors.left: parent.left
                    anchors.right: closeButton.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    acceptedButtons: Qt.LeftButton
                    onPressed: helper.startSystemMove()
                }

                Text {
                    id: headerTitle
                    objectName: "HelperHeaderTitle"
                    text: helper.helperTitle
                    color: ThemeModule.Theme.colors.cyan
                    font.pixelSize: ThemeModule.Theme.fonts.sectionHeading
                    font.bold: true
                    anchors.left: parent.left
                    anchors.right: closeButton.left
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight
                }
                IconButton {
                    id: closeButton
                    objectName: "HelperHeaderCloseButton"
                    text: "X"
                    variant: "danger"
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
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
                visible: helper.bodySlotVisible
                spacing: ThemeModule.Theme.spacing.sm
                Layout.fillWidth: true
                Layout.fillHeight: helper.contentFill && helper.bodySlotVisible
                Layout.preferredHeight: helper.bodySlotVisible ? implicitHeight : 0
            }

            Text {
                visible: helper.showStatus
                text: helper.statusText
                color: helper.statusText.indexOf("Failed") === 0 ? ThemeModule.Theme.colors.red : ThemeModule.Theme.colors.muted
                font.family: ThemeModule.Theme.fonts.mono
                font.pixelSize: ThemeModule.Theme.fonts.consoleText
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }

        HoverHandler {
            onHoveredChanged: helper.mouseInside = hovered
        }
    }
}
