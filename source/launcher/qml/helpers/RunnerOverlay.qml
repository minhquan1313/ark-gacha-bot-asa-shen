import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Window {
    id: overlay

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
            spacing: ThemeModule.Theme.spacing.sm

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: launcherController.appTitle + "\n" + launcherController.uptime
                    color: ThemeModule.Theme.colors.cyan
                    font.bold: true
                    Layout.fillWidth: true

                    MouseArea {
                        anchors.fill: parent
                        onPressed: overlay.startSystemMove()
                    }
                }
                CyberButton {
                    text: "STOP"
                    variant: "danger"
                    onClicked: launcherController.stopProgram()
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: ThemeModule.Theme.spacing.md

                ColumnLayout {
                    Layout.preferredWidth: ThemeModule.Theme.size.overlayQueueWidth
                    spacing: ThemeModule.Theme.spacing.xs

                    Text {
                        objectName: "RunnerOverlayCurrent"
                        text: queueController.currentTask === "IDLE"
                            ? "Waiting for running task..."
                            : "Running " + queueController.currentTask
                        color: ThemeModule.Theme.colors.text
                        font.bold: true
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    Repeater {
                        model: queueController.runnerUpcomingTasks.slice(0, 5)
                        Text {
                            objectName: "RunnerOverlayTask"
                            text: modelData
                            color: ThemeModule.Theme.colors.muted
                            font.family: ThemeModule.Theme.fonts.mono
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }

                Rectangle {
                    Layout.fillHeight: true
                    Layout.preferredWidth: ThemeModule.Theme.border.thin
                    color: ThemeModule.Theme.colors.border
                }

                ColumnLayout {
                    Layout.preferredWidth: ThemeModule.Theme.size.overlayLogWidth
                    spacing: ThemeModule.Theme.spacing.xs

                    Text {
                        text: "LATEST LOGS"
                        color: ThemeModule.Theme.colors.cyan
                        font.pixelSize: ThemeModule.Theme.fonts.badge
                        font.bold: true
                        Layout.fillWidth: true
                    }

                    Text {
                        objectName: "RunnerOverlayLatestLogs"
                        text: logController.dashboardLines.slice(-5).join("")
                        color: ThemeModule.Theme.colors.dim
                        font.family: ThemeModule.Theme.fonts.mono
                        font.pixelSize: ThemeModule.Theme.fonts.consoleText
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }
        }
    }
}
