import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Window {
    id: overlay
    objectName: "RunnerOverlayWindow"

    width: ThemeModule.Theme.size.overlayWidth
    height: Math.max(ThemeModule.Theme.size.overlayMinHeight, content.implicitHeight + ThemeModule.Theme.spacing.lg * 2)
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"

    Rectangle {
        anchors.fill: parent
        color: ThemeModule.Theme.colors.panel
        border.color: ThemeModule.Theme.colors.borderActive
        border.width: ThemeModule.Theme.border.thin
        radius: ThemeModule.Theme.radius.md

        ColumnLayout {
            id: content
            anchors.fill: parent
            anchors.margins: ThemeModule.Theme.spacing.md
            spacing: ThemeModule.Theme.spacing.xxs

            Item {
                objectName: "RunnerOverlayHeader"
                Layout.fillWidth: true
                implicitHeight: Math.max(overlayTitle.implicitHeight, stopButton.implicitHeight)

                MouseArea {
                    objectName: "RunnerOverlayHeaderDragArea"
                    anchors.left: parent.left
                    anchors.right: stopButton.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    acceptedButtons: Qt.LeftButton
                    onPressed: overlay.startSystemMove()
                }

                Text {
                    id: overlayTitle
                    text: launcherController.appTitle + "\n" + launcherController.uptime
                    color: ThemeModule.Theme.colors.cyan
                    font.bold: true
                    anchors.left: parent.left
                    anchors.right: stopButton.left
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight
                }
                CyberButton {
                    id: stopButton
                    objectName: "RunnerOverlayStopButton"
                    text: "STOP"
                    variant: "danger"
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    onClicked: launcherController.stopProgram()
                }
            }

            Text {
                objectName: "RunnerOverlayCurrent"
                Layout.fillWidth: true
                text: queueController.currentTask === "IDLE" ? "Idle, waiting for task" : "Task: " + queueController.currentTask
                color: ThemeModule.Theme.colors.text
                font.bold: true
                elide: Text.ElideRight
            }

            Text {
                objectName: "RunnerOverlayStats"
                Layout.fillWidth: true
                text: launcherController.uptime
                color: ThemeModule.Theme.colors.muted
                font.family: ThemeModule.Theme.fonts.mono
                font.pixelSize: ThemeModule.Theme.fonts.consoleText
                elide: Text.ElideRight
            }

            Text {
                objectName: "RunnerOverlayHelperStatus"
                Layout.fillWidth: true
                text: queueController.runnerUpcomingTasks.length > 0 ? "Queue ready" : "No queued tasks"
                color: ThemeModule.Theme.colors.muted
                font.family: ThemeModule.Theme.fonts.mono
                font.pixelSize: ThemeModule.Theme.fonts.consoleText
                elide: Text.ElideRight
            }

            Text {
                objectName: "RunnerOverlayNextTask"
                visible: queueController.runnerUpcomingTasks.length > 0
                text: "Next: " + queueController.runnerUpcomingTasks[0]
                color: ThemeModule.Theme.colors.muted
                font.family: ThemeModule.Theme.fonts.mono
                font.pixelSize: ThemeModule.Theme.fonts.consoleText
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
        
            Repeater {
                model: queueController.runnerUpcomingTasks.slice(1, 3)
                visible: queueController.runnerUpcomingTasks.length > 1
                Text {
                    objectName: "RunnerOverlayTask"
                    text: modelData
                    color: ThemeModule.Theme.colors.muted
                    font.family: ThemeModule.Theme.fonts.mono
                    font.pixelSize: ThemeModule.Theme.fonts.consoleText
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: ThemeModule.Theme.border.thin
                color: ThemeModule.Theme.colors.border
            }

            Text {
                text: "LATEST"
                color: ThemeModule.Theme.colors.cyan
                font.pixelSize: ThemeModule.Theme.fonts.badge
                font.bold: true
                Layout.fillWidth: true
            }

            Repeater {
                model: logController.overlayLines.length > 0
                    ? logController.overlayLines.slice(0, 3)
                    : ["No recent logs."]

                Text {
                    text: modelData
                    Layout.fillWidth: true
                    width: parent ? parent.width : 0

                    color: ThemeModule.Theme.colors.dim
                    font.family: ThemeModule.Theme.fonts.mono
                    font.pixelSize: ThemeModule.Theme.fonts.consoleText
                    lineHeight: 0.9
                    
                    elide: Text.ElideRight
                    wrapMode: Text.NoWrap
                    clip: true
                }
            }

            Text {
                objectName: "RunnerOverlayLatestLogs"
                visible: false
                text: logController.overlayLines.length > 0
                    ? logController.overlayLines.slice(0, 3).join("\n")
                    : "No recent logs."
            }
        }
    }
}
