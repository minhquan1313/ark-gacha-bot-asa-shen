import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme" as ThemeModule

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: ThemeModule.Theme.spacing.lg
        spacing: ThemeModule.Theme.spacing.md

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: ThemeModule.Theme.size.heroHeight
            radius: ThemeModule.Theme.radius.panel
            color: ThemeModule.Theme.colors.panelStrong
            border.color: ThemeModule.Theme.colors.border

            Image {
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.margins: ThemeModule.Theme.spacing.sm
                width: parent.width * 0.48
                source: assetPaths.dashboard
                fillMode: Image.PreserveAspectFit
                opacity: 0.92
            }

            Column {
                anchors.left: parent.left
                anchors.leftMargin: ThemeModule.Theme.spacing.xxl
                anchors.verticalCenter: parent.verticalCenter
                spacing: ThemeModule.Theme.spacing.sm

                Text {
                    text: "WELCOME BACK,"
                    color: ThemeModule.Theme.colors.cyan
                    font.pixelSize: ThemeModule.Theme.fonts.sectionHeading
                    font.bold: true
                }
                Text {
                    text: launcherController.appTitle + "."
                    color: ThemeModule.Theme.colors.text
                    font.pixelSize: ThemeModule.Theme.fonts.welcomeTitle
                    font.bold: true
                }
                Text {
                    text: "SYSTEM STATUS  ONLINE"
                    color: ThemeModule.Theme.colors.green
                    font.family: ThemeModule.Theme.fonts.mono
                    font.bold: true
                }
            }
        }

        GridLayout {
            columns: 4
            columnSpacing: ThemeModule.Theme.spacing.md
            rowSpacing: ThemeModule.Theme.spacing.md
            Layout.fillWidth: true

            StatCard { label: "SERVER NUMBER"; value: launcherController.serverNumber; sublabel: "ID"; Layout.fillWidth: true }
            StatCard { label: "ACTIVE QUEUE"; value: String(queueController.activeCount); sublabel: "TASKS"; Layout.fillWidth: true }
            StatCard { label: "WAITING QUEUE"; value: String(queueController.waitingCount); sublabel: "TASKS"; Layout.fillWidth: true }
            StatCard { label: "UPTIME"; value: launcherController.uptime; sublabel: "HH:MM:SS"; Layout.fillWidth: true }
        }

        RowLayout {
            spacing: ThemeModule.Theme.spacing.md
            Layout.fillWidth: true
            Layout.fillHeight: true

            Panel {
                title: "QUICK ACTIONS"
                fillBody: true
                Layout.preferredWidth: ThemeModule.Theme.size.quickActionsWidth
                Layout.fillHeight: true

                CyberButton {
                    text: launcherController.startStopText
                    variant: launcherController.startStopVariant
                    Layout.fillWidth: true
                    onClicked: launcherController.toggleProgram()
                }
                CyberButton {
                    text: "START GAME"
                    variant: "secondary"
                    visible: launcherController.showStartGame
                    enabled: launcherController.startGameEnabled
                    Layout.fillWidth: true
                    onClicked: launcherController.startGame()
                }
                CyberButton {
                    text: "RESTORE GAME SETTINGS"
                    variant: "secondary"
                    visible: launcherController.showRestoreGameSettings
                    enabled: launcherController.restoreGameSettingsEnabled
                    Layout.fillWidth: true
                    onClicked: launcherController.restoreGameSettings()
                }
                CyberButton {
                    text: "CLEAR RESTORE DATA"
                    variant: "danger"
                    visible: launcherController.showRestoreGameSettings
                    enabled: launcherController.restoreGameSettingsEnabled
                    Layout.fillWidth: true
                    onClicked: launcherController.clearGameRestoreSettings()
                }
                CyberSwitch {
                    objectName: "AutoStartSwitch"
                    text: "AUTO START"
                    checked: launcherController.autoStartAllowed && settingsController.autoStartProgram
                    enabled: launcherController.autoStartAllowed
                    onToggled: {
                        if (launcherController.autoStartAllowed) {
                            settingsController.setValue("auto_start_program", checked)
                        }
                    }
                }
                Text {
                    objectName: "AutoStartHint"
                    text: launcherController.autoStartHint
                    color: launcherController.autoStartAllowed ? ThemeModule.Theme.colors.muted : ThemeModule.Theme.colors.yellow
                    font.family: ThemeModule.Theme.fonts.mono
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Item { Layout.fillHeight: true }
            }

            Panel {
                title: "LIVE CONSOLE (LATEST)"
                fillBody: true
                Layout.fillWidth: true
                Layout.fillHeight: true

                ConsoleView {
                    lines: logController.dashboardLines
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                }
                CyberButton {
                    text: "OPEN FULL LOGS"
                    variant: "secondary"
                    Layout.alignment: Qt.AlignRight
                    onClicked: launcherController.showPage("logs")
                }
            }
        }

        GridLayout {
            columns: 5
            Layout.fillWidth: true
            columnSpacing: ThemeModule.Theme.spacing.sm

            Panel {
                objectName: "MemoryMeterCard"
                Layout.fillWidth: true
                implicitHeight: ThemeModule.Theme.size.statCardHeight

                Text {
                    text: "MEMORY USAGE"
                    color: ThemeModule.Theme.colors.muted
                    font.pixelSize: ThemeModule.Theme.fonts.statLabel
                    font.bold: true
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
                MeterBar {
                    objectName: "MemoryMeter"
                    value: launcherController.memoryPercent
                    accent: ThemeModule.Theme.colors.green
                    Layout.fillWidth: true
                }
                Text {
                    text: launcherController.memoryUsage
                    color: ThemeModule.Theme.colors.text
                    font.family: ThemeModule.Theme.fonts.mono
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }
            Panel {
                objectName: "CpuMeterCard"
                Layout.fillWidth: true
                implicitHeight: ThemeModule.Theme.size.statCardHeight

                Text {
                    text: "CPU USAGE"
                    color: ThemeModule.Theme.colors.muted
                    font.pixelSize: ThemeModule.Theme.fonts.statLabel
                    font.bold: true
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
                MeterBar {
                    objectName: "CpuMeter"
                    value: launcherController.cpuPercent
                    accent: ThemeModule.Theme.colors.cyan
                    Layout.fillWidth: true
                }
                Text {
                    text: launcherController.cpuUsage
                    color: ThemeModule.Theme.colors.text
                    font.family: ThemeModule.Theme.fonts.mono
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }
            StatCard { label: "RUNNER"; value: launcherController.runnerState; sublabel: ""; Layout.fillWidth: true }
            StatCard { label: "LAST ACTIVITY"; value: launcherController.lastActivity; sublabel: ""; Layout.fillWidth: true }
            StatCard { label: "SYSTEM TIME"; value: launcherController.clock; sublabel: ""; Layout.fillWidth: true }
        }
    }
}
