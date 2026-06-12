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
            text: launcherController.appTitle + " - SETUP GUIDE"
            color: ThemeModule.Theme.colors.cyan
            font.pixelSize: ThemeModule.Theme.fonts.pageTitle
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: ThemeModule.Theme.spacing.md

            Panel {
                objectName: "SetupStepsCard"
                Layout.fillWidth: true
                Layout.fillHeight: true
                fillBody: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: ThemeModule.Theme.spacing.sm

                    Repeater {
                        model: [
                            { "number": "01", "title": "Configure Local Settings", "state": "DONE" },
                            { "number": "02", "title": "Set Server Number", "state": "DONE" },
                            { "number": "03", "title": "Configure Gacha Names", "state": "INCOMPLETE" },
                            { "number": "04", "title": "Review Queue Data", "state": "PENDING" },
                            { "number": "05", "title": "Save Settings", "state": "PENDING" },
                            { "number": "06", "title": "Start Program", "state": "PENDING" }
                        ]
                        delegate: Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: stepRow.implicitHeight + ThemeModule.Theme.spacing.md
                            color: ThemeModule.Theme.colors.panelStrong
                            border.color: ThemeModule.Theme.colors.border
                            border.width: ThemeModule.Theme.border.thin
                            radius: ThemeModule.Theme.radius.sm

                            RowLayout {
                                id: stepRow
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.margins: ThemeModule.Theme.spacing.md
                                spacing: ThemeModule.Theme.spacing.md

                                Text {
                                    text: modelData.number
                                    color: ThemeModule.Theme.colors.cyan
                                    font.pixelSize: ThemeModule.Theme.fonts.sectionHeading
                                    font.bold: true
                                }
                                Text {
                                    text: modelData.title
                                    color: ThemeModule.Theme.colors.text
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }
                                Rectangle {
                                    color: ThemeModule.Theme.colors.panel
                                    border.color: modelData.state === "DONE" ? ThemeModule.Theme.colors.green
                                        : modelData.state === "INCOMPLETE" ? ThemeModule.Theme.colors.yellow
                                        : ThemeModule.Theme.colors.border
                                    border.width: ThemeModule.Theme.border.thin
                                    radius: ThemeModule.Theme.radius.sm
                                    implicitWidth: badgeText.implicitWidth + ThemeModule.Theme.spacing.lg
                                    implicitHeight: badgeText.implicitHeight + ThemeModule.Theme.spacing.sm

                                    Text {
                                        id: badgeText
                                        anchors.centerIn: parent
                                        text: modelData.state
                                        color: modelData.state === "DONE" ? ThemeModule.Theme.colors.green
                                            : modelData.state === "INCOMPLETE" ? ThemeModule.Theme.colors.yellow
                                            : ThemeModule.Theme.colors.muted
                                        font.pixelSize: ThemeModule.Theme.fonts.badge
                                        font.bold: true
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Panel {
                objectName: "SetupDetailCard"
                title: "STEP 03"
                Layout.fillWidth: true
                Layout.fillHeight: true

                Text {
                    text: "CONFIGURE GACHA NAMES"
                    color: ThemeModule.Theme.colors.text
                    font.pixelSize: ThemeModule.Theme.fonts.sectionHeading
                    font.bold: true
                    Layout.fillWidth: true
                }
                Text {
                    text: "Set your gacha station names below. These names are used for text automation and queue processing."
                    color: ThemeModule.Theme.colors.muted
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                CyberButton {
                    text: "GO TO SETTINGS"
                    variant: "primary"
                    Layout.fillWidth: true
                    onClicked: launcherController.showPage("settings")
                }
                Panel {
                    title: "TIP"
                    Layout.fillWidth: true

                    Text {
                        text: "Make sure the names match exactly with your in-game stations to avoid automation errors."
                        color: ThemeModule.Theme.colors.muted
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
                Item { Layout.fillHeight: true }
            }
        }
    }
}
